"""The «Итоги» tab: three rings, budget by day, tiles with walk and spend entered by hand."""
import json
import re


def stats(app, state=None, **kw):
    a = app(state={"prevDay": 2, "prevTime": "13:24", **(state or {})}, **kw)
    a.page.click(".tc-tab[data-tab='stats']")
    return a


def marks(page):
    return json.loads(page.evaluate("localStorage.getItem('japan2026.today.v1')"))


def test_rings_and_legend(app):
    a = stats(app, state={"done": {"d2e3": True, "d2e4": True}})
    assert a.page.locator("#tcHead").is_hidden()
    assert "Деньги" in a.page.inner_text(".tc-stats-title")
    assert a.page.locator(".tc-rings circle.fg").count() == 3
    legend = a.page.inner_text(".tc-legend")
    assert "2/11" in legend
    assert re.search(r"2/\d+", legend.split("Сегодня")[1])
    assert a.errors == []


def test_budget_bars_mark_today(app):
    a = stats(app)
    bars = a.page.locator(".tc-bars .tc-barcol")
    assert bars.count() == 11
    assert "cur" in bars.nth(1).get_attribute("class")
    assert "done" in bars.nth(0).get_attribute("class")
    assert "всего ¥" in a.page.inner_text("#tcBudget")


def test_walk_and_spent_are_entered_and_kept(app):
    a = stats(app)
    a.page.fill("#tcWalk", "5.5")
    a.page.press("#tcWalk", "Enter")
    a.page.fill("#tcSpent", "9800")
    a.page.press("#tcSpent", "Enter")
    m = marks(a.page)
    assert m["walked"]["2"] == 5.5 and m["spent"]["2"] == 9800
    assert "¥9 800" in a.page.inner_text("#tcSpentTile").replace(" ", " ")
    assert "5,5" in a.page.inner_text("#tcWalkTile") or "5.5" in a.page.inner_text("#tcWalkTile")
    for i in a.page.locator("#todayBody input").all():
        assert i.bounding_box()["height"] >= 44


def test_sunset_tile(app):
    a = stats(app)
    assert re.search(r"\d{2}:\d{2}", a.page.inner_text("#tcSunTile"))
