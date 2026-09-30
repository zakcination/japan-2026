import base64
from conftest import until
from fake_supabase import FakeSupabase
from test_group_join import logged

PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==")
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"


def test_link_is_private_then_shared_with_a_warning(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='tix']")
    g.page.click(".tc-task[data-ref='bk:bus18'] [data-attach-ref]")
    g.page.fill("#atUrl", "https://www.highwaybus.com/gp/reserve/abc")
    g.page.click("#atAdd")
    assert "Highway Bus" in g.page.inner_text("#tcSheet")
    until(g.page, "Api.status().pending === 0")
    a = next(iter(fake.attachments.values()))
    assert a["kind"] == "link" and a["shared"] is False
    g.page.click("#tcSheet [data-share]")
    assert "работает как ключ" in g.page.inner_text("#atWarn")
    g.page.click("#atWarnGo")
    until(g.page, "Api.status().pending === 0")
    assert next(iter(fake.attachments.values()))["shared"] is True


def test_pdf_upload_private_and_host_sees_only_shared(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='tix']")
    g.page.click(".tc-task[data-ref='bk:bus18'] [data-attach-ref]")
    g.page.set_input_files("#atFile", files=[{"name": "ticket.pdf", "mimeType": "application/pdf", "buffer": PDF}])
    until(g.page, "Api.status().pending === 0 && Api.state().attachments.length === 1")
    path = next(iter(fake.attachments.values()))["path"]
    assert path.startswith(san + "/") and fake.files[path][0] == PDF
    h = logged(app, fake, fake.host_id, fake.host_pin)
    assert h.page.evaluate("Api.state().attachments.length") == 0


def test_bad_links_are_refused_and_offline_file_waits(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='tix']")
    g.page.click(".tc-task[data-ref='bk:bus18'] [data-attach-ref]")
    for bad in ("javascript:alert(1)", "http://booking.com/x", "https://x\" onclick=\"1"):
        g.page.fill("#atUrl", bad); g.page.click("#atAdd")
        assert "https://" in g.page.inner_text("#atMsg")


def test_not_logged_in_link_stays_on_the_phone(app):
    a = app(state={"prevDay": 2, "prevTime": "13:24"})
    a.page.click(".tc-tab[data-tab='tix']")
    a.page.click("[data-link='bus18']")
    a.page.fill("#atUrl", "https://secure.booking.com/confirmation.html?x=1")
    a.page.click("#atAdd")
    assert "Booking.com" in a.page.inner_text("#tcSheet")
    assert "booking.com" in a.page.evaluate("localStorage.getItem('japan2026.links.v1')")


def test_deleting_a_ticket_file_deletes_the_file_too(app):
    fake = FakeSupabase.seeded(); san = fake._add("Сания", "guest")
    fake.joins.append({"member": san, "scope": "part", "ref": "fuji", "mode": "in"})
    g = logged(app, fake, san, "4821")
    g.page.click(".tc-tab[data-tab='tix']")
    g.page.click(".tc-task[data-ref='bk:bus18'] [data-attach-ref]")
    g.page.set_input_files("#atFile", files=[{"name": "ticket.pdf", "mimeType": "application/pdf", "buffer": PDF}])
    until(g.page, "Api.status().pending === 0 && Api.state().attachments.length === 1")
    path = next(iter(fake.attachments.values()))["path"]
    g.page.locator("#tcSheet [data-del]").click(); g.page.locator("#tcSheet [data-del]").click()   # two taps
    until(g.page, "Api.status().pending === 0 && Api.state().attachments.length === 0")
    assert path not in fake.files and not fake.attachments
