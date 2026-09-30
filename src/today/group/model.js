/* ---------- group model: who is in, the personal schedule, the tasks — pure, no DOM ---------- */
const Group = (() => {
  const toMin = Core.toMin;
  const byId = (xs, id) => (xs || []).find(x => x.id === id);
  const roleOf = (st, id) => (byId(st.members, id) || {}).role;
  const allStops = plan => plan.days.flatMap(d => d.ev.map(e => ({ id: e.id, n: d.n })));

  /* stop > day > part; nothing → out; hosts default in. Returns the Set of group stop ids the member is in. */
  function effectiveIn(plan, st, mid) {
    const js = (st.joins || []).filter(j => j.member === mid);
    const host = roleOf(st, mid) === 'host';
    const rule = (scope, ref) => { const j = js.find(x => x.scope === scope && x.ref === String(ref)); return j ? j.mode : null; };
    const partsOf = (id, n) => (st.parts || []).filter(p => p.stops ? p.stops.includes(id) : p.days.includes(n)).map(p => p.id);
    const partRule = (id, n) => { const ms = partsOf(id, n).map(p => rule('part', p)).filter(Boolean);
      return ms.includes('in') ? 'in' : ms.includes('out') ? 'out' : null; };
    const out = new Set();
    allStops(plan).forEach(({ id, n }) => {
      const m = rule('stop', id) || rule('day', n) || partRule(id, n) || (host ? 'in' : null);
      if (m === 'in') out.add(id);
    });
    return out;
  }

  function personalTrip(plan, st, mid) {
    const inSet = effectiveIn(plan, st, mid);
    const names = new Map((st.members || []).map(m => [m.id, m.name]));
    const who = id => (st.members || []).filter(m => effectiveIn(plan, st, m.id).has(id)).map(m => m.id);
    const joinedMine = new Set((st.joins || []).filter(j => j.member === mid && j.scope === 'mine' && j.mode === 'in').map(j => j.ref));
    const mine = (st.my_stops || []).filter(s => s.member === mid || (s.shared && joinedMine.has(s.id)));
    const days = plan.days.map(d => {
      const g = d.ev.filter(e => inSet.has(e.id)).map(e => ({ ...e, from: 'group', who: who(e.id) }));
      const m = mine.filter(s => s.day === d.n).map(s => ({ st: 'planned', cat: 'activity', ...s.ev, id: s.id, from: 'mine',
        sharedBy: s.member !== mid ? names.get(s.member) || '' : null, shared: !!s.shared }));
      const ev = [...g, ...m].sort((a, b) => (toMin(a.s) || 0) - (toMin(b.s) || 0));
      return { ...d, ev };
    });
    return { ...plan, days };
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

  return { effective: effectiveIn, personalTrip, overlaps, tasks, siteOf };
})();
