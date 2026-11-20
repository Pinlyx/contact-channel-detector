"""Aggregate many results into the percentages a survey needs."""

from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, Iterable, List

from .models import CHANNEL_ORDER, LIVE_CHAT, WHATSAPP, Result

_PROVIDER_CHANNELS = (WHATSAPP, LIVE_CHAT, "multichannel_widget")


def _pct(count: int, n: int) -> Dict[str, Any]:
    p = count / n if n else 0.0
    ci = 1.96 * math.sqrt(p * (1 - p) / n) if n else 0.0
    return {"count": count, "pct": round(100 * p, 1), "ci95": round(100 * ci, 1)}


def summarize(results: Iterable[Result]) -> Dict[str, Any]:
    """Counts and percentages over the sites that were reachable and not parked.

    Unreachable sites and parked, default or placeholder pages are reported
    separately and left out of the denominators.
    """
    rows: List[Result] = list(results)
    reachable = [r for r in rows if r.ok]
    parked = [r for r in reachable if r.parked]
    analysed = [r for r in reachable if not r.parked]
    n = len(analysed)

    channels = {c: _pct(sum(1 for r in analysed if r.has(c)), n) for c in CHANNEL_ORDER}
    instant = sum(1 for r in analysed if r.instant_channel)
    providers: Dict[str, List[Any]] = {}
    for channel in _PROVIDER_CHANNELS:
        counter: Counter = Counter()
        for r in analysed:
            counter.update(r.providers(channel))
        providers[channel] = [[name, c] for name, c in counter.most_common()]

    return {
        "sites": len(rows),
        "unreachable": len(rows) - len(reachable),
        "parked": len(parked),
        "analysed": n,
        "channels": channels,
        "instant_channel": _pct(instant, n),
        "no_instant_channel": _pct(n - instant, n),
        "providers": providers,
    }


def format_summary(summary: Dict[str, Any]) -> str:
    """Render summarize() output as a plain-text table."""
    lines = [
        "Sites: %d   unreachable: %d   parked/placeholder: %d   analysed: %d"
        % (summary["sites"], summary["unreachable"], summary["parked"], summary["analysed"]),
        "",
        "%-22s %7s %7s" % ("channel", "sites", "share"),
        "%-22s %7s %7s" % ("-" * 22, "-" * 7, "-" * 7),
    ]
    rows = [("any instant channel", summary["instant_channel"]),
            ("no instant channel", summary["no_instant_channel"])]
    rows += [(c, summary["channels"][c]) for c in CHANNEL_ORDER]
    for name, v in rows:
        lines.append("%-22s %7d %6.1f%%" % (name, v["count"], v["pct"]))
    for channel, items in summary["providers"].items():
        if items:
            top = ", ".join("%s (%d)" % (name, c) for name, c in items[:8])
            lines.append("")
            lines.append("%s providers: %s" % (channel, top))
    return "\n".join(lines)
