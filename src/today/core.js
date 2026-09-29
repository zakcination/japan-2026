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
