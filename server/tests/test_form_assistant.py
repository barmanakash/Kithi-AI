"""Tests for the Application Assistant (browser form filling): safety rules, planning, approval and sessions.

Run from the server folder:   python -m pytest tests -q
These tests need no browser, Playwright, MongoDB or Ollama. The real browser window itself has to be
tried by hand (see README, "Application Assistant").
"""
import re
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from app.automation import browser_worker
from app.automation.form_assistant import (
    AssistError,
    SessionManager,
    build_plan,
    build_source,
    classify_field,
    plan_hash,
    validate_fill,
)

AUTOMATION_DIR = Path(browser_worker.__file__).resolve().parent

# Any call that could click, press a key, tap, tick a box or submit a form.
FORBIDDEN_CALLS = re.compile(
    r"\.(click|dblclick|press|press_sequentially|type|tap|check|uncheck|set_checked|submit|requestSubmit|"
    r"dispatch_event|dispatchEvent|hover|drag_to|focus|blur)\s*\(",
)
FORBIDDEN_NAMES = re.compile(r"\b(keyboard|mouse|touchscreen)\b\s*\.")


# ====================================================================== the "never submits" guarantee
def automation_sources():
    files = sorted(p for p in AUTOMATION_DIR.glob("*.py"))
    assert {p.name for p in files} >= {"form_assistant.py", "browser_worker.py"}
    return files


@pytest.mark.parametrize("path", automation_sources(), ids=lambda p: p.name)
def test_automation_code_contains_no_click_press_or_submit_call(path):
    source = path.read_text(encoding="utf-8")
    assert not FORBIDDEN_CALLS.search(source), f"{path.name} contains a forbidden browser action"
    assert not FORBIDDEN_NAMES.search(source), f"{path.name} uses keyboard or mouse control"


def test_page_script_only_reads_fields():
    js = browser_worker.DISCOVER_JS
    assert not FORBIDDEN_CALLS.search(js)
    assert "dispatchEvent" not in js and "submit(" not in js and "click(" not in js


def test_page_scripts_run_only_the_discovery_script():
    """The only code ever evaluated inside a page is the field-reading script."""
    for path in automation_sources():
        for call in re.findall(r"\.evaluate\(([^,)]*)", path.read_text(encoding="utf-8")):
            assert call.strip() == "DISCOVER_JS", f"{path.name} evaluates {call!r}"


def test_the_only_page_changes_are_navigation_and_typing_into_approved_fields():
    text = (AUTOMATION_DIR / "browser_worker.py").read_text(encoding="utf-8")
    assert re.findall(r"\.(goto|fill|select_option)\(", text)
    assert set(re.findall(r"locator\.(\w+)\(", text)) <= {"fill", "select_option", "count", "locator"}


# ====================================================================== classification
@pytest.mark.parametrize(
    "desc,kind,action",
    [
        ({"type": "password", "label": "Password"}, "password", "skip"),
        ({"type": "file", "label": "Upload resume"}, "file", "manual"),
        ({"type": "text", "label": "Gender"}, "sensitive", "skip"),
        ({"type": "text", "label": "Date of birth"}, "sensitive", "skip"),
        ({"type": "text", "label": "Aadhaar number"}, "sensitive", "skip"),
        ({"type": "text", "label": "I agree to the terms"}, "consent", "skip"),
        ({"type": "text", "label": "Signature"}, "consent", "skip"),
        ({"type": "checkbox", "label": "Subscribe to updates"}, "choice", "manual"),
        ({"type": "radio", "label": "Are you willing to relocate"}, "choice", "manual"),
        ({"type": "email", "label": "Email"}, "email", "fill"),
        ({"type": "tel", "label": "Phone"}, "phone", "fill"),
        ({"type": "text", "label": "First name"}, "first_name", "fill"),
        ({"type": "text", "label": "Surname"}, "last_name", "fill"),
        ({"type": "text", "label": "Full name"}, "full_name", "fill"),
        ({"type": "text", "label": "LinkedIn profile"}, "linkedin", "fill"),
        ({"type": "text", "label": "Expected salary"}, "salary", "manual"),
        ({"type": "text", "label": "Current CTC"}, "salary", "manual"),
        ({"type": "textarea", "tag": "textarea", "label": "Why do you want to work here?"}, "open_ended", "manual"),
    ],
)
def test_classification(desc, kind, action):
    got_kind, got_action, _ = classify_field(desc)
    assert (got_kind, got_action) == (kind, action)


def test_company_name_is_not_mistaken_for_the_candidates_name():
    kind, action, _ = classify_field({"type": "text", "label": "Company name"})
    assert kind != "full_name" and action == "manual"


def test_sensitive_and_consent_fields_are_never_fillable_even_when_the_page_hides_the_label():
    # the label is in the name attribute only
    assert classify_field({"type": "text", "name": "candidate_gender"})[1] == "skip"
    assert classify_field({"type": "text", "id_attr": "privacy-policy-ack"})[1] == "skip"


# ====================================================================== plan building
CTX = {
    "full_name": "Asha Verma",
    "email": "asha@example.com",
    "years_experience": 4.5,
    "profile": {
        "phone": "+91 98765 43210",
        "location": "Raipur",
        "linkedin_url": "https://www.linkedin.com/in/asha",
        "notice_period_days": 30,
        "experience": [{"company": "Acme", "title": "Backend Developer", "start_date": "2021-01", "current": True}],
    },
}


def field(fid, **kw):
    base = {"id": fid, "tag": "input", "type": "text", "label": "", "placeholder": "", "name": "", "id_attr": "", "autocomplete": ""}
    base.update(kw)
    return base


def plan_for(*descs, ctx=CTX, letter=None):
    return build_plan(list(descs), build_source(ctx, letter))


def by_id(plan):
    return {f["id"]: f for f in plan}


def test_only_verified_profile_values_are_proposed():
    plan = by_id(plan_for(
        field("0_1", type="email", label="Email"),
        field("0_2", type="tel", label="Phone"),
        field("0_3", label="First name"),
        field("0_4", label="Last name"),
        field("0_5", label="Current employer"),
        field("0_6", label="Current job title"),
        field("0_7", label="Years of experience"),
        field("0_8", label="Notice period"),
        field("0_9", label="LinkedIn URL"),
    ))
    assert plan["0_1"]["proposed"] == "asha@example.com"
    assert plan["0_2"]["proposed"] == "+91 98765 43210"
    assert (plan["0_3"]["proposed"], plan["0_4"]["proposed"]) == ("Asha", "Verma")
    assert plan["0_5"]["proposed"] == "Acme" and plan["0_6"]["proposed"] == "Backend Developer"
    assert plan["0_7"]["proposed"] == "4.5"
    assert plan["0_8"]["proposed"] == "30 days"
    assert plan["0_9"]["proposed"] == "https://www.linkedin.com/in/asha"


def test_nothing_is_invented_when_the_profile_has_no_value():
    empty = {"full_name": "Asha Verma", "email": "asha@example.com", "profile": {}}
    plan = by_id(plan_for(field("0_1", type="tel", label="Phone"), field("0_2", label="LinkedIn"), ctx=empty))
    for f in plan.values():
        assert f["proposed"] is None and f["action"] == "manual" and f["reason"]


def test_sensitive_salary_and_open_ended_fields_carry_no_value():
    plan = by_id(plan_for(
        field("0_1", label="Gender"),
        field("0_2", label="Expected salary"),
        field("0_3", tag="textarea", type="textarea", label="Describe a challenge you solved"),
        field("0_4", type="password", label="Password"),
    ))
    assert all(f["proposed"] is None for f in plan.values())
    assert plan["0_1"]["action"] == "skip" and plan["0_4"]["action"] == "skip"
    assert plan["0_2"]["action"] == "manual" and plan["0_3"]["action"] == "manual"


def test_select_value_must_match_an_existing_option():
    ok = by_id(plan_for(field("0_1", tag="select", type="select", label="City", options=["Mumbai", "RAIPUR"])))
    assert ok["0_1"]["proposed"] == "RAIPUR"
    none = by_id(plan_for(field("0_1", tag="select", type="select", label="City", options=["Mumbai", "Delhi"])))
    assert none["0_1"]["proposed"] is None and none["0_1"]["action"] == "manual"


def test_fields_with_existing_text_or_too_small_a_limit_are_left_alone():
    plan = by_id(plan_for(
        field("0_1", type="email", label="Email", current_value="someone@else.com"),
        field("0_2", label="Current employer", max_length=3),
    ))
    assert plan["0_1"]["proposed"] is None and plan["0_1"]["action"] == "manual"
    assert plan["0_2"]["proposed"] is None and plan["0_2"]["action"] == "manual"


def test_cover_letter_is_proposed_only_for_a_cover_letter_text_area():
    area = by_id(plan_for(field("0_1", tag="textarea", type="textarea", label="Cover letter"), letter="Dear team, hello."))
    assert area["0_1"]["proposed"] == "Dear team, hello."
    single_line = by_id(plan_for(field("0_1", label="Cover letter"), letter="Dear team, hello."))
    assert single_line["0_1"]["proposed"] is None
    no_letter = by_id(plan_for(field("0_1", tag="textarea", type="textarea", label="Cover letter")))
    assert no_letter["0_1"]["proposed"] is None


def test_plan_hash_changes_when_the_plan_changes():
    a = plan_for(field("0_1", type="email", label="Email"))
    b = plan_for(field("0_1", type="email", label="Email"))
    c = plan_for(field("0_1", type="email", label="Email"), ctx={**CTX, "email": "other@example.com"})
    assert plan_hash(a) == plan_hash(b) != plan_hash(c)


# ====================================================================== approval checks
def approval_plan():
    return plan_for(
        field("0_1", type="email", label="Email"),
        field("0_2", type="password", label="Password"),
        field("0_3", tag="select", type="select", label="City", options=["Mumbai", "Raipur"]),
        field("0_4", tag="textarea", type="textarea", label="Tell us why you want this job?"),
    )


def check(plan, items, confirmed=True, h=None):
    return validate_fill(plan, items, plan_hash(plan) if h is None else h, confirmed)


def error_of(plan, items, **kw):
    with pytest.raises(AssistError) as info:
        check(plan, items, **kw)
    return info.value


@pytest.mark.parametrize("confirmed", [False, None, "yes", 1])
def test_nothing_is_typed_without_an_explicit_true_confirmation(confirmed):
    err = error_of(approval_plan(), [{"id": "0_1", "value": "a@b.com"}], confirmed=confirmed)
    assert err.status_code == 422


def test_a_changed_plan_invalidates_the_approval():
    plan = approval_plan()
    err = error_of(plan, [{"id": "0_1", "value": "a@b.com"}], h="0" * 64)
    assert err.status_code == 409


def test_fields_kithi_never_touches_are_refused_even_if_the_user_asks():
    err = error_of(approval_plan(), [{"id": "0_2", "value": "hunter2"}])
    assert "never filled" in str(err)


def test_unknown_duplicate_and_non_text_values_are_refused():
    plan = approval_plan()
    assert "Unknown field" in str(error_of(plan, [{"id": "9_9", "value": "x"}]))
    assert "twice" in str(error_of(plan, [{"id": "0_1", "value": "a"}, {"id": "0_1", "value": "b"}]))
    assert "text value" in str(error_of(plan, [{"id": "0_1", "value": 5}]))


def test_select_values_must_be_listed_options_and_are_returned_in_their_exact_form():
    plan = approval_plan()
    assert "not one of the options" in str(error_of(plan, [{"id": "0_3", "value": "Atlantis"}]))
    approved = check(plan, [{"id": "0_3", "value": "raipur"}])
    assert approved == [{"id": "0_3", "value": "Raipur", "tag": "select", "type": "select"}]


def test_users_may_type_their_own_answer_into_a_manual_field_but_not_a_skipped_one():
    approved = check(approval_plan(), [{"id": "0_4", "value": "Because I enjoy building APIs."}])
    assert approved[0]["value"] == "Because I enjoy building APIs."


def test_values_are_cleaned_and_empty_ones_dropped():
    approved = check(approval_plan(), [{"id": "0_1", "value": " a\x00b@c.com\x07 "}, {"id": "0_4", "value": "   "}])
    assert approved == [{"id": "0_1", "value": "ab@c.com", "tag": "input", "type": "email"}]
    assert "Nothing to fill" in str(error_of(approval_plan(), [{"id": "0_1", "value": "  "}]))


def test_overlong_values_are_refused():
    assert "too long" in str(error_of(approval_plan(), [{"id": "0_4", "value": "x" * 2001}]))


# ====================================================================== network guard inside the worker
class FakeRoute:
    def __init__(self, url):
        self.request = type("Req", (), {"url": url})()
        self.outcome = None

    def continue_(self):
        self.outcome = "continue"

    def abort(self, reason):
        self.outcome = f"abort:{reason}"


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:8000/api/auth/me",
        "http://localhost/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://192.168.1.1/",
        "http://10.0.0.5/",
        "ftp://example.com/file",
        "file:///etc/passwd",
        "chrome://settings",
        "http://user:pass@example.com/",
    ],
)
def test_pages_cannot_reach_local_or_private_addresses_or_odd_schemes(url):
    route = FakeRoute(url)
    browser_worker.Worker()._guard(route)
    assert route.outcome == "abort:blockedbyclient"


def test_public_pages_and_inline_content_are_allowed(monkeypatch):
    monkeypatch.setattr(browser_worker, "assert_public_url", lambda url: url)
    worker = browser_worker.Worker()
    for url in ("https://jobs.example.com/apply", "data:image/png;base64,AAAA", "blob:https://x/1", "about:blank"):
        route = FakeRoute(url)
        worker._guard(route)
        assert route.outcome == "continue", url


def test_worker_fill_refuses_unfillable_field_types_even_if_asked():
    worker = browser_worker.Worker()
    worker._live_page = lambda: object()
    result = worker.fill({"items": [
        {"id": "0_1", "value": "x", "type": "password", "tag": "input"},
        {"id": "0_2", "value": "x", "type": "file", "tag": "input"},
        {"id": "0_3", "value": "x", "type": "checkbox", "tag": "input"},
        {"id": "../etc", "value": "x", "type": "text", "tag": "input"},
        {"id": "0_5", "value": "x", "type": "text", "tag": "input"},   # valid id but no such frame
    ]})
    assert result["filled"] == []
    assert len(result["failed"]) == 5


# ====================================================================== session control (real subprocesses)
ECHO_WORKER = (
    "import sys, json\n"
    "for line in sys.stdin:\n"
    "    cmd = json.loads(line)\n"
    "    if cmd['cmd'] == 'close': break\n"
    "    print(json.dumps({'ok': True, 'echo': cmd['cmd']}), flush=True)\n"
)
SILENT_WORKER = "import sys, time\nfor line in sys.stdin:\n    time.sleep(30)\n"


def echo_manager(**kw):
    return SessionManager(command=[sys.executable, "-u", "-c", ECHO_WORKER], **kw)


def test_one_browser_per_user_and_the_previous_one_is_closed():
    manager = echo_manager()
    try:
        first = manager.open("alice")
        second = manager.open("alice")
        assert first.id != second.id and not first.alive() and second.alive()
        assert second.call({"cmd": "ping"}, 5)["echo"] == "ping"
    finally:
        manager.close_all()


def test_sessions_are_private_to_their_owner():
    manager = echo_manager()
    try:
        session = manager.open("alice")
        with pytest.raises(AssistError) as info:
            manager.get(session.id, "bob")
        assert info.value.status_code == 404
        with pytest.raises(AssistError):
            manager.close(session.id, "bob")
        assert session.alive()
    finally:
        manager.close_all()


def test_too_many_open_windows_are_refused():
    manager = echo_manager(max_sessions=1)
    try:
        manager.open("alice")
        with pytest.raises(AssistError) as info:
            manager.open("bob")
        assert info.value.status_code == 429
    finally:
        manager.close_all()


def test_idle_sessions_are_closed_automatically():
    manager = echo_manager(idle_seconds=0.2)
    try:
        session = manager.open("alice")
        time.sleep(0.4)
        with pytest.raises(AssistError) as info:
            manager.get(session.id, "alice")
        assert info.value.status_code == 404 and not session.alive()
    finally:
        manager.close_all()


def test_a_closed_browser_is_reported_not_hidden():
    manager = echo_manager()
    try:
        session = manager.open("alice")
        session.proc.kill()
        session.proc.wait(timeout=5)
        with pytest.raises(AssistError) as info:
            session.call({"cmd": "scan"}, 5)
        assert info.value.status_code == 410
    finally:
        manager.close_all()


def test_a_browser_that_stops_responding_is_closed():
    manager = SessionManager(command=[sys.executable, "-u", "-c", SILENT_WORKER])
    try:
        session = manager.open("alice")
        with pytest.raises(AssistError) as info:
            session.call({"cmd": "scan"}, 0.5)
        assert info.value.status_code == 504
        for _ in range(40):  # the killed process can take a moment to be reaped
            if not session.alive():
                break
            time.sleep(0.1)
        assert not session.alive()
    finally:
        manager.close_all()


# ====================================================================== the real worker process
def real_manager():
    return SessionManager()  # default command: python -m app.automation.browser_worker


@pytest.mark.parametrize(
    "url,fragment",
    [
        ("http://127.0.0.1:8000/", "private or local"),
        ("http://169.254.169.254/latest/meta-data/", "private or local"),
        ("file:///etc/passwd", "Only http(s)"),
        ("javascript:alert(1)", "Only http(s)"),
        ("ftp://example.com/x", "Only http(s)"),
        ("http://user:pw@example.com/", "credentials"),
    ],
)
def test_the_real_worker_refuses_unsafe_addresses_before_starting_any_browser(url, fragment):
    manager = real_manager()
    try:
        session = manager.open("alice")
        with pytest.raises(AssistError) as info:
            session.call({"cmd": "open", "url": url}, 30)
        assert info.value.status_code == 422 and fragment in str(info.value)
    finally:
        manager.close_all()


def test_the_real_worker_rejects_unknown_commands_and_work_without_a_page():
    manager = real_manager()
    try:
        session = manager.open("alice")
        with pytest.raises(AssistError) as unknown:
            session.call({"cmd": "click_submit"}, 30)
        assert unknown.value.status_code == 400
        for command in ({"cmd": "scan"}, {"cmd": "fill", "items": [{"id": "0_1", "value": "x"}]}):
            with pytest.raises(AssistError) as none_open:
                session.call(command, 30)
            assert none_open.value.status_code == 410
    finally:
        manager.close_all()


def test_the_real_worker_exits_cleanly_when_told_to_close():
    manager = real_manager()
    session = manager.open("alice")
    proc = session.proc
    session.close()
    assert proc.poll() is not None
    manager.close_all()
