"""Detection: parse one page and report the channels it offers."""

from __future__ import annotations

import json
import re
from typing import Any, Iterable, List, Optional, Set, Tuple
from urllib.parse import urljoin, urlsplit

from .emails import clean_email, decode_cfemail
from .fetch import DEFAULT_USER_AGENT, fetch_html, normalize_url
from .links import Hit, classify_href, classify_url
from .models import EMAIL, WHATSAPP, Finding, Result
from .page import Page, parse_page
from .signatures import GENERIC_WP_WHATSAPP, PARKED_PHRASES, PARKING_HOSTS, WIDGETS

_INLINE_WA = re.compile(r"(?:https?:)?//wa\.me/\+?(\d{7,15})\b", re.I)


def _clip(text: str, limit: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 3] + "..."


class _Collector:
    """Accumulates findings and drops exact duplicates."""

    def __init__(self) -> None:
        self.findings: List[Finding] = []
        self._seen: Set[Tuple[str, str, str]] = set()

    def add(self, channel: str, provider: str, value: Optional[str], evidence: str, source: str) -> None:
        key = (channel, provider.lower(), (value or "").lower())
        if key in self._seen:
            return
        self._seen.add(key)
        self.findings.append(Finding(channel, provider, value, _clip(evidence), source))

    def add_hits(self, hits: Iterable[Hit], evidence: str, source: str) -> None:
        for hit in hits:
            self.add(hit.channel, hit.provider, hit.value, evidence, source)


def _walk_same_as(node: Any, out: List[str], depth: int = 0) -> None:
    if depth > 8:
        return
    if isinstance(node, dict):
        same = node.get("sameAs")
        if isinstance(same, str):
            out.append(same)
        elif isinstance(same, list):
            out.extend(s for s in same if isinstance(s, str))
        for value in node.values():
            if isinstance(value, (dict, list)):
                _walk_same_as(value, out, depth + 1)
    elif isinstance(node, list):
        for value in node:
            _walk_same_as(value, out, depth + 1)


def _parked(page: Page, final_host: str) -> Optional[str]:
    """Reason string when the page is a parked, default or placeholder page."""
    small = page.anchor_count < 25 and len(page.text.strip()) < 5000
    if not small:
        return None
    hosts = [final_host] + [urlsplit(r if "//" in r else "//" + r).hostname or "" for r in page.resources]
    hosts += [urlsplit(a).hostname or "" for a in page.anchors if "//" in a]
    for host in hosts:
        host = host.lower()
        for parking in PARKING_HOSTS:
            if host == parking or host.endswith("." + parking):
                return "parking host: " + parking
    head = (page.title + " " + page.text[:3000]).strip()
    for phrase in PARKED_PHRASES:
        m = phrase.search(head)
        if m:
            return "page text: " + _clip(m.group(0), 60)
    return None


def _build(page: Page, base_url: str, url: str) -> Result:
    base = urljoin(base_url, page.base) if (page.base and base_url) else (page.base or base_url)
    found = _Collector()

    # 1. Links: every anchor href, classified.
    for href in page.anchors:
        found.add_hits(classify_href(href, base), href, "link")

    # 2. Cloudflare-obfuscated addresses outside of href.
    for encoded in page.cfemails:
        decoded = decode_cfemail(encoded)
        address = clean_email(decoded) if decoded else None
        if address:
            found.add(EMAIL, "cloudflare-obfuscated", address, "data-cfemail=" + encoded, "cfemail")

    # 3. Structured data: the organisation's own declared profiles.
    for raw in page.jsonld:
        try:
            data = json.loads(raw)
        except ValueError:
            continue
        urls: List[str] = []
        _walk_same_as(data, urls)
        for u in urls:
            found.add_hits([h for h in classify_url(u) if h.channel not in (EMAIL,)], "sameAs: " + u, "jsonld")

    # 4. Widgets and plugins.
    resources = [r.strip() for r in page.resources if r and r.strip()]
    for sig in WIDGETS:
        matched: Optional[str] = None
        for res in resources:
            if any(p.search(res) for p in sig.resources):
                matched = res
                break
        if matched is None and sig.inline:
            for text in page.scripts:
                for p in sig.inline:
                    m = p.search(text)
                    if m:
                        matched = m.group(0)
                        break
                if matched:
                    break
        if matched is None and sig.classes:
            for token in page.tokens:
                if any(p.search(token) for p in sig.classes):
                    matched = "class/id: " + token
                    break
        if matched:
            found.add(sig.channel, sig.provider, None, matched, sig.source)

    known_plugin_dirs = ("creame-whatsapp-me", "click-to-chat-for-whatsapp", "wp-whatsapp-chat", "wp-whatsapp", "wp-whatsapp-pro")
    for res in resources:
        m = GENERIC_WP_WHATSAPP.search(res)
        if m and m.group(1).lower() not in known_plugin_dirs:
            found.add(WHATSAPP, "WordPress plugin: " + m.group(1).lower(), None, res, "plugin")

    # 5. WhatsApp numbers written into inline scripts (plugin settings, click handlers).
    for text in page.scripts:
        for m in _INLINE_WA.finditer(text):
            found.add(WHATSAPP, "wa.me", m.group(1), m.group(0), "script")

    final_host = (urlsplit(base_url).hostname or "") if base_url else ""
    reason = _parked(page, final_host)
    return Result(
        url=url,
        final_url=base_url or None,
        parked=reason is not None,
        parked_reason=reason,
        findings=found.findings,
    )


def detect_html(html: str, base_url: str = "") -> Result:
    """Detect channels in HTML you already have. No network access.

    base_url resolves relative links and is recorded as the result's final_url.
    """
    return _build(parse_page(html or ""), base_url, base_url)


def detect(
    url: str,
    *,
    timeout: float = 12.0,
    user_agent: str = DEFAULT_USER_AGENT,
    max_bytes: int = 1_500_000,
    verify_ssl: bool = True,
    respect_robots: bool = False,
    follow_meta_refresh: bool = True,
    accept_language: str = "en;q=0.9,tr;q=0.8",
) -> Result:
    """Fetch one site's homepage and report its contact channels.

    Never raises for network problems: a failed fetch returns a Result with
    ok=False and a short error string.
    """
    try:
        target, had_scheme = normalize_url(url)
    except Exception as exc:
        return Result(url=url, ok=False, error="invalid url: %s" % exc)

    def get(u: str):
        return fetch_html(
            u,
            timeout=timeout,
            user_agent=user_agent,
            max_bytes=max_bytes,
            verify_ssl=verify_ssl,
            respect_robots=respect_robots,
            accept_language=accept_language,
        )

    fetched = get(target)
    if fetched.connection_failed and not had_scheme and target.startswith("https://"):
        retry = get("http://" + target[len("https://"):])
        if retry.error is None or not retry.connection_failed:
            fetched = retry

    hops = 0
    page: Optional[Page] = None
    while fetched.error is None and fetched.html is not None:
        page = parse_page(fetched.html)
        refresh = page.meta_refresh
        if (
            follow_meta_refresh
            and refresh is not None
            and refresh[0] <= 5
            and len(page.text.strip()) < 300
            and hops < 2
        ):
            nxt = urljoin(fetched.final_url or target, refresh[1])
            if nxt.lower().startswith(("http://", "https://")) and nxt != fetched.final_url:
                follow = get(nxt)
                hops += 1
                if follow.error is None and follow.html is not None:
                    fetched = follow
                    continue
        break

    if fetched.error is not None or fetched.html is None or page is None:
        return Result(
            url=url,
            final_url=fetched.final_url,
            status=fetched.status,
            ok=False,
            error=fetched.error or "no content",
        )
    if len(fetched.html.strip()) < 200:
        return Result(url=url, final_url=fetched.final_url, status=fetched.status, ok=False,
                      error="empty or near-empty response")

    result = _build(page, fetched.final_url or target, url)
    result.status = fetched.status
    return result
