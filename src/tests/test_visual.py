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
    for sel in ("#asToTr", "#asMore", ".as-hb.as-sosb", "#tcSheetX", ".as-copy", "#asNewChat"):
        assert pg.locator(sel).first.bounding_box()["height"] >= 44, sel
    assert not a.errors


def test_assistant_on_the_money_tab_too(app):
    fake = FakeSupabase.seeded(); a, _ = guest(app, fake); pg = a.page
    pg.click(".tc-tab[data-tab='stats']")
    assert pg.locator("#tcAsk").count() == 1 and pg.locator("#tcSos").count() == 1 and pg.locator("#tcGear").count() == 1


def test_plural_and_whole_hours(core):
    pg = core()
    got = pg.evaluate("[1, 2, 5, 11, 12, 21, 22, 25, 111].map(n => Core.plural(n, 'вопрос', 'вопроса', 'вопросов'))")
    assert got == ["вопрос", "вопроса", "вопросов", "вопросов", "вопросов", "вопрос", "вопроса", "вопросов", "вопросов"]
    assert pg.evaluate("[Core.dur(60), Core.dur(65), Core.dur(45)]") == ["1 ч", "1 ч 05 мин", "45 мин"]


def test_going_is_a_segmented_control_showing_my_state(app):
    fake = FakeSupabase.seeded(); a, _ = guest(app, fake); pg = a.page
    pg.click(".tc-tab[data-tab='day']"); pg.click("#grView [data-view='group']")      # the group plan keeps stops I skip
    sid = pg.locator(".tc-item >> nth=2").get_attribute("data-id"); pg.click(f".tc-item[data-id='{sid}'] .tc-open")
    seg = pg.locator("#tcSheet .tc-joinseg")
    assert seg.locator("[data-join='in']").inner_text() == "Иду"
    assert seg.locator("[data-join='in']").get_attribute("aria-pressed") == "true"      # she is in «Идут»
    assert seg.locator("[data-join='out']").get_attribute("aria-pressed") == "false"
    seg.locator("[data-join='out']").click()
    pg.click(f".tc-item[data-id='{sid}'] .tc-open")
    assert pg.locator("#tcSheet .tc-joinseg [data-join='out']").get_attribute("aria-pressed") == "true"


def test_reopening_the_assistant_lands_on_the_chat_and_the_field_shrinks_back(app):
    fake = FakeSupabase.seeded(); a, _ = guest(app, fake); pg = a.page
    pg.click("#tcAsk"); pg.click("#asToTr"); pg.click("#tcSheetX"); pg.click("#tcAsk")
    assert pg.locator("#asText").count() == 1 and pg.locator("#trMe").count() == 0
    h0 = pg.locator("#asText").bounding_box()["height"]
    fake.assistant_reply = {"reply": "Да.", "actions": []}
    pg.fill("#asText", "строка\nещё строка\nи ещё одна"); pg.dispatch_event("#asText", "input")
    assert pg.locator("#asText").bounding_box()["height"] > h0 and pg.locator("#asEx").is_hidden()
    pg.click("#asSend")
    from conftest import until
    until(pg, "!document.getElementById('asWait')")
    assert abs(pg.locator("#asText").bounding_box()["height"] - h0) < 2 and pg.locator("#asEx").is_visible()
    assert pg.locator(".as-chip").first.bounding_box()["height"] >= 44


def test_money_bars_one_column_per_day_and_sos_insurance_first(app):
    a = app(trip=OURS, state={"prevDay": 3, "prevTime": "12:00"})
    a.page.click(".tc-tab[data-tab='stats']")
    bars = a.page.locator(".tc-bars .tc-barcol")
    tops = {round(bars.nth(i).bounding_box()["y"]) for i in range(bars.count())}
    assert bars.count() == len(OURS["days"]) and len(tops) == 1                         # one row, «28» doesn't wrap
    a.page.click("#tcSos")
    first = a.page.locator("#sosFirst")
    hrefs = [x.get_attribute("href") for x in first.locator("a").all()]
    assert "Сначала — страховая" in first.inner_text() and hrefs == ["tel:+74959871775", "tel:+441273765321"]   # Freedom for the hosts, Mastercard for the rest
    assert "Мирас, Айкош" in first.inner_text() and "Аманжан, Сания, Шахи" in first.inner_text()
    box = first.bounding_box(); calls = a.page.locator("#sosCalls").bounding_box()
    assert box["y"] < calls["y"]
