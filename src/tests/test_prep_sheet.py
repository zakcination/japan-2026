import json
from conftest import ROOT

OWN = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))


def home(app, **kw):
    return app(trip=OWN, state={"prevDay": 2, "prevTime": "13:24", "preview": False}, **kw)


def test_tick_add_and_delete_own_item(app):
    a = home(app)
    a.page.evaluate("openPrep('phone')")
    s = a.page.locator("#tcSheet")
    s.locator(".tc-prep-item[data-id='p-suica'] .tc-check").click()
    local = json.loads(a.page.evaluate("localStorage.getItem('japan2026.prep.v1')"))
    assert local["done"]["p-suica"] is True
    s.locator("[data-prep-add='packing']").click()
    a.page.fill("#prAddTitle", '<img src=x onerror="window.__pwned=1">Подарки')
    a.page.click("#prAddGo")
    item = a.page.locator(".tc-prep-item", has_text="Подарки")
    assert item.count() == 1 and a.page.evaluate("window.__pwned") is None
    item.locator("[data-prep-del]").click(); item.locator("[data-prep-del]").click()
    assert a.page.locator(".tc-prep-item", has_text="Подарки").count() == 0
    a.page.reload()
    a.page.evaluate("openPrep('phone')")
    assert a.page.locator(".tc-prep-item[data-id='p-suica'] input").is_checked()


def test_auto_items_are_labelled_and_locked(app):
    a = home(app)
    a.page.evaluate("openPrep('tickets')")
    fixed = next(b["id"] for b in OWN["bookings"] if b["st"] == "fixed")
    row = a.page.locator(f".tc-prep-item[data-id='bk:{fixed}']")
    assert "проверено приложением" in row.inner_text()
    assert row.locator("input").is_disabled()
    for b in a.page.locator("#tcSheet button, #tcSheet .tc-check").all():
        assert b.bounding_box()["height"] >= 44
