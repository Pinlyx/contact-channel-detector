"""One pass over an HTML document, collecting only what the detectors need."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Dict, List, Optional, Set, Tuple

# Script types that are data, not code. Their text is never searched.
_DATA_SCRIPT_TYPES = (
    "application/json",
    "application/ld+json",
    "importmap",
    "speculationrules",
    "text/template",
    "text/x-template",
    "text/html",
    "text/x-handlebars-template",
)
_SRC_ATTRS = ("src", "data-src", "data-rocket-src", "data-litespeed-src", "data-lazy-src")
_MAX_INLINE_SCRIPT = 100_000
_MAX_TEXT = 20_000
_MAX_TOKENS = 20_000


class Page(HTMLParser):
    """Collects anchors, resource URLs, inline scripts, class tokens and text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: List[str] = []
        self.anchor_count = 0
        self.resources: List[str] = []
        self.scripts: List[str] = []
        self.jsonld: List[str] = []
        self.cfemails: List[str] = []
        self.tokens: Set[str] = set()
        self.title = ""
        self.text = ""
        self.base: Optional[str] = None
        self.meta_refresh: Optional[Tuple[float, str]] = None
        self._script_type: Optional[str] = None
        self._script_buf: List[str] = []
        self._in_script = False
        self._in_title = False
        self._skip_text = 0

    # -- helpers ---------------------------------------------------------
    def _flush_script(self) -> None:
        if not self._in_script:
            return
        text = "".join(self._script_buf)
        stype = (self._script_type or "").lower().strip()
        if stype == "application/ld+json":
            self.jsonld.append(text)
        elif text.strip() and stype not in _DATA_SCRIPT_TYPES and len(text) <= _MAX_INLINE_SCRIPT:
            self.scripts.append(text)
        self._in_script = False
        self._script_buf = []
        self._script_type = None

    # -- HTMLParser hooks ------------------------------------------------
    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        a: Dict[str, str] = {}
        for k, v in attrs:
            if k not in a:
                a[k] = v or ""

        if len(self.tokens) < _MAX_TOKENS:
            for key in ("class", "id"):
                if a.get(key):
                    self.tokens.update(t for t in a[key].lower().split() if t)
        if "data-cfemail" in a:
            self.cfemails.append(a["data-cfemail"])

        if tag in ("a", "area"):
            if tag == "a":
                self.anchor_count += 1
            if a.get("href"):
                self.anchors.append(a["href"])
        elif tag == "script":
            self._flush_script()
            src = next((a[k] for k in _SRC_ATTRS if a.get(k)), "")
            if src:
                self.resources.append(src)
            else:
                self._in_script = True
                self._script_type = a.get("type", "")
        elif tag == "iframe":
            src = next((a[k] for k in _SRC_ATTRS if a.get(k)), "")
            if src:
                self.resources.append(src)
        elif tag == "link":
            if a.get("href") and (a.get("rel", "").lower() not in ("canonical", "alternate", "next", "prev")):
                self.resources.append(a["href"])
        elif tag == "base":
            if self.base is None and a.get("href"):
                self.base = a["href"]
        elif tag == "meta":
            if a.get("http-equiv", "").lower() == "refresh" and self.meta_refresh is None:
                m = re.match(r"\s*([\d.]+)\s*;?\s*(?:url\s*=\s*)?['\"]?([^'\"]*)", a.get("content", ""), re.I)
                if m and m.group(2):
                    try:
                        self.meta_refresh = (float(m.group(1)), m.group(2).strip())
                    except ValueError:
                        pass
        elif tag == "title":
            self._in_title = True
        elif tag in ("noscript", "template", "style"):
            self._skip_text += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "script":
            self._flush_script()
        elif tag == "title":
            self._in_title = False
        elif tag in ("noscript", "template", "style") and self._skip_text:
            self._skip_text -= 1

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._script_buf.append(data)
        elif self._in_title:
            self.title += data
        elif not self._skip_text and len(self.text) < _MAX_TEXT:
            self.text += data

    def close(self) -> None:
        super().close()
        self._flush_script()


def parse_page(html: str) -> Page:
    page = Page()
    try:
        page.feed(html)
        page.close()
    except Exception:  # malformed markup must never crash a scan
        page._flush_script()
    return page
