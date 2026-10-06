"""The tab bar and header on real iPhone sizes, with the safe areas those phones report in Home Screen mode."""
import pytest

# (name, viewport, top inset, bottom inset) — points, as Safari reports them
PHONES = [
    ("iPhone 16/17 Pro Max", {"width": 440, "height": 956}, 62, 34),
    ("iPhone 13", {"width": 390, "height": 844}, 47, 34),
    ("iPhone 13 in Safari", {"width": 390, "height": 664}, 0, 0),     # toolbars take the rest, insets are 0
]


def insets(page, top, bottom):
    page.add_style_tag(content=f":root {{ --safe-t: {top}px !important; --safe-b: {bottom}px !important; }}")
    page.evaluate("window.dispatchEvent(new Event('japan2026:tick'))")


@pytest.mark.parametrize("name,size,top,bottom", PHONES, ids=[p[0] for p in PHONES])
def test_tab_bar_clears_the_home_indicator_and_fits(app, name, size, top, bottom):
    a = app(state={"prevDay": 2, "prevTime": "13:24"}, size=size)
    insets(a.page, top, bottom)
    H, W = size["height"], size["width"]
    bar = a.page.locator("#tcTabs").bounding_box()
    assert abs(bar["y"] + bar["height"] - H) < 1 and bar["width"] == W
    tabs = a.page.locator(".tc-tab").all()
    assert len(tabs) == 4                                                    # + the ＋ in the middle
    plus = a.page.locator("#tcAdd").bounding_box()
    assert plus["width"] >= 56 and plus["height"] >= 44 and plus["y"] + plus["height"] <= H - max(8, bottom) + 0.5
    for t in tabs:
        b = t.bounding_box()
        assert b["height"] >= 49 and b["width"] >= 64
        assert b["y"] + b["height"] <= H - max(8, bottom) + 0.5          # nothing under the home indicator
        label = t.locator("span").bounding_box()
        assert label["y"] + label["height"] <= H - max(8, bottom)
    # the capsule sits under the Dynamic Island / notch, not behind it
    cap = a.page.locator("#tcCap").bounding_box()
    assert cap["y"] >= top
    # the last content is not hidden under the tab bar
    a.page.evaluate("document.getElementById('today').scrollTo(0, 1e6)")
    last = a.page.locator("#todayBody .tc-page > *").last.bounding_box()
    assert last["y"] + last["height"] <= a.page.locator("#tcTabs").bounding_box()["y"] + 0.5
    assert a.errors == []
