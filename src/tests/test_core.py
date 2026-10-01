DAY = {"n": 2, "ev": [
    {"id": "e0", "s": "10:45", "e": "11:15", "t": "Катер", "cat": "activity", "st": "flex"},
    {"id": "e1", "s": "12:30", "e": "13:00", "t": "Обед", "cat": "food", "st": "planned"},
    {"id": "e2", "s": "13:00", "e": "15:45", "t": "Oishi Park", "cat": "activity", "st": "planned", "walk": 5, "ride": 25},
    {"id": "e3", "s": "15:45", "e": "16:15", "t": "Свободно", "cat": "activity", "st": "flex"},
    {"id": "e4", "s": "17:00", "e": "18:40", "t": "Кавагутико → Мисима", "cat": "transport", "st": "input",
     "walk": 5, "ride": 25, "buf": 15},
]}


def run(pg, day, now, marks=None, iso="2026-10-18"):
    return pg.evaluate("([d, n, m, i]) => Core.plan(d, n, m, i)", [day, now, marks or {}, iso])


def by_id(evs):
    return {e["id"]: e for e in evs}


def test_formatters(core):
    pg = core()
    assert pg.evaluate("[Core.toMin('06:45'), Core.hm(405), Core.cd(171), Core.dur(65), Core.ddmmyyyy('2026-10-18')]") == \
        [405, "06:45", "2 ч 51", "1 ч 05 мин", "18.10.2026"]
    assert pg.evaluate("Number.isNaN(Core.toMin('xx'))") is True


def test_anchor_never_moves_and_flex_is_cut_first(core):
    pg = core()
    evs = by_id(run(pg, DAY, 16 * 60 + 5, {"delay": {"e2": 30}}))
    assert evs["e4"]["ns"] == 17 * 60                 # the bus stays
    assert evs["e3"]["auto"] is True                  # free time goes first
    assert evs["e2"]["ne"] == 16 * 60 + 15            # Oishi trimmed so we leave at 16:15
    assert evs["e4"]["leave"] == 16 * 60 + 15
    assert evs["e0"]["cut"] == 0                      # the past cruise is not touched


def test_unpayable_gap_between_anchors_shows_conflict_not_move(core):
    pg = core()
    day = {"n": 5, "ev": [
        {"id": "a", "s": "16:00", "e": "16:50", "t": "Дзюдо", "cat": "event", "st": "fixed"},
        {"id": "b", "s": "17:00", "e": "18:40", "t": "Поезд", "cat": "transport", "st": "input", "walk": 20, "ride": 10, "buf": 15}]}
    evs = by_id(run(pg, day, 15 * 60))
    assert evs["b"]["ns"] == 17 * 60                  # the train does not move
    assert evs["b"]["conflict"] == 35                 # 16:50 + 45 min to get there - 17:00


def test_delay_of_current_stop_is_paid_back_from_itself(core):
    pg = core()
    evs = by_id(run(pg, DAY, 13 * 60, {"delay": {"e2": 300}}))
    assert evs["e4"]["ns"] == 17 * 60 and evs["e4"]["conflict"] == 0
    assert evs["e2"]["ne"] == 16 * 60 + 15


def test_date_bound_event_off_its_date_needs_input(core):
    pg = core()
    day = {"n": 5, "ev": [{"id": "j", "s": "16:00", "e": "18:30", "t": "Дзюдо", "cat": "event", "st": "fixed",
                           "bound": "2026-10-21"}]}
    on = run(pg, day, None, iso="2026-10-21")[0]
    off = run(pg, day, None, iso="2026-10-22")[0]
    assert (on["st"], on["off"]) == ("fixed", False)
    assert (off["st"], off["off"]) == ("input", True)


def test_plan_tolerates_odd_events(core):
    pg = core()
    day = {"n": 1, "ev": [{"id": "a", "s": "24:30", "t": "поздно", "cat": "activity", "st": "planned"},
                          {"id": "b", "t": "без времени", "cat": "activity", "st": "planned"},
                          {"id": "c", "s": "09:00", "t": "без конца", "cat": "activity", "st": "planned", "lat": ""}]}
    evs = by_id(run(pg, day, 600))
    assert evs["b"]["bad"] is True
    assert evs["c"]["ne"] == 9 * 60 + 15
    assert pg.evaluate("Core.plan({n:1, ev:[]}, 600, {}, '2026-10-17').length") == 0


def test_urgent_prefers_anchor_and_escalates(core):
    pg = core()
    evs = run(pg, DAY, 13 * 60 + 24)
    calm = pg.evaluate("([e, n]) => Core.urgent(e, n)", [evs, 13 * 60 + 24])
    assert calm["ev"]["id"] == "e4" and calm["state"] == "calm" and calm["leaveIn"] == 171
    soon = pg.evaluate("([e, n]) => Core.urgent(e, n)", [run(pg, DAY, 16 * 60 + 5), 16 * 60 + 5])
    assert soon["state"] == "soon"
    go = pg.evaluate("([e, n]) => Core.urgent(e, n)", [run(pg, DAY, 16 * 60 + 18), 16 * 60 + 18])
    assert go["state"] == "go"


def test_capsule_hidden_without_future_event(core):
    pg = core()
    assert pg.evaluate("([e, n]) => Core.urgent(e, n)", [run(pg, DAY, 23 * 60), 23 * 60]) is None
    assert pg.evaluate("([e]) => Core.urgent(e, null)", [run(pg, DAY, None)]) is None


def test_theme_for(core):
    pg = core()
    sun = {"rise": 353, "set": 1027}
    assert pg.evaluate("([s]) => [Core.themeFor(804, s, 'auto'), Core.themeFor(1170, s, 'auto'), Core.themeFor(300, s, 'auto'),"
                       " Core.themeFor(1170, s, 'light'), Core.themeFor(804, null, 'auto')]", [sun]) == \
        ["light", "dark", "dark", "light", "light"]


def test_sun_times_kawaguchiko(core):
    pg = core()
    r = pg.evaluate("Core.sunTimes('2026-10-18', 35.50, 138.76)")
    assert 5 * 60 + 40 <= r["rise"] <= 6 * 60 and 17 * 60 <= r["set"] <= 17 * 60 + 15


def test_valid_trip_and_safe_url(core):
    pg = core()
    assert pg.evaluate("Core.validTrip({days:[{n:1, ev:[{s:'09:00', t:'a'}]}]})") is True
    assert pg.evaluate("Core.validTrip({days:[{n:1, ev:[{s:'<img onerror=1>', t:'a'}]}]})") is False
    assert pg.evaluate("Core.validTrip({days:[]})") is False
    assert pg.evaluate("[Core.safeUrl('https://a.jp'), Core.safeUrl('javascript:alert(1)'), Core.safeUrl('http://a')]") == \
        ["https://a.jp", "", ""]


def test_day_progress(core):
    pg = core()
    evs = run(pg, DAY, None)
    assert pg.evaluate("([e]) => [Core.dayProgress(e, null), Core.dayProgress(e, 0), Core.dayProgress(e, 2000)]", [evs]) == [0, 0, 1]


def test_cut_only_what_reaches_the_anchor(core):
    """Flex 10–11, planned 12–13, fixed flight 13:30 with an hour to get there: the free hour between
    them already covers A, so B is shortened by 30 and nothing moves before its own start."""
    pg = core()
    r = pg.evaluate("""() => Core.plan({ ev: [
      { id: 'a', s: '10:00', e: '11:00', t: 'A', st: 'flex', cat: 'activity' },
      { id: 'b', s: '12:00', e: '13:00', t: 'B', st: 'planned', cat: 'activity' },
      { id: 'f', s: '13:30', e: '15:00', t: 'Flight', st: 'fixed', cat: 'transport', ride: 60 } ] }, null, {}, null)
      .map(e => [e.id, e.ns, e.ne, e.cut, e.conflict])""")
    a, b, f = r
    assert a[1:4] == [600, 660, 0]
    assert b[1] == 720 and b[2] == 750 and b[3] == 30
    assert f[4] == 0
