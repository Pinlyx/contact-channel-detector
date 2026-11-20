"""Turn one link into zero or more channel hits.

The rule that keeps this accurate: only a link that points at a real profile,
number or address counts. Share buttons, embed scripts, single posts, login
walls and the platforms' own corporate pages live on the same hosts and are
all rejected here.
"""

from __future__ import annotations

import re
from typing import List, NamedTuple, Optional
from urllib.parse import parse_qs, unquote, urljoin, urlsplit

from .emails import clean_email, decode_cfemail, split_mailto
from .models import EMAIL, MESSENGER, PHONE, TELEGRAM, VIBER, WHATSAPP


class Hit(NamedTuple):
    channel: str
    provider: str
    value: Optional[str]


# A link like href="instagram.com/foo" has no scheme; browsers would treat it as
# relative, but the author meant the profile.
_SCHEMELESS = re.compile(
    r"^(?:www\.|m\.)?(?:instagram\.com|facebook\.com|fb\.com|twitter\.com|x\.com|"
    r"tiktok\.com|youtube\.com|linkedin\.com|pinterest\.com|threads\.net|threads\.com|"
    r"bsky\.app|t\.me|wa\.me|m\.me)/",
    re.I,
)

# Accounts that belong to the platform itself, not to a business.
_SELF_HANDLES = {
    "facebook", "instagram", "meta", "twitter", "x", "linkedin", "youtube", "tiktok",
    "pinterest", "threads", "bsky", "whatsapp", "messenger", "telegram", "fb", "ig",
}

_FILE_EXT = re.compile(r"\.(?:php|js|json|css|html?|xml|png|jpe?g|gif|svg|ico|webp|txt|map)$", re.I)


def _host(sp) -> str:
    host = (sp.hostname or "").lower().rstrip(".")
    return host


def _is(host: str, *domains: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in domains)


def _segments(sp) -> List[str]:
    return [unquote(s) for s in sp.path.split("/") if s]


def _digits(value: str) -> str:
    return re.sub(r"\D", "", value)


# --------------------------------------------------------------------------
# Messaging apps
# --------------------------------------------------------------------------

def _whatsapp(sp, host: str) -> Optional[Hit]:
    query = {k.lower(): v for k, v in parse_qs(sp.query).items()}
    segs = _segments(sp)
    phone = _digits(query["phone"][0]) if query.get("phone") else ""

    if sp.scheme == "whatsapp":
        # whatsapp://send?phone=...  (whatsapp://send?text=... is a share button)
        return Hit(WHATSAPP, "whatsapp://", phone) if len(phone) >= 6 else None

    if host == "wa.me":
        if segs and segs[0].lower() == "message" and len(segs) > 1:
            return Hit(WHATSAPP, "wa.me", "message/" + segs[1])
        if segs:
            number = _digits(segs[0])
            if len(number) >= 6 and re.fullmatch(r"\+?[\d\s().-]+", segs[0]):
                return Hit(WHATSAPP, "wa.me", number)
        if len(phone) >= 6:
            return Hit(WHATSAPP, "wa.me", phone)
        return None  # wa.me/?text=... is a share button

    if host == "wa.link" and segs:
        return Hit(WHATSAPP, "wa.link", segs[0])

    if host in ("api.whatsapp.com", "web.whatsapp.com", "whatsapp.com", "www.whatsapp.com"):
        if segs and segs[0] == "send":
            return Hit(WHATSAPP, host, phone) if len(phone) >= 6 else None
        if len(segs) > 1 and segs[0] == "message":
            return Hit(WHATSAPP, host, "message/" + segs[1])
        if len(segs) > 1 and segs[0] == "channel":
            return Hit(WHATSAPP, "WhatsApp Channel", "channel/" + segs[1])
        return None

    if host == "chat.whatsapp.com" and segs:
        return Hit(WHATSAPP, "WhatsApp group invite", "group/" + segs[0])
    return None


_TG_RESERVED = {
    "share", "iv", "addstickers", "addemoji", "setlanguage", "proxy", "socks", "login",
    "addlist", "boost", "giftcode", "invoice", "bg", "contact", "c", "m", "dl", "download",
    "apps", "faq", "privacy", "tos", "blog", "web", "k", "a", "z",
}
_TG_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_]{3,31}$")


def _telegram_name(name: str) -> Optional[str]:
    return name.lower() if _TG_NAME.match(name) and name.lower() not in _TG_RESERVED else None


def _telegram(sp, host: str) -> Optional[Hit]:
    if sp.scheme == "tg":
        domain = parse_qs(sp.query).get("domain", [""])[0]
        name = _telegram_name(domain)
        return Hit(TELEGRAM, "t.me", name) if name else None
    segs = _segments(sp)
    if not segs:
        return None
    first = segs[0]
    if first.startswith("+") and len(first) > 6:
        return Hit(TELEGRAM, "t.me", "invite/" + first[1:])
    if first.lower() == "joinchat" and len(segs) > 1:
        return Hit(TELEGRAM, "t.me", "invite/" + segs[1])
    if first.lower() == "s" and len(segs) == 2:  # public preview of a channel
        name = _telegram_name(segs[1])
        return Hit(TELEGRAM, "t.me", name) if name else None
    if len(segs) == 1:
        name = _telegram_name(first)
        return Hit(TELEGRAM, "t.me", name) if name else None
    return None  # t.me/channel/123 is a single post, t.me/share/url is a share button


def _messenger(sp, host: str) -> Optional[Hit]:
    segs = _segments(sp)
    if host == "m.me" and segs:
        name = segs[0].lower()
        if name in ("j", "login") or not re.fullmatch(r"[A-Za-z0-9_.\-]{3,80}", segs[0]):
            return None
        return Hit(MESSENGER, "m.me", name)
    if host == "messenger.com" or host.endswith(".messenger.com"):
        if len(segs) == 2 and segs[0] == "t":
            return Hit(MESSENGER, "messenger.com", segs[1].lower())
        return None
    if host in ("facebook.com", "www.facebook.com", "m.facebook.com") and len(segs) >= 3:
        if segs[0] == "messages" and segs[1] == "t":
            return Hit(MESSENGER, "facebook.com/messages", segs[2].lower())
    if host in ("fb.com", "www.fb.com") and len(segs) == 2 and segs[0] == "msg":
        return Hit(MESSENGER, "fb.com/msg", segs[1].lower())
    return None


def _viber(sp, host: str) -> Optional[Hit]:
    if sp.scheme == "viber":
        action = (sp.netloc or sp.path.strip("/")).lower()
        query = {k.lower(): v for k, v in parse_qs(sp.query).items()}
        if action in ("chat", "add", "contact") and query.get("number"):
            number = _digits(query["number"][0])
            return Hit(VIBER, "viber://", number) if len(number) >= 6 else None
        if action == "pa" and query.get("chaturi"):
            return Hit(VIBER, "viber://", "pa/" + query["chaturi"][0])
        return None  # viber://forward?text=... is a share button
    if host == "invite.viber.com":
        group = parse_qs(sp.query).get("g2", [""])[0]
        return Hit(VIBER, "invite.viber.com", "group/" + group) if group else None
    return None


# --------------------------------------------------------------------------
# Social profiles
# --------------------------------------------------------------------------

def _plain_handle(handle: str, pattern: str, reserved: set) -> Optional[str]:
    handle = handle.lstrip("@")
    low = handle.lower()
    if low in reserved or low in _SELF_HANDLES:
        return None
    if not re.fullmatch(pattern, handle):
        return None
    if _FILE_EXT.search(handle):  # embed.js, widgets.js, sdk.php ...
        return None
    return low


_IG_RESERVED = {
    "p", "reel", "reels", "tv", "explore", "stories", "accounts", "developer", "developers",
    "about", "legal", "embed", "share", "sharer", "static", "direct", "web", "oauth",
    "directory", "privacy", "api", "challenge", "login", "press", "help", "download",
    "invites", "nametag", "topics", "emails", "session", "graphql", "ajax", "locations",
    "tags", "hashtag", "s", "ads", "video", "_n", "a",
}


def _instagram(sp, host: str) -> Optional[Hit]:
    if "ig_embed" in sp.query or "ig_embed" in sp.path:
        return None  # the profile link inside an embedded third-party post
    segs = _segments(sp)
    if len(segs) == 2 and segs[0] == "_u":  # deep-link form instagram.com/_u/handle
        segs = segs[1:]
    if len(segs) != 1:
        return None
    handle = _plain_handle(segs[0], r"[A-Za-z0-9_.]{1,30}", _IG_RESERVED)
    return Hit("instagram", "Instagram", handle) if handle else None


_FB_RESERVED = {
    "sharer", "sharer.php", "share", "share.php", "plugins", "dialog", "tr", "2008", "groups",
    "events", "watch", "login", "login.php", "policies", "privacy", "help", "legal", "hashtag",
    "marketplace", "gaming", "permalink.php", "photo", "photo.php", "video.php", "story.php",
    "ads", "business", "careers", "about", "l.php", "home.php", "notes", "reel", "reels",
    "stories", "flx", "public", "search", "settings", "places", "lists", "games", "friends",
    "messages", "messenger", "bookmarks", "directory", "r.php", "recover", "security",
    "support", "fbml", "v1.0", "plugin", "connect", "sdk", "tos.php", "pages", "people", "pg",
    "profile.php", "p", "media", "photos", "videos", "posts", "fundraisers", "donate",
}
_FB_SUBDOMAINS = re.compile(r"^(?:www|m|web|mbasic|touch|[a-z]{2}(?:-[a-z]{2})?)$")


def _facebook(sp, host: str) -> Optional[Hit]:
    if host in ("fb.com", "fb.me", "www.fb.com"):
        pass
    elif host == "facebook.com":
        pass
    elif host.endswith(".facebook.com") and _FB_SUBDOMAINS.match(host[: -len(".facebook.com")]):
        pass
    else:
        return None
    segs = _segments(sp)
    if not segs:
        return None
    first = segs[0]
    low = first.lower()
    if low == "profile.php" and len(segs) == 1:
        ident = parse_qs(sp.query).get("id", [""])[0]
        return Hit("facebook", "Facebook", "id/" + ident) if ident.isdigit() else None
    if low in ("pages", "people") and len(segs) >= 3 and segs[-1].isdigit():
        return Hit("facebook", "Facebook", "id/" + segs[-1])
    if low == "p" and len(segs) == 2:
        tail = segs[1].rsplit("-", 1)[-1]
        return Hit("facebook", "Facebook", "id/" + tail) if tail.isdigit() else None
    if low == "pg" and len(segs) >= 2:
        segs = segs[1:]
        first, low = segs[0], segs[0].lower()
        if len(segs) > 2:
            return None
    elif len(segs) != 1:
        return None
    if re.fullmatch(r"v\d+(?:\.\d+)*", low):  # SDK paths like /v2.8/plugins/...
        return None
    handle = _plain_handle(first, r"[A-Za-z0-9.\-]{3,80}", _FB_RESERVED)
    return Hit("facebook", "Facebook", handle) if handle else None


_X_RESERVED = {
    "i", "intent", "share", "home", "search", "hashtag", "explore", "login", "signup",
    "settings", "messages", "notifications", "compose", "tos", "privacy", "about", "download",
    "jobs", "who_to_follow", "account", "oauth", "widgets", "status", "statuses", "web",
}


def _x(sp, host: str) -> Optional[Hit]:
    segs = _segments(sp)
    if len(segs) != 1:
        return None
    handle = _plain_handle(segs[0], r"[A-Za-z0-9_]{1,15}", _X_RESERVED)
    return Hit("x", "X (Twitter)", handle) if handle else None


def _tiktok(sp, host: str) -> Optional[Hit]:
    segs = _segments(sp)
    if len(segs) != 1 or not segs[0].startswith("@"):
        return None
    handle = _plain_handle(segs[0], r"[A-Za-z0-9_.]{2,24}", set())
    return Hit("tiktok", "TikTok", handle) if handle else None


def _youtube(sp, host: str) -> Optional[Hit]:
    segs = _segments(sp)
    if not segs:
        return None
    first = segs[0]
    if first.startswith("@") and re.fullmatch(r"@[A-Za-z0-9_.\-]{3,60}", first):
        return Hit("youtube", "YouTube", first.lower())
    if first == "channel" and len(segs) >= 2 and re.fullmatch(r"UC[A-Za-z0-9_\-]{22}", segs[1]):
        return Hit("youtube", "YouTube", "channel/" + segs[1])
    if first in ("c", "user") and len(segs) >= 2 and re.fullmatch(r"[A-Za-z0-9_.\-%]{2,80}", segs[1]):
        return Hit("youtube", "YouTube", first + "/" + segs[1].lower())
    return None


def _linkedin(sp, host: str) -> Optional[Hit]:
    segs = _segments(sp)
    if len(segs) < 2 or segs[0].lower() not in ("company", "in", "school", "showcase"):
        return None
    if any(s.lower() in ("admin", "mycompany") for s in segs[2:]):
        return None  # an admin surface nobody else can open
    slug = segs[1].lower()
    if slug in _SELF_HANDLES or not re.fullmatch(r"[^\s/]{2,100}", slug):
        return None
    return Hit("linkedin", "LinkedIn", segs[0].lower() + "/" + slug)


_PIN_RESERVED = {
    "pin", "pin-builder", "ideas", "search", "business", "today", "topics", "explore",
    "login", "about", "create", "settings", "oauth", "source", "_", "ads", "news",
}


def _pinterest(sp, host: str) -> Optional[Hit]:
    segs = _segments(sp)
    if len(segs) != 1:
        return None
    handle = _plain_handle(segs[0], r"[A-Za-z0-9_]{3,30}", _PIN_RESERVED)
    return Hit("pinterest", "Pinterest", handle) if handle else None


def _threads(sp, host: str) -> Optional[Hit]:
    segs = _segments(sp)
    if len(segs) != 1 or not segs[0].startswith("@"):
        return None
    handle = _plain_handle(segs[0], r"[A-Za-z0-9_.]{1,30}", set())
    return Hit("threads", "Threads", handle) if handle else None


def _bluesky(sp, host: str) -> Optional[Hit]:
    segs = _segments(sp)
    if len(segs) == 2 and segs[0] == "profile" and re.fullmatch(r"[A-Za-z0-9.\-]{3,253}", segs[1]):
        return Hit("bluesky", "Bluesky", segs[1].lower())
    return None


_PINTEREST_HOST = re.compile(r"(?:^|\.)pinterest\.(?:com|[a-z]{2,3}|com\.[a-z]{2}|co\.[a-z]{2})$")


def classify_url(url: str) -> List[Hit]:
    """Classify one absolute URL (or a whatsapp:/tg:/viber: URI)."""
    try:
        sp = urlsplit(url.strip())
    except ValueError:
        return []
    scheme = sp.scheme.lower()
    host = _host(sp)

    if scheme == "whatsapp":
        hit = _whatsapp(sp, host)
        return [hit] if hit else []
    if scheme == "tg":
        hit = _telegram(sp, host)
        return [hit] if hit else []
    if scheme == "viber":
        hit = _viber(sp, host)
        return [hit] if hit else []
    if scheme not in ("http", "https") or not host:
        return []

    hit: Optional[Hit] = None
    if _is(host, "wa.me", "wa.link", "whatsapp.com"):
        hit = _whatsapp(sp, host)
    elif _is(host, "t.me", "telegram.me", "telegram.dog"):
        hit = _telegram(sp, "t.me")
    elif host == "m.me" or _is(host, "messenger.com"):
        hit = _messenger(sp, host)
    elif host == "invite.viber.com":
        hit = _viber(sp, host)
    elif _is(host, "instagram.com", "instagr.am"):
        hit = _instagram(sp, host)
    elif _is(host, "facebook.com", "fb.com", "fb.me"):
        hit = _messenger(sp, host) or _facebook(sp, host)
    elif _is(host, "twitter.com", "x.com"):
        hit = _x(sp, host)
    elif _is(host, "tiktok.com"):
        hit = _tiktok(sp, host)
    elif host in ("youtube.com", "www.youtube.com", "m.youtube.com"):
        hit = _youtube(sp, host)
    elif _is(host, "linkedin.com"):
        hit = _linkedin(sp, host)
    elif _PINTEREST_HOST.search(host):
        hit = _pinterest(sp, host)
    elif _is(host, "threads.net", "threads.com"):
        hit = _threads(sp, host)
    elif host == "bsky.app":
        hit = _bluesky(sp, host)
    return [hit] if hit else []


# --------------------------------------------------------------------------
# mailto: and tel:
# --------------------------------------------------------------------------

def _mailto(rest: str) -> List[Hit]:
    hits: List[Hit] = []
    for raw in split_mailto(rest):
        address = clean_email(raw)
        if address:
            hits.append(Hit(EMAIL, "mailto", address))
    return hits


def _tel(rest: str) -> List[Hit]:
    value = unquote(rest).split(";")[0].strip()
    digits = _digits(value)
    if len(digits) < 5 or len(digits) > 17:
        return []
    return [Hit(PHONE, "tel", ("+" if value.lstrip().startswith("+") else "") + digits)]


def classify_href(href: str, base_url: str = "") -> List[Hit]:
    """Classify the href of an anchor. Relative links resolve against base_url."""
    h = (href or "").strip()
    if not h or h.startswith("#"):
        return []
    low = h.lower()
    if low.startswith("mailto:"):
        return _mailto(h[7:])
    if low.startswith("tel:"):
        return _tel(h[4:])
    if low.startswith(("javascript:", "data:", "sms:", "blob:")):
        return []
    if low.startswith(("whatsapp:", "tg:", "viber:")):
        return classify_url(h)
    if "/cdn-cgi/l/email-protection#" in low:
        encoded = h.split("#", 1)[1]
        decoded = decode_cfemail(encoded)
        address = clean_email(decoded) if decoded else None
        return [Hit(EMAIL, "cloudflare-obfuscated", address)] if address else []
    if _SCHEMELESS.match(h):
        h = "https://" + h
    url = urljoin(base_url, h) if base_url else h
    if "//" not in url and not url.lower().startswith(("whatsapp:", "tg:", "viber:")):
        return []
    return classify_url(url)
