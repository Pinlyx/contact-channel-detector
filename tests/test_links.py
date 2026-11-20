import pytest

from contactchannels.emails import clean_email, decode_cfemail
from contactchannels.links import classify_href, classify_url


def one(url):
    hits = classify_href(url, "https://site.example/")
    return [(h.channel, h.value) for h in hits]


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://wa.me/905551112233", [("whatsapp", "905551112233")]),
        ("https://wa.me/+90 555 111 22 33", [("whatsapp", "905551112233")]),
        ("https://wa.me/message/ABCDEF123", [("whatsapp", "message/ABCDEF123")]),
        ("https://api.whatsapp.com/send?phone=905551112233&text=hi", [("whatsapp", "905551112233")]),
        ("https://api.whatsapp.com/send/?phone=%2B905551112233", [("whatsapp", "905551112233")]),
        ("https://web.whatsapp.com/send?phone=905551112233", [("whatsapp", "905551112233")]),
        ("whatsapp://send?phone=905551112233", [("whatsapp", "905551112233")]),
        ("https://wa.link/abc123", [("whatsapp", "abc123")]),
        ("https://chat.whatsapp.com/AbCdEf", [("whatsapp", "group/AbCdEf")]),
        # share buttons
        ("https://wa.me/?text=hello", []),
        ("https://wa.me/", []),
        ("https://api.whatsapp.com/send?text=hello", []),
        ("whatsapp://send?text=hello", []),
        ("https://wa.me/{phone}", []),
        ("https://faq.whatsapp.com/123", []),
    ],
)
def test_whatsapp(url, expected):
    assert one(url) == expected


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://t.me/OrnekKanal", [("telegram", "ornekkanal")]),
        ("https://telegram.me/ornek_bot", [("telegram", "ornek_bot")]),
        ("https://t.me/s/ornekkanal", [("telegram", "ornekkanal")]),
        ("https://t.me/+AbCdEfGhIjK", [("telegram", "invite/AbCdEfGhIjK")]),
        ("https://t.me/joinchat/AbCdEfGhIjK", [("telegram", "invite/AbCdEfGhIjK")]),
        ("tg://resolve?domain=ornekkanal", [("telegram", "ornekkanal")]),
        ("https://t.me/share/url?url=x", []),
        ("https://t.me/ornekkanal/123", []),
        ("https://t.me/c/123/456", []),
        ("https://t.me/addstickers/pack", []),
        ("https://t.me/", []),
        ("https://t.me/ab", []),
    ],
)
def test_telegram(url, expected):
    assert one(url) == expected


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://m.me/ornekfirma", [("messenger", "ornekfirma")]),
        ("https://m.me/ornekfirma?ref=web", [("messenger", "ornekfirma")]),
        ("https://www.messenger.com/t/ornekfirma", [("messenger", "ornekfirma")]),
        ("https://www.facebook.com/messages/t/ornekfirma", [("messenger", "ornekfirma")]),
        ("viber://chat?number=%2B905551112233", [("viber", "905551112233")]),
        ("viber://add?number=905551112233", [("viber", "905551112233")]),
        ("viber://forward?text=hi", []),
    ],
)
def test_messenger_and_viber(url, expected):
    assert one(url) == expected


@pytest.mark.parametrize(
    "url,expected",
    [
        ("https://www.instagram.com/Ornek.Firma/", [("instagram", "ornek.firma")]),
        ("https://instagram.com/ornek_firma?igshid=abc", [("instagram", "ornek_firma")]),
        ("https://www.instagram.com/_u/ornekfirma", [("instagram", "ornekfirma")]),
        ("https://www.instagram.com/p/ABC/", []),
        ("https://www.instagram.com/reel/ABC/", []),
        ("https://www.instagram.com/explore/tags/x/", []),
        ("https://www.instagram.com/embed.js", []),
        ("https://www.instagram.com/instagram", []),
        ("https://www.instagram.com/", []),
        ("https://www.instagram.com/accounts/login/", []),
        ("https://www.instagram.com/foo?utm_source=ig_embed", []),
        ("https://www.facebook.com/OrnekFirma", [("facebook", "ornekfirma")]),
        ("https://tr-tr.facebook.com/OrnekFirma/", [("facebook", "ornekfirma")]),
        ("https://fb.com/ornekfirma", [("facebook", "ornekfirma")]),
        ("https://www.facebook.com/profile.php?id=100012345", [("facebook", "id/100012345")]),
        ("https://www.facebook.com/pages/Ornek-Firma/123456789", [("facebook", "id/123456789")]),
        ("https://www.facebook.com/p/Ornek-Firma-100012345678901/", [("facebook", "id/100012345678901")]),
        ("https://www.facebook.com/pg/ornekfirma/about", [("facebook", "ornekfirma")]),
        ("https://www.facebook.com/sharer/sharer.php?u=x", []),
        ("https://www.facebook.com/sharer.php?u=x", []),
        ("https://www.facebook.com/tr?id=1&ev=PageView", []),
        ("https://www.facebook.com/2008/fbml", []),
        ("https://www.facebook.com/plugins/page.php?href=x", []),
        ("https://www.facebook.com/dialog/share?x=1", []),
        ("https://www.facebook.com/groups/123", []),
        ("https://www.facebook.com/ornekfirma/posts/123", []),
        ("https://www.facebook.com/v18.0/plugins/page.php", []),
        ("https://www.facebook.com/facebook", []),
        ("https://l.facebook.com/l.php?u=x", []),
        ("https://developers.facebook.com/docs", []),
        ("https://twitter.com/OrnekFirma", [("x", "ornekfirma")]),
        ("https://x.com/ornekfirma/", [("x", "ornekfirma")]),
        ("https://mobile.twitter.com/ornekfirma", [("x", "ornekfirma")]),
        ("https://twitter.com/intent/tweet?text=x", []),
        ("https://twitter.com/share?url=x", []),
        ("https://twitter.com/ornekfirma/status/1", []),
        ("https://twitter.com/home", []),
        ("https://platform.twitter.com/widgets.js", []),
        ("https://x.com/x", []),
        ("https://www.tiktok.com/@ornek.firma", [("tiktok", "ornek.firma")]),
        ("https://www.tiktok.com/@ornekfirma/video/123", []),
        ("https://www.tiktok.com/embed.js", []),
        ("https://www.tiktok.com/", []),
        ("https://www.youtube.com/@OrnekFirma", [("youtube", "@ornekfirma")]),
        ("https://www.youtube.com/@OrnekFirma/videos", [("youtube", "@ornekfirma")]),
        ("https://www.youtube.com/channel/UCBgCqEfwt_454jVG7qpi_KQ", [("youtube", "channel/UCBgCqEfwt_454jVG7qpi_KQ")]),
        ("https://www.youtube.com/c/OrnekFirma", [("youtube", "c/ornekfirma")]),
        ("https://www.youtube.com/user/OrnekFirma", [("youtube", "user/ornekfirma")]),
        ("https://www.youtube.com/watch?v=abc", []),
        ("https://youtu.be/abc", []),
        ("https://www.youtube.com/embed/abc", []),
        ("https://www.youtube.com/playlist?list=PL1", []),
        ("https://www.linkedin.com/company/ornek-firma/", [("linkedin", "company/ornek-firma")]),
        ("https://tr.linkedin.com/in/ahmet-yilmaz", [("linkedin", "in/ahmet-yilmaz")]),
        ("https://www.linkedin.com/company/ornek-firma/admin/", []),
        ("https://www.linkedin.com/company/linkedin", []),
        ("https://www.linkedin.com/shareArticle?url=x", []),
        ("https://www.linkedin.com/sharing/share-offsite/?url=x", []),
        ("https://www.pinterest.com/ornekfirma/", [("pinterest", "ornekfirma")]),
        ("https://tr.pinterest.com/ornekfirma", [("pinterest", "ornekfirma")]),
        ("https://www.pinterest.com.tr/ornekfirma/", [("pinterest", "ornekfirma")]),
        ("https://pinterest.com/pin/create/button/?url=x", []),
        ("https://www.pinterest.com/pin/123/", []),
        ("https://www.threads.net/@ornekfirma", [("threads", "ornekfirma")]),
        ("https://www.threads.com/@ornekfirma", [("threads", "ornekfirma")]),
        ("https://www.threads.net/@ornekfirma/post/abc", []),
        ("https://bsky.app/profile/ornek.bsky.social", [("bluesky", "ornek.bsky.social")]),
        ("https://bsky.app/profile/ornek.bsky.social/post/abc", []),
        ("https://example.com/instagram.com/foo", []),
        ("https://notinstagram.com/foo", []),
        ("https://fakex.com/foo", []),
    ],
)
def test_social_profiles(url, expected):
    assert one(url) == expected


def test_scheme_less_profile_link_is_understood():
    assert one("instagram.com/ornekfirma") == [("instagram", "ornekfirma")]
    assert one("www.facebook.com/ornekfirma") == [("facebook", "ornekfirma")]
    assert one("//www.instagram.com/ornekfirma/") == [("instagram", "ornekfirma")]


def test_mailto_and_tel():
    assert one("mailto:Info@Ornek.example?subject=Hi") == [("email", "info@ornek.example")]
    assert one("mailto:a@ornek.example,b@ornek.example") == [("email", "a@ornek.example"), ("email", "b@ornek.example")]
    assert one("mailto:?subject=Share") == []
    assert one("mailto:not-an-address") == []
    assert one("tel:+90 (212) 555-00-11") == [("phone", "+902125550011")]
    assert one("tel:02125550011") == [("phone", "02125550011")]
    assert one("tel:") == []
    assert one("tel:123") == []


def test_ignored_schemes_and_fragments():
    for href in ("#", "#top", "javascript:void(0)", "data:text/html,x", "sms:?body=x", "", "   "):
        assert classify_href(href, "https://site.example/") == []


def test_classify_url_survives_garbage():
    assert classify_url("http://[::1") == []
    assert classify_url("not a url") == []


def test_cloudflare_decode():
    assert decode_cfemail("4b22252d240b2439252e20662d2239262a65282426653f39") == "info@ornek-firma.com.tr"
    # key byte only, or bad hex
    assert decode_cfemail("4b") is None
    assert decode_cfemail("zz11") is None
    assert decode_cfemail("") is None


def test_clean_email():
    assert clean_email("MAILTO:Foo@Bar.COM?x=1") == "foo@bar.com"
    assert clean_email("foo@bar") is None
    assert clean_email("image@2x.png") is None
