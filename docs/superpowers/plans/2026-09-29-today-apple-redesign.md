# «Сегодня» в стиле Apple — план реализации

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** переделать экран «Сегодня» гида (GitHub Pages) в нативный по ощущениям iOS-интерфейс из пяти вкладок, с темами по закату, возможностями iOS и поездками-файлами в репозитории, не меняя логику пересчёта.

**Architecture:** `src/today.js` (707 строк, один IIFE) разбивается на модули в `src/today/`, которые `build_guide.py` склеивает в один IIFE внутри `index.html`. Чистая логика — `core.js` (без DOM, тестируется отдельно); состояние — `store.js`; поездки — `trips.js`; iOS — `ios.js`; интерфейс — `ui/*.js`; стили — `theme.css` + `components.css`. Поездки лежат в `trips/*.json`, шаблон вшит в страницу.

**Tech Stack:** ванильный JS (ES2020, без сборщиков и зависимостей), CSS custom properties, Python 3 (сборка), pytest + Playwright (sync API) в `.venv`, Pillow (иконки через навык web-asset-generator).

**Spec:** `docs/superpowers/specs/2026-09-29-today-apple-redesign-design.md` · макет: https://claude.ai/artifact/MWYmf6By4yLFUFkeXQ9r1R

## Global Constraints

- Интерфейс на русском; даты ДД.ММ.ГГГГ, время 24 ч, цены ¥ + валюта дома.
- Один офлайн-файл `index.html`; никаких внешних скриптов и шрифтов (шрифт — системный SF / SF Rounded).
- Размеры: вкладка «Сейчас» помещается в 390×844 без прокрутки; любая кнопка ≥ 44×44 CSS px.
- Цвета — токены из раздела 3 спецификации; текст ≥ 4.5:1 (для `--sec` в светлой теме берём `#6E6E73`, а не `#8E8E93`, который даёт 3.1:1 на `#F2F2F7`).
- FIXED и межгородской транспорт никогда не двигаются пересчётом (правила `plan()` не меняются).
- В публичный репозиторий не попадают номера билетов, места, адреса, телефоны, данные карт. Имена, рейсы, первый отель и брони — можно (решение владельца).
- Сторонние навыки: только прочитанные `anthropics/skills/webapp-testing` и `alonw0/web-asset-generator@c6d56dc`; Pillow — только в `.venv`, никогда `--break-system-packages`.
- `survey/` и `research/` не коммитятся.
- Тесты карты запускаются с `#map` в ссылке и должны проходить после каждого таска.

## Review Focus

1. **Пустой или «сломанный» день** (нет событий, событие без `e`, время `24:30`, lat/lng пустые) — экран не падает, показывает «Нет пунктов» / «—». Тест в Task 1 (`test_plan_tolerates_odd_events`) и Task 4 (`test_now_empty_day`).
2. **Поездка из ссылки или файла с HTML/скриптом в названии** — выводится текстом, ссылки не-`https:` отбрасываются. Тест в Task 1 (`test_valid_trip_and_safe_url`) и Task 10 (`test_hostile_trip_is_escaped`).
3. **Время вне дня поездки** (до 17.10, после 27.10, день без событий после 23:00) — капсула не показывает бессмыслицу, «Сейчас» говорит «День завершён» / «Предпросмотр». Тест в Task 3 (`test_capsule_hidden_without_future_event`).
4. **Переход через закат во время открытого приложения** — тема меняется при очередном тике (30 с), без перезагрузки. Тест в Task 3 (`test_theme_switches_on_tick`).
5. **Сеть пропала посреди загрузки `trips/<id>.json`** — берётся сохранённая копия, плашка «версия от …». Тест в Task 10 (`test_trip_fetch_fails_uses_cache`).

---

## File Structure

| Файл | Ответственность |
|---|---|
| `src/today/core.js` | чистые функции: время, `plan`, `urgent`, `themeFor`, `sunTimes`, `validTrip`, `safeUrl`, форматтеры |
| `src/today/store.js` | поездка/настройки/отметки в `localStorage`, билеты в IndexedDB, `#trip=`, деньги |
| `src/today/trips.js` | `?trip=`, загрузка `trips/<id>.json`, локальные правки поверх общей версии |
| `src/today/ios.js` | wake lock, `.ics`, share, Apple Maps, подсказка установки, `theme-color` |
| `src/today/ui/shell.js` | каркас: шапка (капсула, сегменты, заголовок), вкладки, лист, тема, тик |
| `src/today/ui/now.js` | вкладка «Сейчас» |
| `src/today/ui/day.js` | вкладка «День» + лист пункта |
| `src/today/ui/bookings.js` | вкладка «Брони» + просмотр билета |
| `src/today/ui/stats.js` | вкладка «Итоги» |
| `src/today/ui/settings.js` | ⚙, редактор пункта и дня |
| `src/today/boot.js` | запуск |
| `src/today/theme.css`, `src/today/components.css` | токены и компоненты |
| `src/today_data.py` | генерирует `trips/template.json`, `trips/miras-aikosh.json`, `trips/index.json`, `src/stops.json` |
| `trips/*.json` | поездки (публично) |
| `src/build_guide.py` | склейка модулей, вшивание шаблона и индекса поездок, CSP, meta |
| `sw.js` | офлайн + network-first для `trips/*.json` |
| `src/tests/conftest.py`, `src/tests/test_*.py` | тесты (pytest) |

Удаляются в конце: `src/today.js`, `src/today.css`, `src/today.json`, `survey/private_overrides.json` (локально), сборка `PERSONAL=1`.

## Task 0: Инструменты — `.venv`, pytest, навыки, общий conftest

**Files:**
- Create: `src/tests/conftest.py`, `pytest.ini`
- Modify: `.gitignore`
- Install (вне репозитория): `~/.claude/skills/webapp-testing/`, `~/.claude/skills/web-asset-generator/`

**Interfaces:**
- Produces: фикстуры pytest `core` (страница `about:blank` с `window.Core`, и если передан `mods`, с другими модулями), `app(state=None, settings=None, trip=None, size=PHONE, url_suffix="", now=None, dark_os=False) -> App` (`App.page`, `App.errors`), константы `SRC`, `ROOT`, `PHONE`. `now` — строка ISO с часовым поясом, фиксирует `Date` через `page.clock.set_fixed_time`.

- [ ] **Step 1: Окружение и навыки**

```bash
cd /Users/mz/japan-2026
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -q pytest==8.3.3 Pillow==10.4.0
printf '.venv/\n.pytest_cache/\n__pycache__/\n' >> .gitignore
mkdir -p ~/.claude/skills
tmp=$(mktemp -d)
git clone -q --depth 1 --filter=blob:none --sparse https://github.com/anthropics/skills "$tmp/a" && (cd "$tmp/a" && git sparse-checkout set skills/webapp-testing)
cp -R "$tmp/a/skills/webapp-testing" ~/.claude/skills/
git clone -q https://github.com/alonw0/web-asset-generator "$tmp/w" && (cd "$tmp/w" && git checkout -q c6d56dc)
cp -R "$tmp/w/skills/web-asset-generator" ~/.claude/skills/
ls ~/.claude/skills
```
Expected: в списке `webapp-testing` и `web-asset-generator`.

- [ ] **Step 2: `pytest.ini`**

```ini
[pytest]
testpaths = src/tests
python_files = test_*.py
addopts = -q
```

- [ ] **Step 3: `src/tests/conftest.py`**

```python
"""Shared fixtures: build the guide once, a bare page with the pure core, and the full app on a phone."""
import json
import pathlib
import subprocess
import sys
from datetime import datetime

import pytest
from playwright.sync_api import sync_playwright

SRC = pathlib.Path(__file__).resolve().parents[1]
ROOT = SRC.parent
PAGE = (SRC / "Japan_Guide_2026.html").resolve().as_uri()
PHONE = {"width": 390, "height": 844}


@pytest.fixture(scope="session", autouse=True)
def built():
    subprocess.run([sys.executable, "build_guide.py"], cwd=SRC, check=True, capture_output=True)


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture
def core(browser):
    """about:blank with src/today/core.js (and optional extra modules) loaded; exposes window.Core."""
    pages = []

    def load(mods=("core.js",)):
        pg = browser.new_page()
        pg.goto("about:blank")
        code = "\n".join((SRC / "today" / m).read_text(encoding="utf-8") for m in mods)
        pg.add_script_tag(content=code + "\nwindow.Core = Core;" + ("\nwindow.Ios = Ios;" if "ios.js" in mods else ""))
        pages.append(pg)
        return pg

    yield load
    for p in pages:
        p.close()


class App:
    def __init__(self, page, errors):
        self.page, self.errors = page, errors


@pytest.fixture
def app(browser):
    made = []

    def open_(state=None, settings=None, trip=None, size=PHONE, url_suffix="", now="2026-09-30T12:00:00+09:00",
              dark_os=False):
        ctx = browser.new_context(viewport=size, device_scale_factor=2, has_touch=True, is_mobile=True,
                                  color_scheme="dark" if dark_os else "light")
        pg = ctx.new_page()
        errors = []
        pg.on("pageerror", lambda e: errors.append(str(e)))
        if now:
            pg.clock.set_fixed_time(datetime.fromisoformat(now))
        seed = {"japan2026.today.v1": state, "japan2026.settings.v1": settings, "japan2026.trip.v1": trip}
        pg.add_init_script(
            "(s => { if (sessionStorage.getItem('seeded')) return; sessionStorage.setItem('seeded', '1');"
            " for (const [k, v] of Object.entries(s)) if (v) localStorage.setItem(k, JSON.stringify(v)); })("
            + json.dumps(seed) + ")")
        pg.goto(PAGE + url_suffix)
        pg.wait_for_selector("#today", state="attached")
        made.append(ctx)
        return App(pg, errors)

    yield open_
    for c in made:
        c.close()
```

- [ ] **Step 4: Базовый тест, что нынешний экран жив** — `src/tests/test_baseline.py`

```python
def test_today_screen_renders_before_refactor(app):
    a = app(state={"prevDay": 2, "prevTime": "13:24"})
    assert a.page.locator("#today").is_visible()
    assert "Фудзи" in a.page.inner_text("#today")
    assert a.errors == []
```

- [ ] **Step 5: Запуск** — `cd /Users/mz/japan-2026 && .venv/bin/pytest src/tests/test_baseline.py` → `1 passed`. Затем старые тесты карты: `cd src && for t in test_v3 test_cluster test_kz test_overlap; do ../.venv/bin/python tests/$t.py | grep -c '"errors": \[\]'; done` → каждый ≥ 1.

- [ ] **Step 6: Commit**

```bash
git add pytest.ini .gitignore src/tests/conftest.py src/tests/test_baseline.py
git commit -m "Add pytest harness for the TODAY screen"
```

---

## Task 1: `core.js` — чистая логика и её тесты; сборка склеивает модули

**Files:**
- Create: `src/today/core.js`, `src/tests/test_core.py`
- Create: `src/today/legacy.js` (= `src/today.js` без обёртки `(function () {` … `})();` и без функций, переехавших в core)
- Modify: `src/build_guide.py` (склейка модулей)
- Delete: `src/today.js`

**Interfaces:**
- Produces (глобальный `Core` внутри общего IIFE):
  - `Core.pad(n) -> "05"`, `Core.toMin("06:45") -> 405` (`NaN` для мусора), `Core.hm(405) -> "06:45"`, `Core.dur(65) -> "1 ч 05 мин"`, `Core.cd(171) -> "2:51"`, `Core.ddmmyyyy("2026-10-18") -> "18.10.2026"`, `Core.addDays(iso, n) -> iso`
  - `Core.japanNow(date?) -> {date:"YYYY-MM-DD", min, sec}`
  - `Core.sunTimes(iso, lat, lng) -> {rise, set}` (минуты по Японии)
  - `Core.isAnchor(e)`, `Core.isKey(e)`, `Core.travel(e) -> минуты`
  - `Core.plan(day, now|null, marks{skip,done,delay}, dateISO) -> evs[]` — поля `S,E,ns,ne,leave,cut,auto,conflict,skip,done,delay,off,bad`
  - `Core.urgent(evs, now|null) -> null | {ev, leaveIn, startIn, state:"calm"|"soon"|"go"}`
  - `Core.themeFor(nowMin, sun|null, pref:"auto"|"light"|"dark") -> "light"|"dark"`
  - `Core.dayProgress(evs, now|null) -> 0..1`
  - `Core.validTrip(j) -> bool`, `Core.safeUrl(u) -> u|""`

- [ ] **Step 1: Тесты** — `src/tests/test_core.py`

```python
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
        [405, "06:45", "2:51", "1 ч 05 мин", "18.10.2026"]
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
```

- [ ] **Step 2: Запуск** — `.venv/bin/pytest src/tests/test_core.py` → FAIL: `src/today/core.js` не найден.

- [ ] **Step 3: `src/today/core.js`**

```js
/* ---------- core: time, the replanner and pure helpers — no DOM, no storage ----------
   Tested on its own in src/tests/test_core.py. Everything else in the TODAY screen builds on it. */
const Core = (() => {
  const pad = n => String(n).padStart(2, '0');
  const toMin = s => {
    const m = /^(\d{1,2}):(\d{2})$/.exec(String(s == null ? '' : s).trim());
    return m ? +m[1] * 60 + +m[2] : NaN;
  };
  const hm = m => { m = ((Math.round(m) % 1440) + 1440) % 1440; return pad(Math.floor(m / 60)) + ':' + pad(m % 60); };
  const dur = m => { m = Math.max(0, Math.round(m)); const h = Math.floor(m / 60); return h ? `${h} ч ${pad(m % 60)} мин` : `${m} мин`; };
  const cd = m => { m = Math.max(0, Math.round(m)); return Math.floor(m / 60) + ':' + pad(m % 60); };
  const ddmmyyyy = iso => { const [y, mo, d] = String(iso).split('-'); return `${d}.${mo}.${y}`; };
  const addDays = (iso, n) => { const d = new Date(iso + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };

  function japanNow(date) {
    const p = {};
    new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit',
      hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
      .formatToParts(date || new Date()).forEach(x => { p[x.type] = x.value; });
    return { date: `${p.year}-${p.month}-${p.day}`, min: (+p.hour % 24) * 60 + +p.minute, sec: +p.second };
  }

  /* sunrise / sunset, NOAA approximation, minutes in Japan time */
  function sunTimes(iso, lat, lng) {
    const rad = Math.PI / 180, d = new Date(iso + 'T12:00:00Z');
    const n = Math.floor((d - Date.UTC(d.getUTCFullYear(), 0, 0)) / 864e5);
    const g = 2 * Math.PI / 365 * (n - 1);
    const eq = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
    const decl = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g)
               - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
    const ha = Math.acos(Math.cos(90.833 * rad) / (Math.cos(lat * rad) * Math.cos(decl)) - Math.tan(lat * rad) * Math.tan(decl)) / rad;
    const noon = 720 - 4 * lng - eq + 540;
    return { rise: noon - 4 * ha, set: noon + 4 * ha };
  }

  /* Anchors never move: fixed events, intercity transport and hotel check-ins still to be booked. */
  const isAnchor = e => e.st === 'fixed' || ((e.cat === 'transport' || e.cat === 'hotel') && e.st === 'input');
  const isKey = e => e.st !== 'flex' && e.cat !== 'routine' && e.cat !== 'konbini';
  const travel = e => (+e.walk || 0) + (+e.ride || 0) + (+e.buf || 0);

  /* The replanner. A delay pushes what follows; before an anchor the overrun is paid back from
     flexible blocks first (latest first, down to nothing), then planned ones (down to half, never
     under 15 min) — and only from what hasn't happened yet. What can't be paid back is shown as a
     conflict on the anchor. Nothing extra is ever suggested. */
  function plan(day, now, marks, dateISO) {
    const skip = (marks && marks.skip) || {}, done = (marks && marks.done) || {}, delay = (marks && marks.delay) || {};
    const all = (day.ev || []).map(e => {
      const s = toMin(e.s), en0 = e.e ? toMin(e.e) : NaN;
      const bad = !Number.isFinite(s);
      const en = Number.isFinite(en0) ? en0 : s + 15;
      const off = !!(e.bound && dateISO && dateISO !== e.bound);
      return { ...e, st: off ? 'input' : e.st, off, bad, S: s, E: en < s ? en + 1440 : en, ns: s, ne: 0, cut: 0, auto: false,
               conflict: 0, skip: !!skip[e.id], done: !!done[e.id], delay: +(delay[e.id] || 0) };
    });
    // stable sort by start: trips edited by hand or imported may list stops out of order
    const evs = all.filter(e => !e.bad).map((e, i) => [e, i]).sort((x, y) => x[0].S - y[0].S || x[1] - y[1]).map(x => x[0]);
    const bad = all.filter(e => e.bad);
    let t = null, seg = [];
    for (const e of evs) {
      if (e.skip) { e.ns = e.S; e.ne = e.E; continue; }
      const reach = (+e.walk || 0) + (+e.ride || 0);
      if (isAnchor(e)) {
        e.ns = e.S; e.ne = e.E + (e.st === 'fixed' ? 0 : e.delay);
        let over = t == null ? 0 : t + reach + (+e.buf || 0) - e.S;
        if (over > 0) {
          const open = x => now == null || x.ne > now;
          const future = seg.filter(open);
          const order = [...future.filter(x => x.st === 'flex').reverse(), ...future.filter(x => x.st !== 'flex').reverse()];
          for (const x of order) {
            if (over <= 0) break;
            const len = x.ne - Math.max(x.ns, now == null ? -1e9 : now);
            const keep = x.st === 'flex' ? 0 : Math.max(15, Math.round((x.E - x.S) / 2));
            const c = Math.min(Math.max(0, Math.min(len, x.ne - x.ns - keep)), over);
            if (!c) continue;
            x.ne -= c; x.cut += c; over -= c;
            if (x.ne - x.ns <= 0) x.auto = true;
            seg.slice(seg.indexOf(x) + 1).forEach(y => { y.ns -= c; y.ne -= c; });
          }
          if (over > 0) e.conflict = over;
        }
        t = e.ne; seg = [];
      } else {
        e.ns = t == null ? e.S : Math.max(e.S, t + reach);
        e.ne = e.ns + (e.E - e.S) + e.delay;
        t = e.ne; seg.push(e);
      }
    }
    evs.forEach(e => { e.leave = e.ns - travel(e); });
    bad.forEach(e => { e.ns = e.ne = e.leave = NaN; e.skip = true; });
    return evs.concat(bad);
  }

  /* What the capsule shows: the first future anchor, else the next key event. */
  function urgent(evs, now) {
    if (now == null) return null;
    const live = evs.filter(e => !e.skip && !e.auto && !e.bad && e.ns > now);
    const ev = live.find(isAnchor) || live.find(isKey) || live[0];
    if (!ev) return null;
    const leaveIn = ev.leave - now, startIn = ev.ns - now;
    return { ev, leaveIn, startIn, state: leaveIn <= 0 ? 'go' : leaveIn < 30 ? 'soon' : 'calm' };
  }

  const themeFor = (nowMin, sun, pref) =>
    pref === 'light' || pref === 'dark' ? pref : !sun ? 'light' : (nowMin >= sun.set || nowMin < sun.rise) ? 'dark' : 'light';

  function dayProgress(evs, now) {
    const ok = evs.filter(e => !e.bad);
    if (now == null || !ok.length) return 0;
    const a = Math.min(...ok.map(e => e.ns)), b = Math.max(...ok.map(e => e.ne));
    return b > a ? Math.min(1, Math.max(0, (now - a) / (b - a))) : 0;
  }

  const validTrip = j => !!(j && Array.isArray(j.days) && j.days.length &&
    j.days.every(d => Number.isFinite(+d.n) && Array.isArray(d.ev) &&
      d.ev.every(e => e && typeof e.t === 'string' && /^\d{1,2}:\d{2}$/.test(String(e.s)))));
  const safeUrl = u => (typeof u === 'string' && /^https:\/\/[^\s"'<>]+$/i.test(u)) ? u : '';

  return { pad, toMin, hm, dur, cd, ddmmyyyy, addDays, japanNow, sunTimes, isAnchor, isKey, travel,
           plan, urgent, themeFor, dayProgress, validTrip, safeUrl };
})();
```

- [ ] **Step 4: `legacy.js` использует `Core`.** Перенести `src/today.js` → `src/today/legacy.js`; удалить первую строку `(function () {` и последнюю `})();`; удалить из него определения `pad, toMin, hm, dur, ddmmyyyy, addDays, japanNow, sunTimes, isAnchor, travel, plan` (строки 29, 44–62, 71–137 текущего файла) и вставить на их место:

```js
const { pad, toMin, hm, dur, ddmmyyyy, addDays, japanNow, sunTimes, isAnchor, travel } = Core;
const dateOf = d => addDays(SET.start, d.n - 1);
const plan = (day, now) => Core.plan(day, now, S, dateOf(day));
```
(строку `const dateOf = …` на старом месте удалить, чтобы не было двух определений; `validTrip` из обработчика импорта заменить на `Core.validTrip(j)`, а ссылку в редакторе пункта сохранять через `Core.safeUrl`).

- [ ] **Step 5: Сборка склеивает модули.** В `src/build_guide.py` заменить
`.replace("__TODAY_JS__", pathlib.Path("today.js").read_text(encoding="utf-8")))` на
`.replace("__TODAY_JS__", today_js()))` и добавить перед `out = (HTML`:

```python
# The TODAY screen ships as modules under src/today/, glued into one closure in this order.
TODAY_MODULES = ["core.js", "store.js", "trips.js", "ios.js", "ui/shell.js", "ui/now.js", "ui/day.js",
                 "ui/bookings.js", "ui/stats.js", "ui/settings.js", "legacy.js", "boot.js"]
TODAY_STYLES = ["theme.css", "components.css"]


def today_js():
    parts = [pathlib.Path("today", m).read_text(encoding="utf-8") for m in TODAY_MODULES if pathlib.Path("today", m).exists()]
    return "(function () {\n'use strict';\n" + "\n".join(parts) + "\n})();"


def today_css():
    parts = [pathlib.Path("today", m).read_text(encoding="utf-8") for m in TODAY_STYLES if pathlib.Path("today", m).exists()]
    legacy = pathlib.Path("today.css")
    return (legacy.read_text(encoding="utf-8") if legacy.exists() else "") + "\n".join(parts)
```
и `.replace("__TODAY_CSS__", today_css())`.

- [ ] **Step 6: Запуск** — `.venv/bin/pytest src/tests` → все проходят (включая `test_baseline`); старые тесты карты (Task 0 Step 5) — без ошибок.

- [ ] **Step 7: Commit**

```bash
git rm -q src/today.js
git add src/today/core.js src/today/legacy.js src/tests/test_core.py src/build_guide.py
git commit -m "Extract the TODAY core into a tested module and glue modules at build time"
```

## Task 2: `store.js` — хранение отдельно от интерфейса

**Files:** Create `src/today/store.js`, `src/tests/test_store.py`; Modify `src/today/legacy.js`.

**Interfaces — Produces** (в общем замыкании): `TPL, TRIP_KEY, SET_KEY, ST_KEY, CUR, clone, loadTrip(), T, isCustom(), saveTrip(), SET, loadSettings(), saveSettings(), S, save(), dateOf(day), plan(day, now), yen(v), home(v), both(v), money(pp), liveDayN(), clock() -> {live, day, min}, openDB(), ticketPut(id, file), ticketGet(id), ticketDel(id), haveTicket, refreshTickets(), bookingById(id), tripFromHash() -> Promise<bool>` (без вызова интерфейса; `setTitle()` вызывает загрузчик).

- [x] Тесты-страховка до переноса (`test_store.py`: своя поездка из хранилища, импорт по `#trip=` со стиранием адреса, цены × люди) — зелёные на старом коде.
- [x] Перенос блоков «поездка/настройки», «состояние/время/деньги», «билеты», `bookingById`, `tripFromHash` из `legacy.js` в `store.js` без изменений логики.
- [x] `pytest` — всё зелёное; коммит.

## Task 3: Каркас — токены, капсула, сегменты, заголовок, вкладки, тема по закату

**Files:** Create `src/today/ui/shell.js`, `src/today/theme.css`, `src/today/components.css`, `src/tests/test_shell.py`; Modify `src/today/legacy.js` (`render` → `renderLegacy`, все обновления → `renderShell`), `src/today/store.js` (`SET.theme`).

**Interfaces — Produces:** `ICONS`, `icon(key, cls?) -> svg`, `TABS`, `RENDER[tab] = (ctx, rootEl) => void`, `tab`, `ctx() -> {c, cday, cevs, day, evs, csun, urg}`, `renderShell()`, `go(tab)`, `sheet(title, bodyHTML, onReady(el))`, `closeSheet()`, `transportIcon(e)`; события `japan2026:tick` и `visibilitychange` перерисовывают экран.

- [x] Тесты: 5 вкладок ≥ 44 px и переключение; капсула calm/soon/go и её отсутствие после последнего пункта; 11 сегментов и заголовок «Вс 18 · 2/11»; тема светлая днём, тёмная после заката, ручная тема; смена темы по тику.
- [x] Реализация; вкладки без своего рендера показывают старый экран.
- [x] `pytest` 22/22, тесты карты без ошибок; коммит.

## Task 4: Вкладка «Сейчас»

**Files:** Create `src/today/ui/now.js`, `src/tests/test_now.py`; Modify `src/today/components.css` (карточки, кнопки-капсулы, жёлтая карточка, большое время ночью, предпросмотр).

**Interfaces — Produces:** `RENDER.now`, `liveEvs(evs)`, `routeUrl(e)` (Apple Карты подключит `ios.js`, иначе Google), `stDot(st)`, `subOf(e)`; элементы `#tcNow`, `#tcNext`, `.tc-bignow`, `#tcPvDay`, `#tcPvTime`.

- [x] Тесты: сейчас/дальше/«выйти через» и помещается в один экран, кнопки ≥ 44; «Пора выходить» с «Начать маршрут» и «План пересчитан»; ночью большое время; «День завершён»; пустой день — «Нет пунктов».
- [x] Реализация по макету; при «Пора» карточка «Сейчас» скрывается, если до выхода 0.
- [x] Один визуальный просмотр (день / пора / ночь); коммит.


## Task 5: Вкладка «День»

**Files:** Create `src/today/ui/day.js`, `src/tests/test_day.py`; Modify `src/today/components.css` (лента дней, список, круглые отметки, лист пункта).

**Interfaces — Produces:** `RENDER.day`, `openStop(day, id)` (лист пункта; `Ios.calendarForDay(day)` появится кнопкой, когда подключится `ios.js`); элементы `.tc-daypick[data-day]`, `#tcList`, `.tc-item.{now,done,skip}`, `.tc-check input[type=checkbox][switch]`, `.tc-open`, `[data-delay]`, `[data-skip]`, `[data-edit]`, `#tcAdd`, `#tcDayEdit`.

- [x] Тесты: 11 дней в ленте и 13 пунктов дня 2, текущий подсвечен; выбор дня и свайп влево → следующий день; отметка — нативный `switch`, сохраняется; лист пункта: кнопки ≥ 44, +15 и «Пропустить» пишут в хранилище; у купленного (FIXED) нет сдвига и пропуска.
- [x] Реализация; стоимость на группу в строке и итог дня; сдвинутое время показывает старое зачёркнутым.
- [x] `pytest` 32/32, тесты карты; визуальный просмотр (светлая лента, тёмный лист); коммит.
