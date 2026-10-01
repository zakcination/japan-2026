"""Link previews: our trip shares its own page (own title and picture) that forwards into the app, invite and #link kept."""
import re
from html.parser import HTMLParser
from conftest import ROOT, until


def og(path):
    tags = {}
    class P(HTMLParser):
        def handle_starttag(self, tag, a):
            a = dict(a)
            if tag == "meta" and (a.get("property", "") .startswith("og:") or a.get("name", "").startswith("twitter:")):
                tags[a.get("property") or a.get("name")] = a.get("content")
    P().feed(path.read_text(encoding="utf-8"))
    return tags


def test_our_share_page_has_its_own_preview():
    t = og(ROOT / "t" / "miras-aikosh.html")
    assert t["og:title"] == "Мирас и Айкош · Япония 2026" and "выберите себя" in t["og:description"]
    assert t["og:image"] == "https://zakcination.github.io/japan-2026/og-miras-aikosh.jpg" and (ROOT / "og-miras-aikosh.jpg").stat().st_size < 300_000
    assert t["og:url"].endswith("/t/miras-aikosh.html") and t["twitter:card"] == "summary_large_image"
    i = og(ROOT / "src" / "Japan_Guide_2026.html")
    assert i["og:image"].endswith("/og-v2.jpg") and (ROOT / "og-v2.jpg").exists() and i["og:url"] == "https://zakcination.github.io/japan-2026/"


def test_share_page_forwards_into_the_app_keeping_the_invite_and_the_link(app, site):
    a = app(url=site, url_suffix="/../t/miras-aikosh.html?who=00000000-0000-0000-0000-000000000001&code=abc123#tab=tix", now=None)
    until(a.page, "location.search.includes('trip=miras-aikosh')")
    assert "who=00000000-0000-0000-0000-000000000001" in a.page.url and "code=abc123" in a.page.url


def test_the_app_shares_the_preview_page(app, site):
    a = app(url=site, url_suffix="?trip=miras-aikosh")
    until(a.page, "document.title.includes('Мирас')")
    a.page.click("#tcGear")
    assert re.search(r"/t/miras-aikosh\.html$", a.page.inner_text("#setShare small"))
