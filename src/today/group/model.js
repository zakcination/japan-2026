/* ---------- group model: who is in, the personal schedule, the tasks — pure, no DOM ---------- */
const Group = (() => {
  const toMin = Core.toMin;
  const byId = (xs, id) => (xs || []).find(x => x.id === id);
  const roleOf = (st, id) => (byId(st.members, id) || {}).role;
  const allStops = plan => plan.days.flatMap(d => d.ev.map(e => ({ id: e.id, n: d.n })));

  /* «ехать вместе с»: whom the member follows on day n — a day's own choice beats the whole trip; null if nobody */
  function followOn(st, mid, n) {
    const fs = (st.joins || []).filter(j => j.member === mid && j.scope === 'follow');
    const day = fs.find(j => j.ref.endsWith(':' + n)), all = fs.find(j => !j.ref.includes(':'));
    const j = day || all;
    if (!j || j.mode !== 'in') return null;
    const t = j.ref.split(':')[0];
    return t !== mid && byId(st.members, t) ? t : null;
  }

  /* stop > day > following someone > part; nothing → out; hosts default in. The Set of group stop ids the member is in. */
  function effectiveIn(plan, st, mid, seen) {
    seen = seen || new Set(); seen.add(mid);
    const js = (st.joins || []).filter(j => j.member === mid);
    const host = roleOf(st, mid) === 'host';
    const rule = (scope, ref) => { const j = js.find(x => x.scope === scope && x.ref === String(ref)); return j ? j.mode : null; };
    const partsOf = (id, n) => (st.parts || []).filter(p => p.stops ? p.stops.includes(id) : p.days.includes(n)).map(p => p.id);
    const partRule = (id, n) => { const ms = partsOf(id, n).map(p => rule('part', p)).filter(Boolean);
      return ms.includes('in') ? 'in' : ms.includes('out') ? 'out' : null; };
    const theirs = new Map();                                // a followed person's own set, worked out once (cycles stop)
    const followRule = (id, n) => {
      const t = followOn(st, mid, n); if (!t || seen.has(t)) return null;
      if (!theirs.has(t)) theirs.set(t, effectiveIn(plan, st, t, new Set(seen)));
      return theirs.get(t).has(id) ? 'in' : 'out';
    };
    const out = new Set();
    allStops(plan).forEach(({ id, n }) => {
      const m = rule('stop', id) || rule('day', n) || followRule(id, n) || partRule(id, n) || (host ? 'in' : null);
      if (m === 'in') out.add(id);
    });
    return out;
  }

  /* is someone's own stop in my plan: mine, joined by me, or brought by the person I follow that day (unless I said no) */
  function mineIn(st, mid, s, seen) {
    if (s.member === mid) return true;
    if (!s.shared) return false;
    const j = (st.joins || []).find(x => x.member === mid && x.scope === 'mine' && x.ref === s.id);
    if (j) return j.mode === 'in';
    seen = seen || new Set(); seen.add(mid);
    const t = followOn(st, mid, s.day);
    return !!t && !seen.has(t) && mineIn(st, t, s, seen);
  }

  function personalTrip(plan, st, mid) {
    const inSet = effectiveIn(plan, st, mid);
    const names = new Map((st.members || []).map(m => [m.id, m.name]));
    const sets = new Map((st.members || []).map(m => [m.id, effectiveIn(plan, st, m.id)]));
    const who = id => (st.members || []).filter(m => sets.get(m.id).has(id)).map(m => m.id);
    const mine = (st.my_stops || []).filter(s => mineIn(st, mid, s));
    const days = plan.days.map(d => {
      const g = d.ev.filter(e => inSet.has(e.id)).map(e => ({ ...e, from: 'group', who: who(e.id) }));
      const m = mine.filter(s => s.day === d.n).map(s => ({ st: 'planned', cat: 'activity', ...s.ev, id: s.id, from: 'mine',
        sharedBy: s.member !== mid ? names.get(s.member) || '' : null, shared: !!s.shared }));
      const ev = [...g, ...m].sort((a, b) => (toMin(a.s) || 0) - (toMin(b.s) || 0));
      return { ...d, ev };
    });
    return { ...plan, days };
  }

  /* the group plan as hosts plan it, plus the own stops people shared (and mine), so others can join them */
  function groupTrip(plan, st, mid) {
    const names = new Map((st.members || []).map(m => [m.id, m.name]));
    const vis = (st.my_stops || []).filter(s => s.shared || s.member === mid);
    return { ...plan, days: plan.days.map(d => ({ ...d, ev: [...d.ev, ...vis.filter(s => s.day === d.n).map(s => ({ st: 'planned', cat: 'activity', ...s.ev,
      id: s.id, from: 'mine', sharedBy: s.member !== mid ? names.get(s.member) || '' : null, shared: !!s.shared }))]
      .sort((a, b) => (toMin(a.s) || 0) - (toMin(b.s) || 0)) })) };
  }

  function overlaps(evs) {
    const iv = evs.map(e => { const s = toMin(e.s); let en = e.e ? toMin(e.e) : s + 15; if (en < s) en += 1440; return [e.id, s, en]; })
      .filter(x => Number.isFinite(x[1])).sort((a, b) => a[1] - b[1]);
    const out = [];
    for (let i = 0; i < iv.length; i++) for (let k = i + 1; k < iv.length && iv[k][1] < iv[i][2]; k++) out.push([iv[i][0], iv[k][0]]);
    return out;
  }

  function tasks(plan, st, mid, nowMs) {
    const inSet = effectiveIn(plan, st, mid);
    const done = new Map((st.task_state || []).map(t => [t.ref, !!t.done]));
    const bkStops = new Map();
    plan.days.forEach(d => d.ev.forEach(e => { if (e.bk) { if (!bkStops.has(e.bk)) bkStops.set(e.bk, []); bkStops.get(e.bk).push(e.id); } }));
    const out = [];
    (st.recipes || []).forEach(r => {
      const ids = bkStops.get(r.bk) || [];
      const going = ids.some(id => inSet.has(id)), ref = 'bk:' + r.bk, d = done.get(ref) || false;
      if (going || d) out.push({ ref, kind: 'recipe', title: r.what, recipe: r, done: d, dropped: !going && d });
    });
    (st.my_bookings || []).filter(b => b.member === mid).forEach(b => {
      const ref = 'mb:' + b.id; out.push({ ref, kind: 'mine', title: b.what || b.title || 'Моя бронь', recipe: b, done: done.get(ref) || false, dropped: false });
    });
    (st.tasks || []).filter(t => !t.assignee || t.assignee === mid).forEach(t => {
      const ref = 't:' + t.id; out.push({ ref, kind: 'task', title: t.title, task: t, done: done.get(ref) || false, dropped: false });
    });
    const at = x => { const v = x && Date.parse(x); return Number.isFinite(v) ? v : Infinity; };
    const rank = t => {
      if (t.done && !t.dropped) return [3, 0];
      const r = t.recipe || {}, opens = at(r.opens), by = at(r.buy_by || (t.task || {}).due);
      if (t.dropped) return [0, 0];
      if (opens <= nowMs || !Number.isFinite(opens)) return [1, by];
      return [2, opens];
    };
    return out.sort((a, b) => { const x = rank(a), y = rank(b); return x[0] - y[0] || x[1] - y[1]; });
  }

  const SITES = [[/(^|\.)highwaybus\.com$/, 'Highway Bus'], [/(^|\.)booking\.com$/, 'Booking.com'], [/(^|\.)smart-ex\.jp$/, 'Smart EX'],
                 [/(^|\.)tokyodisneyresort\.jp$/, 'Tokyo Disney Resort'], [/(^|\.)teamlab\.art$/, 'teamLab']];
  function siteOf(url) {
    if (!Core.safeUrl(url)) return null;
    let host; try { host = new URL(url).hostname.toLowerCase(); } catch (e) { return null; }
    const hit = SITES.find(([re]) => re.test(host));
    return { site: hit ? hit[1] : host.replace(/^www\./, ''), host };
  }

  return { effective: effectiveIn, followOn, mineIn, personalTrip, groupTrip, overlaps, tasks, siteOf };
})();
