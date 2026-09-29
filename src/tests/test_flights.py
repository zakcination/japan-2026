"""Flights: time zones, lookup of a known number, the countdown card, entering your own flight."""
import json

from conftest import ROOT

OURS = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
UTC = "Date.UTC"


def test_times_follow_each_airports_zone(core):
    pg = core(("core.js", "flights.js"))
    # Almaty is UTC+5, Shanghai +8: 20:50 in Almaty on the 16th → 05:30 in Shanghai on the 17th
    t = pg.evaluate("() => Flights.times({ no: 'MU6042', date: '2026-10-16', frm: 'ALA', dep: '20:50', to: 'PVG', arr: '05:30' })")
    assert t["dep"] == pg.evaluate("Date.UTC(2026, 9, 16, 15, 50)")
    assert t["arr"] == pg.evaluate("Date.UTC(2026, 9, 16, 21, 30)")
    # summer time where there is one: Frankfurt in July is UTC+2
    assert pg.evaluate("Flights.epochOf('2026-07-01', '12:00', 'FRA')") == pg.evaluate("Date.UTC(2026, 6, 1, 10, 0)")
    # an unknown airport needs the traveller's own offset
    assert pg.evaluate("Flights.epochOf('2026-10-16', '10:00', 'XXX')") is None
    assert pg.evaluate("Flights.epochOf('2026-10-16', '10:00', 'XXX', 360)") == pg.evaluate("Date.UTC(2026, 9, 16, 4, 0)")


def test_lookup_fills_a_known_flight_and_names_the_airline(core):
    pg = core(("core.js", "flights.js"))
    known = json.dumps(OURS["flights"])
    f = pg.evaluate(f"Flights.lookup('mu 575', {known})")
    assert f["no"] == "MU575" and f["airline"] == "China Eastern"
    assert (f["frm"], f["dep"], f["to"], f["arr"]) == ("PVG", "17:15", "HND", "21:20")
    g = pg.evaluate(f"Flights.lookup('KC-123', {known})")
    assert g["airline"] == "Air Astana" and "frm" not in g
    assert pg.evaluate("Flights.lookup('hello', [])") is None


def test_next_departure_heads_to_japan_then_home(core):
    pg = core(("core.js", "flights.js"))
    legs = json.dumps(OURS["flights"])
    n = pg.evaluate(f"Flights.next({legs}, Date.UTC(2026, 8, 30))")
    assert n["leg"]["no"] == "MU6042" and n["dir"] == "japan"
    assert [c["no"] for c in n["chain"]] == ["MU6042", "MU575"]
    back = pg.evaluate(f"Flights.next({legs}, Date.UTC(2026, 9, 27, 0, 0))")
    assert back["leg"]["no"] == "MU540" and back["dir"] == "home"
    assert pg.evaluate(f"Flights.next({legs}, Date.UTC(2026, 10, 1))") is None
    cd = pg.evaluate("Flights.countdown((16 * 1440 + 12 * 60 + 50) * 60000)")
    assert cd == {"d": 16, "h": 12, "m": 50, "unit": "дней"}
    assert pg.evaluate("Flights.countdown(21 * 1440 * 60000).unit") == "день"


def test_countdown_card_on_our_trip(app):
    # 30.09 12:00 in Japan = 03:00 UTC; MU6042 leaves Almaty 16.10 20:50 (+5) = 15:50 UTC
    a = app(trip=OURS, state={"prevDay": 2, "prevTime": "13:24"})
    card = a.page.locator("#tcFlight")
    t = card.inner_text()
    assert "До вылета в Японию" in t and "MU 6042" in t
    assert card.locator(".tc-fl-count").get_attribute("aria-label").endswith("16 дней 12 ч 50 мин")
    assert "Алматы → Шанхай Пудун → Токио Ханэда" in t
    assert "Прилёт 17.10 в 21:20" in t and "к 17:50" in t
    assert card.locator("a[href='https://www.flightradar24.com/data/flights/mu6042']").count() == 1
    for b in card.locator("a, button").all():
        assert b.bounding_box()["height"] >= 44
    assert a.errors == []


def test_everyone_can_enter_their_own_flight(app):
    a = app(state={"prevDay": 2, "prevTime": "13:24"})          # the template has no flights
    a.page.click("#tcFlights")
    a.page.fill("#flNo", "mu575")                                # known from our trip, baked into the page
    assert a.page.input_value("#flFrm") == "PVG" and a.page.input_value("#flArr") == "21:20"
    assert "China Eastern" in a.page.inner_text("#flInfo")
    a.page.fill("#flDate", "2026-10-17")
    a.page.click("#flAdd")
    assert "MU 575" in a.page.inner_text("#tcFlight")
    # an unknown airport asks for its time zone
    a.page.click("#tcFlights")
    a.page.fill("#flNo", "KC901")
    assert "Air Astana" in a.page.inner_text("#flInfo")
    a.page.fill("#flDate", "2026-10-15")
    a.page.fill("#flFrm", "XYZ")
    assert a.page.is_visible("#flFrmOff")
    a.page.fill("#flDep", "08:00")
    a.page.fill("#flTo", "NRT")
    a.page.fill("#flArr", "18:00")
    a.page.click("#flAdd")
    assert "KC 901" in a.page.inner_text("#tcFlight")               # the earlier one is next
    saved = json.loads(a.page.evaluate("localStorage.getItem('japan2026.flights.v1')"))
    assert [f["no"] for f in saved] == ["KC901", "MU575"] and saved[0]["frmOff"] == 300


def test_bad_flight_entry_is_refused(app):
    a = app(state={"prevDay": 2, "prevTime": "13:24"})
    a.page.click("#tcFlights")
    a.page.fill("#flNo", '<img src=x onerror="window.__pwned=1">')
    a.page.click("#flAdd")
    assert "Нужны рейс" in a.page.inner_text("#flMsg")
    assert a.page.evaluate("window.__pwned") is None
