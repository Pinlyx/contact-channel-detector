"""Script, host and plugin signatures for chat widgets.

Every signature is matched against three things only:

* resources: the URL of a <script src>, <iframe src> or <link href>
* inline: the text of an inline <script> (JSON and template blocks are skipped)
* classes: the class and id tokens of elements

Plain text, comments and anchors are never searched, so a blog post that merely
talks about a vendor does not count as installing it.
"""

from __future__ import annotations

import re
from typing import List, Pattern, Tuple

from .models import LIVE_CHAT, MESSENGER, MULTICHANNEL_WIDGET, WHATSAPP


class Signature:
    def __init__(
        self,
        key: str,
        provider: str,
        channel: str,
        resources: Tuple[str, ...] = (),
        inline: Tuple[str, ...] = (),
        classes: Tuple[str, ...] = (),
        source: str = "script",
    ) -> None:
        self.key = key
        self.provider = provider
        self.channel = channel
        self.source = source
        self.resources: List[Pattern[str]] = [re.compile(p, re.I) for p in resources]
        self.inline: List[Pattern[str]] = [re.compile(p, re.I) for p in inline]
        self.classes: List[Pattern[str]] = [re.compile(p, re.I) for p in classes]


S = Signature

# Live chat and help-desk widgets. Each one is identified by the host it loads
# from or by the global object its documented snippet creates.
WIDGETS: Tuple[Signature, ...] = (
    S("tawk", "Tawk.to", LIVE_CHAT,
      resources=(r"embed\.tawk\.to",),
      inline=(r"embed\.tawk\.to", r"\bTawk_API\b")),
    S("tidio", "Tidio", LIVE_CHAT,
      resources=(r"code\.tidio\.co", r"widget-v\d+\.tidiochat\.com"),
      inline=(r"code\.tidio\.co", r"\btidioChatApi\b")),
    S("jivo", "JivoChat", LIVE_CHAT,
      resources=(r"code\.jivosite\.com", r"code\.jivo\.ru", r"cdn\.jivosite\.com", r"//jivo\.chat"),
      inline=(r"code\.jivosite\.com", r"\bjivo_api\b", r"\bjivo_config\b")),
    S("crisp", "Crisp", LIVE_CHAT,
      resources=(r"client\.crisp\.chat",),
      inline=(r"client\.crisp\.chat", r"\bCRISP_WEBSITE_ID\b", r"\$crisp\s*=")),
    S("intercom", "Intercom", LIVE_CHAT,
      resources=(r"widget\.intercom\.io", r"js\.intercomcdn\.com"),
      inline=(r"widget\.intercom\.io", r"\bintercomSettings\b", r"Intercom\(\s*['\"]boot")),
    S("zendesk", "Zendesk Web Widget", LIVE_CHAT,
      resources=(r"static\.zdassets\.com/ekr/", r"v2\.zopim\.com", r"assets\.zendesk\.com/embeddable_framework"),
      inline=(r"static\.zdassets\.com/ekr", r"\$zopim", r"v2\.zopim\.com")),
    S("livechat", "LiveChat", LIVE_CHAT,
      resources=(r"cdn\.livechatinc\.com/(?!partners/)",),
      inline=(r"cdn\.livechatinc\.com/(?!partners/)", r"\b__lc\.license\b")),
    S("hubspot_chat", "HubSpot Conversations", LIVE_CHAT,
      resources=(r"js\.usemessages\.com",),
      inline=(r"js\.usemessages\.com", r"\bHubSpotConversations\b")),
    S("drift", "Drift", LIVE_CHAT,
      resources=(r"js\.driftt\.com", r"js\.drift\.com"),
      inline=(r"js\.driftt\.com", r"\bdrift\.load\(")),
    S("freshchat", "Freshchat", LIVE_CHAT,
      resources=(r"wchat\.freshchat\.com", r"snippets\.freshchat\.com", r"freshchat\.com/js/widget"),
      inline=(r"wchat\.freshchat\.com", r"\bfcWidget\.init\b")),
    S("smartsupp", "Smartsupp", LIVE_CHAT,
      resources=(r"smartsuppchat\.com",),
      inline=(r"smartsuppchat\.com", r"\b_smartsupp\s*=")),
    S("zoho_salesiq", "Zoho SalesIQ", LIVE_CHAT,
      resources=(r"salesiq\.zoho[a-z.]*/", r"salesiq\.zohopublic\.[a-z.]+"),
      inline=(r"salesiq\.zoho", r"\$zoho\.salesiq", r"\bzsiqchat\b")),
    S("olark", "Olark", LIVE_CHAT,
      resources=(r"static\.olark\.com",),
      inline=(r"static\.olark\.com", r"\bolark\.identify\b")),
    S("chatra", "Chatra", LIVE_CHAT,
      resources=(r"call\.chatra\.io",),
      inline=(r"call\.chatra\.io", r"\bChatraID\b")),
    S("liveagent", "LiveAgent", LIVE_CHAT,
      resources=(r"\.ladesk\.com/scripts/track\.js", r"liveagent\.com/scripts/track\.js"),
      inline=(r"\bLiveAgent\.createButton\b",)),
    S("userlike", "Userlike", LIVE_CHAT,
      resources=(r"userlike-cdn-widgets", r"userlike\.com/"),
      inline=(r"userlike-cdn-widgets",)),
    S("gorgias", "Gorgias Chat", LIVE_CHAT,
      resources=(r"gorgias\.chat",),
      inline=(r"gorgias\.chat",)),
    S("reamaze", "Re:amaze", LIVE_CHAT,
      resources=(r"cdn\.reamaze\.com", r"reamaze\.com/assets/reamaze"),
      inline=(r"\$\.reamaze\b",)),
    S("helpscout", "Help Scout Beacon", LIVE_CHAT,
      resources=(r"beacon-v2\.helpscout\.net", r"beacon\.helpscout\.net"),
      inline=(r"beacon-v2\.helpscout\.net", r"\bBeacon\(\s*['\"]init['\"]")),
    S("front_chat", "Front Chat", LIVE_CHAT,
      resources=(r"chat-assets\.frontapp\.com",),
      inline=(r"chat-assets\.frontapp\.com", r"\bFrontChat\(")),
    S("chatwoot", "Chatwoot", LIVE_CHAT,
      resources=(r"chatwoot",),
      inline=(r"\bchatwootSDK\b", r"\bchatwootSettings\b")),
    S("bitrix24", "Bitrix24 site button", LIVE_CHAT,
      resources=(r"/crm/site_button/", r"bitrix24\.[a-z.]+/b\d+/crm/site_button"),
      inline=(r"/crm/site_button/",)),
    S("livesupporti", "Livesupporti", LIVE_CHAT,
      resources=(r"livesupporti",)),
    # Meta's page chat plugin (deprecated, but still on many older sites).
    S("fb_customerchat", "Facebook Customer Chat plugin", MESSENGER,
      resources=(r"xfbml\.customerchat",),
      inline=(r"xfbml\.customerchat",),
      classes=(r"^fb-customerchat$",)),
    # Floating-button services that can expose several channels at once. They
    # are reported as a widget of their own: the HTML does not say which apps
    # (WhatsApp, Telegram, a form ...) the owner switched on.
    S("getbutton", "GetButton", MULTICHANNEL_WIDGET,
      resources=(r"getbutton\.io",)),
    S("chaty", "Chaty", MULTICHANNEL_WIDGET,
      resources=(r"/wp-content/plugins/chaty(?:-pro)?/",),
      classes=(r"^chaty-widget$", r"^chaty-main$")),
    # WordPress WhatsApp plugins. Their button is often injected by script, so
    # the plugin's own files and CSS classes are the reliable fingerprint.
    S("joinchat", "Joinchat (WordPress)", WHATSAPP,
      resources=(r"/wp-content/plugins/creame-whatsapp-me/", r"/joinchat(?:\.min)?\.(?:js|css)"),
      inline=(r"\bjoinchat_obj\b",),
      classes=(r"^joinchat(?:__.*)?$",),
      source="plugin"),
    S("click_to_chat", "Click to Chat (WordPress)", WHATSAPP,
      resources=(r"/wp-content/plugins/click-to-chat-for-whatsapp/",),
      inline=(r"\bht_ctc_chat_(?:var|data)\b",),
      classes=(r"^ht[-_]ctc(?:[-_].*)?$",),
      source="plugin"),
    S("qlwapp", "WhatsApp Chat QuadLayers (WordPress)", WHATSAPP,
      resources=(r"/wp-content/plugins/wp-whatsapp-chat/", r"/qlwapp[-.]"),
      inline=(r"\bqlwapp\b",),
      classes=(r"^qlwapp(?:[-_].*)?$",),
      source="plugin"),
    S("wp_whatsapp", "WP Chat App (WordPress)", WHATSAPP,
      resources=(r"/wp-content/plugins/wp-whatsapp(?:-pro)?/",),
      classes=(r"^wa__(?:btn_popup|popup|stt)",),
      source="plugin"),
    S("whatshelp", "WhatsHelp", WHATSAPP,
      resources=(r"whatshelp\.io",),
      source="plugin"),
)

# Any other WordPress plugin whose folder name says "whatsapp".
GENERIC_WP_WHATSAPP = re.compile(
    r"/wp-content/plugins/([a-z0-9_-]*whatsapp[a-z0-9_-]*)/", re.I
)

# Hosts of domain parking and default-page services.
PARKING_HOSTS = (
    "sedoparking.com",
    "sedo.com",
    "parkingcrew.net",
    "bodis.com",
    "afternic.com",
    "dan.com",
    "hugedomains.com",
    "above.com",
    "domainsponsor.com",
    "parklogic.com",
    "namebright.com",
    "uniregistry.com",
)

# Phrases that mark a parked, default or placeholder page. They are only used
# together with a "page is small" check (see detect.py).
PARKED_PHRASES = tuple(
    re.compile(p, re.I)
    for p in (
        r"domain (?:name )?(?:is |may be )?for sale",
        r"this domain (?:is|may be) (?:for sale|parked|available)",
        r"buy this domain",
        r"domain parking",
        r"parked (?:free|domain|by)",
        r"bu alan ad[ıi] sat[ıi]l[ıi]k",
        r"alan ad[ıi] sat[ıi]l[ıi]kt[ıi]r",
        r"sat[ıi]l[ıi]k (?:alan ad[ıi]|domain)",
        r"welcome to nginx",
        r"apache2? (?:ubuntu |debian )?default page",
        r"^index of /",
        r"\bit works!",
        r"default web site page",
        r"internet information services",
        r"plesk default|default parallels plesk",
        r"web server is working",
        r"yap[ıi]m a[şs]amas[ıi]nda",
        r"under construction",
        r"coming soon",
        r"[çc]ok yak[ıi]nda",
        r"site (?:burada|yak[ıi]nda) yay[ıi]nda",
    )
)
