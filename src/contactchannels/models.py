"""Result types shared by the library and the CLI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Channel kinds, in the order they are reported.
WHATSAPP = "whatsapp"
TELEGRAM = "telegram"
MESSENGER = "messenger"
VIBER = "viber"
LIVE_CHAT = "live_chat"
MULTICHANNEL_WIDGET = "multichannel_widget"
EMAIL = "email"
PHONE = "phone"

SOCIAL_CHANNELS = (
    "instagram",
    "facebook",
    "x",
    "tiktok",
    "youtube",
    "linkedin",
    "pinterest",
    "threads",
    "bluesky",
)

CHANNEL_ORDER = (
    WHATSAPP,
    TELEGRAM,
    MESSENGER,
    VIBER,
    LIVE_CHAT,
    MULTICHANNEL_WIDGET,
) + SOCIAL_CHANNELS + (EMAIL, PHONE)

# Channels a visitor can use to talk to the business right now.
INSTANT_CHANNELS = (WHATSAPP, TELEGRAM, MESSENGER, VIBER, LIVE_CHAT, MULTICHANNEL_WIDGET)


@dataclass
class Finding:
    """One detected channel, with the evidence that proves it.

    channel   one of the kinds in CHANNEL_ORDER
    provider  vendor or platform ("Tawk.to", "wa.me", "Instagram", "joinchat")
    value     normalised handle, number, address or None (widgets have none)
    evidence  the matching href, script URL or code fragment
    source    where it was found: link, script, plugin, jsonld or cfemail
    """

    channel: str
    provider: str
    value: Optional[str]
    evidence: str
    source: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel": self.channel,
            "provider": self.provider,
            "value": self.value,
            "evidence": self.evidence,
            "source": self.source,
        }


@dataclass
class Result:
    """What one website offers customers."""

    url: str
    final_url: Optional[str] = None
    status: Optional[int] = None
    ok: bool = True
    error: Optional[str] = None
    parked: bool = False
    parked_reason: Optional[str] = None
    findings: List[Finding] = field(default_factory=list)

    @property
    def channels(self) -> List[str]:
        """Channel kinds present, in canonical order."""
        present = {f.channel for f in self.findings}
        return [c for c in CHANNEL_ORDER if c in present]

    @property
    def instant_channel(self) -> bool:
        """True when at least one real-time channel (chat, WhatsApp, ...) is offered."""
        return any(f.channel in INSTANT_CHANNELS for f in self.findings)

    def has(self, channel: str) -> bool:
        return any(f.channel == channel for f in self.findings)

    def by_channel(self, channel: str) -> List[Finding]:
        return [f for f in self.findings if f.channel == channel]

    def providers(self, channel: str) -> List[str]:
        out: List[str] = []
        for f in self.by_channel(channel):
            if f.provider not in out:
                out.append(f.provider)
        return out

    def values(self, channel: str) -> List[str]:
        out: List[str] = []
        for f in self.by_channel(channel):
            if f.value and f.value not in out:
                out.append(f.value)
        return out

    @property
    def social(self) -> Dict[str, str]:
        """First normalised handle per social platform."""
        out: Dict[str, str] = {}
        for f in self.findings:
            if f.channel in SOCIAL_CHANNELS and f.value and f.channel not in out:
                out[f.channel] = f.value
        return out

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "status": self.status,
            "ok": self.ok,
            "error": self.error,
            "parked": self.parked,
            "parked_reason": self.parked_reason,
            "channels": self.channels,
            "instant_channel": self.instant_channel,
            "social": self.social,
            "findings": [f.to_dict() for f in self.findings],
        }
