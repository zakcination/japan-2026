"""⚙ «Моя поездка» and the editors, all as bottom sheets; the old screen is gone."""
import json


def open_(app, **kw):
    a = app(state={"prevDay": 2, "prevTime": "13:24", **kw.pop("state", {})}, **kw)
    return a


def settings(a):
    a.page.click("#tcGear")
    s = a.page.locator("#tcSheet")
    s.wait_for(state="visible")
    return s


def stored(page, key):
    return json.loads(page.evaluate(f"localStorage.getItem('{key}')") or "null")


def test_gear_opens_sheet_with_big_controls(app):
    a = open_(app)
    s = settings(a)
    assert "Моя поездка" in s.inner_text()
    for b in s.locator("button, input:not([type=radio]):not([type=file]), select, label.tc-seg3 span").all():
        if b.is_visible():
            assert b.bounding_box()["height"] >= 44, b.evaluate("e => e.outerHTML.slice(0, 80)")
    assert a.page.locator("#tdModal, #today .td-wrap, #today [class^='td-']").count() == 0
    assert a.errors == []


def test_gear_is_on_stats_tab_too(app):
    a = open_(app)
    a.page.click(".tc-tab[data-tab='stats']")
    assert "Моя поездка" in settings(a).inner_text()


def test_theme_choice(app):
    a = open_(app)
    s = settings(a)
    s.locator("label.tc-seg3:has(input[value='dark'])").click()
    assert a.page.get_attribute("#today", "data-th") == "dark"
    assert stored(a.page, "japan2026.settings.v1")["theme"] == "dark"
    s.locator("label.tc-seg3:has(input[value='auto'])").click()
    assert a.page.get_attribute("#today", "data-th") == "light"


def test_prices_are_per_person(app):
    a = open_(app)
    s = settings(a)
    assert s.locator("#setTrav").count() == 0
    a.page.keyboard.press("Escape")
    a.page.click(".tc-tab[data-tab='day']")
    assert "¥210/чел" in a.page.inner_text("#tcList").replace("\u00a0", " ")


def test_edit_add_and_day_label(app):
    a = open_(app)
    a.page.click(".tc-tab[data-tab='day']")
    a.page.click(".tc-item.now .tc-open")
    a.page.click("#tcSheet [data-edit]")
    a.page.fill("#edT", "Oishi Park — долго")
    a.page.click("#edSave")
    assert "Oishi Park — долго" in a.page.inner_text("#tcList")
    a.page.click("#tcAdd")
    a.page.fill("#edT", "Онсэн")
    a.page.fill("#edS", "23:10")
    a.page.click("#edSave")
    assert "Онсэн" in a.page.locator(".tc-item").last.inner_text()
    a.page.click("#tcDayEdit")
    a.page.fill("#dyLabel", "Фудзи-день")
    a.page.click("#dySave")
    assert "Фудзи-день" in a.page.inner_text(".tc-title h1")
    trip = stored(a.page, "japan2026.trip.v1")
    assert trip["days"][1]["label"] == "Фудзи-день"


def test_import_hostile_trip_is_escaped(app):
    a = open_(app)
    s = settings(a)
    evil = '<img src=x onerror="window.__pwned=1">'
    trip = {"name": evil, "days": [{"n": 1, "label": evil, "ev": [{"id": "x1", "s": "10:00", "e": "11:00", "t": evil,
            "link": "javascript:alert(1)",
            "lat": '1" onclick="window.__pwned=1', "lng": 2, "bound": evil, "ride": evil, "walk": evil, "buf": evil},
            {"id": "constructor", "s": "12:00", "e": "12:30", "t": "обычный пункт"}]}], "bookings": [{"id": "b", "days": [1], "t": evil, "when": evil}]}
    s.locator("#setJson").fill(json.dumps(trip))
    s.locator("#setLoad").click()
    for t in ("now", "day", "tix", "stats"):
        a.page.click(f".tc-tab[data-tab='{t}']")
    a.page.click(".tc-tab[data-tab='day']")
    a.page.click(".tc-item .tc-open")
    assert a.page.evaluate("window.__pwned") is None
    assert a.page.locator("#tcSheet a[href^='javascript']").count() == 0
    assert a.page.locator("#tcSheet [onclick], #today [onclick], #today [onerror], img[src=x]").count() == 0
    a.page.keyboard.press("Escape")
    assert "done" not in a.page.locator(".tc-item", has_text="обычный пункт").get_attribute("class")
    assert a.errors == []


def test_back_to_template_takes_two_taps(app):
    a = open_(app)
    s = settings(a)
    s.locator("#setName").fill("Наша")
    s.locator("#setSave").click()
    assert a.page.title() == "Наша"
    s = settings(a)
    s.locator("#setReset").click()
    assert a.page.title() == "Наша"
    s.locator("#setReset").click()
    assert a.page.title() != "Наша"
