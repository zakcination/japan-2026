def test_today_screen_renders_before_refactor(app):
    a = app(state={"prevDay": 2, "prevTime": "13:24"})
    assert a.page.locator("#today").is_visible()
    assert "Фудзи" in a.page.inner_text("#today")
    assert a.errors == []


def test_assets_exist_and_are_linked():
    """Icons, splash screens and the share preview are in the site root and linked from the page."""
    import re
    from PIL import Image
    from conftest import ROOT, SRC
    html = (SRC / "Japan_Guide_2026.html").read_text(encoding="utf-8")
    for f, size in [("apple-touch-icon.png", (180, 180)), ("icon-192.png", (192, 192)), ("icon-512.png", (512, 512)),
                    ("favicon-32x32.png", (32, 32)), ("og.png", (1200, 630))]:
        assert Image.open(ROOT / f).size == size, f
    assert (ROOT / "favicon.ico").exists()
    splashes = re.findall(r'apple-touch-startup-image" href="(splash/[^"]+)"', html)
    assert len(splashes) >= 8
    for s in splashes:
        w, h = map(int, re.search(r"(\d+)x(\d+)", s).groups())
        assert Image.open(ROOT / s).size == (w, h)
    assert 'og:image" content="https://zakcination.github.io/japan-2026/og.png"' in html
