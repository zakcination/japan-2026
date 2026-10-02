/* ---------- store: the trip, settings, marks and tickets on this device ---------- */
/* ---------- the trip: the built-in template, or the traveller's own copy on this device ---------- */
const TPL = DATA.today;
const TRIP_KEY = 'japan2026.trip.v1', SET_KEY = 'japan2026.settings.v1', ST_KEY = 'japan2026.today.v1';
const CUR = { KZT: { sym: '₸', rate: 2.81 }, USD: { sym: '$', rate: 0.0067 }, EUR: { sym: '€', rate: 0.0061 },
              RUB: { sym: '₽', rate: 0.56 }, JPY: { sym: '¥', rate: 1 } };
const clone = x => JSON.parse(JSON.stringify(x));
function loadTrip() {
  try { const j = Core.cleanTrip(JSON.parse(localStorage.getItem(TRIP_KEY) || 'null')); if (j) return j; } catch (e) {}
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
  SET = { travelers: +(s.travelers || T.travelers || 2), start: s.start || T.start || TPL.start,
          cur, rate: +(s.rate || (cur === (T.currency || 'KZT') ? T.rate : 0) || (CUR[cur] || CUR.KZT).rate),
          theme: ['auto', 'light', 'dark'].includes(s.theme) ? s.theme : 'auto' };
}
loadSettings();
/* only what differs from the trip is stored, so a new version of a shared trip (start date,
   people, currency) still reaches the phone unless the traveller changed that field here */
const tripDefaults = () => { const cur = T.currency || 'KZT';
  return { travelers: +(T.travelers || 2), start: T.start || TPL.start, cur, rate: +(T.rate || (CUR[cur] || CUR.KZT).rate) }; };
const saveSettings = () => {
  const d = tripDefaults(), o = { theme: SET.theme };
  ['travelers', 'start', 'cur', 'rate'].forEach(k => { if (SET[k] !== d[k]) o[k] = SET[k]; });
  try { localStorage.setItem(SET_KEY, JSON.stringify(o)); } catch (e) {}
};

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
/* costs are per person (owners' choice): «¥210/чел · 590 ₸» */
const money = pp => pp == null || !pp ? '—' : `${yen(pp)}/чел${home(pp) ? ' · ' + home(pp) : ''}`;

const liveDayN = () => { const n = japanNow(); const d = T.days.find(x => dateOf(x) === n.date); return d ? d.n : null; };
/* the clock the screen reasons with: real Japan time during the trip; outside it, the preview clock
   only when the traveller asked for a preview on «День» (S.preview), else real Japan time on day 1 */
function clock() {
  const live = liveDayN();
  if (live) {
    // after midnight, yesterday's stop that is still going (an onsen till 00:30) keeps the screen
    const now = japanNow().min, prev = TV().days.find(d => d.n === live - 1);
    if (prev && now < 360 && plan(prev, now + 1440).some(e => !e.skip && !e.auto && !e.bad && e.ne > now + 1440))
      return { live: true, day: prev.n, min: now + 1440 };
    return { live: true, day: live, min: now };
  }
  if (S.preview === true) return { live: false, day: S.prevDay, min: toMin(S.prevTime || '09:00') };
  return { live: false, day: T.days[0].n, min: japanNow().min };
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


/* the trip on screen: the group plan, or my own schedule (joined group stops + my stops) when logged in */
const planDoc = () => { const s = typeof Api !== 'undefined' && Api.me() && Api.state(); const d = s && s.plan && Core.cleanTrip(s.plan.doc); return d || T; };
/* «День» can show another member's personal plan: S.viewMode = 'person:<id>' */
function viewPerson() {
  const m = /^person:(.+)$/.exec(S.viewMode || ''), s = typeof Api !== 'undefined' && Api.me() && Api.state();
  return m && s && m[1] !== Api.me().id && (s.members || []).some(x => x.id === m[1]) ? m[1] : null;
}
function TV() {
  const s = typeof Api !== 'undefined' && Api.me() && Api.state();
  if (!s) return planDoc();
  if (S.viewMode === 'group') return Group.groupTrip(planDoc(), s, Api.me().id);
  const who = viewPerson();                                   // someone else's plan: on «День» only, read-only
  if (who && typeof tab !== 'undefined' && tab === 'day') return Group.personalTrip(planDoc(), s, who);
  return Group.personalTrip(planDoc(), s, Api.me().id);
}
const bookingById = id => planDoc().bookings.find(b => b.id === id);

/* A personal link carries the whole trip after '#trip=' (deflate + base64url). The part after '#'
   never reaches the server, so a private trip travels in the link, not in the public repo. */
async function tripFromHash() {
  const m = location.hash.match(/^#trip=([A-Za-z0-9_-]+)/);
  if (!m || typeof DecompressionStream === 'undefined') return false;
  try {
    const b64 = m[1].replace(/-/g, '+').replace(/_/g, '/');
    const bin = Uint8Array.from(atob(b64 + '='.repeat((4 - b64.length % 4) % 4)), c => c.charCodeAt(0));
    const txt = await new Response(new Blob([bin]).stream().pipeThrough(new DecompressionStream('deflate-raw'))).text();
    const j = Core.cleanTrip(JSON.parse(txt));
    if (!j) return false;
    T = j; saveTrip();
    S.done = {}; S.skip = {}; S.delay = {}; S.spent = {}; S.walked = {}; save();
    SET = { theme: SET.theme || 'auto', travelers: +(j.travelers || 2), start: j.start || TPL.start, cur: j.currency || 'KZT',
            rate: +(j.rate || (CUR[j.currency] || CUR.KZT).rate) };
    saveSettings();
    history.replaceState(null, '', location.pathname + location.search);   // don't leave the trip in the address bar
    return true;
  } catch (e) { return false; }
}

/* ---------- places, links, weather ---------- */
/* only numbers go into a link as coordinates; anything else is searched for by name, URL-encoded */
const where = e => {
  const lat = e.lat === '' || e.lat == null ? NaN : +e.lat, lng = e.lng === '' || e.lng == null ? NaN : +e.lng;
  return Number.isFinite(lat) && Number.isFinite(lng) ? `${lat}%2C${lng}` : encodeURIComponent((e.pname || e.to || e.t || '') + ' Japan');
};
const gmap = e => `https://www.google.com/maps/search/?api=1&query=${where(e)}`;
const groute = e => `https://www.google.com/maps/dir/?api=1&destination=${where(e)}&travelmode=transit`;
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
