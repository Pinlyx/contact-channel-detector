"""Command line interface: contact-channels."""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from typing import Iterable, Iterator, List, Optional, Sequence, TextIO

from . import __version__
from .detect import detect
from .fetch import DEFAULT_USER_AGENT
from .models import CHANNEL_ORDER, Result
from .summary import format_summary, summarize

CSV_COLUMNS = ["url", "final_url", "status", "ok", "error", "parked", "instant_channel", "channels"] + list(
    CHANNEL_ORDER
)


def _read_urls(path: str) -> List[str]:
    handle = sys.stdin if path == "-" else open(path, "r", encoding="utf-8-sig")
    try:
        urls = []
        for line in handle:
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line.split()[0].split(",")[0])
        return urls
    finally:
        if handle is not sys.stdin:
            handle.close()


def result_to_csv_row(result: Result) -> List[str]:
    row = [
        result.url,
        result.final_url or "",
        "" if result.status is None else str(result.status),
        "true" if result.ok else "false",
        result.error or "",
        "true" if result.parked else "false",
        "true" if result.instant_channel else "false",
        ";".join(result.channels),
    ]
    for channel in CHANNEL_ORDER:
        details = []
        for f in result.by_channel(channel):
            label = f.value if f.value else f.provider
            if f.value and f.channel in ("live_chat", "multichannel_widget"):
                label = f.provider
            if label not in details:
                details.append(label)
        row.append(";".join(details))
    return row


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="contact-channels",
        description="Find out which contact channels a website offers customers "
        "(WhatsApp, Telegram, live chat widgets, social profiles, e-mail, phone).",
    )
    p.add_argument("urls", nargs="*", help="one or more site URLs or domains")
    p.add_argument("-i", "--input", metavar="FILE", help="file with one URL per line ('-' for stdin)")
    p.add_argument("-o", "--output", metavar="FILE", help="write results here instead of stdout")
    p.add_argument("--format", choices=("jsonl", "csv"), default="jsonl", help="output format (default: jsonl)")
    p.add_argument("--pretty", action="store_true", help="indent JSON (one URL at a time is easier to read)")
    p.add_argument("--workers", type=int, default=16, help="parallel fetches (default: 16)")
    p.add_argument("--timeout", type=float, default=12.0, help="seconds per request (default: 12)")
    p.add_argument("--max-bytes", type=int, default=1_500_000, help="stop reading a page after this many bytes")
    p.add_argument("--respect-robots", action="store_true", help="skip sites whose robots.txt disallows the homepage")
    p.add_argument("--insecure", action="store_true", help="do not verify TLS certificates")
    p.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help="override the User-Agent header")
    p.add_argument("--no-summary", action="store_true", help="never print the summary table")
    p.add_argument("--summary", action="store_true", help="always print the summary table (also for one URL)")
    p.add_argument("--version", action="version", version="contact-channel-detector " + __version__)
    return p


def _scan(urls: Sequence[str], args: argparse.Namespace) -> Iterator[Result]:
    def one(u: str) -> Result:
        return detect(
            u,
            timeout=args.timeout,
            user_agent=args.user_agent,
            max_bytes=args.max_bytes,
            verify_ssl=not args.insecure,
            respect_robots=args.respect_robots,
        )

    workers = max(1, min(args.workers, len(urls)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        yield from pool.map(one, urls)


def _write(results: Iterable[Result], fmt: str, pretty: bool, out: TextIO) -> List[Result]:
    kept: List[Result] = []
    writer = None
    if fmt == "csv":
        writer = csv.writer(out, lineterminator="\n")
        writer.writerow(CSV_COLUMNS)
    for r in results:
        kept.append(r)
        if writer is not None:
            writer.writerow(result_to_csv_row(r))
        elif pretty:
            out.write(json.dumps(r.to_dict(), ensure_ascii=False, indent=2) + "\n")
        else:
            out.write(json.dumps(r.to_dict(), ensure_ascii=False) + "\n")
        out.flush()
    return kept


def main(argv: Optional[Sequence[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure:
            reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    urls = list(args.urls)
    if args.input:
        urls += _read_urls(args.input)
    if not urls:
        build_parser().print_usage(sys.stderr)
        print("contact-channels: give at least one URL or -i FILE", file=sys.stderr)
        return 2

    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as fh:
            results = _write(_scan(urls, args), args.format, args.pretty, fh)
    else:
        results = _write(_scan(urls, args), args.format, args.pretty, sys.stdout)

    show_summary = args.summary or (len(urls) > 1 and not args.no_summary)
    if show_summary and not args.no_summary:
        print("", file=sys.stderr)
        print(format_summary(summarize(results)), file=sys.stderr)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
