/* ---------- readiness before the trip: four groups, one «first thing», nothing invented — pure ---------- */
const Prep = (() => {
  const ORDER = ['tickets', 'money', 'phone', 'packing'];               // tie-break for «Сначала это»
  const SHOW = ['tickets', 'phone', 'money', 'packing'];                // display order
  const TITLES = { tickets: 'Билеты и отели', phone: 'Телефон', money: 'Деньги и документы', packing: 'Сборы' };
  const at = v => { const t = v ? Date.parse(v.length === 10 ? v + 'T00:00:00+09:00' : v) : NaN; return Number.isFinite(t) ? t : null; };

  /* «Купить: …» for tickets; a recipe that already says «забронировать» (hotels) becomes «Забронировать: …» */
  function taskTitle(what) {
    const w = String(what || '');
    if (!/забронировать/i.test(w)) return 'Купить: ' + w;
    const t = w.replace(/\s*:?\s*(выбрать\s+и\s+)?забронировать\s*$/i, '').trim();
    return 'Забронировать: ' + t.charAt(0).toLowerCase() + t.slice(1);
  }
  function items(trip, local, auto) {
    const recipes = new Map((trip.recipes || []).map(r => [r.bk, r]));
    const done = (local && local.done) || {};
    const out = (trip.bookings || []).map(b => {
      const r = recipes.get(b.id) || {};
      return { id: 'bk:' + b.id, group: 'tickets', title: taskTitle(r.what || b.t), note: r.tips || b.when || '',
               url: r.url || null, due: r.buy_by || null, opens: r.opens || null, from: null, auto: 'booking:' + b.id,
               bought: b.st === 'fixed' };
    });
    (trip.prep || []).forEach(p => out.push({ note: '', url: null, due: null, opens: null, from: null, auto: null, ...p }));
    ((local && local.own) || []).forEach(o => out.push({ id: o.id, group: SHOW.includes(o.group) ? o.group : 'packing',
      title: String(o.title || ''), note: '', url: null, due: null, opens: null, from: null, auto: null, own: true }));
    return out.map(i => {
      let checked = null;
      if (i.auto === 'installed' && auto.installed) checked = 'auto';
      else if (i.auto && i.auto.startsWith('booking:') && (i.bought || auto.booked.has(i.auto.slice(8)))) checked = 'auto';
      else if (i.auto && i.auto.startsWith('ticket:') && auto.tickets.has(i.auto.slice(7))) checked = 'auto';
      else if (done[i.id]) checked = 'me';
      return { ...i, own: !!i.own, done: !!checked, checked };
    });
  }
  const groups = list => SHOW.map(k => ({ key: k, title: TITLES[k], done: list.filter(i => i.group === k && i.done).length,
                                          total: list.filter(i => i.group === k).length }));
  function first(list, nowMs, departMs) {
    const open = list.filter(i => !i.done);
    const doable = open.filter(i => (!at(i.opens) || at(i.opens) <= nowMs) && (!at(i.from) || at(i.from) <= nowMs)
      && (i.group !== 'packing' || !departMs || nowMs >= departMs - 3 * 864e5));
    doable.sort((a, b) => (at(a.due) ?? Infinity) - (at(b.due) ?? Infinity) || ORDER.indexOf(a.group) - ORDER.indexOf(b.group));
    const item = doable[0] || null;
    return { item, rest: item ? open.length - 1 : 0 };
  }
  function opening(list, nowMs) {
    const soon = list.filter(i => !i.done && at(i.opens) && at(i.opens) > nowMs && at(i.opens) <= nowMs + 48 * 3600e3);
    return soon.sort((a, b) => at(a.opens) - at(b.opens))[0] || null;
  }
  return { items, groups, first, opening, taskTitle, TITLES };
})();
