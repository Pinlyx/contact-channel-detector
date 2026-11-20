from pathlib import Path

import pytest

from contactchannels import detect_html

FIXTURES = Path(__file__).parent / "fixtures"


def load(name, base="https://www.ornek.example/"):
    return detect_html((FIXTURES / name).read_text(encoding="utf-8"), base)


def pairs(result, channel):
    return [(f.provider, f.value) for f in result.by_channel(channel)]


# --------------------------------------------------------------------------
# Real pages, trimmed to the relevant markup
# --------------------------------------------------------------------------

def test_real_turkish_ecommerce_whatsapp_phone_email_and_socials():
    r = load("real_koton.html")
    assert pairs(r, "whatsapp") == [("api.whatsapp.com", "908502087171")]
    assert r.values("phone") == ["08502087171"]
    assert r.values("email") == ["mim@koton.com"]
    assert r.social == {
        "facebook": "koton",
        "instagram": "koton",
        "x": "koton",
        "linkedin": "company/kotonretail",
        "youtube": "user/kotonmagazalari",
        "tiktok": "kotoncom",
    }
    assert r.instant_channel


def test_real_site_two_whatsapp_links_one_number():
    r = load("real_bellona.html")
    # wa.me/<n>?text=... and wa.me/<n> are the same contact point, two links
    assert r.values("whatsapp") == ["908502223399"]
    assert r.social["instagram"] == "bellonamobilya"


@pytest.mark.parametrize(
    "fixture,provider",
    [
        ("real_livechat.html", "LiveChat"),
        ("real_olark.html", "Olark"),
        ("real_userlike.html", "Userlike"),
    ],
)
def test_real_vendor_pages_detect_their_widget(fixture, provider):
    r = load(fixture)
    assert r.providers("live_chat") == [provider]


def test_real_wordpress_joinchat_site():
    r = load("real_joinchat.html")
    assert r.providers("whatsapp") == ["Joinchat (WordPress)"]
    assert r.by_channel("whatsapp")[0].source == "plugin"


def test_real_page_without_widget_reports_no_instant_channel():
    r = load("real_crisp.html")  # only the footer links were kept
    assert not r.instant_channel
    assert "live_chat" not in r.channels


# --------------------------------------------------------------------------
# Hand-written fixtures
# --------------------------------------------------------------------------

def test_small_business_all_channels_normalised():
    r = load("small_business_tr.html")
    assert r.values("whatsapp") == ["905321234567"]
    assert r.values("phone") == ["+902165550011"]
    assert r.values("email") == ["merhaba@ornek-berber.example"]
    assert r.values("telegram") == ["ornekberberkanal"]
    assert r.values("messenger") == ["ornekberber"]
    assert r.values("viber") == ["905321234567"]
    assert r.values("instagram") == ["ornekberber.kadikoy"]
    assert r.values("facebook") == ["ornekberberkadikoy", "ornekberber2", "id/100012345678901"]
    assert r.values("tiktok") == ["ornekberber"]
    assert r.values("youtube") == ["@ornekberber"]
    assert r.values("linkedin") == ["company/ornek-berber"]
    assert r.values("x") == ["ornekberber"]
    assert r.values("pinterest") == ["ornekberber"]
    assert r.values("threads") == ["ornekberber"]
    assert r.values("bluesky") == ["ornekberber.bsky.social"]
    assert r.instant_channel
    assert not r.parked


def test_evidence_is_the_matching_link():
    r = load("small_business_tr.html")
    wa = r.by_channel("whatsapp")[0]
    assert wa.evidence.startswith("https://api.whatsapp.com/send/?phone=%2B905321234567")
    assert wa.source == "link"


def test_wordpress_whatsapp_plugins_by_files_and_classes():
    r = load("wordpress_whatsapp_plugins.html")
    providers = r.providers("whatsapp")
    assert "Joinchat (WordPress)" in providers
    assert "Click to Chat (WordPress)" in providers
    assert "WhatsApp Chat QuadLayers (WordPress)" in providers
    assert "WordPress plugin: whatsapp-for-wordpress-extra" in providers
    assert all(f.source == "plugin" for f in r.by_channel("whatsapp"))


def test_jsonld_same_as_profiles_are_read_and_share_links_ignored():
    r = load("jsonld_org.html")
    assert r.social == {"instagram": "ornekhukuk", "linkedin": "company/ornek-hukuk", "x": "ornekhukuk"}
    assert all(f.source == "jsonld" for f in r.findings)
    # the JSON data block mentions wa.me and embed.tawk.to but is not code
    assert not r.has("whatsapp") and not r.has("live_chat")


def test_cloudflare_obfuscated_emails_are_decoded():
    r = load("cloudflare_email.html")
    assert r.values("email") == ["satis@ornek-firma.com.tr", "info@ornek-firma.com.tr"]
    assert {f.source for f in r.by_channel("email")} == {"link", "cfemail"}


# --------------------------------------------------------------------------
# False positives: every one of these was counted by a naive pattern
# --------------------------------------------------------------------------

def test_share_buttons_embed_scripts_xmlns_and_posts_find_nothing():
    r = load("false_positives.html")
    assert r.findings == [], [(f.channel, f.value, f.evidence) for f in r.findings]
    assert not r.instant_channel


def test_instagram_embed_script_is_not_a_profile():
    html = '<script async src="//www.instagram.com/embed.js"></script><a href="https://www.instagram.com/embed.js">x</a>'
    assert detect_html(html).findings == []


def test_xmlns_namespace_urls_are_not_facebook_links():
    html = '<html xmlns:fb="http://www.facebook.com/2008/fbml" xmlns:og="http://ogp.me/ns#"><body></body></html>'
    assert detect_html(html).findings == []


def test_embedded_third_party_instagram_post_is_not_the_site_profile():
    html = (
        '<blockquote><a href="https://www.instagram.com/baskasi?utm_source=ig_embed&amp;utm_campaign=loading">x</a>'
        "</blockquote>"
    )
    assert detect_html(html).findings == []


def test_html_comments_and_prose_do_not_count():
    html = (
        '<!-- <a href="https://wa.me/905551112233">x</a> --><p>wa.me/905551112233 and embed.tawk.to</p>'
    )
    assert detect_html(html).findings == []


def test_partner_tracking_script_is_not_a_live_chat_widget():
    html = '<script src="https://cdn.livechatinc.com/partners/tracking/track.js"></script>'
    assert not detect_html(html).has("live_chat")


def test_widget_names_inside_a_huge_inline_bundle_do_not_count():
    html = "<script>var bundle='embed.tawk.to';" + ("x" * 120_000) + "</script>"
    assert not detect_html(html).has("live_chat")


def test_inline_json_script_types_are_ignored():
    html = '<script type="application/json">{"loader":"embed.tawk.to"}</script>'
    assert not detect_html(html).has("live_chat")


# --------------------------------------------------------------------------
# Parked pages
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fixture,fragment",
    [
        ("parked_sedo.html", "sedoparking.com"),
        ("parked_tr.html", "sat"),
        ("default_nginx.html", "nginx"),
    ],
)
def test_parked_and_default_pages_are_flagged(fixture, fragment):
    r = load(fixture)
    assert r.parked
    assert fragment in r.parked_reason.lower()


def test_real_site_that_mentions_coming_soon_is_not_parked():
    r = load("coming_soon_badge_real_site.html")
    assert not r.parked
    assert r.values("whatsapp") == ["905551234567"]


# --------------------------------------------------------------------------
# Widgets: one minimal snippet per provider
# --------------------------------------------------------------------------

WIDGET_SNIPPETS = [
    ("Tawk.to", "<script>var s1=document.createElement('script');s1.src='https://embed.tawk.to/5f0/default';</script>"),
    ("Tidio", '<script src="//code.tidio.co/abcdefghijklmnop.js" async></script>'),
    ("JivoChat", '<script src="//code.jivosite.com/widget/AbCdEf" async></script>'),
    ("Crisp", "<script>window.$crisp=[];window.CRISP_WEBSITE_ID='00000000-0000-0000-0000-000000000000';(function(){var d=document;var s=d.createElement('script');s.src='https://client.crisp.chat/l.js';})();</script>"),
    ("Intercom", '<script>window.intercomSettings={app_id:"abc123"};(function(){var w=window;})();</script>'),
    ("Intercom", '<script src="https://widget.intercom.io/widget/abc123"></script>'),
    ("Zendesk Web Widget", '<script id="ze-snippet" src="https://static.zdassets.com/ekr/snippet.js?key=00000000-0000-0000-0000-000000000000"></script>'),
    ("LiveChat", "<script>window.__lc=window.__lc||{};window.__lc.license=1234567;</script>"),
    ("HubSpot Conversations", '<script type="text/javascript" id="hs-script-loader" async defer src="//js.usemessages.com/conversations-embed.js"></script>'),
    ("Drift", "<script>drift.load('abcd1234');</script>"),
    ("Freshchat", '<script src="https://wchat.freshchat.com/js/widget.js"></script>'),
    ("Smartsupp", "<script>var _smartsupp=_smartsupp||{};_smartsupp.key='abc';var c=document.createElement('script');c.src='https://www.smartsuppchat.com/loader.js?';</script>"),
    ("Zoho SalesIQ", '<script>window.$zoho=window.$zoho||{};$zoho.salesiq=$zoho.salesiq||{widgetcode:"abc"};</script><script src="https://salesiq.zoho.com/widget" defer></script>'),
    ("Olark", "<script>window.olark.identify('0000-000-00-0000');</script>"),
    ("Chatra", '<script>(function(d,w,c){w.ChatraID="abc";var s=d.createElement("script");s.src="https://call.chatra.io/chatra.js";})(document,window,"Chatra");</script>'),
    ("LiveAgent", '<script type="text/javascript">(function(d,src,c){var t=d.scripts[d.scripts.length-1];})(document,"https://ornek.ladesk.com/scripts/track.js");LiveAgent.createButton("abc",this);</script>'),
    ("Userlike", '<script src="https://userlike-cdn-widgets.s3-eu-west-1.amazonaws.com/0123.js"></script>'),
    ("Gorgias Chat", '<script id="gorgias-chat-widget-install-v3" src="https://config.gorgias.chat/bundle-loader/01ABCDEF"></script>'),
    ("Re:amaze", '<script src="https://cdn.reamaze.com/assets/reamaze.js"></script>'),
    ("Help Scout Beacon", '<script>!function(e,t,n){}(window,document);window.Beacon("init","abc-123");</script>'),
    ("Help Scout Beacon", '<script src="https://beacon-v2.helpscout.net"></script>'),
    ("Front Chat", '<script src="https://chat-assets.frontapp.com/v1/chat.bundle.js"></script>'),
    ("Chatwoot", '<script>window.chatwootSettings={position:"right"};(function(d,t){var g=d.createElement(t);g.src="https://app.chatwoot.com/packs/js/sdk.js";})(document,"script");</script>'),
    ("Bitrix24 site button", '<script>(function(w,d,u){var s=d.createElement("script");s.src=u;})(window,document,"https://cdn.bitrix24.com.tr/b123/crm/site_button/loader_1_abc.js");</script>'),
    ("Livesupporti", '<script src="https://livesupporti.com/script/abc.js"></script>'),
]


@pytest.mark.parametrize("provider,snippet", WIDGET_SNIPPETS)
def test_live_chat_widget_signatures(provider, snippet):
    r = detect_html("<html><head></head><body>%s</body></html>" % snippet)
    assert provider in r.providers("live_chat"), r.findings
    assert r.instant_channel


def test_messenger_customer_chat_plugin_by_class_and_sdk():
    r = detect_html('<div class="fb-customerchat" page_id="123"></div>'
                    '<script src="https://connect.facebook.net/tr_TR/sdk/xfbml.customerchat.js"></script>')
    assert r.providers("messenger") == ["Facebook Customer Chat plugin"]


def test_multichannel_button_services_are_a_separate_channel():
    r = detect_html('<script src="//static.getbutton.io/widget/bundle.js"></script>')
    assert r.providers("multichannel_widget") == ["GetButton"]
    assert not r.has("whatsapp")
    assert r.instant_channel


def test_elfsight_is_not_treated_as_a_chat_widget():
    r = detect_html('<script src="https://elfsightcdn.com/platform.js" async></script><div class="elfsight-app-0000"></div>')
    assert r.findings == []


# --------------------------------------------------------------------------
# WhatsApp numbers inside inline scripts, relative links, result API
# --------------------------------------------------------------------------

def test_whatsapp_number_in_inline_script_counts_but_a_share_handler_does_not():
    html = (
        "<script>var u='https://wa.me/905321234567';</script>"
        "<script>window.open('https://wa.me/?text='+encodeURIComponent(location.href));</script>"
    )
    r = detect_html(html)
    assert r.values("whatsapp") == ["905321234567"]


def test_relative_links_resolve_against_base_url():
    r = detect_html('<a href="/cdn-cgi/l/email-protection#4b22252d240b2439252e20662d2239262a65282426653f39">x</a>',
                    "https://www.ornek.example/")
    assert r.values("email") == ["info@ornek-firma.com.tr"]


def test_duplicate_findings_are_collapsed():
    r = detect_html('<a href="https://wa.me/905551112233">a</a><a href="https://wa.me/905551112233?text=hi">b</a>')
    assert len(r.by_channel("whatsapp")) == 1


def test_result_to_dict_is_json_serialisable():
    import json

    r = load("small_business_tr.html")
    d = json.loads(json.dumps(r.to_dict()))
    assert d["instant_channel"] is True
    assert "whatsapp" in d["channels"]
    assert d["findings"][0].keys() == {"channel", "provider", "value", "evidence", "source"}


def test_empty_and_garbage_input_never_raises():
    assert detect_html("").findings == []
    assert detect_html("<<<>>><a href=").findings == []
    assert detect_html("<script>").findings == []
