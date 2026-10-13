"""UX pass 14.10: secondary buttons visible on every surface, dark sheets raised, 44 pt targets, switches, distinct icons."""
import json
from conftest import ROOT
from fake_supabase import FakeSupabase
from test_assistant import guest, ask

OURS = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
BG = "getComputedStyle(document.querySelector('{}')).backgroundColor"


def test_secondary_buttons_differ_from_the_surface_in_both_themes(app):
    for th in ("light", "dark"):
        a = app(trip=OURS, state={"prevDay": 3, "prevTime": "12:00"}, settings={"theme": th})
        page = a.page.evaluate(BG.format("#today"))
        assert a.page.evaluate(BG.format("#tcPvExit")) != page                     # «Выйти из предпросмотра» on the page
        a.page.click(".tc-tab[data-tab='day']"); a.page.click(".tc-item .tc-open >> nth=1")
        sheet = a.page.evaluate(BG.format("#tcSheet .tc-sheet"))
        assert a.page.evaluate(BG.format("#tcSheetX")) != sheet
        if th == "dark":
            assert sheet != page                                                    # a raised sheet, not black on black
        assert not a.errors


def test_switches_targets_and_icons(app):
    fake = FakeSupabase.seeded(); a, _ = guest(app, fake); pg = a.page
    assert pg.locator("#tcSos").bounding_box()["height"] >= 44
    pg.click("#tcGear")
    sw = pg.locator("#grShareAll").bounding_box()
    assert sw["width"] >= 50 and sw["height"] >= 30                                   # an iOS switch, not a 13 pt box
    pg.click("#tcSheetX"); pg.click("#tcSos")
    assert pg.locator("#sosIns a[href^='http'] svg path").first.get_attribute("d").startswith("M10 14")   # a link icon
    pg.click("#tcSheetX"); pg.click("#tcAsk")
    fake.assistant_reply = {"reply": "Да.", "actions": []}
    ask(pg, "Привет")
    for sel in ("#asToTr", "#asToProf", ".as-hb.as-sosb", "#tcSheetX", ".as-copy"):
        assert pg.locator(sel).first.bounding_box()["height"] >= 44, sel
    assert not a.errors


def test_assistant_on_the_money_tab_too(app):
    fake = FakeSupabase.seeded(); a, _ = guest(app, fake); pg = a.page
    pg.click(".tc-tab[data-tab='stats']")
    assert pg.locator("#tcAsk").count() == 1 and pg.locator("#tcSos").count() == 1 and pg.locator("#tcGear").count() == 1
