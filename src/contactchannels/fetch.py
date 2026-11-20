"""A small, polite HTTP fetcher built on urllib."""

from __future__ import annotations

import codecs
import http.cookiejar
import re
import socket
import ssl
import threading
import urllib.error
import urllib.request
import urllib.robotparser
import zlib
from typing import Dict, NamedTuple, Optional, Tuple
from urllib.parse import quote, urlsplit, urlunsplit

from . import __version__

_MAJOR_MINOR = ".".join(__version__.split(".")[:2])
DEFAULT_USER_AGENT = (
    "contact-channel-detector/%s (+https://github.com/Pinlyx/contact-channel-detector)" % _MAJOR_MINOR
)
ROBOTS_TOKEN = "contact-channel-detector"


class FetchResult(NamedTuple):
    final_url: Optional[str]
    status: Optional[int]
    html: Optional[str]
    error: Optional[str]
    # True when the failure was at the connection level (DNS, TLS, refused, timeout),
    # so a different scheme is worth trying.
    connection_failed: bool = False


def normalize_url(raw: str) -> Tuple[str, bool]:
    """Return (absolute url, whether the caller gave a scheme)."""
    value = raw.strip()
    had_scheme = bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", value))
    if not had_scheme:
        value = "https://" + value.lstrip("/")
    parts = urlsplit(value)
    host = parts.hostname or ""
    try:
        host_ascii = host.encode("idna").decode("ascii") if host else host
    except UnicodeError:
        host_ascii = host
    netloc = host_ascii
    if ":" in host_ascii:  # IPv6 literal
        netloc = "[" + host_ascii + "]"
    if parts.port:
        netloc += ":%d" % parts.port
    path = quote(parts.path or "/", safe="%/:@&=+$,;~!*'()-._")
    query = quote(parts.query, safe="%/:@&=+$,;~!*'()?-._")
    return urlunsplit((parts.scheme.lower(), netloc, path, query, "")), had_scheme


def _context(verify_ssl: bool) -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    if not verify_ssl:
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _opener(verify_ssl: bool) -> urllib.request.OpenerDirector:
    jar = http.cookiejar.CookieJar()
    return urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(jar),
        urllib.request.HTTPSHandler(context=_context(verify_ssl)),
    )


def _request(url: str, user_agent: str, accept_language: str) -> urllib.request.Request:
    return urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.5",
            "Accept-Language": accept_language,
            "Accept-Encoding": "gzip, deflate",
        },
    )


def _read_limited(resp, max_bytes: int) -> bytes:
    encoding = (resp.headers.get("Content-Encoding") or "").lower().strip()
    decomp = None
    if encoding in ("gzip", "x-gzip"):
        decomp = zlib.decompressobj(16 + zlib.MAX_WBITS)
    elif encoding == "deflate":
        decomp = zlib.decompressobj()
    out = bytearray()
    try:
        while len(out) < max_bytes:
            chunk = resp.read(65536)
            if not chunk:
                break
            if decomp is not None:
                try:
                    chunk = decomp.decompress(chunk)
                except zlib.error:
                    if encoding == "deflate":  # some servers send raw deflate
                        decomp = zlib.decompressobj(-zlib.MAX_WBITS)
                        try:
                            chunk = decomp.decompress(chunk)
                        except zlib.error:
                            break
                    else:
                        break
            out.extend(chunk)
    except (OSError, ValueError):
        pass  # keep whatever arrived before the connection broke
    return bytes(out[:max_bytes])


def decode_body(body: bytes, content_type: str = "") -> str:
    """Decode bytes using the HTTP charset, then <meta charset>, then UTF-8."""
    if body.startswith(codecs.BOM_UTF8):
        return body[len(codecs.BOM_UTF8):].decode("utf-8", "replace")
    charset = None
    m = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    if m:
        charset = m.group(1)
    else:
        m2 = re.search(rb"<meta[^>]+charset=[\"']?([\w\-]+)", body[:4096], re.I)
        if m2:
            charset = m2.group(1).decode("ascii", "ignore")
    if charset:
        try:
            return body.decode(codecs.lookup(charset).name, "replace")
        except (LookupError, ValueError):
            pass
    return body.decode("utf-8", "replace")


_robots_cache: Dict[str, Optional[urllib.robotparser.RobotFileParser]] = {}
_robots_lock = threading.Lock()


def robots_allows(url: str, user_agent: str, timeout: float, verify_ssl: bool) -> bool:
    """True when robots.txt allows fetching url. Missing or broken robots.txt allows it."""
    parts = urlsplit(url)
    origin = "%s://%s" % (parts.scheme, parts.netloc)
    with _robots_lock:
        known = origin in _robots_cache
        parser = _robots_cache.get(origin)
    if not known:
        parser = None
        try:
            resp = _opener(verify_ssl).open(_request(origin + "/robots.txt", user_agent, "en"), timeout=timeout)
            if getattr(resp, "status", 200) == 200:
                text = decode_body(_read_limited(resp, 500_000), resp.headers.get("Content-Type", ""))
                parser = urllib.robotparser.RobotFileParser()
                parser.parse(text.splitlines())
        except Exception:
            parser = None
        with _robots_lock:
            _robots_cache[origin] = parser
    if parser is None:
        return True
    return parser.can_fetch(ROBOTS_TOKEN, url) or parser.can_fetch(user_agent, url)


def _describe(exc: BaseException) -> Tuple[str, bool]:
    reason = getattr(exc, "reason", exc)
    if isinstance(reason, (socket.timeout, TimeoutError)):
        return "timeout", True
    if isinstance(reason, ssl.SSLError):
        return "ssl error: %s" % (getattr(reason, "reason", None) or reason), True
    if isinstance(reason, socket.gaierror):
        return "dns error", True
    if isinstance(reason, ConnectionError):
        return "connection error: %s" % type(reason).__name__, True
    if isinstance(exc, (urllib.error.URLError, OSError)):
        return "network error: %s" % reason, True
    return "%s: %s" % (type(exc).__name__, exc), False


def fetch_html(
    url: str,
    *,
    timeout: float = 12.0,
    user_agent: str = DEFAULT_USER_AGENT,
    max_bytes: int = 1_500_000,
    verify_ssl: bool = True,
    respect_robots: bool = False,
    accept_language: str = "en;q=0.9,tr;q=0.8",
) -> FetchResult:
    """GET one page, following redirects, and return its decoded HTML."""
    if respect_robots and not robots_allows(url, user_agent, timeout, verify_ssl):
        return FetchResult(None, None, None, "blocked by robots.txt")
    try:
        resp = _opener(verify_ssl).open(_request(url, user_agent, accept_language), timeout=timeout)
    except urllib.error.HTTPError as exc:
        return FetchResult(exc.geturl(), exc.code, None, "HTTP %d" % exc.code)
    except Exception as exc:  # urllib raises a wide mix of exception types
        message, conn = _describe(exc)
        return FetchResult(None, None, None, message, conn)
    try:
        status = getattr(resp, "status", 200)
        final_url = resp.geturl()
        ctype = resp.headers.get("Content-Type", "")
        if ctype and not re.search(r"html|xml", ctype, re.I):
            return FetchResult(final_url, status, None, "not html (%s)" % ctype.split(";")[0].strip())
        body = _read_limited(resp, max_bytes)
        return FetchResult(final_url, status, decode_body(body, ctype), None)
    except Exception as exc:
        message, conn = _describe(exc)
        return FetchResult(None, None, None, message, conn)
    finally:
        resp.close()
