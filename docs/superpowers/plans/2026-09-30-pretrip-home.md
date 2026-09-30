# Pre-trip Home (version 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** «Сейчас» knows the trip phase: before departure it shows the countdown, one urgent to-do and readiness in four groups; on departure day the flight; in transit «Первые сутки» (with Shanghai in Shanghai time); after landing the live screen — version 1 without Supabase.

**Architecture:** A pure `Flights.phase()` decides the phase from the flight legs and trip dates; `Core.plan` learns per-stop time-zone offsets (`off`) so Shanghai stops sit correctly in the Japan-time planner; a pure `Prep` module builds the readiness list (four groups) from the trip's bookings + recipes + a baked list `prep`, applies auto ticks and picks the one «Сначала это». Local ticks and own items live in `localStorage`. `RENDER.now` branches by phase; the old time preview moves to «День» behind an explicit `S.preview` flag.

**Tech Stack:** Vanilla JS modules glued by `src/build_guide.py`; Python data in `src/today_data.py` → `trips/*.json`; pytest + Playwright (sync) in `.venv`.

**Spec:** `docs/superpowers/specs/2026-09-30-pretrip-home-design.md`

## Global Constraints

- Phases: `pre` until the day of the first departure (origin airport time), `departure` that day until take-off, `transit` until the first arrival in Japan, `live` in the trip days, `post` after the last day; no flights → `pre` before day 1 (Japan time), `post` after the last day.
- Pre screen order: title «Япония» + «через N дней»; hero countdown; «Сначала это»; readiness 2×2; «Первые сутки»; route line; weather/sun row only from T-7; items 1–4 above the fold on iPhone 13 (390×844).
- Countdown text: «N дней» until T-2, then «1 д 5 ч», in the last 24 h «5:12».
- Capsule before the trip: hidden unless a deadline (`opens`) is < 48 h away; day segments hidden.
- Readiness groups, in this order and with these titles: «Билеты и отели», «Телефон», «Деньги и документы», «Сборы».
- «Сначала это»: open items doable now (`opens` passed or absent, `from` passed), earliest `due` first; ties: tickets > money > phone > packing; packing never before T-3; closed sales are not picked; all done → «Всё готово ✓».
- Auto ticks: `installed` (Home Screen app), `booking:<id>` (booking bought), `ticket:<id>` (ticket attached) — labelled «проверено приложением».
- Progress is private: ticks and own items only on this phone (`japan2026.prep.v1`) in version 1.
- Stop time zones: `off` = minutes east of UTC for the stop's `s`/`e` (Shanghai 480); planner time = `toMin(s) + (540 − off)`; the UI shows the original time with «по Шанхаю».
- Nothing private in the trip file (no statuses, no seats); texts via `esc()`, links only `https:`.
- UI copy Russian; tap targets ≥ 44 px; text ≥ 15 px for body; contrast AA.
- All existing tests stay green; tests that drive «Сейчас» with a preview time set `preview: true` explicitly.

## Review Focus

1. The phone's clock/time zone is Almaty while the trip logic is Japan/Shanghai time — phases and the countdown must not shift by the zone difference (test in Task 2).
2. A traveller deletes all flights in «Мои рейсы» — the home falls back to date-based phases without errors (Task 2 + Task 6).
3. An item whose sales open tomorrow is never shown as the urgent to-do today, but the capsule shows it when < 48 h (Task 4 + Task 6).
4. Own items with HTML in the title render as text (Task 5).
5. After the trip (`post`) the home shows a summary instead of a stale countdown (Task 6).

---

## File Structure

| File | Responsibility |
|---|---|
| `src/today/flights.js` | + `Flights.phase(nowMs, legs, firstISO, lastISO)` |
| `src/today/core.js` | `plan()` honours `off`; + `Core.shiftOf(e)`, `Core.localMin(e, min)` |
| `src/today/prep.js` (new) | pure `Prep`: `items()`, `groups()`, `first()`, `opening()` |
| `src/today/ui/prep.js` (new) | «Подготовка» sheet, local ticks and own items |
| `src/today/ui/now.js` | phase branching; pre/departure/transit/post layouts |
| `src/today/ui/shell.js` | header by phase (title, capsule, segments) |
| `src/today/ui/day.js` | shows `off` stops in local time; «▶ Как «Сейчас»» preview switch |
| `src/today/store.js` | `S.preview`; `clock()` uses preview only when `S.preview` |
| `src/today_data.py` | Shanghai stops (own trip only), `prep` list, `only="own"` events |
| `src/build_guide.py` | module list (`prep.js` after `flights.js`; `ui/prep.js` before `ui/now.js`) |
| `src/tests/conftest.py` | a state with `prevDay` and no `preview` gets `preview: true` (keeps old tests meaning) |

---

### Task 1: Bring recipes and parts onto main

**Files:** Modify via cherry-pick: `src/today_data.py`, `trips/*.json`, `src/tests/test_group_data.py`, `src/stops.json`

**Interfaces:**
- Produces: `trips/miras-aikosh.json` has `recipes: [{bk, what, site, url, opens, opens_note, buy_by, price_pp, tips}]` and `parts`.

- [ ] **Step 1:** After group-planning Task 3 is reviewed on `group-stage1`, note its commit(s): `git log --oneline main..group-stage1 -- src/today_data.py`.
- [ ] **Step 2:** On `main`: `git cherry-pick <task-3 commits>`. Conflicts only in generated `trips/*.json`/`src/stops.json`: resolve by regenerating (`cd src && python3 today_data.py`), `git add`, `git cherry-pick --continue`.
- [ ] **Step 3:** Run `.venv/bin/pytest src/tests/test_group_data.py -q` → PASS; full suite → green.
- [ ] **Step 4:** (the cherry-pick is the commit). Later, when `group-stage1` rebases onto `main`, git drops the duplicate.

### Task 2: Phases and stop time zones (pure)

**Files:**
- Modify: `src/today/flights.js`, `src/today/core.js`
- Test: `src/tests/test_phase.py`

**Interfaces:**
- Produces:
  - `Flights.phase(nowMs, legs, firstISO, lastISO) -> {phase: 'pre'|'departure'|'transit'|'live'|'post', dep: ms|null, arrive: ms|null, leg: leg|null}` — `legs` = any list `Flights.cleanList` accepts; `firstISO`/`lastISO` = trip day 1 and last day dates.
  - `Core.shiftOf(e) -> minutes` = `Number.isFinite(+e.off) ? 540 - +e.off : 0`.
  - `Core.localMin(e, min) -> min - Core.shiftOf(e)` (for display).
  - `Core.plan` uses `toMin(s) + shiftOf(e)` and `toMin(e) + shiftOf(e)`.

- [ ] **Step 1: Tests** (`src/tests/test_phase.py`)

```python
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
```

- [ ] **Step 2: Run — fails** (`Flights.phase is not a function`).
- [ ] **Step 3: Implement.** In `core.js` add near `travel`:

```js
  /* a stop may keep its times in another zone (Shanghai: off = 480); the planner works in Japan time */
  const shiftOf = e => (e && e.off != null && e.off !== '' && Number.isFinite(+e.off)) ? 540 - +e.off : 0;
  const localMin = (e, min) => min - shiftOf(e);
```

in `plan()` replace `const s = toMin(e.s), en0 = e.e ? toMin(e.e) : NaN;` with
`const sh = shiftOf(e), s = toMin(e.s) + sh, en0 = e.e ? toMin(e.e) + sh : NaN;` and export `shiftOf, localMin`.

In `flights.js` add before the `return`:

```js
  /* where the traveller is: before the trip, departure day, in transit, in Japan, after */
  const JST = 540;
  const dayStart = (iso, off) => Date.parse(iso + 'T00:00:00Z') - off * 60000;
  function phase(nowMs, list, firstISO, lastISO) {
    const legs = cleanList(list);
    const end = dayStart(lastISO, JST) + 864e5;
    if (nowMs >= end) return { phase: 'post', dep: null, arrive: null, leg: null };
    if (!legs.length) return { phase: nowMs < dayStart(firstISO, JST) ? 'pre' : 'live', dep: null, arrive: null, leg: null };
    const first = legs[0], t0 = times(first);
    const o = offsetAt(first.frm, t0.dep, first.frmOff) || 0;
    const toJapan = legs.find(l => JAPAN.has(l.to) && times(l).dep >= t0.dep);
    const arrive = toJapan ? times(toJapan).arr : null;
    if (nowMs < dayStart(first.date, o)) return { phase: 'pre', dep: t0.dep, arrive, leg: first };
    if (nowMs < t0.dep) return { phase: 'departure', dep: t0.dep, arrive, leg: first };
    if (arrive && nowMs < arrive) return { phase: 'transit', dep: t0.dep, arrive, leg: legs.find(l => times(l).dep > nowMs) || null };
    return { phase: 'live', dep: t0.dep, arrive, leg: null };
  }
```

and add `phase` to the returned object.

- [ ] **Step 4: Run** `.venv/bin/pytest src/tests/test_phase.py src/tests/test_core.py src/tests/test_flights.py -q` → PASS; full suite green.
- [ ] **Step 5: Commit** `git add src/today/flights.js src/today/core.js src/tests/test_phase.py && git commit -m "Trip phases from flights and dates; stops can keep their own time zone"`

### Task 3: Shanghai stops and the preparation list in the trip data

**Files:**
- Modify: `src/today_data.py`, `trips/*.json` (regenerated), `src/stops.json`
- Test: `src/tests/test_prep_data.py`

**Interfaces:**
- Produces in trip JSON: day 1 stops with `off: 480` (own trip only); `prep: [{id, group, title, note?, url?, due?, from?, auto?}]` (both trips; Shanghai items own trip only).

- [ ] **Step 1: Tests**

```python
import json
from conftest import ROOT

OWN = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
TPL = json.loads((ROOT / "trips" / "template.json").read_text(encoding="utf-8"))
GROUPS = {"tickets", "phone", "money", "packing"}


def test_shanghai_day_only_in_our_trip():
    d1 = OWN["days"][0]["ev"]
    sh = [e for e in d1 if e.get("off") == 480]
    assert [e["s"] for e in sh] == ["05:30", "07:00", "07:30", "08:15", "10:45", "12:30", "14:15"]
    assert any(e["st"] == "fixed" and e["s"] == "14:15" for e in sh)          # back at the airport: an anchor
    assert not any(e.get("off") for d in TPL["days"] for e in d["ev"])


def test_prep_list_is_complete_and_public_safe():
    for t in (OWN, TPL):
        ids = [p["id"] for p in t["prep"]]
        assert len(ids) == len(set(ids)) and {p["group"] for p in t["prep"]} <= GROUPS
        assert all(p.get("url", "https://").startswith("https://") for p in t["prep"])
    own_titles = " ".join(p["title"] for p in OWN["prep"])
    assert "Шанхай" in own_titles and "Шанхай" not in " ".join(p["title"] for p in TPL["prep"])
    assert any(p.get("auto") == "installed" for p in OWN["prep"])
    vjw = next(p for p in OWN["prep"] if "Visit Japan Web" in p["title"])
    assert vjw["from"] == "2026-10-10"                                           # T-6
    assert "09A" not in json.dumps(OWN, ensure_ascii=False)
```

- [ ] **Step 2: Run — fails** (`KeyError: 'prep'`).
- [ ] **Step 3: Implement** in `src/today_data.py`:
  - `E(...)` accepts `only=None`; `trip(personal)` skips events with `only == "own"` when `personal` is False (strip the `only` key from output).
  - Places: `"pvg": (31.1443, 121.8083, None, None)`, `"maglev": (31.2034, 121.5578, None, None)`, `"bund": (31.2400, 121.4900, None, None)`, `"yuyuan": (31.2272, 121.4921, None, None)` (no map pins: stop name `None`).
  - Day 1 `ev` gets, before the HND arrival (all with `off=480, only="own"`):

```python
   E("05:30", "06:45", "Шанхай: прилёт, паспортный контроль, выход в город", "pvg", "transport", "fixed", off=480, only="own",
     mode="Самолёт MU6042", note="Безвиз для граждан РК до 30 дней — проверить. Уточнить, сквозной ли багаж до Ханэды."),
   E("07:00", "07:30", "Маглев до Longyang Rd", "maglev", "transport", "planned", off=480, only="own", mode="Maglev",
     note="Ходит с 06:45, ~50 юаней — проверить."),
   E("07:30", "08:15", "Метро до Бунда", "bund", "transport", "planned", off=480, only="own", mode="Метро, линия 2", walk=10),
   E("08:15", "10:30", "Набережная Бунд, Nanjing Road", "bund", "activity", "planned", off=480, only="own", km=3.0),
   E("10:45", "12:15", "Сад Юйюань, старый город, обед", "yuyuan", "activity", "planned", off=480, only="own", walk=20, km=1.5),
   E("12:30", "13:45", "Обратно в Пудун: метро + маглев", "pvg", "transport", "planned", off=480, only="own", mode="Метро + Maglev"),
   E("14:15", "17:15", "В аэропорту: регистрация MU575, досмотр, посадка", "pvg", "transport", "fixed", off=480, only="own",
     note="Не позже 14:15 — вылет в 17:15, международный рейс."),
```

  - `PREP` list (Appendix B of the spec) with ids and groups; `due`/`from` dates:

```python
PREP = [
    dict(id="p-home", group="phone", title="Приложение на экране «Домой»", auto="installed", note="Поделиться → На экран «Домой». Сделайте до того, как прикреплять билеты."),
    dict(id="p-suica", group="phone", title="Suica в Wallet", note="Wallet → + → Проездной → Suica. Проверьте казахстанскую карту заранее."),
    dict(id="p-esim", group="phone", title="eSIM или роуминг", due="2026-10-14"),
    dict(id="p-maps", group="phone", title="Офлайн-карты Токио, Киото, Нагои", due="2026-10-15"),
    dict(id="p-translate", group="phone", title="Google Переводчик: японский офлайн", due="2026-10-15"),
    dict(id="p-passport", group="money", title="Паспорт и японская виза на руках", due="2026-10-14"),
    dict(id="p-insurance", group="money", title="Страховка", due="2026-10-14"),
    dict(id="p-card", group="money", title="Карта работает за границей", note="Предупредите банк; проверьте оплату в иенах.", due="2026-10-14"),
    dict(id="p-cash", group="money", title="Наличные: план на первые дни", note="Менять в World Currency Shop, только если ≥ ¥155 за $1; иначе — 7-Bank."),
    dict(id="p-vjw", group="money", title="Visit Japan Web: QR иммиграции и таможни", url="https://www.vjw.digital.go.jp/", **{"from": "2026-10-10"}, due="2026-10-15",
         note="Заполнить за 1–6 дней до прилёта — проверить сроки."),
    dict(id="p-offline", group="money", title="Брони сохранены офлайн", note="Скриншоты или PDF — во вкладке «Брони»."),
    dict(id="p-adapter", group="packing", title="Переходник тип A"),
    dict(id="p-powerbank", group="packing", title="Пауэрбанк ≤ 100 Wh — в ручной клади"),
    dict(id="p-shoes", group="packing", title="Удобная обувь"),
    dict(id="p-umbrella", group="packing", title="Зонт или дождевик"),
    dict(id="p-warm", group="packing", title="Тёплый слой", note="Ночью у Фудзи около 8°."),
    dict(id="p-meds", group="packing", title="Лекарства"),
    dict(id="p-snacks", group="packing", title="Халяль-перекус"),
    dict(id="p-space", group="packing", title="Место для покупок / курьер чемоданов"),
]
PREP_OWN = [
    dict(id="p-sh-bags", group="money", title="Шанхай: уточнить, сквозной ли багаж до Ханэды", due="2026-10-10"),
    dict(id="p-sh-visa", group="money", title="Шанхай: безвиз для граждан РК — проверить", due="2026-10-10"),
    dict(id="p-sh-pay", group="money", title="Шанхай: юани или Alipay/WeChat Pay с иностранной картой", due="2026-10-14"),
]
```

and emit `prep=PREP + (PREP_OWN if personal else [])` in `trip()`. Regenerate (`cd src && python3 today_data.py`).

- [ ] **Step 4: Run** tests → PASS; full suite green (existing day-1 tests use the template or day 2).
- [ ] **Step 5: Commit** `git add src/today_data.py trips src/stops.json src/tests/test_prep_data.py && git commit -m "Trip data: Shanghai layover in Shanghai time and the preparation list"`

### Task 4: `Prep` — readiness model (pure)

**Files:**
- Create: `src/today/prep.js`
- Modify: `src/build_guide.py` (module after `flights.js`), `src/tests/conftest.py` (`core()` exposes `window.Prep` when `prep.js` loaded)
- Test: `src/tests/test_prep_model.py`

**Interfaces:**
- Produces `Prep`:
  - `Prep.items(trip, local, auto) -> [item]` — `item = {id, group, title, note, url, due, opens, from, auto, done, own, checked: 'auto'|'me'|null}`; tickets group = one item per trip booking (`id: 'bk:<bk>'`, title `Купить: <booking.t>` or the recipe's `what`, `url/opens/buy_by→due` from the recipe, `auto: 'booking:<bk>'`) plus `prep` items of group tickets; other groups from `trip.prep`; own items from `local.own`. `local = {done: {id: true}, own: [{id, group, title}]}`; `auto = {installed: bool, booked: Set<bk>, tickets: Set<bk>}`.
  - `Prep.groups(items) -> [{key, title, done, total}]` in the fixed order.
  - `Prep.first(items, nowMs, departMs) -> {item|null, rest: int}`.
  - `Prep.opening(items, nowMs) -> item|null` — the soonest `opens` in `(now, now + 48 h]`.
  - `Prep.TITLES = {tickets: 'Билеты и отели', phone: 'Телефон', money: 'Деньги и документы', packing: 'Сборы'}`.

- [ ] **Step 1: Tests**

```python
import json
from conftest import ROOT

OWN = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
DEP = "Date.UTC(2026, 9, 16, 15, 50)"


def P(pg, js, local=None, auto=None):
    local = local or {"done": {}, "own": []}
    auto = auto or {"installed": False, "booked": [], "tickets": []}
    return pg.evaluate(f"""(() => {{ const T = {json.dumps(OWN)}; const L = {json.dumps(local)};
      const A = {{installed: {json.dumps(auto['installed'])}, booked: new Set({json.dumps(auto['booked'])}), tickets: new Set({json.dumps(auto['tickets'])})}};
      const I = Prep.items(T, L, A); {js} }})()""")


def test_groups_count_and_auto_ticks(core):
    pg = core(("core.js", "flights.js", "prep.js"))
    g = P(pg, "return Prep.groups(I);", auto={"installed": True, "booked": ["bus_mishima"], "tickets": []})
    assert [x["title"] for x in g] == ["Билеты и отели", "Телефон", "Деньги и документы", "Сборы"]
    tickets = g[0]
    fixed = sum(b["st"] == "fixed" for b in OWN["bookings"])
    assert tickets["total"] == len(OWN["bookings"]) and tickets["done"] == fixed + 1   # + the one the app sees as bought
    phone = g[1]
    assert phone["done"] == 1                                    # installed on the Home Screen, ticked by the app
    it = P(pg, "return I.find(i => i.id === 'p-home');", auto={"installed": True, "booked": [], "tickets": []})
    assert it["checked"] == "auto"


def test_first_picks_the_nearest_doable_deadline(core):
    pg = core(("core.js", "flights.js", "prep.js"))
    f = P(pg, f"return Prep.first(I, Date.UTC(2026, 8, 30, 3), {DEP});")
    assert f["item"]["due"] == "2026-10-10" and f["rest"] > 5    # the earliest deadline that can be done today
    assert f["item"]["id"] != "bk:sky"                          # Shibuya Sky: sales open 11.10 — not today
    op = P(pg, "return Prep.opening(I, Date.UTC(2026, 9, 9, 16));")   # 10.10 01:00 Tokyo → sales in < 48 h
    assert op and op["id"] == "bk:sky"
    assert P(pg, "return Prep.opening(I, Date.UTC(2026, 8, 30, 3));") is None


def test_packing_waits_until_three_days_before(core):
    pg = core(("core.js", "flights.js", "prep.js"))
    done_all_but_packing = {"done": {}, "own": []}
    ids = P(pg, "return I.filter(i => i.group !== 'packing').map(i => i.id);")
    done_all_but_packing["done"] = {i: True for i in ids}
    f = P(pg, f"return Prep.first(I, Date.UTC(2026, 9, 1), {DEP});", local=done_all_but_packing)
    assert f["item"] is None                                     # 15 days out: packing isn't urgent yet
    f = P(pg, f"return Prep.first(I, Date.UTC(2026, 9, 14), {DEP});", local=done_all_but_packing)
    assert f["item"]["group"] == "packing"


def test_own_items_and_everything_done(core):
    pg = core(("core.js", "flights.js", "prep.js"))
    local = {"done": {}, "own": [{"id": "own-1", "group": "packing", "title": "Подарки друзьям"}]}
    it = P(pg, "return I.find(i => i.id === 'own-1');", local=local)
    assert it["own"] is True and it["group"] == "packing"
    all_ids = P(pg, "return I.map(i => i.id);", local=local)
    local["done"] = {i: True for i in all_ids}
    f = P(pg, f"return Prep.first(I, Date.UTC(2026, 9, 14), {DEP});", local=local)
    assert f == {"item": None, "rest": 0}
```

- [ ] **Step 2: Run — fails.**
- [ ] **Step 3: Implement** `src/today/prep.js`:

```js
/* ---------- readiness before the trip: four groups, one «first thing», nothing invented — pure ---------- */
const Prep = (() => {
  const ORDER = ['tickets', 'money', 'phone', 'packing'];               // tie-break for «Сначала это»
  const SHOW = ['tickets', 'phone', 'money', 'packing'];                // display order
  const TITLES = { tickets: 'Билеты и отели', phone: 'Телефон', money: 'Деньги и документы', packing: 'Сборы' };
  const at = v => { const t = v ? Date.parse(v.length === 10 ? v + 'T00:00:00+09:00' : v) : NaN; return Number.isFinite(t) ? t : null; };

  function items(trip, local, auto) {
    const recipes = new Map((trip.recipes || []).map(r => [r.bk, r]));
    const done = (local && local.done) || {};
    const out = (trip.bookings || []).map(b => {
      const r = recipes.get(b.id) || {};
      return { id: 'bk:' + b.id, group: 'tickets', title: 'Купить: ' + (r.what || b.t), note: r.tips || b.when || '',
               url: r.url || null, due: r.buy_by || null, opens: r.opens || null, from: null, auto: 'booking:' + b.id,
               bought: b.st === 'fixed' };
    });
    (trip.prep || []).forEach(p => out.push({ note: '', url: null, due: null, opens: null, from: null, auto: null, ...p }));
    ((local && local.own) || []).forEach(o => out.push({ id: o.id, group: SHOW.includes(o.group) ? o.group : 'packing',
      title: String(o.title || ''), note: '', url: null, due: null, opens: null, from: null, auto: null, own: true }));
    return out.map(i => {
      let checked = null;
      if (i.auto === 'installed' && auto.installed) checked = 'auto';
      else if (i.auto && i.auto.startsWith('booking:') && (i.bought || auto.booked.has(i.auto.slice(8)))) checked = 'auto';
      else if (i.auto && i.auto.startsWith('ticket:') && auto.tickets.has(i.auto.slice(7))) checked = 'auto';
      else if (done[i.id]) checked = 'me';
      return { ...i, own: !!i.own, done: !!checked, checked };
    });
  }
  const groups = list => SHOW.map(k => ({ key: k, title: TITLES[k], done: list.filter(i => i.group === k && i.done).length,
                                          total: list.filter(i => i.group === k).length }));
  function first(list, nowMs, departMs) {
    const open = list.filter(i => !i.done);
    const doable = open.filter(i => (!at(i.opens) || at(i.opens) <= nowMs) && (!at(i.from) || at(i.from) <= nowMs)
      && (i.group !== 'packing' || !departMs || nowMs >= departMs - 3 * 864e5));
    doable.sort((a, b) => (at(a.due) ?? Infinity) - (at(b.due) ?? Infinity) || ORDER.indexOf(a.group) - ORDER.indexOf(b.group));
    const item = doable[0] || null;
    return { item, rest: item ? open.length - 1 : 0 };
  }
  function opening(list, nowMs) {
    const soon = list.filter(i => !i.done && at(i.opens) && at(i.opens) > nowMs && at(i.opens) <= nowMs + 48 * 3600e3);
    return soon.sort((a, b) => at(a.opens) - at(b.opens))[0] || null;
  }
  return { items, groups, first, opening, TITLES };
})();
```

Note: the «rest» when nothing is doable but items are open is `0`; the home then shows «Сейчас делать нечего» with the next opening date (Task 6).

- [ ] **Step 4: Run** tests → PASS; full suite green.
- [ ] **Step 5: Commit** `git add src/today/prep.js src/build_guide.py src/tests/conftest.py src/tests/test_prep_model.py && git commit -m "Readiness model: four groups, auto ticks, one first thing"`

### Task 5: «Подготовка» sheet — ticks and own items on the phone

**Files:**
- Create: `src/today/ui/prep.js`
- Modify: `src/build_guide.py` (module before `ui/now.js`), `src/today/components.css`
- Test: `src/tests/test_prep_sheet.py`

**Interfaces:**
- Consumes: `Prep.*`, `Ios.standalone()`, `planDoc()` if defined else `T`, `bookingById`, `haveTicket`, `sheet`, `closeSheet`, `twoTap`, `icon`, `esc`, `fld`.
- Produces: `prepLocal() -> {done, own}` (key `japan2026.prep.v1`), `prepItems() -> [item]`, `openPrep(group?)` (sheet `#tcPrep`, sections `[data-group]`, items `.tc-prep-item[data-id]` with `input[type=checkbox][switch][data-prep]`, `[data-prep-add="<group>"]` → `#prAddTitle` + `#prAddGo`, own items have `[data-prep-del]`).

- [ ] **Step 1: Tests**

```python
import json
from conftest import ROOT

OWN = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))


def home(app, **kw):
    return app(trip=OWN, state={"prevDay": 2, "prevTime": "13:24", "preview": False}, **kw)


def test_tick_add_and_delete_own_item(app):
    a = home(app)
    a.page.evaluate("openPrep('phone')")
    s = a.page.locator("#tcSheet")
    s.locator(".tc-prep-item[data-id='p-suica'] .tc-check").click()
    local = json.loads(a.page.evaluate("localStorage.getItem('japan2026.prep.v1')"))
    assert local["done"]["p-suica"] is True
    s.locator("[data-prep-add='packing']").click()
    a.page.fill("#prAddTitle", '<img src=x onerror="window.__pwned=1">Подарки')
    a.page.click("#prAddGo")
    item = a.page.locator(".tc-prep-item", has_text="Подарки")
    assert item.count() == 1 and a.page.evaluate("window.__pwned") is None
    item.locator("[data-prep-del]").click(); item.locator("[data-prep-del]").click()
    assert a.page.locator(".tc-prep-item", has_text="Подарки").count() == 0
    a.page.reload()
    a.page.evaluate("openPrep('phone')")
    assert a.page.locator(".tc-prep-item[data-id='p-suica'] input").is_checked()


def test_auto_items_are_labelled_and_locked(app):
    a = home(app)
    a.page.evaluate("openPrep('tickets')")
    fixed = next(b["id"] for b in OWN["bookings"] if b["st"] == "fixed")
    row = a.page.locator(f".tc-prep-item[data-id='bk:{fixed}']")
    assert "проверено приложением" in row.inner_text()
    assert row.locator("input").is_disabled()
    for b in a.page.locator("#tcSheet button, #tcSheet .tc-check").all():
        assert b.bounding_box()["height"] >= 44
```

- [ ] **Step 2: Run — fails.**
- [ ] **Step 3: Implement** `src/today/ui/prep.js`:

```js
/* ---------- «Подготовка»: the readiness list, ticks and own items kept on this phone ---------- */
const PREP_KEY = 'japan2026.prep.v1';
function prepLocal() {
  try { const j = JSON.parse(localStorage.getItem(PREP_KEY) || 'null'); if (j && typeof j === 'object') return { done: j.done || {}, own: Array.isArray(j.own) ? j.own : [] }; } catch (e) {}
  return { done: {}, own: [] };
}
const prepSave = l => { try { localStorage.setItem(PREP_KEY, JSON.stringify(l)); } catch (e) {} };
function prepItems() {
  const trip = typeof planDoc === 'function' ? planDoc() : T;
  const booked = new Set((trip.bookings || []).filter(b => b.st === 'fixed').map(b => b.id));
  return Prep.items(trip, prepLocal(), { installed: Ios.standalone(), booked, tickets: new Set(Object.keys(haveTicket || {})) });
}
function openPrep(focus) {
  const list = prepItems(), dm = v => v ? Core.ddmmyyyy(v.slice(0, 10)).slice(0, 5) : '';
  const row = i => `<div class="tc-prep-item${i.done ? ' done' : ''}" data-id="${esc(i.id)}">
      <label class="tc-check"><input type="checkbox" switch data-prep="${esc(i.id)}"${i.done ? ' checked' : ''}${i.checked === 'auto' ? ' disabled' : ''}
        aria-label="${esc(i.title)}"><span aria-hidden="true">${icon('check')}</span></label>
      <span class="tc-prep-t"><b>${esc(i.title)}</b>${i.checked === 'auto' ? '<small>проверено приложением</small>' : i.note ? `<small>${esc(i.note)}</small>` : ''}</span>
      <span class="tc-prep-r">${i.due ? `<small>до ${esc(dm(i.due))}</small>` : ''}${Core.safeUrl(i.url) ? `<a class="tc-x" href="${Core.safeUrl(i.url)}" target="_blank" rel="noopener" aria-label="Открыть сайт">${icon('share')}</a>` : ''}
        ${i.own ? `<button type="button" class="tc-x" data-prep-del="${esc(i.id)}" aria-label="Удалить свой пункт">${icon('close')}</button>` : ''}</span></div>`;
  sheet('Подготовка', Prep.groups(list).map(g => `<section class="tc-prep-sec" data-group="${g.key}"><h3 class="tc-sech">${esc(g.title)} · ${g.done}/${g.total}</h3>
      <div class="tc-group">${list.filter(i => i.group === g.key).map(row).join('')}</div>
      <button type="button" class="tc-btn" data-prep-add="${g.key}">${icon('plus')}Свой пункт</button></section>`).join('')
    + `<p class="tc-foot">Отметки и свои пункты — только на этом телефоне.</p>`, m => {
    const sec = focus && m.querySelector(`[data-group="${focus}"]`); if (sec) sec.scrollIntoView({ block: 'start' });
    m.querySelectorAll('[data-prep]').forEach(inp => inp.addEventListener('change', () => {
      const l = prepLocal(); if (inp.checked) l.done[inp.dataset.prep] = true; else delete l.done[inp.dataset.prep];
      prepSave(l); renderShell();
    }));
    m.querySelectorAll('[data-prep-add]').forEach(b => b.addEventListener('click', () => {
      b.outerHTML = `<div class="tc-form2">${fld('prAddTitle', 'Свой пункт', '', 'text', 'maxlength="80"')}
        <button type="button" class="tc-btn primary" id="prAddGo" data-g="${b.dataset.prepAdd}">Добавить</button></div>`;
      const go = m.querySelector('#prAddGo');
      go.addEventListener('click', () => {
        const t = m.querySelector('#prAddTitle').value.trim(); if (!t) return;
        const l = prepLocal(); l.own.push({ id: 'own-' + Date.now().toString(36), group: go.dataset.g, title: t.slice(0, 80) });
        prepSave(l); openPrep(go.dataset.g); renderShell();
      });
      m.querySelector('#prAddTitle').focus();
    }));
    m.querySelectorAll('[data-prep-del]').forEach(b => b.addEventListener('click', () => twoTap(b, '?', () => {
      const l = prepLocal(); l.own = l.own.filter(o => o.id !== b.dataset.prepDel); delete l.done[b.dataset.prepDel];
      prepSave(l); openPrep(); renderShell();
    })));
  });
}
```

CSS: `.tc-prep-item` like `.tc-flrow` (min-height 56 px, grid `auto 1fr auto`), `.tc-prep-t b` 16 px/600, `small` 13 px `--sec`, `.tc-prep-item.done b` struck through and `--sec`, `.tc-prep-sec` gap 8 px.

Expose `openPrep` on `window` in the boot test hook (file: / 127.0.0.1) alongside `Api`/`renderShell`.

- [ ] **Step 4: Run** → PASS; full suite green.
- [ ] **Step 5: Commit** `git add src/today/ui/prep.js src/build_guide.py src/today/components.css src/today/boot.js src/tests/test_prep_sheet.py && git commit -m "«Подготовка»: readiness list with auto ticks and own items on the phone"`

### Task 6: «Сейчас» by phase; preview moves to «День»

**Files:**
- Modify: `src/today/store.js` (`S.preview`, `clock()`), `src/today/ui/shell.js` (`ctx()` adds `phase`; header by phase), `src/today/ui/now.js` (layouts), `src/today/ui/day.js` (`off` stops in local time; preview switch), `src/today/components.css`, `src/tests/conftest.py` (default `preview: true` when a test sets `prevDay` without `preview`)
- Test: `src/tests/test_pretrip_home.py`

**Interfaces:**
- Consumes: `Flights.phase`, `myFlights()`, `Prep.*`, `prepItems()`, `openPrep()`, `flightCardHTML`, `weatherTileHTML`, `sunTileHTML`, `Core.localMin/shiftOf`.
- Produces:
  - `clock()` → preview time only when `S.preview === true` (otherwise real Japan time; `live` false before the trip).
  - `ctx()` adds `ph = Flights.phase(Date.now(), myFlights(), dateOf(T.days[0]), dateOf(T.days[T.days.length - 1]))` unless `S.preview` (then `{phase: 'live'}`).
  - Header in `pre`: no segments; capsule only for `Prep.opening()` → `.tc-cap.soon` «<title> · продажи через H:MM»; title «Япония» + «через N дней».
  - `RENDER.now` in `pre`: `#tcCount` (hero), `#tcFirst` («Сначала это» / «Всё готово ✓» / «Сейчас делать нечего — продажи откроются …»), `#tcReady` (2×2 `button[data-ready=<group>]` → `openPrep(group)`), `#tcDay1` («Первые сутки», one line; expanded from T-1), `#tcRoute` (route line → «День» day 1), weather/sun row only when `dep − now ≤ 7 days`.
  - `departure`: `flightCardHTML` as hero + open items due before departure.
  - `transit`: «Первые сутки» expanded with the current step highlighted (from day 1 `off` stops and the flight legs).
  - `post`: «Поездка завершена» + the day count and a link to «Итоги».
  - «День»: stops with `off` show `hm(Core.localMin(e, e.ns))` + «по Шанхаю»; a button `#tcPreviewDay` «▶ Как «Сейчас»» sets `S.preview = true; S.prevDay = x.day.n` and opens «Сейчас»; in preview «Сейчас» shows the existing preview line with «Выйти из предпросмотра» `#tcPvExit` (sets `S.preview = false`).

- [ ] **Step 1: Tests** (`src/tests/test_pretrip_home.py`)

```python
import json, re
from conftest import ROOT, PHONE

OWN = json.loads((ROOT / "trips" / "miras-aikosh.json").read_text(encoding="utf-8"))
REAL = {"prevDay": 2, "prevTime": "13:24", "preview": False}


def home(app, now="2026-09-30T12:00:00+09:00", **kw):
    return app(trip=OWN, state=REAL, now=now, **kw)


def test_before_the_trip_countdown_first_thing_and_readiness_above_the_fold(app):
    a = home(app)
    assert "Япония" in a.page.inner_text(".tc-title h1") and "через 17 дней" in a.page.inner_text(".tc-title")   # 16.5 days, rounded up
    assert a.page.locator(".tc-segs").count() == 0 and a.page.locator("#tcCap").count() == 0
    assert "17 дней" in a.page.inner_text("#tcCount") and "MU 6042" in a.page.inner_text("#tcCount")
    first = a.page.inner_text("#tcFirst")
    assert a.page.inner_text("#tcFirst b").strip() and "ещё" in first
    ready = a.page.locator("#tcReady [data-ready]")
    assert [b.get_attribute("data-ready") for b in ready.all()] == ["tickets", "phone", "money", "packing"]
    bar = a.page.locator("#tcTabs").bounding_box()["y"]
    for sel in ("#tcCount", "#tcFirst", "#tcReady"):
        b = a.page.locator(sel).bounding_box(); assert b["y"] + b["height"] <= bar
    assert a.page.locator("#tcWx, #tcSun, #tcNow, #tcNext, .tc-preview").count() == 0      # no weather before T-7, no fake time
    ready.first.click()
    assert a.page.locator("#tcSheet [data-group='tickets']").is_visible()
    assert a.errors == []


def test_week_before_shows_weather_and_capsule_before_sales_open(app):
    a = home(app, now="2026-10-10T01:00:00+09:00")            # Shibuya Sky sales in < 48 h; departure in 6 days
    assert a.page.locator("#tcCap").count() == 1 and "Shibuya Sky" in a.page.inner_text("#tcCap")
    assert a.page.locator("#tcDay1").count() == 1


def test_departure_transit_live_post(app):
    d = home(app, now="2026-10-16T12:00:00+05:00")           # Almaty, departure day
    assert "MU 6042" in d.page.inner_text("#tcFlight") and d.page.locator("#tcFirst").count() == 0
    t = home(app, now="2026-10-17T09:00:00+08:00")           # Shanghai morning
    day1 = t.page.inner_text("#tcDay1")
    assert "по Шанхаю" in day1 and t.page.locator("#tcDay1 .now").count() == 1
    l = home(app, now="2026-10-18T13:24:00+09:00")           # in Japan
    assert "Oishi Park" in l.page.inner_text("#tcNow")
    p = home(app, now="2026-10-29T12:00:00+09:00")
    assert "Поездка завершена" in p.page.inner_text("#todayBody")


def test_no_flights_falls_back_to_dates(app):
    a = app(trip=dict(OWN, flights=[]), state=REAL, now="2026-09-30T12:00:00+09:00")
    a.page.evaluate("localStorage.setItem('japan2026.flights.v1', '[]'); renderShell()")
    assert "через 17 дней" in a.page.inner_text(".tc-title") and a.errors == []


def test_preview_lives_on_day_tab(app):
    a = home(app)
    a.page.click(".tc-tab[data-tab='day']")
    a.page.click(".tc-daypick >> nth=1")
    a.page.click("#tcPreviewDay")
    assert a.page.locator("#tcNow").count() == 1 and "Предпросмотр" in a.page.inner_text("#todayBody")
    a.page.click("#tcPvExit")
    assert a.page.locator("#tcCount").count() == 1


def test_shanghai_stops_show_local_time_on_day_tab(app):
    a = home(app)
    a.page.click(".tc-tab[data-tab='day']")
    a.page.click(".tc-daypick >> nth=0")
    row = a.page.locator(".tc-item", has_text="Маглев").inner_text()
    assert "07:00" in row and "по Шанхаю" in row
```

`conftest.app()`: `if state and "prevDay" in state and "preview" not in state: state = {**state, "preview": True}` (keeps every existing test that drives «Сейчас» with a preview time).

- [ ] **Step 2: Run — fails.**
- [ ] **Step 3: Implement.**

`store.js` `clock()`:

```js
function clock() {
  const live = liveDayN();
  if (live) { /* unchanged live branch, including the after-midnight carry-over */ }
  if (S.preview) return { live: false, day: S.prevDay, min: toMin(S.prevTime || '09:00') };
  return { live: false, day: T.days[0].n, min: japanNow().min };   // before/after the trip: real time
}
```

(Stage 1 Task 7 later swaps `T` for `TV()` here.)

`shell.js` `ctx()` adds:

```js
  const ph = S.preview ? { phase: 'live' } : Flights.phase(Date.now(), myFlights(), dateOf(T.days[0]), dateOf(T.days[T.days.length - 1]));
  return { c, cday, cevs, day, evs, csun, urg: Core.urgent(cevs, c.min), ph };
```

`renderShell()` header:

```js
  const pre = x.ph.phase === 'pre' || x.ph.phase === 'post';
  head.innerHTML = withHead ? gearHTML() + (pre ? preCapsuleHTML() : capsuleHTML(x.urg)) + (pre ? '' : segmentsHTML(x))
    + (pre && tab === 'now' ? preTitleHTML(x) : titleHTML(tab === 'now' ? x.cday : x.day)) : '';
```

with (in `now.js`):

```js
function preCapsuleHTML() {
  const o = Prep.opening(prepItems(), Date.now()); if (!o) return '';
  const left = Date.parse(o.opens) - Date.now();
  return `<button type="button" class="tc-cap soon" id="tcCap" aria-label="${esc(o.title)}: продажи через ${Core.cd(left / 60000)}">
    <span class="tc-cap-ic">${icon('tix')}</span><span class="tc-cap-t">${esc(o.title.replace(/^Купить: /, '').slice(0, 18))}</span>
    <span class="tc-cap-sep" aria-hidden="true"></span><span class="tc-cap-n">${Core.cd(left / 60000)}</span></button>`;
}
function daysWord(n) { return n % 10 === 1 && n % 100 !== 11 ? 'день' : [2, 3, 4].includes(n % 10) && ![12, 13, 14].includes(n % 100) ? 'дня' : 'дней'; }
function preTitleHTML(x) {
  if (x.ph.phase === 'post') return `<div class="tc-title"><h1>Япония</h1><span>поездка завершена</span></div>`;
  const dep = x.ph.dep || Date.parse(dateOf(T.days[0]) + 'T00:00:00+09:00');
  const n = Math.max(0, Math.ceil((dep - Date.now()) / 864e5));
  return `<div class="tc-title"><h1>Япония</h1><span>через ${n} ${daysWord(n)}</span></div>`;
}
```

`RENDER.now` starts with:

```js
  if (x.ph.phase === 'pre') return renderPre(x, root);
  if (x.ph.phase === 'post') return renderPost(x, root);
  if (x.ph.phase === 'departure') return renderDeparture(x, root);
  if (x.ph.phase === 'transit') return renderTransit(x, root);
```

and the preview block becomes `if (S.preview) { … existing line … + '<button type="button" class="tc-btn" id="tcPvExit">Выйти из предпросмотра</button>' }` with `#tcPvExit` → `S.preview = false; save(); renderShell();`.

`renderPre(x, root)`:

```js
function countdownText(ms) {
  const m = Math.max(0, Math.floor(ms / 60000)), d = Math.floor(m / 1440), h = Math.floor(m % 1440 / 60);
  if (ms > 2 * 864e5) return `${Math.ceil(ms / 864e5)} ${daysWord(Math.ceil(ms / 864e5))}`;
  if (ms > 864e5) return `${d} д ${h} ч`;
  return Core.cd(m);
}
function day1HTML(expanded) {
  const d1 = T.days[0], evs = plan(d1, null).filter(e => !e.bad);
  const legs = myFlights(), l0 = legs[0];
  const now = Date.now();
  const steps = [];
  if (l0) steps.push({ t: `Вылет ${Flights.pretty(l0.no)}`, when: `${l0.date.slice(8)}.${l0.date.slice(5, 7)} ${l0.dep}`, at: Flights.times(l0).dep });
  evs.forEach(e => {
    const sh = Core.shiftOf(e), base = Date.parse(dateOf(d1) + 'T00:00:00+09:00');
    steps.push({ t: e.t, when: hm(Core.localMin(e, e.ns)) + (sh ? ' по Шанхаю' : ''), at: base + e.ns * 60000, end: base + e.ne * 60000 });
  });
  const cur = steps.findIndex((s, i) => now >= s.at && now < (s.end || (steps[i + 1] || {}).at || Infinity));
  if (!expanded) return `<button type="button" class="tc-card tc-day1" id="tcDay1"><span class="tc-lbl">Первые сутки</span>
      <span class="tc-sub">${steps.slice(0, 1).concat(steps.filter(s => /Шанхай|Ханэд|Заселение/.test(s.t)).slice(0, 3)).map(s => esc(s.when.split(' по')[0] + ' ' + s.t.split(':')[0])).join(' → ')}</span></button>`;
  return `<section class="tc-card tc-day1" id="tcDay1"><span class="tc-lbl">Первые сутки</span><ol class="tc-steps">${steps.map((s, i) =>
    `<li class="${i === cur ? 'now' : i < cur ? 'done' : ''}"><b>${esc(s.when)}</b><span>${esc(s.t)}</span></li>`).join('')}</ol></section>`;
}
function renderPre(x, root) {
  const now = Date.now(), list = prepItems(), dep = x.ph.dep;
  const f = Prep.first(list, now, dep), g = Prep.groups(list);
  const leg = x.ph.leg, t0 = dep ? atAirport(dep, leg.frm, leg.frmOff) : null;
  const chain = myFlights();
  const route = chain.length ? [chain[0].frm, ...chain.filter(l => Flights.times(l).dep < (x.ph.arrive || Infinity) + 1).map(l => l.to)]
    .map(c => esc(Flights.airport(c))).join(' → ') : '';
  const opening = list.filter(i => !i.done && i.opens && Date.parse(i.opens) > now).sort((a, b) => Date.parse(a.opens) - Date.parse(b.opens))[0];
  let html = Ios.installHint();
  html += `<section class="tc-card tc-count" id="tcCount"><span class="tc-lbl">До вылета</span>
    <b class="tc-count-n">${dep ? countdownText(dep - now) : countdownText(Date.parse(dateOf(T.days[0]) + 'T00:00:00+09:00') - now)}</b>
    ${leg ? `<span class="tc-sub">${esc(Flights.pretty(leg.no))} · вылет ${t0.dm} в ${t0.hm} по времени ${esc(Flights.airport(leg.frm))}</span>` : ''}
    ${route ? `<span class="tc-fl-route">${route}</span>` : ''}</section>`;
  html += f.item ? `<section class="tc-card tc-first" id="tcFirst"><span class="tc-lbl">Сначала это</span><b>${esc(f.item.title)}</b>
      ${f.item.due ? `<span class="tc-sub">до ${Core.ddmmyyyy(f.item.due.slice(0, 10)).slice(0, 5)}</span>` : ''}
      <div class="tc-actions two">${Core.safeUrl(f.item.url) ? `<a class="tc-btn primary" href="${Core.safeUrl(f.item.url)}" target="_blank" rel="noopener">${icon('share')}Открыть сайт</a>` : ''}
        <button type="button" class="tc-btn${Core.safeUrl(f.item.url) ? '' : ' primary'}" data-first-done="${esc(f.item.id)}"${f.item.auto ? ' hidden' : ''}>${icon('check')}Готово</button></div>
      ${f.rest ? `<button type="button" class="tc-link" data-ready="all">ещё ${f.rest} ${f.rest === 1 ? 'дело' : f.rest < 5 ? 'дела' : 'дел'} ›</button>` : ''}</section>`
    : `<section class="tc-card tc-first" id="tcFirst"><span class="tc-lbl">Сначала это</span>
      <b>${list.every(i => i.done) ? 'Всё готово ✓' : 'Сейчас делать нечего'}</b>
      ${opening ? `<span class="tc-sub">${esc(opening.title)} — продажи откроются ${Core.ddmmyyyy(opening.opens.slice(0, 10)).slice(0, 5)}</span>` : ''}</section>`;
  html += `<section class="tc-ready" id="tcReady">${g.map(x2 => `<button type="button" class="tc-ready-chip" data-ready="${x2.key}">
      <svg viewBox="0 0 36 36" class="tc-ready-ring" aria-hidden="true"><circle cx="18" cy="18" r="15" class="bg"/><circle cx="18" cy="18" r="15" class="fg"
        stroke-dasharray="${(94.25 * (x2.total ? x2.done / x2.total : 0)).toFixed(1)} 94.25" transform="rotate(-90 18 18)"/></svg>
      <span><b>${esc(x2.title)}</b><small>${x2.done}/${x2.total}</small></span></button>`).join('')}</section>`;
  const weekOut = dep && dep - now <= 7 * 864e5;
  html += day1HTML(dep && dep - now <= 864e5);
  html += `<button type="button" class="tc-flline" id="tcRoute">${icon('day')}<span>${esc(T.days.map(d => d.city.split(' →')[0]).filter((c, i, a) => a.indexOf(c) === i).join(' · '))}<small>маршрут по дням</small></span>${icon('arrow')}</button>`;
  if (weekOut) html += topRowHTML(x);
  if (!chain.length) html += flightTileHTML(x);
  root.innerHTML = `<div class="tc-page">${html}</div>`;
  Ios.wireInstall(root); wireFlightCard(root);
  root.querySelectorAll('[data-ready]').forEach(b => b.addEventListener('click', () => openPrep(b.dataset.ready === 'all' ? null : b.dataset.ready)));
  const fd = root.querySelector('[data-first-done]'); if (fd) fd.addEventListener('click', () => { const l = prepLocal(); l.done[fd.dataset.firstDone] = true; prepSave(l); renderShell(); });
  root.querySelector('#tcRoute').addEventListener('click', () => { viewDay = T.days[0].n; go('day'); });
  const d1 = root.querySelector('button#tcDay1'); if (d1) d1.addEventListener('click', () => { viewDay = T.days[0].n; go('day'); });
}
function renderPost(x, root) {
  root.innerHTML = `<div class="tc-page"><section class="tc-card" id="tcNow"><span class="tc-lbl">Япония</span><h2 class="tc-h2">Поездка завершена</h2>
    <span class="tc-sub">${T.days.length} дней · итоги — во вкладке «Итоги»</span></section></div>`;
}
function renderDeparture(x, root) {
  const list = prepItems().filter(i => !i.done && (i.group === 'money' || i.group === 'packing'));
  root.innerHTML = `<div class="tc-page">${flightCardHTML(x)}${list.length ? `<section class="tc-card" id="tcLeft"><span class="tc-lbl">Перед выходом</span>
    ${list.slice(0, 5).map(i => `<span class="tc-sub">• ${esc(i.title)}</span>`).join('')}<button type="button" class="tc-link" data-ready="money">все дела ›</button></section>` : ''}${day1HTML(true)}</div>`;
  wireFlightCard(root);
  root.querySelectorAll('[data-ready]').forEach(b => b.addEventListener('click', () => openPrep(b.dataset.ready)));
}
function renderTransit(x, root) {
  root.innerHTML = `<div class="tc-page">${day1HTML(true)}${flightCardHTML(x)}</div>`;
  wireFlightCard(root);
}
```

`flightCardHTML(x)`: in `departure`/`transit`, remove the `x.c.live && … > 36 h` guard (it is shown there by design).

`day.js` `itemRow`: time shown as `hm(Core.localMin(e, e.ns))` plus `<small>по Шанхаю</small>` when `Core.shiftOf(e)`; the stop sheet likewise. In `RENDER.day` add under the strip: `<button type="button" class="tc-btn" id="tcPreviewDay">▶ Как «Сейчас»</button>` → `S.preview = true; S.prevDay = x.day.n; S.prevTime = S.prevTime || '09:00'; save(); go('now');`.

CSS: `.tc-count-n` 56 px/700 rounded tabular; `.tc-first b` 18 px/600; `.tc-ready` grid 2×2 gap 12; `.tc-ready-chip` card, min-height 64, ring 36 px (`circle.bg` `--seg`, `circle.fg` `--ok`, stroke-width 4, linecap round); `.tc-link` text button 44 px `--tint`; `.tc-steps` list with 8 px dots, `.now` bold + `--tint`, `.done` `--sec`.

- [ ] **Step 4: Run** `.venv/bin/pytest src/tests/test_pretrip_home.py -q` → PASS; full suite green (fix tests that relied on the preview default only through the conftest rule).
- [ ] **Step 5: Screens:** screenshot `pre` (30.09, 10.10), `departure`, `transit` at 390×844 and 440×956, light and dark; check hierarchy and above-the-fold.
- [ ] **Step 6: Commit** `git commit -am "«Сейчас» by phase: before the trip, departure day, transit via Shanghai, after; preview moves to «День»"` (add new files).

### Task 7: Review and publish

- [ ] **Step 1:** Final whole-branch review (most capable model) over the plan's commits; fix confirmed findings with tests.
- [ ] **Step 2:** `cd src && ../.venv/bin/python build_guide.py && cd .. && cp src/Japan_Guide_2026.html index.html`; full suite + map scripts (`cd src && for t in test_v3 test_cluster test_kz test_overlap test_offline; do ../.venv/bin/python tests/$t.py; done`; delete screenshots they write into `src/`).
- [ ] **Step 3:** Commit, push `main`, wait for Pages (`gh api repos/zakcination/japan-2026/pages/builds/latest`), open `?trip=miras-aikosh` live with an iPhone user agent and check the `pre` screen.
- [ ] **Step 4:** Rebase `group-stage1` onto `main`; note in its ledger that `TV()`/`planDoc()` (Stage 1 Task 7) must replace `T` in `renderPre`, `day1HTML`, `prepItems`.
