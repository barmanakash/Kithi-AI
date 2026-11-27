"""Browser worker: runs in its own process and drives a visible Chromium window on this computer.

Started by app.automation.form_assistant (never run it by hand). It reads one JSON command per line on
stdin and writes exactly one JSON reply per line on stdout:

    {"cmd": "open", "url": "https://..."}                -> {"ok": true, "url", "title", "fields": [...]}
    {"cmd": "scan"}                                      -> same, for whatever page is showing now
    {"cmd": "fill", "items": [{"id", "value", ...}]}     -> {"ok": true, "filled": [...], "failed": [...]}
    {"cmd": "close"}                                     -> closes the browser and exits
    any failure                                          -> {"ok": false, "error": "...", "status": 4xx/5xx}

SAFETY (see the module docstring of form_assistant.py for the full model):
- This file contains no click, key-press, tap, check or submit call. It only navigates to the page you
  asked for, reads form fields, and sets the text of fields you approved. You submit the form yourself.
- Only public http(s) sites are opened. Every request the page makes is checked, so a page cannot reach
  addresses on your own network. Downloads, permissions and service workers are blocked.
- Page text is data. It is returned as JSON and is never executed, approved or acted on.
"""
import json
import os
import re
import sys
from urllib.parse import urlparse

from app.automation.form_assistant import NEVER_FILL_TYPES
from app.services.safe_fetch import UnsafeURLError, assert_public_url

MAX_FIELDS = 150
FIELD_ID = re.compile(r"^\d{1,2}_\d{1,4}$")
NAV_TIMEOUT_MS = 45_000
ACTION_TIMEOUT_MS = 5_000
SETTLE_TIMEOUT_MS = 8_000
WEB_SCHEMES = {"http", "https"}
PASSIVE_SCHEMES = {"data", "blob", "about"}

# Reads the form controls on a page and tags each with a data attribute so it can be found again.
# It only reads values and sets that one attribute.
DISCOVER_JS = r"""
({ prefix, max }) => {
  const SKIP = new Set(["hidden", "submit", "button", "image", "reset"]);
  const clean = (s, n) => (s || "").replace(/\s+/g, " ").trim().slice(0, n);
  const textOf = (id) => { const e = id ? document.getElementById(id) : null; return e ? (e.innerText || e.textContent) : ""; };
  const labelOf = (el) => {
    const aria = el.getAttribute("aria-label");
    if (aria) return clean(aria, 200);
    const by = el.getAttribute("aria-labelledby");
    if (by) { const t = clean(by.split(/\s+/).map(textOf).join(" "), 200); if (t) return t; }
    if (el.labels && el.labels.length) return clean(Array.from(el.labels).map((l) => l.innerText || l.textContent).join(" "), 200);
    const wrap = el.closest("label");
    if (wrap) return clean(wrap.innerText || wrap.textContent, 200);
    const set = el.closest("fieldset");
    const legend = set && set.querySelector("legend");
    if (legend && (el.type === "radio" || el.type === "checkbox")) return clean(legend.innerText, 200);
    return "";
  };
  const visible = (el) => {
    const style = window.getComputedStyle(el);
    if (style.visibility === "hidden" || style.display === "none") return false;
    const r = el.getBoundingClientRect();
    return r.width > 0 && r.height > 0;
  };
  const out = [];
  const seenRadio = new Set();
  let n = 0;
  for (const el of document.querySelectorAll("input, textarea, select")) {
    if (out.length >= max) break;
    const tag = el.tagName.toLowerCase();
    const type = tag === "input" ? (el.getAttribute("type") || "text").toLowerCase() : tag;
    if (SKIP.has(type) || el.disabled || el.readOnly) continue;
    if (type !== "file" && !visible(el)) continue;
    if (type === "radio") {
      const group = el.name || "";
      if (group && seenRadio.has(group)) continue;
      seenRadio.add(group);
    }
    n += 1;
    const id = prefix + "_" + n;
    el.setAttribute("data-kithi-id", id);
    let current = "";
    if (tag === "select") current = el.selectedIndex > 0 ? clean(el.value, 100) : "";
    else if (type !== "file" && type !== "radio" && type !== "checkbox") current = clean(el.value, 200);
    const options = tag === "select"
      ? Array.from(el.options).map((o) => clean(o.text, 100)).filter((t) => t && !/^(select|choose|please select|--)/i.test(t)).slice(0, 100)
      : [];
    out.push({
      id, tag, type,
      label: labelOf(el),
      placeholder: clean(el.getAttribute("placeholder"), 120),
      name: clean(el.getAttribute("name"), 80),
      id_attr: clean(el.id, 80),
      autocomplete: clean(el.getAttribute("autocomplete"), 40),
      required: !!(el.required || el.getAttribute("aria-required") === "true"),
      max_length: el.maxLength > 0 ? el.maxLength : null,
      current_value: current,
      options,
    });
  }
  return out;
}
"""


class WorkerError(Exception):
    def __init__(self, message: str, status: int = 422):
        super().__init__(message)
        self.status = status


class Worker:
    def __init__(self) -> None:
        self._pw = None
        self.browser = None
        self.context = None
        self.page = None
        self.frames: dict[int, object] = {}
        self._host_ok_cache: dict[str, bool] = {}

    # ------------------------------------------------------------------ browser lifecycle
    def _ensure_browser(self) -> None:
        if self.browser is not None and not self.browser.is_connected():
            self.shutdown()
        if self.browser is None:
            try:
                from playwright.sync_api import sync_playwright
            except ImportError:
                raise WorkerError("Playwright is not installed. Run: pip install playwright   then: playwright install chromium", 503)
            self._pw = sync_playwright().start()
            try:
                self.browser = self._pw.chromium.launch(
                    headless=os.environ.get("KITHI_BROWSER_HEADLESS") == "1",
                    args=["--disable-extensions", "--disable-background-networking"],
                )
            except Exception as exc:
                self.shutdown()
                raise WorkerError(f"The browser could not start ({type(exc).__name__}). Run once: playwright install chromium", 503)
            self.context = self.browser.new_context(accept_downloads=False, service_workers="block", permissions=[])
            self.context.route("**/*", self._guard)
        if self.page is None or self.page.is_closed():
            self.page = self.context.new_page()
            self.page.on("download", lambda download: download.cancel())

    def _live_page(self):
        if self.browser is None or not self.browser.is_connected() or self.page is None or self.page.is_closed():
            raise WorkerError("The browser window was closed. Open the form again.", 410)
        return self.page

    def shutdown(self) -> None:
        for closer in (
            lambda: self.context and self.context.close(),
            lambda: self.browser and self.browser.close(),
            lambda: self._pw and self._pw.stop(),
        ):
            try:
                closer()
            except Exception:
                pass
        self._pw = self.browser = self.context = self.page = None
        self.frames = {}

    # ------------------------------------------------------------------ network guard
    def _host_ok(self, url: str, hostname: str) -> bool:
        if hostname not in self._host_ok_cache:
            try:
                assert_public_url(url)
                self._host_ok_cache[hostname] = True
            except UnsafeURLError:
                self._host_ok_cache[hostname] = False
        return self._host_ok_cache[hostname]

    def _guard(self, route) -> None:
        """Every request the page makes passes through here. Non-public destinations are refused."""
        url = route.request.url
        parsed = urlparse(url)
        scheme = parsed.scheme.lower()
        if scheme in PASSIVE_SCHEMES:
            route.continue_()
        elif scheme in WEB_SCHEMES and parsed.hostname and self._host_ok(url, parsed.hostname):
            route.continue_()
        else:
            route.abort("blockedbyclient")

    # ------------------------------------------------------------------ commands
    def open(self, cmd: dict) -> dict:
        url = str(cmd.get("url") or "")
        try:
            assert_public_url(url)
        except UnsafeURLError as exc:
            raise WorkerError(str(exc), 422)
        self._ensure_browser()
        try:
            self.page.goto(url, wait_until="domcontentloaded", timeout=NAV_TIMEOUT_MS)
        except Exception as exc:
            raise WorkerError(f"The page could not be opened ({type(exc).__name__}). Check the address and your connection.", 502)
        self._settle()
        return self._scan()

    def scan(self, cmd: dict) -> dict:
        self._live_page()
        self._settle()
        return self._scan()

    def _settle(self) -> None:
        try:
            self.page.wait_for_load_state("networkidle", timeout=SETTLE_TIMEOUT_MS)
        except Exception:
            pass  # busy pages never go idle; scan whatever is there

    def _scan(self) -> dict:
        page = self._live_page()
        fields: list[dict] = []
        self.frames = {}
        for index, frame in enumerate(page.frames):
            remaining = MAX_FIELDS - len(fields)
            if remaining <= 0 or index > 99:
                break
            try:
                if frame.is_detached():
                    continue
                found = frame.evaluate(DISCOVER_JS, {"prefix": str(index), "max": remaining})
            except Exception:
                continue
            if found:
                self.frames[index] = frame
                fields.extend(found)
        try:
            title = (page.title() or "")[:200]
        except Exception:
            title = ""
        return {"url": page.url, "title": title, "fields": fields}

    def fill(self, cmd: dict) -> dict:
        self._live_page()
        items = cmd.get("items")
        if not isinstance(items, list) or not items:
            raise WorkerError("Nothing to fill.", 422)
        filled: list[str] = []
        failed: list[dict] = []
        for item in items[:MAX_FIELDS]:
            fid = str(item.get("id") or "") if isinstance(item, dict) else ""
            value = item.get("value") if isinstance(item, dict) else None
            if not FIELD_ID.match(fid) or not isinstance(value, str):
                failed.append({"id": fid[:20], "error": "Invalid field."})
                continue
            if (item.get("type") or "").lower() in NEVER_FILL_TYPES:
                failed.append({"id": fid, "error": "This kind of field is never filled."})
                continue
            frame = self.frames.get(int(fid.split("_")[0]))
            try:
                if frame is None or frame.is_detached():
                    raise WorkerError("The field is no longer on the page. Rescan the page.")
                locator = frame.locator(f'[data-kithi-id="{fid}"]')
                if locator.count() != 1:
                    raise WorkerError("The field is no longer on the page. Rescan the page.")
                if item.get("tag") == "select":
                    self._choose(locator, value)
                else:
                    locator.fill(value, timeout=ACTION_TIMEOUT_MS)
                filled.append(fid)
            except WorkerError as exc:
                failed.append({"id": fid, "error": str(exc)})
            except Exception as exc:
                failed.append({"id": fid, "error": f"Could not fill this field ({type(exc).__name__})."})
        return {"filled": filled, "failed": failed}

    @staticmethod
    def _choose(locator, value: str) -> None:
        texts = [" ".join(t.split()) for t in locator.locator("option").all_text_contents()]
        target = " ".join(value.split()).lower()
        for index, text in enumerate(texts):
            if text.lower() == target:
                locator.select_option(index=index, timeout=ACTION_TIMEOUT_MS)
                return
        raise WorkerError("That option is not in the list.")


def main() -> None:
    out = sys.stdout
    sys.stdout = sys.stderr  # nothing but protocol lines may reach the real stdout

    def reply(payload: dict) -> None:
        out.write(json.dumps(payload) + "\n")  # ASCII-only JSON, safe on any console encoding
        out.flush()

    worker = Worker()
    handlers = {"open": worker.open, "scan": worker.scan, "fill": worker.fill}
    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                cmd = json.loads(line)
                name = cmd.get("cmd") if isinstance(cmd, dict) else None
            except json.JSONDecodeError:
                reply({"ok": False, "error": "Unreadable command.", "status": 400})
                continue
            if name == "close":
                worker.shutdown()
                reply({"ok": True})
                return
            handler = handlers.get(name)
            if handler is None:
                reply({"ok": False, "error": "Unknown command.", "status": 400})
                continue
            try:
                reply({"ok": True, **handler(cmd)})
            except WorkerError as exc:
                reply({"ok": False, "error": str(exc), "status": exc.status})
            except Exception as exc:
                reply({"ok": False, "error": f"Unexpected browser error ({type(exc).__name__}).", "status": 500})
    finally:
        worker.shutdown()


if __name__ == "__main__":
    main()
