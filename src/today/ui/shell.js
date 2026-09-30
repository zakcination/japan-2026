/* ---------- shell: header (capsule, day segments, title), tabs, theme, bottom sheet, tick ----------
   Tabs register a renderer in RENDER[tab]. */
const WD2 = ['Вс', 'Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб'];
const ICONS = {
  now: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  day: '<path d="M9 6h11M9 12h11M9 18h11"/><circle cx="4.5" cy="6" r="1.2"/><circle cx="4.5" cy="12" r="1.2"/><circle cx="4.5" cy="18" r="1.2"/>',
  tix: '<path d="M3 8a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v2a2 2 0 0 0 0 4v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 0 0-4z"/>',
  stats: '<circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/>',
  map: '<path d="M9 4 3 6v14l6-2 6 2 6-2V4l-6 2z"/><path d="M9 4v14M15 6v14"/>',
  bus: '<rect x="4" y="3" width="16" height="15" rx="3"/><path d="M4 11h16M8 21l1-3M16 21l-1-3"/>',
  train: '<rect x="5" y="3" width="14" height="14" rx="4"/><path d="M5 11h14M9 21l2-4M15 21l-2-4"/>',
  plane: '<path d="M21 16v-2l-8-5V3.5a1.5 1.5 0 0 0-3 0V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5z"/>',
  bed: '<path d="M3 18V7M3 13h18v5M21 13a3 3 0 0 0-3-3h-7v3"/><circle cx="7" cy="11" r="1.6"/>',
  clock: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  arrow: '<path d="M5 12h14M13 6l6 6-6 6"/>',
  pin: '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/>',
  cal: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  share: '<path d="M12 3v12M7 8l5-5 5 5"/><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>',
  skip: '<path d="M6 5l8 7-8 7zM18 5v14"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>',
  clip: '<path d="M16 7l-7.5 7.5a2.5 2.5 0 0 0 3.5 3.5L19.5 10a4.5 4.5 0 0 0-6.4-6.4L5.6 11.1"/>',
  bell: '<path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4z"/><path d="M10 20a2 2 0 0 0 4 0"/>',
  bulb: '<circle cx="12" cy="12" r="4"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  sunrise: '<path d="M4 18h16M7 14a5 5 0 0 1 10 0M12 3v4M9.5 5.5 12 3l2.5 2.5M4.9 9.9l1.4 1.4M19.1 9.9l-1.4 1.4M2 22h20"/>',
  sunset: '<path d="M4 18h16M7 14a5 5 0 0 1 10 0M12 3v4M9.5 4.5 12 7l2.5-2.5M4.9 9.9l1.4 1.4M19.1 9.9l-1.4 1.4M2 22h20"/>',
  check: '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
};
const icon = (k, cls = '') => `<svg class="tc-ic ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[k] || ''}</svg>`;
const TABS = [['now', 'Сейчас'], ['day', 'День'], ['tix', 'Брони'], ['stats', 'Итоги'], ['map', 'Карта']];
const RENDER = {};
let tab = 'now';

/* everything a tab needs about "now", computed once per render */
function ctx() {
  const c = clock();
  const cday = T.days.find(d => d.n === c.day) || T.days[0];
  if (viewDay == null || !T.days.some(d => d.n === viewDay)) viewDay = cday.n;
  const day = T.days.find(d => d.n === viewDay) || cday;
  const cevs = plan(cday, c.min);
  const evs = day === cday ? cevs : plan(day, null);
  const csun = cday.sun ? sunTimes(dateOf(cday), cday.sun[0], cday.sun[1]) : null;
  // where the traveller is (before the trip, departure day, in transit, in Japan, after); a preview is always «live»
  const ph = S.preview === true && !c.live ? { phase: 'live', dep: null, arrive: null, leg: null }
    : Flights.phase(Date.now(), myFlights(), dateOf(T.days[0]), dateOf(T.days[T.days.length - 1]));
  // before the trip, on departure day and after it, the day-1 plan isn't "today": nothing is urgent yet
  const quiet = ['pre', 'departure', 'post'].includes(ph.phase);
  return { c, cday, cevs, day, evs, csun, urg: quiet ? null : Core.urgent(cevs, c.min), ph, quiet };
}

function transportIcon(e) {
  const s = (e.mode || '') + ' ' + (e.t || '');
  if (e.cat === 'hotel') return 'bed';
  if (e.cat !== 'transport') return 'clock';
  return /самол|вылет|прилёт|рейс|MU\d/i.test(s) ? 'plane' : /автобус|bus/i.test(s) ? 'bus' : 'train';
}

function capsuleHTML(u) {
  if (!u) return '';
  const e = u.ev, go = u.state === 'go';
  const say = go ? 'пора выходить' : 'выйти через ' + Core.cd(u.leaveIn);
  const at = hm(Core.localMin(e, e.ns));        // a Shanghai stop in Shanghai time
  return `<button type="button" class="tc-cap ${u.state}" id="tcCap" aria-label="${esc(e.t)}, ${at}${e.sh ? ' по Шанхаю' : ''}: ${say}">
    <span class="tc-cap-ic">${icon(transportIcon(e))}</span>
    <span class="tc-cap-t">${go ? 'Пора' : at}</span><span class="tc-cap-sep" aria-hidden="true"></span>
    <span class="tc-cap-n">${Core.cd(go ? u.startIn : u.leaveIn)}</span></button>`;
}

function segmentsHTML(x) {
  const p = Math.round(Core.dayProgress(x.cevs, x.c.min) * 100);
  return `<div class="tc-segs" role="img" aria-label="День ${x.cday.n} из ${T.days.length}">` + T.days.map(d =>
    `<span class="tc-seg${d.n < x.cday.n ? ' done' : d.n === x.cday.n ? ' cur' : ''}"${d.n === x.cday.n ? ` style="--p:${p}%"` : ''}></span>`).join('') + '</div>';
}

const gearHTML = () => `<button type="button" class="tc-gear" id="tcGear" data-gear aria-label="Моя поездка: настройки">${icon('gear')}</button>`;
function titleHTML(day) {
  const iso = dateOf(day), w = new Date(iso + 'T12:00:00Z').getUTCDay();
  return `<div class="tc-title"><h1>${esc(day.label)}</h1><span>${WD2[w]} ${+iso.slice(8)} · ${day.n}/${T.days.length}</span></div>`;
}

function mountShell() {
  const root = document.getElementById('today');
  if (document.getElementById('tcHead')) return;
  const head = document.createElement('header'); head.className = 'tc-head'; head.id = 'tcHead';
  root.prepend(head);
  const nav = document.createElement('nav'); nav.className = 'tc-tabs'; nav.id = 'tcTabs';
  nav.setAttribute('role', 'tablist'); nav.setAttribute('aria-label', 'Разделы');
  nav.innerHTML = TABS.map(([k, l]) =>
    `<button type="button" role="tab" class="tc-tab" data-tab="${k}" aria-selected="false">${icon(k)}<span>${l}</span></button>`).join('');
  root.appendChild(nav);
  nav.addEventListener('click', ev => { const b = ev.target.closest('.tc-tab'); if (b) go(b.dataset.tab); });
  head.addEventListener('click', ev => { if (ev.target.closest('#tcCap')) go('now'); });
}

function applyTheme(x) {
  const th = Core.themeFor(x.c.min, x.csun, SET.theme || 'auto');
  const root = document.getElementById('today');
  if (root.dataset.th !== th) root.dataset.th = th;
  let m = document.querySelector('meta[name="theme-color"]');
  if (!m) { m = document.createElement('meta'); m.name = 'theme-color'; document.head.appendChild(m); }
  m.content = th === 'dark' ? '#000000' : '#F2F2F7';
}

function renderShell() {
  const root = document.getElementById('today');
  if (!root || root.hidden) return;
  mountShell();
  const x = ctx();
  applyTheme(x);
  const head = document.getElementById('tcHead');
  const withHead = tab !== 'stats';
  head.hidden = !withHead;
  head.innerHTML = !withHead ? '' : x.quiet
    ? gearHTML() + preCapsuleHTML() + (tab === 'now' ? preTitleHTML(x) : titleHTML(x.day))
    : gearHTML() + capsuleHTML(x.urg) + segmentsHTML(x) + titleHTML(tab === 'now' ? x.cday : x.day);
  document.querySelectorAll('.tc-tab').forEach(b => b.setAttribute('aria-selected', String(b.dataset.tab === tab)));
  root.dataset.tab = tab;
  const main = document.getElementById('todayBody');
  (RENDER[tab] || RENDER.now)(x, main);
  Ios.keepAwake(tab === 'now' && !!x.urg && x.urg.state === 'go');
}

function go(t) {
  if (t === 'map') {
    closeToday();
    const chip = document.getElementById('dayChips').children[viewDay || 1];
    if (chip) chip.click();
    return;
  }
  tab = t; S.tab = t; save();
  document.getElementById('today').scrollTop = 0;
  renderShell();
}

/* bottom sheet (settings, editors, event details) */
function sheet(title, bodyHTML, onReady) {
  let m = document.getElementById('tcSheet');
  if (!m) {
    m = document.createElement('div'); m.className = 'tc-sheet-bg'; m.id = 'tcSheet';
    m.setAttribute('role', 'dialog'); m.setAttribute('aria-modal', 'true');
    document.body.appendChild(m);
    m.addEventListener('click', e => { if (e.target === m) closeSheet(); });
  }
  m.innerHTML = `<div class="tc-sheet"><span class="tc-grab" aria-hidden="true"></span>
    <div class="tc-sheet-head"><h2>${esc(title)}</h2><button type="button" class="tc-x" id="tcSheetX" aria-label="Закрыть">${icon('close')}</button></div>
    ${bodyHTML}</div>`;
  m.dataset.th = document.getElementById('today').dataset.th || 'light';
  m.hidden = false;
  m.querySelector('#tcSheetX').addEventListener('click', closeSheet);
  if (onReady) onReady(m);
}
function closeSheet() { const m = document.getElementById('tcSheet'); if (m) { m.hidden = true; m.innerHTML = ''; } }
