"""Network behaviour, tested against a throwaway local HTTP server (no internet)."""

import csv
import gzip
import io
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from contactchannels import detect, summarize, format_summary
from contactchannels.cli import main
from contactchannels.fetch import DEFAULT_USER_AGENT, decode_body

SHOP = """<!doctype html><html><head><meta charset="utf-8"><title>Dükkan</title>
<script src="https://embed.tawk.to/abc/default" async></script></head><body>
<a href="https://wa.me/905551112233">WhatsApp</a>
<a href="https://www.instagram.com/dukkan/">Instagram</a>
<p>%s</p></body></html>""" % ("Ürünlerimiz " * 60)

SEEN_UA = []


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def _send(self, code, body=b"", ctype="text/html; charset=utf-8", headers=None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        SEEN_UA.append(self.headers.get("User-Agent"))
        path = self.path
        if path == "/":
            self._send(200, SHOP.encode("utf-8"))
        elif path == "/redirect":
            self._send(302, b"", headers={"Location": "/"})
        elif path == "/gzip":
            self._send(200, gzip.compress(SHOP.encode("utf-8")), headers={"Content-Encoding": "gzip"})
        elif path == "/latin5":
            body = SHOP.replace('charset="utf-8"', 'charset="windows-1254"').encode("cp1254")
            self._send(200, body, ctype="text/html")
        elif path == "/refresh":
            self._send(200, b'<html><head><meta http-equiv="refresh" content="0; url=/"></head><body>Redirecting</body></html>' + b" " * 300)
        elif path == "/pdf":
            self._send(200, b"%PDF-1.4", ctype="application/pdf")
        elif path == "/missing":
            self._send(404, b"nope")
        elif path == "/tiny":
            self._send(200, b"<html></html>")
        elif path == "/blocked":
            self._send(200, SHOP.encode("utf-8"))
        elif path == "/robots.txt":
            self._send(200, b"User-agent: *\nDisallow: /blocked\n", ctype="text/plain")
        else:
            self._send(404, b"")


@pytest.fixture(scope="module")
def base():
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield "http://127.0.0.1:%d" % server.server_address[1]
    server.shutdown()


def test_detect_fetches_and_reports(base):
    r = detect(base + "/")
    assert r.ok and r.status == 200
    assert r.values("whatsapp") == ["905551112233"]
    assert r.providers("live_chat") == ["Tawk.to"]
    assert r.social == {"instagram": "dukkan"}
    assert r.final_url == base + "/"


def test_redirects_are_followed(base):
    r = detect(base + "/redirect")
    assert r.ok and r.final_url == base + "/"
    assert r.url == base + "/redirect"


def test_gzip_and_legacy_charset(base):
    assert detect(base + "/gzip").has("whatsapp")
    assert detect(base + "/latin5").has("whatsapp")


def test_decode_body_turkish_charsets():
    text = "Çözüm İletişim ğüşıö"
    assert decode_body(text.encode("cp1254"), "text/html; charset=windows-1254") == text
    assert decode_body(text.encode("iso-8859-9"), "text/html; charset=iso-8859-9") == text
    assert decode_body(b"<meta charset='windows-1254'>" + text.encode("cp1254"), "text/html").endswith(text)
    assert decode_body(b"\xef\xbb\xbfabc", "") == "abc"


def test_meta_refresh_is_followed_once(base):
    r = detect(base + "/refresh")
    assert r.ok and r.has("whatsapp")
    assert detect(base + "/refresh", follow_meta_refresh=False).has("whatsapp") is False


def test_failures_are_results_not_exceptions(base):
    assert detect(base + "/missing").error == "HTTP 404"
    assert detect(base + "/pdf").error.startswith("not html")
    assert "near-empty" in detect(base + "/tiny").error
    closed = detect("http://127.0.0.1:1/", timeout=2)
    assert not closed.ok and closed.error
    assert not detect("http://", timeout=2).ok


def test_polite_user_agent_and_robots(base):
    del SEEN_UA[:]
    detect(base + "/")
    assert SEEN_UA[-1] == DEFAULT_USER_AGENT
    assert DEFAULT_USER_AGENT.startswith("contact-channel-detector/0.1 (+https://github.com/Pinlyx/contact-channel-detector)")
    assert detect(base + "/blocked").ok  # robots not respected unless asked
    r = detect(base + "/blocked", respect_robots=True)
    assert not r.ok and r.error == "blocked by robots.txt"
    assert detect(base + "/", respect_robots=True).ok


def test_cli_jsonl_single_url(base, capsys):
    assert main([base + "/"]) == 0
    out, err = capsys.readouterr()
    row = json.loads(out.strip().splitlines()[0])
    assert row["channels"] == ["whatsapp", "live_chat", "instagram"]
    assert row["instant_channel"] is True
    assert "Sites:" not in err  # no summary for one URL unless asked


def test_cli_file_input_csv_and_summary(base, tmp_path, capsys):
    urls = tmp_path / "urls.txt"
    urls.write_text("# comment\n%s/\n\n%s/missing\n%s/gzip\n" % (base, base, base), encoding="utf-8")
    out_file = tmp_path / "out.csv"
    assert main(["-i", str(urls), "--format", "csv", "-o", str(out_file), "--workers", "3"]) == 0
    rows = list(csv.DictReader(io.StringIO(out_file.read_text(encoding="utf-8"))))
    assert [r["ok"] for r in rows] == ["true", "false", "true"]  # input order kept
    assert rows[0]["whatsapp"] == "905551112233"
    assert rows[0]["live_chat"] == "Tawk.to"
    assert rows[1]["error"] == "HTTP 404"
    err = capsys.readouterr().err
    assert "Sites: 3" in err and "unreachable: 1" in err and "analysed: 2" in err
    assert "whatsapp" in err and "100.0%" in err


def test_cli_requires_input(capsys):
    assert main([]) == 2


def test_summarize_excludes_unreachable_and_parked():
    from contactchannels import detect_html
    from contactchannels.models import Result

    good = detect_html('<a href="https://wa.me/905551112233">x</a>')
    plain = detect_html("<p>nothing here</p>")
    parked = detect_html("<title>Welcome to nginx!</title><h1>Welcome to nginx!</h1>")
    dead = Result(url="x", ok=False, error="timeout")
    s = summarize([good, plain, parked, dead])
    assert (s["sites"], s["unreachable"], s["parked"], s["analysed"]) == (4, 1, 1, 2)
    assert s["channels"]["whatsapp"]["count"] == 1
    assert s["channels"]["whatsapp"]["pct"] == 50.0
    assert s["no_instant_channel"]["count"] == 1
    assert "50.0%" in format_summary(s)
