"""E-mail helpers, including Cloudflare's address obfuscation."""

from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import unquote

_EMAIL = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,24}$")


_FILE_TLDS = {"png", "jpg", "jpeg", "gif", "svg", "webp", "css", "js", "ico", "avif"}


def decode_cfemail(encoded: str) -> Optional[str]:
    """Decode a Cloudflare e-mail protection string.

    Cloudflare replaces an address with a hex string found in a
    ``data-cfemail`` attribute or after ``/cdn-cgi/l/email-protection#``. The
    first byte is an XOR key and every following byte is one character XORed
    with it.
    """
    encoded = (encoded or "").strip()
    if len(encoded) < 4 or len(encoded) % 2 or not re.fullmatch(r"[0-9a-fA-F]+", encoded):
        return None
    data = bytes.fromhex(encoded)
    key = data[0]
    try:
        return bytes(b ^ key for b in data[1:]).decode("utf-8")
    except UnicodeDecodeError:
        return None


def clean_email(raw: str) -> Optional[str]:
    """Return a lower-case address from a mailto fragment, or None if invalid."""
    value = unquote(raw or "").strip()
    if value.lower().startswith("mailto:"):
        value = value[7:]
    value = value.split("?", 1)[0].strip().strip("<>\"' ")
    if not _EMAIL.match(value):
        return None
    if value.rsplit(".", 1)[-1].lower() in _FILE_TLDS:  # image@2x.png is a filename
        return None
    return value.lower()


def split_mailto(rest: str) -> List[str]:
    """Split the part after ``mailto:`` into its (possibly several) addresses."""
    head = rest.split("?", 1)[0]
    return [p for p in re.split(r"[,;]", unquote(head)) if p.strip()]
