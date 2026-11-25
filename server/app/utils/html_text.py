import re
from html.parser import HTMLParser

_BLOCK = {"p", "br", "div", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "section", "article", "ul", "ol", "table"}
_SKIP = {"script", "style", "noscript", "svg", "template", "iframe"}


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip = 0
        self.title = ""
        self.in_title = False
        self.description = ""

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self.skip += 1
        elif tag == "title":
            self.in_title = True
        elif tag == "meta":
            attributes = dict(attrs)
            name = (attributes.get("name") or attributes.get("property") or "").lower()
            if name in ("description", "og:description") and not self.description:
                self.description = (attributes.get("content") or "").strip()
        if tag == "li":
            self.parts.append("\n- ")
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self.in_title = False
        if tag in _BLOCK or tag == "li":
            self.parts.append("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self.parts.append(data)


def extract_page_info(html: str) -> dict:
    parser = _Extractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        pass
    text = "".join(parser.parts)
    lines = [re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in text.splitlines()]
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(line for line in lines if line or True)).strip()
    return {"title": parser.title.strip(), "description": parser.description, "text": cleaned}


def html_to_text(html: str) -> str:
    return extract_page_info(html or "")["text"]
