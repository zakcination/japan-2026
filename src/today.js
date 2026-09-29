/* ================= TODAY / trip dashboard =================
   Everything here runs on data baked into the page (DATA.today) plus two stores on this
   device: localStorage for ticks, skips, delays and spend, IndexedDB for ticket files.
   Nothing needs the network, so the screen works offline once the page is open. */
(function () {
const T = DATA.today;
const FX = T.fx;
const TRIP0 = T.days[0].date, TRIP1 = T.days[T.days.length - 1].date;
const ST_KEY = 'japan2026.today.v1';
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

/* ---------- time ---------- */
const pad = n => String(n).padStart(2, '0');
const toMin = hm => { const [h, m] = hm.split(':').map(Number); return h * 60 + m; };
const hm = m => { m = ((Math.round(m) % 1440) + 1440) % 1440; return pad(Math.floor(m / 60)) + ':' + pad(m % 60); };
const dur = m => { m = Math.max(0, Math.round(m)); const h = Math.floor(m / 60); return h ? `${h} ч ${pad(m % 60)} мин` : `${m} мин`; };
const ddmmyyyy = iso => { const [y, m, d] = iso.split('-'); return `${d}.${m}.${y}`; };
const yen = v => v == null ? '—' : '¥' + Math.round(v).toLocaleString('ru-RU');
const kzt = v => v == null ? '' : Math.round(v * FX).toLocaleString('ru-RU') + ' ₸';
const money = v => v == null || !v ? '—' : `${yen(v)} · ${kzt(v)}`;

function japanNow() {
  const p = {};
  new Intl.DateTimeFormat('en-GB', { timeZone: 'Asia/Tokyo', year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
    .formatToParts(new Date()).forEach(x => { p[x.type] = x.value; });
  return { date: `${p.year}-${p.month}-${p.day}`, min: (+p.hour % 24) * 60 + +p.minute, sec: +p.second };
}
const liveDayN = () => { const n = japanNow(); const d = T.days.find(x => x.date === n.date); return d ? d.n : null; };
/* the clock the screen reasons with: real Japan time during the trip, the preview clock before it */
function clock() {
  const live = liveDayN();
  if (live) return { live: true, day: live, min: japanNow().min };
  return { live: false, day: S.prevDay, min: toMin(S.prevTime || '09:00') };
}

/* ---------- sunrise / sunset (NOAA approximation, local, no network) ---------- */
function sunTimes(iso, lat, lng) {
  const rad = Math.PI / 180, d = new Date(iso + 'T12:00:00Z');
  const n = Math.floor((d - Date.UTC(d.getUTCFullYear(), 0, 0)) / 864e5);
  const g = 2 * Math.PI / 365 * (n - 1);
  const eq = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  const decl = 0.006918 - 0.399912 * Math.cos(g) + 0.070257 * Math.sin(g) - 0.006758 * Math.cos(2 * g) + 0.000907 * Math.sin(2 * g)
             - 0.002697 * Math.cos(3 * g) + 0.00148 * Math.sin(3 * g);
  const ha = Math.acos(Math.cos(90.833 * rad) / (Math.cos(lat * rad) * Math.cos(decl)) - Math.tan(lat * rad) * Math.tan(decl)) / rad;
  const noon = 720 - 4 * lng - eq + 540;            // minutes, Japan time (UTC+9)
  return { rise: noon - 4 * ha, set: noon + 4 * ha };
}

/* ---------- the replanner ----------
   Anchors never move: fixed events, intercity transport and hotel check-ins still to be booked.
   A delay pushes what follows; before an anchor the overrun is paid back from flexible blocks
   first (latest first, down to nothing), then planned ones (down to half, never under 15 min).
   What can't be paid back is shown as a conflict on the anchor — nothing extra is ever suggested. */
const isAnchor = e => e.st === 'fixed' || ((e.cat === 'transport' || e.cat === 'hotel') && e.st === 'input');
const travel = e => (e.walk || 0) + (e.ride || 0) + (e.buf || 0);

function plan(day, now) {
  const evs = day.ev.map(e => {
    const s = toMin(e.s), en = e.e ? toMin(e.e) : s + 15;
    return { ...e, S: s, E: en < s ? en + 1440 : en, ns: s, ne: 0, cut: 0, auto: false, conflict: 0,
             skip: !!S.skip[e.id], done: !!S.done[e.id], delay: +(S.delay[e.id] || 0) };
  });
  let t = null, seg = [];
  for (const e of evs) {
    if (e.skip) { e.ns = e.S; e.ne = e.E; continue; }
    const reach = (e.walk || 0) + (e.ride || 0);
    if (isAnchor(e)) {
      e.ns = e.S; e.ne = e.E + (e.st === 'fixed' ? 0 : e.delay);
      let over = t == null ? 0 : t + reach + (e.buf || 0) - e.S;
      if (over > 0) {
        // only what hasn't happened yet can give time back: future blocks, and the rest of the current one
        const open = x => now == null || x.ne > now;
        const future = seg.filter(open);
        const order = [...future.filter(x => x.st === 'flex').reverse(), ...future.filter(x => x.st !== 'flex').reverse()];
        for (const x of order) {
          if (over <= 0) break;
          const len = x.ne - Math.max(x.ns, now == null ? -1e9 : now);
          const keep = x.st === 'flex' ? 0 : Math.max(15, Math.round((x.E - x.S) / 2));
          const can = Math.max(0, Math.min(len, x.ne - x.ns - keep));
          const c = Math.min(can, over);
          if (!c) continue;
          x.ne -= c; x.cut += c; over -= c;
          if (x.ne - x.ns <= 0) x.auto = true;
          // everything after x in the segment slides earlier by c
          const i = seg.indexOf(x);
          seg.slice(i + 1).forEach(y => { y.ns -= c; y.ne -= c; });
        }
        if (over > 0) e.conflict = over;
      }
      t = e.ne; seg = [];
    } else {
      e.ns = t == null ? e.S : Math.max(e.S, t + reach);
      e.ne = e.ns + (e.E - e.S) + e.delay;
      t = e.ne; seg.push(e);
    }
    e.leave = e.ns - travel(e);
  }
  evs.forEach(e => { if (e.leave == null) e.leave = e.ns - travel(e); });
  return evs;
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
const gmap = e => `https://www.google.com/maps/search/?api=1&query=${e.lat}%2C${e.lng}`;
const groute = e => `https://www.google.com/maps/dir/?api=1&destination=${e.lat}%2C${e.lng}&travelmode=transit`;
const pill = st => `<span class="td-pill ${STR[st]}">${STL[st]}</span>`;
const bookingById = id => T.bookings.find(b => b.id === id);
let viewDay = null;

function weatherFor(day) {
  try {
    const v = typeof wxFor === 'function' ? wxFor(day.wcity, day.date) : null;
    if (!v) return null;
    const src = WX.byCity[day.wcity] || {};
    const i = (src.time || []).indexOf(day.date);
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
  const sun = sunTimes(day.date, day.sun[0], day.sun[1]);
  const wx = weatherFor(day);
  const dt = new Date(day.date + 'T12:00:00Z');
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
    <span class="td-brand">Japan 2026 · 17–27 октября</span>
    <button class="td-hbtn" type="button" id="tdMap">🗺 Карта</button>
    <button class="td-hbtn" type="button" id="tdBook">🎫 Брони</button>`));
  const hero = el('div', 'td-hero');
  hero.innerHTML = `
    <div><div class="td-day">День ${day.n} из 11 · ${esc(day.label)}</div>
      <div class="td-sub">${ddmmyyyy(day.date)} · ${WD[dt.getUTCDay()]} · ${esc(day.city)}</div></div>
    <div class="td-clock td-mono">${c.live ? hm(jp.min) : hm(c.min)}<small>${c.live ? 'время в Японии' : 'предпросмотр'}</small></div>
    <div class="td-facts">
      <span>${wx ? (wx.code != null ? WX_ICON(wx.code) : '🌡️') + ' ' + wx.hi + '°' + (wx.lo != null ? ' / ' + wx.lo + '°' : '') +
        (wx.prob != null ? ' · дождь ' + wx.prob + '%' : wx.rain ? ' · осадки ' + wx.rain.toFixed(1) + ' мм' : '') +
        (wx.forecast ? '' : ' <small>(норма)</small>') : '🌡️ нет данных'}</span>
      <span>🌅 ${hm(sun.rise)} · 🌇 ${hm(sun.set)}</span>
      <span>🏨 ${esc(day.hotel)}</span>
    </div>`;
  head.appendChild(hero);
  if (!c.live) {
    const days = Math.round((Date.parse(TRIP0) - Date.parse(jp.date)) / 864e5);
    const pv = el('div', 'td-preview');
    pv.innerHTML = `<b>Предпросмотр</b><span>${days > 0 ? 'поездка через ' + days + ' дн.' : 'поездка завершена'} · «сейчас» =</span>
      <select id="tdPvDay" aria-label="День предпросмотра">${T.days.map(d => `<option value="${d.n}"${d.n === S.prevDay ? ' selected' : ''}>${d.date.slice(8)}.10</option>`).join('')}</select>
      <input id="tdPvTime" type="time" value="${S.prevTime}" aria-label="Время предпросмотра">`;
    head.appendChild(pv);
  }
  const dates = el('div', 'td-dates');
  T.days.forEach(d => {
    const b = el('button', 'td-date' + (d.n === day.n ? ' on' : '') + (c.live && d.n === c.day ? ' live' : ''));
    b.type = 'button';
    const w = new Date(d.date + 'T12:00:00Z').getUTCDay();
    b.innerHTML = `<small>${WD_SHORT[w]}</small><b>${+d.date.slice(8)}</b><small>окт</small>`;
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
          ${e.cost ? `<span>${yen(e.cost)} · ${kzt(e.cost)}</span>` : ''}
          ${bk ? `<span>${bk.st === 'fixed' ? '✅ бронь' : '⚠️ купить'}</span>` : ''}
          ${e.auto ? '<span class="td-pill warn">убрано ради расписания</span>' : ''}</div>
        ${e.note ? `<div class="td-evnote">${esc(e.note)}</div>` : ''}
        <div class="td-evbtns">
          <button class="td-mini${e.done ? ' on' : ''}" type="button" data-done="${e.id}">✓ ${e.done ? 'Сделано' : 'Отметить'}</button>
          ${e.st !== 'fixed' && !past ? `<button class="td-mini" type="button" data-skip="${e.id}">${e.skip ? '↺ Вернуть' : '⏭ Пропустить'}</button>` : ''}
          ${e.st !== 'fixed' && !isAnchor(e) && !e.skip && !past ? `<button class="td-mini" type="button" data-delay="${e.id}" data-by="15">+15</button>
            <button class="td-mini" type="button" data-delay="${e.id}" data-by="30">+30</button>
            ${e.delay ? `<button class="td-mini" type="button" data-delay="${e.id}" data-by="0">сброс (+${e.delay})</button>` : ''}` : ''}
          <a class="td-mini" href="${gmap(e)}" target="_blank" rel="noopener">Карта</a>
          ${e.bk ? `<button class="td-mini" type="button" data-ticket="${e.bk}">Билет</button>` : ''}
        </div></div>`;
    tl.appendChild(row);
  });
  sec.appendChild(tl);
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
      <div class="td-stat"><span>Потрачено, ¥</span><b>${spent != null ? money(spent) : '—'}</b>
        <input type="number" min="0" step="100" id="tdSpent" placeholder="¥ факт" value="${spent ?? ''}"></div>
      <div class="td-stat"><span>Погода</span><b>${wx ? wx.hi + '° / ' + (wx.lo ?? '—') + '°' + (wx.prob != null ? ' · ' + wx.prob + '%' : '') : '—'}</b></div>
      <div class="td-stat"><span>Закат</span><b class="td-mono">${hm(sun.set)}</b></div>
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
    r.innerHTML = `<div><b>${b.st === 'fixed' ? '✅' : '⚠️'} ${esc(b.t)}</b><small>${esc(b.when)}${b.cost ? ' · ' + money(b.cost) : ''}</small></div>
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
    b.innerHTML = `<b class="td-mono">${+d.date.slice(8)}</b><span>${esc(d.label)}<br><small>${esc(d.summary)}</small></span>
      <small class="td-mono">${p.filter(e => e.done).length}/${p.length}</small>`;
    b.addEventListener('click', () => { viewDay = d.n; render(); document.getElementById('today').scrollTo({ top: 0, behavior: 'smooth' }); });
    ol.appendChild(b);
  });
  ov.appendChild(ol);
  root.appendChild(ov);
  root.appendChild(el('p', 'td-foot', `Курс: 1 ¥ = ${FX} ₸ · цены — на двоих · «~» в заметках = оценка. Отметки и билеты сохраняются на этом устройстве.`));

  wire(root, day);
}

/* ---------- interactions ---------- */
function wire(root, day) {
  root.querySelector('#tdMap').addEventListener('click', () => {
    closeToday();
    const chip = document.getElementById('dayChips').children[day.n];
    if (chip) chip.click();
  });
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

function openToday() { document.getElementById('today').hidden = false; S.open = true; save(); viewDay = null; render(); }
function closeToday() { document.getElementById('today').hidden = true; S.open = false; save(); }
window.openToday = openToday;

document.getElementById('btnToday').addEventListener('click', openToday);
document.getElementById('tdTicketClose').addEventListener('click', () => { document.getElementById('tdTicket').hidden = true; });
document.addEventListener('keydown', e => { if (e.key === 'Escape') document.getElementById('tdTicket').hidden = true; });

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
})();
