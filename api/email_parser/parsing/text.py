"""HTML to line-oriented text conversion."""

from __future__ import annotations

from html.parser import HTMLParser

from .models import Email

MAX_CHARS = 20_000
_SKIP = {"script", "style", "head", "title"}
_BREAKS = {"br", "div", "p", "tr", "td", "th", "li", "ul", "ol", "table",
           "h1", "h2", "h3", "h4", "h5", "h6"}


class _Extractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP:
            self._skip_depth += 1
        elif tag in _BREAKS:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in _SKIP:
            self._skip_depth = max(0, self._skip_depth - 1)
        elif tag in _BREAKS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip_depth:
            self.parts.append(data)


def html_to_text(html: str) -> str:
    """One cell/block per line, whitespace collapsed, empty lines dropped."""
    extractor = _Extractor()
    extractor.feed(html)
    extractor.close()
    lines = (" ".join(line.split()) for line in "".join(extractor.parts).splitlines())
    return "\n".join(line for line in lines if line)[:MAX_CHARS]


def email_text(email: Email) -> str:
    """Prefer the HTML body as text; fall back to the plain body."""
    return html_to_text(email.html) or email.plain[:MAX_CHARS]
