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


def test_my_documents_come_down_from_the_server_and_open_offline(app):
    from fake_supabase import FakeSupabase
    from test_group_join import logged
    fake = FakeSupabase.seeded()
    me, other = fake.host_id, fake.host2_id
    fake.files[f"{me}/docs/China_QR_Мирас.png"] = (PNG, "image/png")
    fake.files[f"{other}/docs/China_QR_Айкош.png"] = (PNG, "image/png")
    fake.attachments["d1"] = {"id": "d1", "member": me, "ref": "doc:wallet", "kind": "file", "path": f"{me}/docs/China_QR_Мирас.png", "name": "China_QR_Мирас.png", "shared": False}
    fake.attachments["d2"] = {"id": "d2", "member": other, "ref": "doc:wallet", "kind": "file", "path": f"{other}/docs/China_QR_Айкош.png", "name": "China_QR_Айкош.png", "shared": False}
    a = logged(app, fake, me, fake.host_pin, state={"prevDay": 1, "prevTime": "05:00"})
    pg = a.page
    pg.click("#tcSos"); pg.click("#sosDocs")
    until(pg, "/Готово|China_QR_Мирас/.test(document.getElementById('docList').textContent) || !document.getElementById('docSync').hidden")
    if pg.locator("#docSync").is_visible():                                    # not yet pulled by the background sync
        pg.click("#docSync")
    until(pg, "document.querySelectorAll('#docList [data-doc]').length === 1")
    assert "Китай · QR въезда" in pg.inner_text("#docList") and pg.locator("#docList [data-doc]").count() == 1   # only my own, in Russian
    pg.context.set_offline(True)
    pg.click("#docList [data-doc]"); pg.wait_for_selector(".tc-docview img")
    assert pg.evaluate("document.querySelector('.tc-docview img').naturalWidth") == 1
    assert a.errors == []
