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
    a.page.fill("[data-prep-form='packing'] input", '<img src=x onerror="window.__pwned=1">Подарки')
    a.page.click("[data-prep-go='packing']")
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
        assert b.bounding_box()["height"] >= 43.5


def test_add_form_is_scoped_to_its_group(app):
    """Opening «Свой пункт» in two groups must not collide on a shared id: the item
    typed into the second form must be saved to that form's own group, not dropped
    or misfiled into the first group's form."""
    a = home(app)
    a.page.evaluate("openPrep()")
    s = a.page.locator("#tcSheet")
    s.locator("[data-prep-add='tickets']").click()
    s.locator("[data-prep-add='money']").click()
    s.locator("[data-prep-form='money'] input").fill("Обменять деньги")
    s.locator("[data-prep-go='money']").click()
    assert a.errors == []
    local = json.loads(a.page.evaluate("localStorage.getItem('japan2026.prep.v1')"))
    added = next(o for o in local["own"] if o["title"] == "Обменять деньги")
    assert added["group"] == "money"


def test_tolerates_corrupt_local_storage(app):
    """A hand-edited or half-written japan2026.prep.v1 (done as a string, not an
    object) must not crash the next tick."""
    a = home(app)
    a.page.evaluate("localStorage.setItem('japan2026.prep.v1', JSON.stringify({done: 'oops', own: []}))")
    a.page.evaluate("openPrep('phone')")
    s = a.page.locator("#tcSheet")
    s.locator(".tc-prep-item[data-id='p-suica'] .tc-check").click()
    assert a.errors == []
    local = json.loads(a.page.evaluate("localStorage.getItem('japan2026.prep.v1')"))
    assert local["done"]["p-suica"] is True
