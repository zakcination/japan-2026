"""«Документы в телефоне»: files stay on the phone (IndexedDB), open full screen offline, delete with a second tap."""
import base64
from conftest import until
from test_kz_cards import OURS

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4z8DwHwAFAAH/iZk9HQAAAABJRU5ErkJggg==")


def test_add_open_survive_reload_and_delete(app):
    a = app(trip=OURS, state={"prevDay": 1, "prevTime": "05:00"})
    pg = a.page
    pg.click("#tcSos"); pg.click("#sosDocs")
    pg.wait_for_selector("#docFile", state="attached")
    pg.set_input_files("#docFile", files=[{"name": "China_QR_Мирас.png", "mimeType": "image/png", "buffer": PNG},
                                          {"name": "notes.txt", "mimeType": "text/plain", "buffer": b"x"}])
    until(pg, "document.querySelectorAll('#docList [data-doc]').length === 1")
    assert "China_QR_Мирас" in pg.inner_text("#docList") and "пропущена" in pg.inner_text("#docMsg")
    pg.context.set_offline(True)
    pg.click("#docList [data-doc]")
    pg.wait_for_selector(".tc-docview img")
    assert pg.locator(".tc-docview").is_visible() and pg.evaluate("document.querySelector('.tc-docview img').naturalWidth") == 1
    pg.click("#docClose"); pg.context.set_offline(False)
    pg.reload(); pg.wait_for_selector("#today", state="attached")
    pg.click("#tcSos"); pg.click("#sosDocs")
    until(pg, "document.querySelectorAll('#docList [data-doc]').length === 1")      # still on the phone
    pg.click("[data-docdel]")
    assert pg.locator("#docList [data-doc]").count() == 1 and "ещё раз" in pg.inner_text("#docMsg")
    pg.click("[data-docdel]")
    until(pg, "document.querySelectorAll('#docList [data-doc]').length === 0")
    assert a.errors == []
