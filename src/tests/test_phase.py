import json
from conftest import ROOT

LEGS = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))["flights"]
F, L = "2026-10-17", "2026-10-27"


def ph(pg, iso_utc, legs=LEGS):
    return pg.evaluate(f"Flights.phase(Date.parse('{iso_utc}'), {json.dumps(legs)}, '{F}', '{L}')")


def test_phases_follow_the_flights(core):
    pg = core(("core.js", "flights.js"))
    assert ph(pg, "2026-09-30T03:00:00Z")["phase"] == "pre"
    assert ph(pg, "2026-10-15T18:59:00Z")["phase"] == "pre"          # 23:59 on 15.10 in Almaty (+5)
    assert ph(pg, "2026-10-15T19:01:00Z")["phase"] == "departure"    # 00:01 on 16.10 in Almaty
    assert ph(pg, "2026-10-16T15:49:00Z")["phase"] == "departure"    # 20:49 in Almaty, MU6042 at 20:50
    assert ph(pg, "2026-10-16T16:00:00Z")["phase"] == "transit"      # in the air
    assert ph(pg, "2026-10-17T02:00:00Z")["phase"] == "transit"      # 10:00 in Shanghai
    assert ph(pg, "2026-10-17T12:21:00Z")["phase"] == "live"         # 21:21 in Tokyo, landed
    assert ph(pg, "2026-10-27T14:59:00Z")["phase"] == "live"         # 23:59 on 27.10 in Tokyo
    assert ph(pg, "2026-10-27T15:01:00Z")["phase"] == "post"


def test_phases_without_flights_use_the_dates(core):
    pg = core(("core.js", "flights.js"))
    assert ph(pg, "2026-10-16T14:59:00Z", [])["phase"] == "pre"      # 23:59 on 16.10 in Tokyo
    assert ph(pg, "2026-10-16T15:01:00Z", [])["phase"] == "live"
    assert ph(pg, "2026-10-27T15:01:00Z", [])["phase"] == "post"


def test_shanghai_stop_sits_one_hour_later_in_japan_time(core):
    pg = core(("core.js",))
    r = pg.evaluate("""Core.plan({ev: [
      {id: 'a', s: '07:00', e: '07:30', t: 'Маглев', st: 'planned', cat: 'transport', off: 480},
      {id: 'b', s: '09:00', e: '10:00', t: 'Токио', st: 'planned', cat: 'activity'}]}, null, {}, null)
      .map(e => [e.id, e.ns, e.ne, Core.localMin(e, e.ns)])""")
    assert r[0] == ["a", 480, 510, 420]        # 07:00 Shanghai = 08:00 Japan; shown as 07:00
    assert r[1][1] == 540
