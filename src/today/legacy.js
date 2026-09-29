/* ================= TODAY / trip dashboard =================
   Everything here runs on data baked into the page (DATA.today) plus two stores on this
   device: localStorage for ticks, skips, delays and spend, IndexedDB for ticket files.
   Nothing needs the network, so the screen works offline once the page is open. */
/* ---------- the trip: the built-in template, or the traveller's own copy on this device ---------- */
const TPL = DATA.today;
const TRIP_KEY = 'japan2026.trip.v1', SET_KEY = 'japan2026.settings.v1', ST_KEY = 'japan2026.today.v1';
const CUR = { KZT: { sym: '₸', rate: 2.81 }, USD: { sym: '$', rate: 0.0067 }, EUR: { sym: '€', rate: 0.0061 },
              RUB: { sym: '₽', rate: 0.56 }, JPY: { sym: '¥', rate: 1 } };
const clone = x => JSON.parse(JSON.stringify(x));
function loadTrip() {
  try { const j = JSON.parse(localStorage.getItem(TRIP_KEY) || 'null'); if (j && Array.isArray(j.days) && j.days.length) return j; } catch (e) {}
  return clone(TPL);
}
let T = loadTrip();
const isCustom = () => { try { return !!localStorage.getItem(TRIP_KEY); } catch (e) { return false; } };
function saveTrip() { try { localStorage.setItem(TRIP_KEY, JSON.stringify(T)); return true; } catch (e) { return false; } }
let SET = {};
function loadSettings() {
  let s = {};
  try { s = JSON.parse(localStorage.getItem(SET_KEY) || '{}') || {}; } catch (e) {}
  const cur = s.cur || T.currency || 'KZT';
  SET = { travelers: +(s.travelers || T.travelers || 2), start: s.start || T.start || T.days[0].date,
          cur, rate: +(s.rate || (cur === (T.currency || 'KZT') ? T.rate : 0) || (CUR[cur] || CUR.KZT).rate) };
}
loadSettings();
const saveSettings = () => { try { localStorage.setItem(SET_KEY, JSON.stringify(SET)); } catch (e) {} };
const MON = ['янв', 'фев', 'мар', 'апр', 'мая', 'июн', 'июл', 'авг', 'сен', 'окт', 'ноя', 'дек'];
const WD = ['воскресенье', 'понедельник', 'вторник', 'среда', 'четверг', 'пятница', 'суббота'];
const WD_SHORT = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];
const CAT = { transport: '🚆 транспорт', activity: '📍 место', event: '🎟 событие', food: '🍜 еда',
              hotel: '🏨 жильё', konbini: '🏪 конбини', routine: '⏰ быт', money: '💴 деньги' };
const STL = { fixed: '🔒 FIXED', planned: '🟢 PLANNED', flex: '🟡 FLEXIBLE', input: '⚠️ NEEDS INPUT' };
const STR = { fixed: 'fixed', planned: 'planned', flex: 'flex', input: 'input' };

/* ---------- state on this device ---------- */
let S = { done: {}, skip: {}, delay: {}, spent: {}, walked: {}, view: null, prevDay: 2, prevTime: '13:24', open: true };
try { Object.assign(S, JSON.parse(localStorage.getItem(ST_KEY) || '{}')); } catch (e) {}
const save = () => { try { localStorage.setItem(ST_KEY, JSON.stringify(S)); } catch (e) {} };

/* the pure logic lives in core.js */
const { pad, toMin, hm, dur, ddmmyyyy, addDays, japanNow, sunTimes, isAnchor, travel } = Core;
const dateOf = d => addDays(SET.start, d.n - 1);
const plan = (day, now) => Core.plan(day, now, S, dateOf(day));

/* ---------- time ---------- */
const yen = v => v == null ? '—' : '¥' + Math.round(v).toLocaleString('ru-RU');
const home = v => SET.cur === 'JPY' || v == null ? '' : Math.round(v * SET.rate).toLocaleString('ru-RU') + ' ' + (CUR[SET.cur] || CUR.KZT).sym;
const both = v => v == null || !v ? '—' : `${yen(v)}${home(v) ? ' · ' + home(v) : ''}`;
/* costs in the data are per person; shown for the whole group */
const money = pp => pp == null || !pp ? '—' : both(pp * SET.travelers);

const liveDayN = () => { const n = japanNow(); const d = T.days.find(x => dateOf(x) === n.date); return d ? d.n : null; };
/* the clock the screen reasons with: real Japan time during the trip, the preview clock before it */
function clock() {
  const live = liveDayN();
  if (live) return { live: true, day: live, min: japanNow().min };
  return { live: false, day: S.prevDay, min: toMin(S.prevTime || '09:00') };
}

/* ---------- tickets: files kept in this browser (IndexedDB), readable offline ---------- */
let idb = null;
function openDB() {
  if (idb) return Promise.resolve(idb);
  return new Promise((res, rej) => {
    try {
      const r = indexedDB.open('japan2026-tickets', 1);
      r.onupgradeneeded = () => r.result.createObjectStore('files');
      r.onsuccess = () => { idb = r.result; res(idb); };
      r.onerror = () => rej(r.error);
    } catch (e) { rej(e); }
  });
}
const tx = (mode, fn) => openDB().then(db => new Promise((res, rej) => {
  const t = db.transaction('files', mode); const st = t.objectStore('files');
  const r = fn(st); t.oncomplete = () => res(r && r.result); t.onerror = () => rej(t.error);
}));
const ticketPut = (id, file) => tx('readwrite', st => st.put({ name: file.name, type: file.type, blob: file, at: Date.now() }, id));
const ticketGet = id => tx('readonly', st => st.get(id));
const ticketDel = id => tx('readwrite', st => st.delete(id));
let haveTicket = {};
function refreshTickets() {
  return tx('readonly', st => st.getAllKeys()).then(keys => {
    haveTicket = {}; (keys || []).forEach(k => { haveTicket[k] = true; });
  }).catch(() => {});
}

/* ---------- rendering helpers ---------- */
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
const where = e => (e.lat != null && e.lng != null && e.lat !== '') ? `${e.lat}%2C${e.lng}` : encodeURIComponent((e.pname || e.to || e.t) + ' Japan');
const gmap = e => `https://www.google.com/maps/search/?api=1&query=${where(e)}`;
const groute = e => `https://www.google.com/maps/dir/?api=1&destination=${where(e)}&travelmode=transit`;
const pill = st => `<span class="td-pill ${STR[st]}">${STL[st]}</span>`;
const bookingById = id => T.bookings.find(b => b.id === id);
let viewDay = null;

function weatherFor(day) {
  try {
    const v = typeof wxFor === 'function' ? wxFor(day.wcity, dateOf(day)) : null;
    if (!v) return null;
    const src = WX.byCity[day.wcity] || {};
    const i = (src.time || []).indexOf(dateOf(day));
    const prob = src.precipitation_probability_max ? src.precipitation_probability_max[i] : null;
    return { ...v, prob, forecast: WX.source === 'forecast' };
  } catch (e) { return null; }
}

function render() {
  const root = document.getElementById('todayBody');
  if (!root) return;
  const c = clock();
  if (viewDay == null) viewDay = c.day;
  const day = T.days.find(d => d.n === viewDay) || T.days[0];
  const isClockDay = day.n === c.day;
  const now = isClockDay ? c.min : null;
  const evs = plan(day, now);
  const sun = day.sun ? sunTimes(dateOf(day), day.sun[0], day.sun[1]) : null;
  const wx = weatherFor(day);
  const dt = new Date(dateOf(day) + 'T12:00:00Z');
  const jp = japanNow();

  // NOW / NEXT on the clock day; on other days the first event is "next"
  const act = evs.filter(e => !e.skip && !e.auto);
  const cur = now == null ? null : act.find(e => e.ns <= now && now < e.ne) || null;
  // NEXT skips free time, wake-ups and konbini runs: it points at what the day hinges on
  const key = e => e.st !== 'flex' && e.cat !== 'routine' && e.cat !== 'konbini';
  const next = now == null ? act.find(key) || act[0] : act.find(e => e.ns > now && key(e)) || act.find(e => e.ns > now) || null;

  root.replaceChildren();

  /* header */
  const head = el('section', 'td-head');
  head.appendChild(el('div', 'td-toprow', `
    <span class="td-brand">${esc(T.name || 'Поездка')} · ${ddmmyyyy(dateOf(T.days[0])).slice(0, 5)}–${ddmmyyyy(dateOf(T.days[T.days.length - 1]))}</span>
    <button class="td-hbtn" type="button" id="tdSet" aria-label="Моя поездка: настройки">⚙ Моя поездка</button>
    <button class="td-hbtn" type="button" id="tdMap">🗺 Карта</button>
    <button class="td-hbtn" type="button" id="tdBook">🎫 Брони</button>`));
  const hero = el('div', 'td-hero');
  hero.innerHTML = `
    <div><div class="td-day">День ${day.n} из ${T.days.length} · ${esc(day.label)} <button class="td-mini" type="button" id="tdDayEdit" aria-label="Изменить день">✎</button></div>
      <div class="td-sub">${ddmmyyyy(dateOf(day))} · ${WD[dt.getUTCDay()]} · ${esc(day.city)}</div></div>
    <div class="td-clock td-mono">${c.live ? hm(jp.min) : hm(c.min)}<small>${c.live ? 'время в Японии' : 'предпросмотр'}</small></div>
    <div class="td-facts">
      <span>${wx ? (wx.code != null ? WX_ICON(wx.code) : '🌡️') + ' ' + wx.hi + '°' + (wx.lo != null ? ' / ' + wx.lo + '°' : '') +
        (wx.prob != null ? ' · дождь ' + wx.prob + '%' : wx.rain ? ' · осадки ' + wx.rain.toFixed(1) + ' мм' : '') +
        (wx.forecast ? '' : ' <small>(норма)</small>') : '🌡️ нет данных'}</span>
      ${sun ? `<span>🌅 ${hm(sun.rise)} · 🌇 ${hm(sun.set)}</span>` : ''}
      <span>🏨 ${esc(day.hotel)}</span>
    </div>`;
  head.appendChild(hero);
  if (!c.live) {
    const days = Math.round((Date.parse(dateOf(T.days[0])) - Date.parse(jp.date)) / 864e5);
    const pv = el('div', 'td-preview');
    pv.innerHTML = `<b>Предпросмотр</b><span>${days > 0 ? 'поездка через ' + days + ' дн.' : 'поездка завершена'} · «сейчас» =</span>
      <select id="tdPvDay" aria-label="День предпросмотра">${T.days.map(d => `<option value="${d.n}"${d.n === S.prevDay ? ' selected' : ''}>${ddmmyyyy(dateOf(d)).slice(0, 5)}</option>`).join('')}</select>
      <input id="tdPvTime" type="time" value="${S.prevTime}" aria-label="Время предпросмотра">`;
    head.appendChild(pv);
  }
  const dates = el('div', 'td-dates');
  T.days.forEach(d => {
    const b = el('button', 'td-date' + (d.n === day.n ? ' on' : '') + (c.live && d.n === c.day ? ' live' : ''));
    b.type = 'button';
    const iso = dateOf(d), w = new Date(iso + 'T12:00:00Z').getUTCDay();
    b.innerHTML = `<small>${WD_SHORT[w]}</small><b>${+iso.slice(8)}</b><small>${MON[+iso.slice(5, 7) - 1]}</small>`;
    b.addEventListener('click', () => { viewDay = d.n; render(); });
    dates.appendChild(b);
  });
  head.appendChild(dates);
  root.appendChild(head);

  /* compact NOW / NEXT */
  const quick = el('section', 'td-quick');
  const qNow = cur
    ? `<div class="td-qcard"><span class="td-qlabel">СЕЙЧАС ${pill(cur.st)}</span><span class="td-qtitle">${esc(cur.t)}</span>
       <span class="td-qtime td-mono">${hm(cur.ns)} → ${hm(cur.ne)} · осталось ${dur(cur.ne - now)}</span></div>`
    : `<div class="td-qcard"><span class="td-qlabel">СЕЙЧАС</span><span class="td-qtitle">${now == null ? 'Выбран другой день' : next ? 'Свободное время' : 'День завершён'}</span>
       <span class="td-qtime">${now == null ? 'Таймлайн ниже' : next ? 'до следующего пункта ' + dur(next.leave - now) : 'Отдыхайте'}</span></div>`;
  quick.innerHTML = qNow + (next
    ? `<div class="td-qcard"><span class="td-qlabel">ДАЛЬШЕ ${pill(next.st)}</span><span class="td-qtitle">${esc(next.t)}</span>
       <span class="td-qtime td-mono">${hm(next.ns)}${travel(next) ? ' · выйти в ' + hm(next.leave) + ' · 🚶+🚆 ' + dur(travel(next)) : ''}</span></div>`
    : `<div class="td-qcard"><span class="td-qlabel">ДАЛЬШЕ</span><span class="td-qtitle">На сегодня всё</span></div>`);
  root.appendChild(quick);

  /* NEXT — the big card */
  if (next) {
    const leaveIn = now == null ? null : next.leave - now;
    const startIn = now == null ? null : next.ns - now;
    const urgent = leaveIn != null && leaveIn < 30 && leaveIn >= 0;
    const go = leaveIn != null && leaveIn < 0 && startIn > 0;
    const card = el('section', 'td-next' + (go ? ' go' : urgent ? ' urgent' : ''));
    const bk = next.bk ? bookingById(next.bk) : null;
    const countTxt = now == null ? `<b class="td-mono">${hm(next.ns)}</b><span>первое в этот день</span>`
      : go ? `<b>ПОРА ВЫХОДИТЬ</b><span>начало через ${dur(startIn)}</span>`
      : travel(next) ? `<b class="td-mono">${dur(leaveIn)}</b><span>до выхода · в ${hm(next.leave)}</span>`
      : `<b class="td-mono">${dur(startIn)}</b><span>до начала</span>`;
    card.innerHTML = `
      <div class="td-nhead"><div><div class="td-qlabel">ДАЛЬШЕ ${pill(next.st)}</div>
        <div class="td-ntitle">${hm(next.ns)} ${esc(next.t)}</div></div>
        <div class="td-count">${countTxt}</div></div>
      ${go ? '<span class="td-go">TIME TO LEAVE · ВЫХОДИТЕ</span>' : ''}
      ${next.conflict ? `<div class="td-warn">⚠️ Не успеваете на ${dur(next.conflict)} — пропустите гибкий пункт или выходите раньше.</div>` : ''}
      <dl class="td-kv">
        <div><dt>Начало → конец</dt><dd class="td-mono">${hm(next.ns)} → ${hm(next.ne)}</dd></div>
        <div><dt>Длительность</dt><dd>${dur(next.ne - next.ns)}</dd></div>
        <div><dt>Выйти до</dt><dd class="td-mono">${travel(next) ? hm(next.leave) : '—'}</dd></div>
        <div><dt>Откуда</dt><dd>${esc(next.frm || '—')}</dd></div>
        <div><dt>Куда</dt><dd>${esc(next.to || next.t)}</dd></div>
        <div><dt>Пешком / в пути / запас</dt><dd>${next.walk || 0} / ${next.ride || 0} / ${next.buf || 0} мин</dd></div>
        <div><dt>Транспорт</dt><dd>${esc(next.mode || '—')}</dd></div>
        <div><dt>Рейс / поезд</dt><dd>${esc(next.num || '—')}</dd></div>
        <div><dt>Платформа / выход</dt><dd>${esc(next.plat || '—')}</dd></div>
        <div><dt>Бронь</dt><dd>${bk ? (bk.st === 'fixed' ? '✅ куплено' : '⚠️ не куплено') : '—'}</dd></div>
        <div><dt>Стоимость</dt><dd>${money(next.cost)}</dd></div>
        <div><dt>Город</dt><dd>${esc(day.city)}</dd></div>
      </dl>
      ${next.note ? `<div class="td-evnote">${esc(next.note)}</div>` : ''}
      <div class="td-actions">
        <a class="td-btn" href="${gmap(next)}" target="_blank" rel="noopener">🗺 OPEN MAP</a>
        <button class="td-btn" type="button" data-ticket="${next.bk || ''}" ${next.bk ? '' : 'disabled'}>🎫 SHOW TICKET</button>
        <a class="td-btn primary" href="${groute(next)}" target="_blank" rel="noopener">▶ START ROUTE</a>
        ${next.link ? `<a class="td-btn" href="${esc(next.link)}" target="_blank" rel="noopener">↗ Официальный сайт</a>` : ''}
      </div>`;
    root.appendChild(card);
  }

  /* transfer tonight */
  if (day.transfer) {
    const tr = day.transfer;
    const tb = el('section', 'td-transfer');
    tb.innerHTML = `<span class="td-trl">${day.n === 11 ? 'СЕГОДНЯ · ВЫЛЕТ' : 'СЕГОДНЯ ВЕЧЕРОМ · ПЕРЕЕЗД'}</span>
      <span class="route">${esc(tr.frm)} → ${esc(tr.to)}</span>
      <span class="td-mono">${tr.s} → ${tr.e} · ${esc(tr.how)} · ${esc(tr.dur)}</span>
      <ol>${tr.after.map(a => `<li>${esc(a)}</li>`).join('')}</ol>`;
    root.appendChild(tb);
  }

  /* progress + timeline */
  const counted = evs.filter(e => !e.skip && e.cat !== 'routine');
  const doneN = counted.filter(e => e.done).length;
  const sec = el('section', 'td-sec');
  sec.innerHTML = `<h3>Таймлайн дня <span class="r">${doneN} из ${counted.length} выполнено</span></h3>
    <div class="td-bar"><i style="width:${counted.length ? doneN / counted.length * 100 : 0}%"></i></div>`;
  const conflicts = evs.filter(e => e.conflict);
  if (conflicts.length) sec.appendChild(el('div', 'td-warn', conflicts.map(e => `⚠️ ${hm(e.S)} ${esc(e.t)}: не хватает ${dur(e.conflict)}. Пропустите гибкий пункт (🟡) — фиксированное не двигается.`).join('<br>')));
  const cutN = evs.filter(e => e.cut && !e.auto);
  if (cutN.length) sec.appendChild(el('div', 'td-evnote', '✂️ Сокращено ради следующего фиксированного пункта: ' + cutN.map(e => `${esc(e.t)} (−${e.cut} мин)`).join(', ')));
  const tl = el('div', 'td-tl');
  evs.forEach(e => {
    const moved = e.ns !== e.S || e.ne !== e.E;
    const row = el('div', `td-ev st-${STR[e.st]}${e.done ? ' done' : ''}${e.skip || e.auto ? ' skip' : ''}${cur && cur.id === e.id ? ' now' : ''}`);
    const bk = e.bk ? bookingById(e.bk) : null;
    const past = now != null && e.ne <= now;
    row.innerHTML = `<span class="td-rail"></span>
      <div class="td-evtime td-mono">${hm(e.ns)}${e.ne - e.ns > 15 || e.e ? '<br>→ ' + hm(e.ne) : ''}
        <small>${dur(e.ne - e.ns)}</small>${moved && !e.skip ? `<s>${hm(e.S)}–${hm(e.E)}</s>` : ''}</div>
      <div><div class="td-evt">${esc(e.t)}</div>
        <div class="td-evmeta">${pill(e.st)}<span>${CAT[e.cat] || e.cat}</span><span>${esc(day.city)}</span>
          ${travel(e) ? `<span>выйти ${hm(e.leave)}</span>` : ''}
          ${e.walk ? `<span>🚶 ${e.walk} мин</span>` : ''}${e.ride ? `<span>🚆 ${e.ride} мин</span>` : ''}
          ${e.cost ? `<span>${money(e.cost)}</span>` : ''}
          ${bk ? `<span>${bk.st === 'fixed' ? '✅ бронь' : '⚠️ купить'}</span>` : ''}
          ${e.auto ? '<span class="td-pill warn">убрано ради расписания</span>' : ''}${e.bound ? `<span class="td-pill ${e.off ? 'warn' : 'muted'}">📅 только ${ddmmyyyy(e.bound)}</span>` : ''}</div>
        ${e.note ? `<div class="td-evnote">${esc(e.note)}</div>` : ''}
        <div class="td-evbtns">
          <button class="td-mini${e.done ? ' on' : ''}" type="button" data-done="${e.id}">✓ ${e.done ? 'Сделано' : 'Отметить'}</button>
          ${e.st !== 'fixed' && !past ? `<button class="td-mini" type="button" data-skip="${e.id}">${e.skip ? '↺ Вернуть' : '⏭ Пропустить'}</button>` : ''}
          ${e.st !== 'fixed' && !isAnchor(e) && !e.skip && !past ? `<button class="td-mini" type="button" data-delay="${e.id}" data-by="15">+15</button>
            <button class="td-mini" type="button" data-delay="${e.id}" data-by="30">+30</button>
            ${e.delay ? `<button class="td-mini" type="button" data-delay="${e.id}" data-by="0">сброс (+${e.delay})</button>` : ''}` : ''}
          <a class="td-mini" href="${gmap(e)}" target="_blank" rel="noopener">Карта</a>
          ${e.bk ? `<button class="td-mini" type="button" data-ticket="${e.bk}">Билет</button>` : ''}
          <button class="td-mini" type="button" data-edit="${e.id}" aria-label="Изменить пункт">✎</button>
        </div></div>`;
    tl.appendChild(row);
  });
  sec.appendChild(tl);
  const addB = el('button', 'td-btn', '＋ Добавить пункт'); addB.type = 'button'; addB.id = 'tdAdd';
  sec.appendChild(addB);
  root.appendChild(sec);

  /* daily statistics */
  const live = evs.filter(e => !e.skip && !e.auto);
  const kmPlan = live.reduce((s, e) => s + (e.km || 0) + (e.walk || 0) / 60 * 4.5, 0);
  const trMin = live.reduce((s, e) => s + (e.cat === 'transport' ? e.ne - e.ns : 0) + (e.ride || 0), 0);
  const budget = live.reduce((s, e) => s + (e.cost || 0), 0);
  const spent = S.spent[day.n];
  const crit = [...live].reverse().find(e => isAnchor(e) && e.cat !== 'hotel') || null;
  const st = el('section', 'td-sec');
  st.innerHTML = `<h3>Статистика дня</h3>
    <div class="td-stats">
      <div class="td-stat"><span>Пешком: план / факт</span><b>${kmPlan.toFixed(1)} км / ${S.walked[day.n] != null ? S.walked[day.n] + ' км' : '—'}</b>
        <input type="number" min="0" step="0.5" id="tdWalk" placeholder="км факт" value="${S.walked[day.n] ?? ''}"></div>
      <div class="td-stat"><span>Транспорт</span><b>${dur(trMin)}</b></div>
      <div class="td-stat"><span>Пунктов</span><b>${live.filter(e => e.cat !== 'routine').length}</b></div>
      <div class="td-stat"><span>Бюджет: план</span><b>${money(budget)}</b></div>
      <div class="td-stat"><span>Потрачено, ¥</span><b>${spent != null ? both(spent) : '—'}</b>
        <input type="number" min="0" step="100" id="tdSpent" placeholder="¥ факт" value="${spent ?? ''}"></div>
      <div class="td-stat"><span>Погода</span><b>${wx ? wx.hi + '° / ' + (wx.lo ?? '—') + '°' + (wx.prob != null ? ' · ' + wx.prob + '%' : '') : '—'}</b></div>
      <div class="td-stat"><span>Закат</span><b class="td-mono">${sun ? hm(sun.set) : '—'}</b></div>
      <div class="td-stat" style="grid-column: span 2"><span>Критичный дедлайн</span><b>${crit ? hm(crit.ns) + ' · ' + esc(crit.t) : '—'}</b></div>
    </div>`;
  root.appendChild(st);

  /* today's bookings */
  const bks = T.bookings.filter(b => b.days.includes(day.n));
  const bs = el('section', 'td-sec'); bs.id = 'tdBookings';
  bs.innerHTML = `<h3>Брони дня <span class="r">${bks.filter(b => b.st === 'fixed').length} из ${bks.length} куплено</span></h3>`;
  const bl = el('div', 'td-bk');
  if (!bks.length) bl.appendChild(el('div', 'td-bkrow', '<small>На этот день броней нет.</small>'));
  bks.forEach(b => {
    const r = el('div', 'td-bkrow');
    r.innerHTML = `<div><b><button class="td-mini${b.st === 'fixed' ? ' on' : ''}" type="button" data-bkst="${b.id}" aria-label="Отметить бронь как купленную">${b.st === 'fixed' ? '✅ куплено' : '⚠️ купить'}</button> ${esc(b.t)}</b><small>${esc(b.when)}${b.cost ? ' · ' + money(b.cost) : ''}</small></div>
      <div class="td-bkbtns">${haveTicket[b.id]
        ? `<button class="td-mini on" type="button" data-ticket="${b.id}">Показать билет</button>
           <button class="td-mini" type="button" data-rmticket="${b.id}">✕</button>`
        : `<label class="td-mini" style="cursor:pointer">📎 Прикрепить<input type="file" accept="image/*,application/pdf" data-attach="${b.id}" hidden></label>`}</div>`;
    bl.appendChild(r);
  });
  bs.appendChild(bl);
  bs.appendChild(el('div', 'td-evnote', 'Скриншот QR-кода или PDF хранится только в этом браузере на этом телефоне и открывается без интернета. Лучше всего — картинка с QR.'));
  root.appendChild(bs);

  /* trip overview */
  const ov = el('section', 'td-sec');
  ov.innerHTML = '<h3>Вся поездка</h3>';
  const ol = el('div', 'td-ov');
  T.days.forEach(d => {
    const p = plan(d, null).filter(e => !e.skip && e.cat !== 'routine');
    const b = el('button', 'td-ovrow' + (d.n === day.n ? ' on' : ''));
    b.type = 'button';
    b.innerHTML = `<b class="td-mono">${+dateOf(d).slice(8)}</b><span>${esc(d.label)}<br><small>${esc(d.summary)}</small></span>
      <small class="td-mono">${p.filter(e => e.done).length}/${p.length}</small>`;
    b.addEventListener('click', () => { viewDay = d.n; render(); document.getElementById('today').scrollTo({ top: 0, behavior: 'smooth' }); });
    ol.appendChild(b);
  });
  ov.appendChild(ol);
  root.appendChild(ov);
  root.appendChild(el('p', 'td-foot', `${SET.cur !== 'JPY' ? 'Курс: 1 ¥ = ' + SET.rate + ' ' + (CUR[SET.cur] || CUR.KZT).sym + ' · ' : ''}цены — на ${SET.travelers} чел. · «~» в заметках = оценка · ${isCustom() ? 'ваша версия поездки' : 'шаблон маршрута'}. Всё хранится на этом устройстве.`));

  wire(root, day);
}

/* ---------- interactions ---------- */
function wire(root, day) {
  root.querySelector('#tdMap').addEventListener('click', () => {
    closeToday();
    const chip = document.getElementById('dayChips').children[day.n];
    if (chip) chip.click();
  });
  root.querySelector('#tdSet').addEventListener('click', openSettings);
  root.querySelector('#tdDayEdit').addEventListener('click', () => openDayEditor(day));
  root.querySelector('#tdAdd').addEventListener('click', () => openEditor(day, null));
  root.querySelectorAll('[data-edit]').forEach(b => b.addEventListener('click', () => openEditor(day, b.dataset.edit)));
  root.querySelectorAll('[data-bkst]').forEach(b => b.addEventListener('click', () => {
    const bk = bookingById(b.dataset.bkst); if (!bk) return;
    bk.st = bk.st === 'fixed' ? 'input' : 'fixed'; saveTrip(); render();
  }));
  root.querySelector('#tdBook').addEventListener('click', () =>
    document.getElementById('tdBookings').scrollIntoView({ behavior: 'smooth', block: 'start' }));
  const pd = root.querySelector('#tdPvDay'), pt = root.querySelector('#tdPvTime');
  if (pd) pd.addEventListener('change', () => { S.prevDay = +pd.value; viewDay = S.prevDay; save(); render(); });
  if (pt) pt.addEventListener('change', () => { if (pt.value) { S.prevTime = pt.value; save(); render(); } });
  root.querySelectorAll('[data-done]').forEach(b => b.addEventListener('click', () => {
    const id = b.dataset.done; if (S.done[id]) delete S.done[id]; else S.done[id] = true; save(); render();
  }));
  root.querySelectorAll('[data-skip]').forEach(b => b.addEventListener('click', () => {
    const id = b.dataset.skip; if (S.skip[id]) delete S.skip[id]; else S.skip[id] = true; save(); render();
  }));
  root.querySelectorAll('[data-delay]').forEach(b => b.addEventListener('click', () => {
    const id = b.dataset.delay, by = +b.dataset.by;
    if (!by) delete S.delay[id]; else S.delay[id] = (S.delay[id] || 0) + by; save(); render();
  }));
  root.querySelectorAll('[data-ticket]').forEach(b => b.addEventListener('click', () => showTicket(b.dataset.ticket)));
  root.querySelectorAll('[data-rmticket]').forEach(b => b.addEventListener('click', () => {
    if (b.dataset.confirm) { ticketDel(b.dataset.rmticket).then(refreshTickets).then(render); return; }
    b.dataset.confirm = '1'; b.textContent = 'Удалить?'; setTimeout(() => { if (b.isConnected) { delete b.dataset.confirm; b.textContent = '✕'; } }, 4000);
  }));
  root.querySelectorAll('[data-attach]').forEach(inp => inp.addEventListener('change', () => {
    const f = inp.files && inp.files[0]; if (!f) return;
    ticketPut(inp.dataset.attach, f).then(refreshTickets).then(render).catch(() => alertLine('Не удалось сохранить файл в этом браузере.'));
  }));
  const w = root.querySelector('#tdWalk'), sp = root.querySelector('#tdSpent');
  w.addEventListener('change', () => { if (w.value === '') delete S.walked[day.n]; else S.walked[day.n] = +w.value; save(); render(); });
  sp.addEventListener('change', () => { if (sp.value === '') delete S.spent[day.n]; else S.spent[day.n] = +sp.value; save(); render(); });
}
function alertLine(msg) { const r = document.getElementById('todayBody'); r.prepend(el('div', 'td-warn', esc(msg))); }

let ticketURL = null;
function showTicket(id) {
  const box = document.getElementById('tdTicket');
  const b = bookingById(id);
  const cap = document.getElementById('tdTicketCap');
  const holder = box.querySelector('.hold');
  holder.replaceChildren();
  if (ticketURL) { URL.revokeObjectURL(ticketURL); ticketURL = null; }
  cap.textContent = b ? `${b.t} · ${b.when}` : 'Билет';
  ticketGet(id).then(rec => {
    if (!rec) { holder.appendChild(el('p', null, 'Билет ещё не прикреплён. Прикрепите скриншот QR в разделе «Брони дня».')); return; }
    ticketURL = URL.createObjectURL(rec.blob);
    if ((rec.type || '').startsWith('image/')) { const i = new Image(); i.src = ticketURL; i.alt = 'Билет'; holder.appendChild(i); }
    else { const f = document.createElement('iframe'); f.src = ticketURL; f.title = 'Билет'; holder.appendChild(f);
           holder.appendChild(el('p', null, 'Если PDF не показался — прикрепите вместо него скриншот QR.')); }
  }).catch(() => holder.appendChild(el('p', null, 'Хранилище билетов недоступно в этом окне.')));
  box.hidden = false;
}

/* ---------- modal: settings, event editor, day editor ---------- */
function modal(title, bodyHTML, onReady) {
  let m = document.getElementById('tdModal');
  if (!m) {
    m = el('div', 'td-modal'); m.id = 'tdModal'; m.setAttribute('role', 'dialog'); m.setAttribute('aria-modal', 'true');
    document.body.appendChild(m);
    m.addEventListener('click', e => { if (e.target === m) closeModal(); });
  }
  m.innerHTML = `<div class="td-mbox"><div class="td-mhead"><b>${esc(title)}</b>
    <button class="td-mini" type="button" id="tdMClose" aria-label="Закрыть">✕</button></div>${bodyHTML}</div>`;
  m.hidden = false;
  m.querySelector('#tdMClose').addEventListener('click', closeModal);
  onReady(m);
  const first = m.querySelector('input,select,textarea'); if (first) first.focus();
}
function closeModal() { const m = document.getElementById('tdModal'); if (m) m.hidden = true; }
const fld = (id, label, val, type = 'text', extra = '') =>
  `<label class="td-f" for="${id}">${label}<input id="${id}" type="${type}" value="${esc(val == null ? '' : val)}" ${extra}></label>`;
const sel = (id, label, val, opts) =>
  `<label class="td-f" for="${id}">${label}<select id="${id}">${opts.map(([k, v]) => `<option value="${k}"${k === val ? ' selected' : ''}>${esc(v)}</option>`).join('')}</select></label>`;

function openSettings() {
  const custom = isCustom();
  modal('Моя поездка', `
    <p class="td-evnote">Маршрут — шаблон «${esc(TPL.name)}». Меняйте даты, число людей и валюту, правьте пункты ✎ —
      всё сохраняется только на этом устройстве. Экспорт даёт файл, который можно открыть на другом телефоне или отдать друзьям.</p>
    <div class="td-fgrid">
      ${fld('setName', 'Название', T.name || '')}
      ${fld('setTrav', 'Путешественников', SET.travelers, 'number', 'min="1" max="20" step="1"')}
      ${fld('setStart', 'Первый день', SET.start, 'date')}
      ${sel('setCur', 'Валюта дома', SET.cur, Object.keys(CUR).map(k => [k, k + ' ' + CUR[k].sym]))}
      ${fld('setRate', 'Курс: 1 ¥ =', SET.rate, 'number', 'min="0" step="0.0001"')}
    </div>
    <p class="td-evnote">Курсы по умолчанию примерные — впишите актуальный. Сдвиг даты переносит весь маршрут;
      события с 📅 (например, финалы Asian Para Games) привязаны к своей дате и помечаются ⚠️, если не совпадают.</p>
    <div class="td-actions"><button class="td-btn primary" type="button" id="setSave">Сохранить</button></div>
    <h4 class="td-mh">Поделиться или перенести</h4>
    <div class="td-actions">
      <button class="td-btn" type="button" id="setExport">⬇ Экспорт JSON</button>
      <label class="td-btn" style="cursor:pointer">⬆ Импорт из файла<input type="file" id="setFile" accept="application/json,.json" hidden></label>
      <button class="td-btn" type="button" id="setReset">${custom ? '↺ Вернуть шаблон' : 'Шаблон активен'}</button>
    </div>
    <label class="td-f" for="setJson">JSON поездки (можно вставить свой и нажать «Загрузить»)<textarea id="setJson" rows="5" spellcheck="false"></textarea></label>
    <div class="td-actions"><button class="td-btn" type="button" id="setLoad">Загрузить из текста</button>
      <button class="td-btn" type="button" id="setCopy">Скопировать</button></div>
    <p class="td-evnote" id="setMsg" role="status"></p>`, m => {
    const msg = t => { m.querySelector('#setMsg').textContent = t; };
    m.querySelector('#setCur').addEventListener('change', e => { m.querySelector('#setRate').value = (CUR[e.target.value] || CUR.KZT).rate; });
    m.querySelector('#setSave').addEventListener('click', () => {
      const name = m.querySelector('#setName').value.trim();
      if (name && name !== T.name) { T.name = name; saveTrip(); }
      SET.travelers = Math.max(1, Math.min(20, +m.querySelector('#setTrav').value || 1));
      SET.start = m.querySelector('#setStart').value || SET.start;
      SET.cur = m.querySelector('#setCur').value;
      SET.rate = +m.querySelector('#setRate').value || (CUR[SET.cur] || CUR.KZT).rate;
      saveSettings(); setTitle(); viewDay = null; render(); msg('Сохранено.');
    });
    const exportObj = () => ({ ...T, travelers: SET.travelers, start: SET.start, currency: SET.cur, rate: SET.rate,
                               exported: new Date().toISOString() });
    m.querySelector('#setExport').addEventListener('click', () => {
      const txt = JSON.stringify(exportObj(), null, 1);
      m.querySelector('#setJson').value = txt;
      try {
        const a = document.createElement('a');
        a.href = URL.createObjectURL(new Blob([txt], { type: 'application/json' }));
        a.download = (T.name || 'trip').replace(/[^\p{L}\p{N}]+/gu, '_').slice(0, 40) + '.json';
        document.body.appendChild(a); a.click(); a.remove();
        msg('Файл сохранён. Если скачивание не началось — JSON в поле ниже, его можно скопировать.');
      } catch (e) { msg('JSON в поле ниже — скопируйте его.'); }
    });
    m.querySelector('#setCopy').addEventListener('click', () => {
      const ta = m.querySelector('#setJson');
      if (!ta.value) ta.value = JSON.stringify(exportObj(), null, 1);
      ta.select();
      (navigator.clipboard ? navigator.clipboard.writeText(ta.value) : Promise.reject()).then(() => msg('Скопировано.'), () => msg('Выделено — скопируйте вручную.'));
    });
    const load = txt => {
      let j; try { j = JSON.parse(txt); } catch (e) { msg('Это не JSON. Проверьте, что скопирован весь текст.'); return; }
      const ok = Core.validTrip(j);
      if (!ok) { msg('Файл не похож на поездку: нужен список days, у каждого дня n и ev с полями s и t.'); return; }
      j.bookings = Array.isArray(j.bookings) ? j.bookings : [];
      T = j; saveTrip();
      SET = { travelers: +(j.travelers || 2), start: j.start || j.days[0].date || SET.start, cur: j.currency || SET.cur,
              rate: +(j.rate || (CUR[j.currency] || CUR.KZT).rate) };
      saveSettings();
      S.done = {}; S.skip = {}; S.delay = {}; S.spent = {}; S.walked = {}; save();
      setTitle(); viewDay = null; closeModal(); render();
    };
    m.querySelector('#setLoad').addEventListener('click', () => load(m.querySelector('#setJson').value));
    m.querySelector('#setFile').addEventListener('change', e => {
      const f = e.target.files && e.target.files[0]; if (!f) return;
      f.text().then(load, () => msg('Не удалось прочитать файл.'));
    });
    m.querySelector('#setReset').addEventListener('click', e => {
      if (!isCustom()) return;
      if (!e.target.dataset.sure) { e.target.dataset.sure = '1'; e.target.textContent = 'Точно? Ваши правки удалятся'; return; }
      try { localStorage.removeItem(TRIP_KEY); localStorage.removeItem(SET_KEY); } catch (err) {}
      T = clone(TPL); loadSettings(); S.done = {}; S.skip = {}; S.delay = {}; save();
      setTitle(); viewDay = null; closeModal(); render();
    });
  });
}

const CATS = Object.entries(CAT);
const STS = Object.entries(STL);
function openEditor(day, id) {
  const d = T.days.find(x => x.n === day.n);
  const e = id ? d.ev.find(x => x.id === id) : { s: '12:00', e: '13:00', t: '', st: 'planned', cat: 'activity' };
  if (!e) return;
  modal(id ? 'Изменить пункт' : 'Новый пункт · день ' + day.n, `
    <div class="td-fgrid">
      ${fld('edT', 'Что', e.t, 'text', 'required')}
      ${fld('edS', 'Начало', e.s, 'time')}
      ${fld('edE', 'Конец', e.e || '', 'time')}
      ${sel('edSt', 'Статус', e.st, STS)}
      ${sel('edCat', 'Тип', e.cat, CATS)}
      ${fld('edPlace', 'Место (для карты)', e.pname || '')}
      ${fld('edLat', 'Широта', e.lat ?? '', 'number', 'step="any"')}
      ${fld('edLng', 'Долгота', e.lng ?? '', 'number', 'step="any"')}
      ${fld('edWalk', 'Пешком до места, мин', e.walk || 0, 'number', 'min="0"')}
      ${fld('edRide', 'Транспорт до места, мин', e.ride || 0, 'number', 'min="0"')}
      ${fld('edBuf', 'Запас, мин', e.buf || 0, 'number', 'min="0"')}
      ${fld('edCost', 'Цена на человека, ¥', e.cost || '', 'number', 'min="0" step="10"')}
      ${fld('edMode', 'Транспорт (вид)', e.mode || '')}
      ${fld('edNum', 'Рейс / поезд', e.num || '')}
      ${fld('edFrm', 'Откуда', e.frm || '')}
      ${fld('edTo', 'Куда', e.to || '')}
      ${fld('edPlat', 'Платформа / выход', e.plat || '')}
      ${fld('edLink', 'Ссылка', e.link || '', 'url')}
    </div>
    <label class="td-f" for="edNote">Заметки<textarea id="edNote" rows="3">${esc(e.note || '')}</textarea></label>
    <div class="td-actions"><button class="td-btn primary" type="button" id="edSave">Сохранить</button>
      ${id ? '<button class="td-btn" type="button" id="edDel">Удалить пункт</button>' : ''}</div>
    <p class="td-evnote" id="edMsg" role="status"></p>`, m => {
    const v = k => m.querySelector('#' + k).value.trim();
    const num = k => { const x = v(k); return x === '' ? null : +x; };
    m.querySelector('#edSave').addEventListener('click', () => {
      if (!v('edT') || !v('edS')) { m.querySelector('#edMsg').textContent = 'Нужны название и время начала.'; return; }
      const x = id ? e : { id: 'u' + Date.now().toString(36) };
      Object.assign(x, { t: v('edT'), s: v('edS'), e: v('edE') || null, st: v('edSt'), cat: v('edCat'), pname: v('edPlace'),
        lat: num('edLat'), lng: num('edLng'), walk: num('edWalk') || 0, ride: num('edRide') || 0, buf: num('edBuf') || 0,
        cost: num('edCost'), mode: v('edMode'), num: v('edNum'), frm: v('edFrm'), to: v('edTo'), plat: v('edPlat'),
        link: Core.safeUrl(v('edLink')), note: v('edNote') });
      if (!id) d.ev.push(x);
      d.ev.sort((a, b) => a.s.localeCompare(b.s));
      saveTrip(); closeModal(); render();
    });
    const del = m.querySelector('#edDel');
    if (del) del.addEventListener('click', () => {
      if (!del.dataset.sure) { del.dataset.sure = '1'; del.textContent = 'Точно удалить?'; return; }
      d.ev = d.ev.filter(x => x.id !== id); saveTrip(); closeModal(); render();
    });
  });
}
function openDayEditor(day) {
  const d = T.days.find(x => x.n === day.n);
  modal('День ' + day.n, `
    <div class="td-fgrid">
      ${fld('dyLabel', 'Короткое название', d.label)}
      ${fld('dyCity', 'Город', d.city)}
      ${fld('dyHotel', 'Отель на эту ночь', d.hotel)}
    </div>
    <label class="td-f" for="dySum">Главное за день<textarea id="dySum" rows="2">${esc(d.summary || '')}</textarea></label>
    <div class="td-actions"><button class="td-btn primary" type="button" id="dySave">Сохранить</button></div>`, m => {
    m.querySelector('#dySave').addEventListener('click', () => {
      const v = k => m.querySelector('#' + k).value.trim();
      d.label = v('dyLabel') || d.label; d.city = v('dyCity') || d.city; d.hotel = v('dyHotel'); d.summary = v('dySum');
      saveTrip(); closeModal(); render();
    });
  });
}
function setTitle() {
  const t = document.getElementById('tripTitle');
  if (t) t.textContent = '🇯🇵 ' + (T.name || 'Поездка');
  document.title = T.name || 'Поездка';
}

function openToday() { document.getElementById('today').hidden = false; S.open = true; save(); viewDay = null; render(); }
function closeToday() { document.getElementById('today').hidden = true; S.open = false; save(); }
window.openToday = openToday;

document.getElementById('btnToday').addEventListener('click', openToday);
document.getElementById('tdTicketClose').addEventListener('click', () => { document.getElementById('tdTicket').hidden = true; });
document.addEventListener('keydown', e => { if (e.key === 'Escape') { document.getElementById('tdTicket').hidden = true; closeModal(); } });
setTitle();

/* A personal link carries the whole trip after '#trip=' (deflate + base64url). The part after '#'
   never reaches the server, so a private trip travels in the link, not in the public repo. */
async function tripFromHash() {
  const m = location.hash.match(/^#trip=([A-Za-z0-9_-]+)/);
  if (!m || typeof DecompressionStream === 'undefined') return false;
  try {
    const b64 = m[1].replace(/-/g, '+').replace(/_/g, '/');
    const bin = Uint8Array.from(atob(b64 + '='.repeat((4 - b64.length % 4) % 4)), c => c.charCodeAt(0));
    const txt = await new Response(new Blob([bin]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).text();
    const j = JSON.parse(txt);
    if (!j || !Array.isArray(j.days) || !j.days.length) return false;
    T = j; saveTrip();
    SET = { travelers: +(j.travelers || 2), start: j.start || j.days[0].date, cur: j.currency || 'KZT',
            rate: +(j.rate || (CUR[j.currency] || CUR.KZT).rate) };
    saveSettings(); setTitle();
    history.replaceState(null, '', location.pathname + location.search);   // don't leave the trip in the address bar
    return true;
  } catch (e) { return false; }
}
tripFromHash().then(ok => { if (ok) { viewDay = null; render(); } });
refreshTickets().then(render);
// '#map' in the link opens straight onto the map (also used by the map tests)
if (S.open === false || location.hash === '#map') document.getElementById('today').hidden = true; else render();
setInterval(() => {
  const a = document.activeElement;
  if (document.getElementById('today').hidden) return;
  if (a && a.closest && a.closest('#today') && /INPUT|SELECT/.test(a.tagName)) return;   // don't wipe what is being typed
  render();
}, 30000);

/* On a real web host (GitHub Pages) the guide installs as an app and keeps working offline. */
if (/^https?:$/.test(location.protocol) && /github\.io$|^localhost$|^127\.0\.0\.1$/.test(location.hostname)) {
  const add = (rel, href) => { const l = document.createElement('link'); l.rel = rel; l.href = href; document.head.appendChild(l); };
  add('manifest', 'manifest.webmanifest'); add('apple-touch-icon', 'icon-192.png');
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
}
window.addEventListener('japan2026:wx', render);
