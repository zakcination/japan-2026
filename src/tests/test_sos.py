"""SOS sheet: one tap from the header on any tab, insurance first, personal notes only on the phone."""
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
OURS = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
KEY = "japan2026.sos.v1"


def open_sos(app, tab="now", state=None):
    a = app(trip=OURS, state=state or {"prevDay": 3, "prevTime": "12:00"})
    if tab != "now":
        a.page.click(f".tc-tab[data-tab='{tab}']")
    a.page.click("#tcSos")
    a.page.wait_for_selector("#tcSheet .tc-sheet")
    return a


def test_header_button_on_every_tab(app):
    for tab in ("now", "day", "tix", "stats"):
        a = open_sos(app, tab)
        assert a.page.locator("#tcSheet h2").inner_text() == "SOS"
        box = a.page.locator("#tcSos").bounding_box()
        gear = a.page.locator("#tcGear").bounding_box()
        assert box["x"] + box["width"] <= gear["x"] + 1 and box["height"] >= 28
        cap = a.page.locator(".tc-cap")
        if cap.count():
            c = cap.first.bounding_box()
            assert box["x"] + box["width"] <= c["x"] or box["x"] >= c["x"] + c["width"]
        assert a.errors == []


def test_calls_are_tel_links_and_insurance_first(app):
    a = open_sos(app)
    hrefs = a.page.eval_on_selector_all("#sosCalls a", "as => as.map(a => a.getAttribute('href'))")
    assert {"tel:110", "tel:119", "tel:+815038162787", "tel:+441273765321"} <= set(hrefs)
    assert all(" " not in h for h in hrefs)
    assert "только если билеты оплачены" in a.page.locator("#sosIns").inner_text()
    ext = a.page.locator("#sosIns a[target='_blank']")
    assert ext.count() == 1 and "noopener" in ext.get_attribute("rel")
    for b in a.page.locator("#sosCalls a").all():
        assert b.bounding_box()["height"] >= 44


def test_personal_notes_stay_local(app):
    a = open_sos(app)
    a.page.fill("#sos_allergy", "пенициллин")
    a.page.click("#sosSave")
    assert "Сохранено" in a.page.locator("#sosMsg").inner_text()
    saved = json.loads(a.page.evaluate(f"localStorage.getItem('{KEY}')"))
    assert saved["allergy"] == "пенициллин"
    a.page.click("#tcSheetX")
    a.page.click("#tcSos")
    assert a.page.locator("#sos_allergy").input_value() == "пенициллин"
    assert a.page.locator("#sosMe").get_attribute("open") is None


def test_japanese_phrase_full_screen(app):
    a = open_sos(app)
    a.page.wait_for_timeout(400)                                    # the sheet slides up; let it settle before tapping
    a.page.locator("#sosPhr summary").scroll_into_view_if_needed()
    a.page.locator("#sosPhr summary").click()
    ja = a.page.locator(".tc-sos-ja").first
    ja.scroll_into_view_if_needed()
    a.page.wait_for_timeout(200)
    ja.click()
    big = a.page.locator(".tc-sos-big")
    assert big.is_visible() and "救急車" in big.inner_text()
    big.click()
    assert a.page.locator(".tc-sos-big").count() == 0
    assert a.errors == []
