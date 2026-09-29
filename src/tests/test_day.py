"""The «День» tab: week strip, swipe, list with done checks, the stop sheet."""
import json


def day_tab(app, time="13:24", day=2, **kw):
    a = app(state={"prevDay": day, "prevTime": time, **kw.pop("state", {})}, **kw)
    a.page.click(".tc-tab[data-tab='day']")
    return a


def marks(page):
    return json.loads(page.evaluate("localStorage.getItem('japan2026.today.v1')"))


def test_strip_and_list(app):
    a = day_tab(app)
    assert a.page.locator(".tc-daypick").count() == 11
    rows = a.page.locator(".tc-item")
    assert rows.count() == 13
    assert "Oishi Park" in a.page.inner_text(".tc-item.now")
    assert a.errors == []


def test_pick_day_and_swipe(app):
    a = day_tab(app)
    a.page.click(".tc-daypick >> nth=2")
    assert "3/11" in a.page.inner_text(".tc-title")
    box = a.page.locator("#tcList").bounding_box()
    y = box["y"] + 60
    a.page.mouse.move(box["x"] + box["width"] - 30, y)
    a.page.mouse.down()
    a.page.mouse.move(box["x"] + 30, y, steps=6)
    a.page.mouse.up()
    assert "4/11" in a.page.inner_text(".tc-title")


def test_done_check_is_a_native_switch_and_persists(app):
    a = day_tab(app)
    sw = a.page.locator(".tc-item >> nth=3 >> input[type=checkbox]")
    assert sw.get_attribute("switch") is not None
    a.page.locator(".tc-item >> nth=3 >> .tc-check").click()
    assert marks(a.page)["done"].get("d2e3") is True
    assert "done" in a.page.locator(".tc-item >> nth=3").get_attribute("class")


def test_stop_sheet_actions(app):
    a = day_tab(app)
    a.page.click(".tc-item.now .tc-open")
    sheet = a.page.locator("#tcSheet")
    assert sheet.is_visible() and "Oishi Park" in sheet.inner_text()
    for b in sheet.locator("button, a").all():
        assert b.bounding_box()["height"] >= 44
    sheet.locator("[data-delay='15']").click()
    assert marks(a.page)["delay"]["d2e7"] == 15
    a.page.click(".tc-item.now .tc-open")
    a.page.locator("#tcSheet [data-skip]").click()
    assert marks(a.page)["skip"]["d2e7"] is True


def test_fixed_stop_cannot_be_delayed_or_skipped(app):
    a = day_tab(app)
    a.page.click(".tc-daypick >> nth=4")
    judo = a.page.locator(".tc-item", has_text="пара-дзюдо")
    judo.locator(".tc-open").click()
    s = a.page.locator("#tcSheet")
    assert s.locator("[data-delay]").count() == 0 and s.locator("[data-skip]").count() == 0
