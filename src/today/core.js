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

  /* a stop may keep its times in another zone (Shanghai: off = 480); the planner works in Japan time.
     `off` on a plan() result is already the date-bound boolean (see below), so once a stop has gone
     through plan(), its zone shift lives in `.sh` instead — shiftOf/localMin fall back to it there. */
  const shiftOf = e => (e && typeof e.off !== 'boolean' && e.off != null && e.off !== '' && Number.isFinite(+e.off)) ? 540 - +e.off : 0;
  const localMin = (e, min) => min - (e && Number.isFinite(e.sh) ? e.sh : shiftOf(e));

  /* The replanner. A delay pushes what follows; before an anchor the overrun is paid back from
     flexible blocks first (latest first, down to nothing), then planned ones (down to half, never
     under 15 min) — and only from what hasn't happened yet. What can't be paid back is shown as a
     conflict on the anchor. Nothing extra is ever suggested. */
  function plan(day, now, marks, dateISO) {
    const own = (o, k) => !!o && Object.prototype.hasOwnProperty.call(o, k);
    const skip = (marks && marks.skip) || {}, done = (marks && marks.done) || {}, delay = (marks && marks.delay) || {};
    const all = (day.ev || []).map(e => {
      const sh = shiftOf(e), s = toMin(e.s) + sh, en0 = e.e ? toMin(e.e) + sh : NaN;
      const bad = !Number.isFinite(s);
      const en = Number.isFinite(en0) ? en0 : s + 15;
      const off = !!(e.bound && dateISO && dateISO !== e.bound);
      return { ...e, st: off ? 'input' : e.st, off, bad, sh, S: s, E: en < s ? en + 1440 : en, ns: s, ne: 0, cut: 0, auto: false,
               conflict: 0, skip: own(skip, e.id) && !!skip[e.id], done: own(done, e.id) && !!done[e.id], delay: own(delay, e.id) ? +delay[e.id] || 0 : 0 };
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
            // shortening x helps only as far as the stops after it were pushed: a stop is never
            // moved before its own start, and slack between stops already absorbs the overrun
            const after = seg.slice(seg.indexOf(x) + 1);
            const pushed = after.reduce((m, y) => Math.min(m, y.ns - y.S), Infinity);
            const c = Math.min(Math.max(0, Math.min(len, x.ne - x.ns - keep)), over, pushed);
            if (!(c > 0)) continue;
            x.ne -= c; x.cut += c; over -= c;
            if (x.ne - x.ns <= 0) x.auto = true;
            after.forEach(y => { y.ns -= c; y.ne -= c; });
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
  /* Every trip that comes from outside (a file, a link, the site, this phone's storage) goes through
     here: numbers become numbers, day numbers integers, a date-bound stop keeps only a real date.
     Returns a clean copy, or null when it isn't a trip. */
  const NUM = ['walk', 'ride', 'buf', 'cost', 'km', 'lat', 'lng'];
  const numOr = (v, d) => v === '' || v == null || !Number.isFinite(+v) ? d : +v;
  function cleanTrip(j) {
    if (!validTrip(j)) return null;
    const t = JSON.parse(JSON.stringify(j));
    t.days = t.days.map(d => ({ ...d, n: Math.round(+d.n), sun: Array.isArray(d.sun) && d.sun.length === 2 && d.sun.every(v => Number.isFinite(+v)) ? d.sun.map(Number) : null,
      ev: d.ev.map(e => {
        const x = { ...e, id: String(e.id == null ? '' : e.id), t: String(e.t) };
        NUM.forEach(k => { x[k] = numOr(e[k], k === 'lat' || k === 'lng' || k === 'cost' || k === 'km' ? null : 0); });
        if (x.bound != null && !/^\d{4}-\d{2}-\d{2}$/.test(String(x.bound))) delete x.bound;
        return x;
      }) }));
    t.bookings = (Array.isArray(t.bookings) ? t.bookings : []).filter(b => b && typeof b === 'object').map(b => ({
      ...b, id: String(b.id == null ? '' : b.id), t: String(b.t == null ? '' : b.t),
      days: Array.isArray(b.days) ? b.days.map(Number).filter(Number.isFinite) : [], cost: numOr(b.cost, null) }));
    if (!['KZT', 'USD', 'EUR', 'RUB', 'JPY'].includes(t.currency)) delete t.currency;
    ['travelers', 'rate'].forEach(k => { if (t[k] != null && !(+t[k] > 0)) delete t[k]; });
    const isDate = v => /^\d{4}-\d{2}-\d{2}$/.test(String(v)) && !isNaN(Date.parse(v));
    t.days.forEach(d => { if (d.date != null && !isDate(d.date)) delete d.date; });
    if (!isDate(t.start)) { if (t.days[0].date) t.start = t.days[0].date; else delete t.start; }
    return t;
  }
  const safeUrl = u => (typeof u === 'string' && /^https:\/\/[^\s"'<>]+$/i.test(u)) ? u : '';

  return { pad, toMin, hm, dur, cd, ddmmyyyy, addDays, japanNow, sunTimes, isAnchor, isKey, travel,
           shiftOf, localMin, plan, urgent, themeFor, dayProgress, validTrip, cleanTrip, safeUrl };
})();
