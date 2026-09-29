/* ---------- store: the trip, settings, marks and tickets on this device ---------- */
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
          cur, rate: +(s.rate || (cur === (T.currency || 'KZT') ? T.rate : 0) || (CUR[cur] || CUR.KZT).rate),
          theme: ['auto', 'light', 'dark'].includes(s.theme) ? s.theme : 'auto' };
}
loadSettings();
const saveSettings = () => { try { localStorage.setItem(SET_KEY, JSON.stringify(SET)); } catch (e) {} };

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


const bookingById = id => T.bookings.find(b => b.id === id);

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
    SET = { theme: SET.theme || 'auto', travelers: +(j.travelers || 2), start: j.start || j.days[0].date, cur: j.currency || 'KZT',
            rate: +(j.rate || (CUR[j.currency] || CUR.KZT).rate) };
    saveSettings();
    history.replaceState(null, '', location.pathname + location.search);   // don't leave the trip in the address bar
    return true;
  } catch (e) { return false; }
}
