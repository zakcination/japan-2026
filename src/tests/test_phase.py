import json
from conftest import ROOT

LEGS = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))["flights"]
F, L = "2026-10-17", "2026-10-27"


def ph(pg, iso_utc, legs=LEGS, first=F, last=L):
    return pg.evaluate(f"Flights.phase(Date.parse('{iso_utc}'), {json.dumps(legs)}, '{first}', '{last}')")


def test_phases_follow_the_flights(core):
    pg = core(("core.js", "flights.js"))

    r = ph(pg, "2026-09-30T03:00:00Z")
    assert r["phase"] == "pre" and r["leg"]["no"] == "MU6042" and r["dep"] is not None and r["arrive"] is not None

    r = ph(pg, "2026-10-15T18:59:00Z")             # 23:59 on 15.10 in Almaty (+5)
    assert r["phase"] == "pre" and r["leg"]["no"] == "MU6042"

    r = ph(pg, "2026-10-15T19:01:00Z")             # 00:01 on 16.10 in Almaty
    assert r["phase"] == "departure" and r["leg"]["no"] == "MU6042"

    r = ph(pg, "2026-10-16T15:49:00Z")             # 20:49 in Almaty, MU6042 at 20:50
    assert r["phase"] == "departure" and r["leg"]["no"] == "MU6042"

    r = ph(pg, "2026-10-16T16:00:00Z")             # in the air on MU6042
    assert r["phase"] == "transit" and r["leg"]["no"] == "MU6042" and r["arrive"] is not None

    r = ph(pg, "2026-10-17T02:00:00Z")             # 10:00 in Shanghai, waiting for MU575
    assert r["phase"] == "transit" and r["leg"]["no"] == "MU575"

    r = ph(pg, "2026-10-17T10:00:00Z")             # mid-MU575 flight — regression: used to report MU540
    assert r["phase"] == "transit" and r["leg"]["no"] == "MU575"

    r = ph(pg, "2026-10-17T12:21:00Z")             # 21:21 in Tokyo, landed
    assert r["phase"] == "live" and r["leg"] is None

    r = ph(pg, "2026-10-27T14:59:00Z")             # 23:59 on 27.10 in Tokyo
    assert r["phase"] == "live" and r["leg"] is None

    r = ph(pg, "2026-10-27T15:01:00Z")
    assert r["phase"] == "post" and r["leg"] is None and r["dep"] is None and r["arrive"] is None


def test_phases_without_flights_use_the_dates(core):
    pg = core(("core.js", "flights.js"))
    r = ph(pg, "2026-10-16T14:59:00Z", [])          # 23:59 on 16.10 in Tokyo
    assert r["phase"] == "pre" and r["leg"] is None and r["dep"] is None and r["arrive"] is None
    r = ph(pg, "2026-10-16T15:01:00Z", [])
    assert r["phase"] == "live" and r["leg"] is None and r["dep"] is None and r["arrive"] is None
    r = ph(pg, "2026-10-27T15:01:00Z", [])
    assert r["phase"] == "post"


RETURN_ONLY = [                                     # only the way home was entered — no leg lands in Japan
    {"no": "MU540", "date": "2026-10-27", "frm": "HND", "dep": "11:00", "to": "PVG", "arr": "14:00"},
    {"no": "MU6041", "date": "2026-10-27", "frm": "PVG", "dep": "16:00", "to": "ALA", "arr": "19:30"},
]

FROM_JAPAN_FIRST = [                                # a later leg lands in Japan, but the earliest one starts there
    {"no": "AA1", "date": "2026-10-20", "frm": "HND", "dep": "09:00", "to": "ICN", "arr": "11:00"},
    {"no": "AA2", "date": "2026-10-25", "frm": "ICN", "dep": "09:00", "to": "HND", "arr": "11:00"},
]


def test_no_outbound_leg_falls_back_to_dates(core):
    pg = core(("core.js", "flights.js"))
    for legs in (RETURN_ONLY, FROM_JAPAN_FIRST):
        r = ph(pg, "2026-09-30T03:00:00Z", legs)
        assert r["phase"] == "pre" and r["leg"] is None and r["dep"] is None and r["arrive"] is None
        r = ph(pg, "2026-10-20T03:00:00Z", legs)    # well inside the trip
        assert r["phase"] == "live" and r["leg"] is None
        r = ph(pg, "2026-10-27T15:01:00Z", legs)
        assert r["phase"] == "post"


BLANK_ARR = [{"no": "MU575", "date": "2026-10-19", "frm": "ALA", "dep": "10:00", "to": "HND", "arr": ""}]


def test_blank_arrival_stays_transit_until_day_one_japan_time(core):
    pg = core(("core.js", "flights.js"))
    r = ph(pg, "2026-10-19T08:00:00Z", BLANK_ARR, first="2026-10-20")   # in the air, arrival unknown
    assert r["phase"] == "transit" and r["arrive"] is None and r["leg"]["no"] == "MU575"
    r = ph(pg, "2026-10-19T15:01:00Z", BLANK_ARR, first="2026-10-20")   # past day 1, 00:00 JST
    assert r["phase"] == "live" and r["leg"] is None and r["arrive"] is None


def test_shanghai_stop_sits_one_hour_later_in_japan_time(core):
    pg = core(("core.js",))
    r = pg.evaluate("""Core.plan({ev: [
      {id: 'a', s: '07:00', e: '07:30', t: 'Маглев', st: 'planned', cat: 'transport', off: 480},
      {id: 'b', s: '09:00', e: '10:00', t: 'Токио', st: 'planned', cat: 'activity'}]}, null, {}, null)
      .map(e => [e.id, e.ns, e.ne, Core.localMin(e, e.ns)])""")
    assert r[0] == ["a", 480, 510, 420]        # 07:00 Shanghai = 08:00 Japan; shown as 07:00
    assert r[1][1] == 540
