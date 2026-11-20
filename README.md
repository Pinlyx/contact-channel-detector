# contact-channel-detector

Find out which ways a website gives its customers to reach it: WhatsApp, Telegram, Messenger, Viber, live chat widgets, social profiles, e-mail and phone. One homepage fetch in, one JSON object out, with the evidence for every finding.

```console
$ contact-channels example-shop.com.tr --pretty
{
  "url": "example-shop.com.tr",
  "final_url": "https://www.example-shop.com.tr/",
  "channels": ["whatsapp", "live_chat", "instagram", "facebook", "email", "phone"],
  "instant_channel": true,
  "findings": [
    {"channel": "whatsapp", "provider": "api.whatsapp.com", "value": "905551112233",
     "evidence": "https://api.whatsapp.com/send?phone=905551112233", "source": "link"},
    ...
```

Python 3.9+, standard library only, no dependencies.

## Why this exists

Wanting to know "does this business answer on WhatsApp, or only through a contact form?" sounds like a solved problem. It is not.

- **Wappalyzer stopped being open source in 2023.** The open forks of its fingerprint database are general technology detectors (which CMS, which CDN). They are not built around the question "how can a customer talk to this company right now", and their live chat and WhatsApp coverage is thin.
- **Social link libraries do not fetch pages**, and they do not know the false positives that dominate real HTML. A pattern like `instagram\.com/([A-Za-z0-9_.]+)` happily returns `embed.js`, `p`, `reel`, `explore` and `instagram` itself as "handles".
- **WhatsApp needs more than one pattern.** Real sites use `wa.me`, `api.whatsapp.com/send`, `whatsapp://send`, `wa.link` short links, and WordPress plugins that draw the button with JavaScript so no link exists in the HTML at all.

This library grew out of the scanner Pinlyx wrote for a study of 5,014 Turkish business websites. That scanner was used to produce [the research](https://pinlyx.com/research/turkey-website-whatsapp-live-chat-2026) (WhatsApp on 38.9% of sites, live chat on 2.2%, no instant channel at all on 59.9%) and the open dataset [turkey-website-contact-channels](https://github.com/Pinlyx/turkey-website-contact-channels). The rules here are the cleaned-up, tested version of that scanner, and they are stricter in a few places (see "Differences from the study scanner").

## Install

The package is not on PyPI yet. Install from GitHub:

```console
pip install git+https://github.com/Pinlyx/contact-channel-detector
```

## Quick start

Command line:

```console
# one site
contact-channels example.com

# many sites, 32 in parallel, results as CSV, percentage table on stderr
contact-channels -i urls.txt --format csv --workers 32 -o results.csv

# polite mode: honour robots.txt, 8 second timeout
contact-channels -i urls.txt --respect-robots --timeout 8
```

`urls.txt` has one URL or domain per line. Blank lines and lines starting with `#` are skipped.

Python:

```python
from contactchannels import detect, detect_html

result = detect("https://example.com")     # fetches the homepage
print(result.channels)                     # ['whatsapp', 'live_chat', 'instagram']
print(result.instant_channel)              # True: WhatsApp, chat, Telegram, Messenger or Viber is offered
print(result.values("whatsapp"))           # ['905551112233']
print(result.providers("live_chat"))       # ['Tawk.to']
print(result.social)                       # {'instagram': 'examplehandle'}

for f in result.findings:
    print(f.channel, f.provider, f.value, f.evidence, f.source)

# no network: parse HTML you already have
result = detect_html(open("page.html", encoding="utf-8").read(), base_url="https://example.com/")
```

`detect()` never raises for network problems. A failed fetch returns a `Result` with `ok=False` and a short `error` such as `timeout`, `dns error`, `HTTP 403`, `blocked by robots.txt`.

## Output

Each site produces one object:

```json
{
  "url": "example.com",
  "final_url": "https://www.example.com/",
  "status": 200,
  "ok": true,
  "error": null,
  "parked": false,
  "parked_reason": null,
  "channels": ["whatsapp", "live_chat", "instagram", "email"],
  "instant_channel": true,
  "social": {"instagram": "examplehandle"},
  "findings": [
    {"channel": "live_chat", "provider": "Tawk.to", "value": null,
     "evidence": "https://embed.tawk.to/abc/default", "source": "script"}
  ]
}
```

| Field | Meaning |
| --- | --- |
| `channel` | `whatsapp`, `telegram`, `messenger`, `viber`, `live_chat`, `multichannel_widget`, `instagram`, `facebook`, `x`, `tiktok`, `youtube`, `linkedin`, `pinterest`, `threads`, `bluesky`, `email`, `phone` |
| `provider` | Vendor or platform: `Tawk.to`, `Joinchat (WordPress)`, `wa.me`, `Instagram` ... |
| `value` | Normalised handle, number or address. `null` for widgets, which have none. |
| `evidence` | The matching link, script URL, class name or code fragment. |
| `source` | `link`, `script`, `plugin`, `jsonld` (schema.org `sameAs`) or `cfemail` (Cloudflare-protected address) |

`instant_channel` is true when the site offers any of `whatsapp`, `telegram`, `messenger`, `viber`, `live_chat` or `multichannel_widget`.

Values are normalised: WhatsApp and Viber numbers are digits only, handles are lower case without `@`, YouTube is `@name`, `channel/UC...`, `c/name` or `user/name`, LinkedIn is `company/slug` or `in/slug`, Facebook ids are `id/123`.

CSV output has one column per channel (details joined with `;`), plus `url`, `final_url`, `status`, `ok`, `error`, `parked`, `instant_channel` and `channels`.

### Summary table

With more than one URL the CLI prints a table to stderr (stdout stays clean for piping). Percentages are computed over sites that were reachable and not parked:

```text
Sites: 5   unreachable: 0   parked/placeholder: 0   analysed: 5

channel                  sites   share
---------------------- ------- -------
any instant channel          3   60.0%
no instant channel           2   40.0%
whatsapp                     2   40.0%
live_chat                    1   20.0%
instagram                    5  100.0%
...

whatsapp providers: api.whatsapp.com (2)
live_chat providers: Crisp (1)
```

(Real output from a five-site run, trimmed. Every channel is listed in the full table.) The same data is available from Python as `summarize(results)` and `format_summary(...)`.

### CLI options

| Option | Default | |
| --- | --- | --- |
| `URL ...` / `-i FILE` | | URLs on the command line and/or a file (`-` for stdin) |
| `--format jsonl\|csv` | `jsonl` | |
| `--pretty` | off | indented JSON |
| `-o FILE` | stdout | |
| `--workers N` | 16 | parallel fetches |
| `--timeout S` | 12 | seconds per request |
| `--max-bytes N` | 1500000 | stop reading a page after this many bytes |
| `--respect-robots` | off | skip sites whose robots.txt disallows the homepage |
| `--insecure` | off | do not verify TLS certificates (many small sites have broken ones) |
| `--user-agent S` | `contact-channel-detector/0.1 (+https://github.com/Pinlyx/contact-channel-detector)` | |
| `--summary` / `--no-summary` | summary for 2+ URLs | |

The fetcher follows redirects, keeps cookies for the duration of one request (some sites redirect-loop without them), decodes gzip and legacy Turkish charsets (windows-1254, iso-8859-9), tries `http://` when `https://` fails for a URL given without a scheme, and follows one short `<meta http-equiv="refresh">` hop, which parked and migrated sites often use.

## Why this is accurate

Everything here was learned from false positives in a real crawl. The rules:

1. **Only `href` values count for profiles.** Anchors are classified; page text, comments and attributes are not searched. An earlier pattern-over-raw-HTML version counted `//www.instagram.com/embed.js`, `xmlns:fb="http://www.facebook.com/2008/fbml"`, the `facebook.com/tr?id=` pixel and share buttons as "has Instagram / Facebook".
2. **Share, intent, embed and post paths are not profiles.** Rejected: `sharer`, `share`, `intent`, `plugins`, `dialog`, `embed`, `p/`, `reel/`, `tv/`, `stories/`, `explore/`, `status/`, `watch`, `hashtag`, `groups`, `events`, `login`, `/video/` links, `t.me/share`, `t.me/channel/123`, `pinterest.com/pin/...`, `linkedin.com/shareArticle`. A profile is one clean path segment (or the platform's documented profile form such as `profile.php?id=`, `@handle`, `company/slug`).
3. **Share buttons for messengers are not contact points.** `wa.me/?text=...`, `api.whatsapp.com/send?text=...`, `whatsapp://send?text=...`, `viber://forward` and `mailto:?subject=...` carry no recipient and are ignored. A WhatsApp link needs a phone number, a `message/` code or a `wa.link` code.
4. **The platforms' own accounts are not customers.** `instagram.com/instagram`, `linkedin.com/company/linkedin`, `x.com/x` and similar are dropped, as are other people's posts embedded with `utm_source=ig_embed`.
5. **Widgets are matched where they load, not where they are mentioned.** A signature must match a `<script src>`, `<iframe src>`, `<link href>`, an inline script or an element class/id. Plain text, comments, `application/json` and `ld+json` blocks, and inline scripts over 100 KB (framework bundles that list every vendor they support) are skipped. This is why a vendor's marketing page that talks about its own widget is not reported as having it.
6. **Look-alike hosts of the same vendor are told apart.** LiveChat's `cdn.livechatinc.com/partners/tracking/track.js` is an affiliate tracker, not the chat widget, and is not matched. HubSpot's general `hs-scripts.com` tracker is not matched, only the `js.usemessages.com` conversations embed. Elfsight hosts dozens of unrelated widgets (feeds, reviews) so it is not reported at all.
7. **Parked and placeholder pages are flagged.** Parking hosts (`sedoparking.com`, `parkingcrew.net`, `dan.com`, `afternic.com` ...), "domain for sale" phrases in English and Turkish ("bu alan adı satılıktır"), default server pages ("Welcome to nginx", "It works!"), and "under construction / yapım aşamasında / çok yakında" pages. A page is only flagged when it is also small (under 25 links and little text), so a real shop with a "coming soon" badge is not parked. Flagged pages are returned with `parked: true` and are excluded from summary percentages.
8. **Cloudflare e-mail protection is decoded.** Cloudflare replaces addresses with `data-cfemail="..."` or `/cdn-cgi/l/email-protection#...`. The first byte of that hex string is an XOR key for the rest. Both forms are decoded, otherwise every protected site looks like it has no e-mail.
9. **Resolved before classified.** Relative links resolve against `<base href>` and the final URL after redirects; scheme-less `href="instagram.com/foo"` written by site owners is understood.

Each rule has a regression test in `tests/`, using hand-written fixtures and HTML trimmed from real sites.

### Differences from the study scanner

The scanner behind the research counted `getbutton`, `elfsight` and the HubSpot tracking script as WhatsApp / live chat signals and only counted Messenger through the page plugin. This library reports `getbutton` and `chaty` as a separate `multichannel_widget` channel (the HTML does not say which apps are switched on), drops Elfsight and the HubSpot tracker, and counts `m.me` links as Messenger. Numbers from the two will therefore differ slightly.

## Detected providers

**WhatsApp** (links): `wa.me/<number>`, `wa.me/message/<code>`, `api.whatsapp.com/send?phone=`, `web.whatsapp.com/send?phone=`, `whatsapp://send?phone=`, `wa.link/<code>`, `chat.whatsapp.com/<code>` (group invite), `whatsapp.com/channel/<id>`. Numbers inside inline scripts as `wa.me/<number>` also count.

**WhatsApp** (WordPress plugins and widgets, found by files and CSS classes because the button is often drawn by JavaScript):

| Provider | Fingerprint |
| --- | --- |
| Joinchat | `/plugins/creame-whatsapp-me/`, `joinchat.min.js`, `.joinchat` classes |
| Click to Chat | `/plugins/click-to-chat-for-whatsapp/`, `.ht-ctc` classes |
| WhatsApp Chat (QuadLayers) | `/plugins/wp-whatsapp-chat/`, `.qlwapp` classes |
| WP Chat App | `/plugins/wp-whatsapp/`, `.wa__btn_popup` |
| WhatsHelp | `whatshelp.io` |
| any other WordPress plugin with "whatsapp" in its folder name | `/wp-content/plugins/<name>/` |

**Other messengers**: Telegram (`t.me/<name>`, `telegram.me`, `tg://resolve`, invite links), Messenger (`m.me/<page>`, `messenger.com/t/`, Facebook Customer Chat plugin), Viber (`viber://chat`, `viber://add`, `viber://pa`, `invite.viber.com`).

**Live chat and help widgets**:

| Provider | Matched on |
| --- | --- |
| Tawk.to | `embed.tawk.to`, `Tawk_API` |
| Tidio | `code.tidio.co`, `tidioChatApi` |
| JivoChat | `code.jivosite.com`, `jivo_api` |
| Crisp | `client.crisp.chat`, `CRISP_WEBSITE_ID` |
| Intercom | `widget.intercom.io`, `js.intercomcdn.com`, `intercomSettings` |
| Zendesk Web Widget | `static.zdassets.com/ekr/`, `v2.zopim.com` (the widget can be help-center only) |
| LiveChat | `cdn.livechatinc.com`, `__lc.license` |
| HubSpot Conversations | `js.usemessages.com`, `HubSpotConversations` |
| Drift | `js.driftt.com`, `drift.load(` |
| Freshchat | `wchat.freshchat.com`, `fcWidget.init` |
| Smartsupp | `smartsuppchat.com`, `_smartsupp` |
| Zoho SalesIQ | `salesiq.zoho.*`, `$zoho.salesiq` |
| Olark | `static.olark.com`, `olark.identify` |
| Chatra | `call.chatra.io`, `ChatraID` |
| LiveAgent | `*.ladesk.com/scripts/track.js`, `LiveAgent.createButton` |
| Userlike | `userlike-cdn-widgets` |
| Gorgias Chat | `gorgias.chat` |
| Re:amaze | `cdn.reamaze.com` |
| Help Scout Beacon | `beacon-v2.helpscout.net`, `Beacon('init'` |
| Front Chat | `chat-assets.frontapp.com`, `FrontChat(` |
| Chatwoot | `chatwoot` script URLs, `chatwootSDK`, `chatwootSettings` |
| Bitrix24 site button | `/crm/site_button/` |
| Livesupporti | `livesupporti` |

**Multichannel button services** (`multichannel_widget`): GetButton (`getbutton.io`), Chaty (`/plugins/chaty/`).

**Social profiles** (normalised handle): Instagram, Facebook (including `profile.php?id=`, `pages/...`, `p/...`), X / Twitter, TikTok, YouTube (`@name`, `channel/`, `c/`, `user/`), LinkedIn (`company/`, `in/`, `school/`, `showcase/`), Pinterest (all country domains), Threads (`threads.net` and `threads.com`), Bluesky. Profiles are read from anchors and from schema.org `sameAs` in JSON-LD.

**E-mail**: `mailto:` links and Cloudflare-obfuscated addresses. **Phone**: `tel:` links.

Adding a provider is a few lines in `src/contactchannels/signatures.py`; please include a fixture and a test.

## Limits

Be careful before trusting a negative result.

- **One page, raw HTML, no JavaScript.** Only the homepage is fetched and nothing is executed. A widget that a tag manager or another script injects after load (very common for Intercom, HubSpot, Drift, and for chat added through Google Tag Manager) is invisible. The same goes for WhatsApp buttons drawn entirely by script without a plugin class or file. Treat "no live chat found" as "none in the page source", not "none".
- **Single-page apps** that render their footer client-side show few or no links.
- **Bot protection.** Sites behind Cloudflare challenges or WAF rules answer 403 or serve an interstitial; they come back as `ok: false`. Large retailers do this often. Respecting a site's wishes is the point of `--respect-robots`; this tool does not try to evade blocking.
- **Contact pages are not visited.** Many sites keep their WhatsApp number only on `/contact`. Run the tool on that URL as well if it matters.
- **A link is a claim, not proof.** A `wa.me` number can be disconnected; a chat widget can be installed but switched off outside office hours. The detector reports what the page offers.
- **Handles are not verified.** Nothing checks that an Instagram profile exists.
- **Widget signatures are vendor-visible strings** that vendors can change. They are checked against live pages when added, not continuously.
- **Parked detection is heuristic.** It favours not discarding real sites over catching every placeholder.

## Contributing

Issues and pull requests are welcome, especially new providers and false positives from real sites. See [CONTRIBUTING.md](CONTRIBUTING.md). Tests never touch the network:

```console
pip install -e ".[test]"
python -m pytest
```

## License

MIT, see [LICENSE](LICENSE).

Built and maintained by [Pinlyx](https://pinlyx.com/?utm_source=github&utm_medium=readme&utm_campaign=contact-channel-detector), one inbox for WhatsApp, Instagram, live chat and more.
