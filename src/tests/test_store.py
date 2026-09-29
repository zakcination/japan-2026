"""Storage behaviour that must survive the module split: own trip, the #trip= link, settings."""
import base64
import json
import zlib


def trip(name="Тестовая поездка"):
    return {"schema": 1, "name": name, "travelers": 2, "start": "2026-10-17", "currency": "KZT", "rate": 2.81,
            "bookings": [], "days": [{"n": 1, "date": "2026-10-17", "city": "Токио", "label": "Токио", "wcity": "Tokyo",
                                      "sun": [35.6, 139.7], "summary": "", "konbini": "", "hotel": "", "ev": [
                                          {"id": "x1", "s": "10:00", "e": "11:00", "t": "Сэнсо-дзи", "cat": "activity",
                                           "st": "planned", "place": "sensoji"}]}]}


def link_for(t):
    raw = json.dumps(t, ensure_ascii=False, separators=(",", ":")).encode()
    c = zlib.compressobj(9, zlib.DEFLATED, -15)
    return "#trip=" + base64.urlsafe_b64encode(c.compress(raw) + c.flush()).decode().rstrip("=")


def test_own_trip_from_storage_is_shown(app):
    a = app(trip=trip(), state={"prevDay": 1, "prevTime": "09:00"})
    assert a.page.title() == "Тестовая поездка"
    assert a.errors == []


def test_trip_link_imports_and_clears_the_address(app):
    a = app(url_suffix=link_for(trip("Из ссылки")), state={"prevDay": 1, "prevTime": "09:00"})
    a.page.wait_for_function("() => !location.hash.includes('trip=')")
    assert a.page.title() == "Из ссылки"
    assert json.loads(a.page.evaluate("localStorage.getItem('japan2026.trip.v1')"))["name"] == "Из ссылки"


def test_travellers_setting_scales_prices(app):
    a = app(settings={"travelers": 4, "start": "2026-10-17", "cur": "KZT", "rate": 2.81},
            state={"prevDay": 2, "prevTime": "05:20"})
    a.page.click(".tc-tab[data-tab='day']")
    text = a.page.inner_text("#today")
    assert "¥840" in text          # JR Yamanote ¥210 per person × 4
