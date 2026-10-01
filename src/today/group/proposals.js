/* ---------- proposals: what a guest suggests, and the plan after a host accepts it — pure ---------- */
const Proposals = (() => {
  const HM = /^([01]\d|2[0-3]):[0-5]\d$/;
  const clone = o => JSON.parse(JSON.stringify(o));
  const findEv = (doc, ref) => {
    for (const d of doc.days || []) { const i = (d.ev || []).findIndex(e => String(e.id) === String(ref)); if (i >= 0) return { d, i, e: d.ev[i] }; }
    return null;
  };
  /* the plan with the proposal applied; throws when it no longer fits (the stop is gone, bad times) */
  function apply(doc, p) {
    const out = clone(doc), pl = p.payload || {};
    if (p.kind === 'comment') return out;
    if (p.kind === 'add') {
      const d = (out.days || []).find(x => x.n === p.day);
      if (!d || !HM.test(pl.s || '') || !HM.test(pl.e || '') || pl.e <= pl.s || !String(pl.t || '').trim()) throw new Error('bad proposal');
      const ev = { id: 'p-' + String(p.id).replace(/[^a-z0-9]/gi, '').slice(0, 10), s: pl.s, e: pl.e, t: String(pl.t).trim().slice(0, 120),
                   cat: 'activity', st: 'planned', note: String(pl.note || '').slice(0, 500), lat: null, lng: null, walk: 0, ride: 0, buf: 0 };
      d.ev = (d.ev || []).concat([ev]).sort((a, b) => String(a.s).localeCompare(String(b.s)));
      return out;
    }
    const hit = findEv(out, p.ref);
    if (!hit) throw new Error('stop gone');
    if (p.kind === 'remove') { hit.d.ev.splice(hit.i, 1); return out; }
    if (p.kind === 'time') {
      if (!HM.test(pl.s || '') || !HM.test(pl.e || '') || pl.e <= pl.s) throw new Error('bad proposal');
      hit.e.s = pl.s; hit.e.e = pl.e;
      hit.d.ev.sort((a, b) => String(a.s).localeCompare(String(b.s)));
      return out;
    }
    throw new Error('bad proposal');
  }
  /* one line about what is proposed, for the cards (plain text: the caller escapes) */
  function describe(p, doc) {
    const pl = p.payload || {}, hit = p.ref ? findEv(doc || {}, p.ref) : null, what = hit ? `«${hit.e.t}»` : 'пункт';
    if (p.kind === 'time') return `${what}: другое время ${pl.s}–${pl.e}`;
    if (p.kind === 'remove') return `${what}: убрать из плана`;
    if (p.kind === 'add') return `Новый пункт: ${pl.s}–${pl.e} ${String(pl.t || '')}`;
    return `${what}: комментарий`;
  }
  const dayOf = (p, doc) => { if (p.day) return p.day; const h = p.ref ? findEv(doc || {}, p.ref) : null; return h ? h.d.n : null; };
  return { apply, describe, dayOf, findEv, HM };
})();
