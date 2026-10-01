"""Polish round 01.10: Dynamic Type, «Мои рейсы» rows and delete, the two-tap confirm, contrast tokens."""
import json
from conftest import ROOT
from test_now import at

OURS = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))


def test_body_text_follows_the_iphone_text_size_but_heroes_do_not(app):
    a = at(app, "13:24")
    size = lambda sel: a.page.evaluate(f"parseFloat(getComputedStyle(document.querySelector('{sel}')).fontSize)")
    body, hero = size("#tcNext .tc-sub, #tcNext small, .tc-sub"), size(".tc-cap-n")
    a.page.evaluate("document.documentElement.style.fontSize = '23px'")      # what a larger Dynamic Type setting does to the root
    assert size("#tcNext .tc-sub, #tcNext small, .tc-sub") > body * 1.25
    assert size(".tc-cap-n") == hero
    a.page.evaluate("document.documentElement.style.fontSize = '60px'")      # accessibility sizes: capped, the layout holds
    assert size("#tcNext .tc-sub, #tcNext small, .tc-sub") <= body * 1.4 + 0.5


def test_flight_rows_keep_number_and_date_together_and_delete_says_so(app):
    a = app(trip=OURS, state={"prevDay": 2, "prevTime": "13:24"})
    a.page.click("#tcFlight #tcFlights, #tcFlights")
    row = a.page.locator("#flList .tc-flrow").first
    t = row.locator(".tc-fl-t")
    assert t.count() == 1 and t.bounding_box()["height"] < 26                 # «MU 6042 · 16.10» on one line
    assert "РЕЙСЫ ПОЕЗДКИ" in a.page.inner_text("#tcSheet").upper()
    x = row.locator("[data-fldel]")
    x.click()
    assert x.inner_text() == "Удалить?" and x.bounding_box()["height"] >= 44
    a.page.wait_for_timeout(4300)
    assert x.locator("svg").count() == 1                                      # the × comes back as an icon, not blank
