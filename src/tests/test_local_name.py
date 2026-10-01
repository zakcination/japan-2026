"""«Показать по-японски» (R11): the place full screen in Japanese (Chinese in Shanghai), copy, walking route."""
import json
from conftest import ROOT, IPHONE_UA
from urllib.parse import unquote

OURS = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))


def stop(app, day, eid, **kw):
    a = app(trip=OURS, state={"prevDay": day, "prevTime": "06:00"}, **kw)
    a.page.click(".tc-tab[data-tab='day']")
    a.page.locator(f".tc-item[data-id='{eid}'] .tc-open").click()
    return a


def test_show_in_japanese_big_and_copyable(app):
    a = stop(app, 3, "d3e3")                                              # Тэнрю-дзи
    s = a.page.locator("#tcSheet")
    assert "Показать по-японски" in s.inner_text() and "Пешком" in s.inner_text()
    s.locator("[data-local]").click()
    card = a.page.locator("#tcLocal")
    assert card.is_visible() and a.page.locator("#tcSheet").is_hidden()
    assert a.page.inner_text(".tc-local-name") == "天龍寺" and "ここまでお願いします" in card.inner_text()
    assert "Тэнрю-дзи" in card.inner_text()
    assert a.page.evaluate("parseFloat(getComputedStyle(document.querySelector('.tc-local-name')).fontSize)") >= 40
    assert card.bounding_box()["width"] == a.page.viewport_size["width"]          # full screen
    for b in card.locator("button").all():
        assert b.bounding_box()["height"] >= 44
    a.page.locator(".tc-local-name").click()                                  # a tap anywhere closes it
    assert card.is_hidden()
    assert a.errors == []


def test_shanghai_shows_chinese(app):
    a = stop(app, 1, "d1e4")
    a.page.locator("#tcSheet [data-local]").click()
    assert "Показать по-китайски" not in a.page.inner_text("#tcLocal")
    assert a.page.inner_text(".tc-local-name") == "豫园" and "请带我去这里" in a.page.inner_text("#tcLocal")
    a.page.keyboard.press("Escape")
    assert a.page.locator("#tcLocal").is_hidden()


def test_walking_route_and_no_local_name_for_hotels(app):
    a = stop(app, 3, "d3e3", ua=IPHONE_UA)
    href = a.page.locator("#tcSheet a.tc-act", has_text="Пешком").get_attribute("href")
    assert href.startswith("https://maps.apple.com/?daddr=") and href.endswith("dirflg=w")
    hotels = [e for d in OURS["days"] for e in d["ev"] if e["cat"] == "hotel"]
    assert hotels and not any(e.get("loc") for e in hotels)                  # a hotel's address lives in the booking


def test_imported_trip_cannot_inject_through_the_local_name(app):
    bad = json.loads(json.dumps(OURS))
    bad["days"][2]["ev"][3]["loc"] = '<img src=x onerror="window.__pwned=1">'
    b = app(trip=bad, state={"prevDay": 3, "prevTime": "06:00"})
    b.page.click(".tc-tab[data-tab='day']")
    b.page.locator(".tc-item[data-id='d3e3'] .tc-open").click()
    b.page.locator("#tcSheet [data-local]").click()
    assert "<img" in b.page.inner_text(".tc-local-name") and not b.page.evaluate("window.__pwned")
