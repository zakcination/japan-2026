"""Storage behaviour that must survive the module split: own trip, the #trip= link, settings."""
import base64
import json

from conftest import until
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
    until(a.page, "() => !location.hash.includes('trip=')")
    assert a.page.title() == "Из ссылки"
    assert json.loads(a.page.evaluate("localStorage.getItem('japan2026.trip.v1')"))["name"] == "Из ссылки"


def test_prices_stay_per_person_whatever_the_group_size(app):
    a = app(settings={"travelers": 4, "start": "2026-10-17", "cur": "KZT", "rate": 2.81},
            state={"prevDay": 2, "prevTime": "05:20"})
    a.page.click(".tc-tab[data-tab='day']")
    text = a.page.inner_text("#today")
    assert "¥210/чел" in text      # JR Yamanote, per person (owners' choice)


def test_link_without_bookings_opens_every_tab_and_resets_marks(app):
    t = {"name": "Без броней", "days": [{"n": 1, "label": "Д1", "ev": [{"id": "d2e3", "s": "10:00", "e": "11:00", "t": "Пункт"}]}]}
    a = app(state={"prevDay": 1, "prevTime": "09:00", "done": {"d2e3": True}}, url_suffix=link_for(t))
    until(a.page, "() => document.title === 'Без броней'")
    for tab in ("now", "day", "stats", "tix"):
        a.page.click(f".tc-tab[data-tab='{tab}']")
    assert "броней нет" in a.page.inner_text("#todayBody")
    assert json.loads(a.page.evaluate("localStorage.getItem('japan2026.today.v1')"))["done"] == {}
    assert a.errors == []


def test_a_stop_past_midnight_stays_on_screen(app):
    t = {"name": "Ночь", "start": "2026-10-17", "days": [
        {"n": 1, "label": "Первый", "ev": [{"id": "a", "s": "23:30", "e": "00:30", "t": "Онсэн", "st": "planned", "cat": "activity"}]},
        {"n": 2, "label": "Второй", "ev": [{"id": "b", "s": "09:00", "e": "10:00", "t": "Завтрак", "st": "planned", "cat": "food"}]}],
        "bookings": []}
    a = app(trip=t, now="2026-10-18T00:10:00+09:00")
    assert "Онсэн" in a.page.inner_text("#tcNow")
    assert "Первый" in a.page.inner_text(".tc-title h1")
