"""The «Брони» tab: today's bookings, the whole trip, bought toggle, ticket files, the full-screen ticket."""
import base64
import json

# 1×1 white PNG
PNG = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==")

# a fake Wake Lock that records requests and releases
WAKE = """
window.__wake = { req: 0, rel: 0 };
Object.defineProperty(navigator, 'wakeLock', { configurable: true, value: {
  request: () => { __wake.req++; return Promise.resolve({ release: () => { __wake.rel++; return Promise.resolve(); },
                                                          addEventListener() {} }); } } });
"""


def tix(app, day=2, **kw):
    a = app(state={"prevDay": day, "prevTime": "13:24"}, **kw)
    a.page.click(".tc-tab[data-tab='tix']")
    return a


def test_today_and_whole_trip(app):
    a = tix(app)
    today = a.page.locator("#tcBkToday .tc-bk")
    assert today.count() == 5
    assert "0 из 5 куплено" in a.page.text_content("#tcBkToday")
    assert "Автобус Keio" in a.page.text_content("#tcBkToday")
    assert a.page.locator("#tcBkAll .tc-bk").count() == 10
    for b in a.page.locator("#todayBody button, #todayBody label.tc-file").all():
        assert b.bounding_box()["height"] >= 44
    assert a.errors == []


def test_bought_toggle_is_saved_in_the_trip(app):
    a = tix(app)
    a.page.click("[data-bkst='bus18']")
    trip = json.loads(a.page.evaluate("localStorage.getItem('japan2026.trip.v1')"))
    assert next(b for b in trip["bookings"] if b["id"] == "bus18")["st"] == "fixed"
    assert "1 из 5 куплено" in a.page.text_content("#tcBkToday")


def test_attach_and_show_ticket_keeps_screen_on(app):
    a = tix(app)
    a.page.add_init_script(WAKE)
    a.page.evaluate(WAKE)
    a.page.set_input_files("[data-attach='bus18']", files=[{"name": "qr.png", "mimeType": "image/png", "buffer": PNG}])
    a.page.wait_for_selector("[data-ticket='bus18']")
    a.page.click("[data-ticket='bus18']")
    t = a.page.locator("#tcTicket")
    t.wait_for(state="visible")
    t.locator("img").wait_for()
    assert "Автобус Keio" in t.inner_text()
    a.page.wait_for_function("__wake.req === 1")
    assert "Экран не погаснет" in t.inner_text()
    a.page.click("#tcTicketDone")
    assert not t.is_visible()
    a.page.wait_for_function("__wake.rel === 1")


def test_delete_ticket_takes_two_taps(app):
    a = tix(app)
    a.page.set_input_files("[data-attach='bus18']", files=[{"name": "qr.png", "mimeType": "image/png", "buffer": PNG}])
    a.page.wait_for_selector("[data-ticket='bus18']")
    a.page.click("[data-ticket='bus18']")
    a.page.click("#tcTicketDel")
    a.page.click("#tcTicketDel")          # second tap confirms
    a.page.wait_for_selector("[data-attach='bus18']", state="attached")
    assert not a.page.locator("#tcTicket").is_visible()
