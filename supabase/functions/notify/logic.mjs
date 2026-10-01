// Who gets which push, and what it says — pure, so it is tested with Node (src/tests/test_push_logic.py).
// Input: the event from the database trigger or the daily cron, and the trip's rows. Output: messages with recipients.
const APP = 'https://zakcination.github.io/japan-2026/?trip=';
const dm = iso => { const d = String(iso || '').slice(0, 10); return d ? `${d.slice(8, 10)}.${d.slice(5, 7)}` : ''; };
const almaty = (ms) => new Date(ms + 5 * 3600e3).toISOString();               // Asia/Almaty is UTC+5 all year
const findEv = (doc, ref) => { for (const d of (doc && doc.days) || []) for (const e of d.ev || []) if (String(e.id) === String(ref)) return e; return null; };

function describe(p, doc) {
  const pl = p.payload || {}, e = p.ref ? findEv(doc, p.ref) : null, what = e ? `«${e.t}»` : 'пункт';
  if (p.kind === 'time') return `${what}: другое время ${pl.s}–${pl.e}`;
  if (p.kind === 'remove') return `${what}: убрать из плана`;
  if (p.kind === 'add') return `Новый пункт: ${pl.s}–${pl.e} ${pl.t || ''}`.trim();
  return `${what}: ${p.note || 'комментарий'}`;
}

// D = { trip, members, proposals, plan: {doc}, parts, joins, recipes, task_state } for one trip; now = epoch ms
export function messages(ev, D, now) {
  const url = h => APP + encodeURIComponent(D.trip) + '#' + h;
  const name = id => (D.members.find(m => m.id === id) || {}).name || 'Кто-то';
  const hosts = D.members.filter(m => m.role === 'host').map(m => m.id);
  const guests = D.members.filter(m => m.role !== 'host').map(m => m.id);
  const doc = (D.plan && D.plan.doc) || {};
  const out = [];
  if (ev.type === 'proposal') {
    const p = D.proposals.find(x => x.id === ev.id); if (!p) return out;
    out.push({ to: hosts.filter(h => h !== p.member), title: `Предложение от ${name(p.member)}`, body: describe(p, doc), url: url('tab=tix'), tag: 'prop-' + p.id });
  } else if (ev.type === 'decision') {
    const p = D.proposals.find(x => x.id === ev.id); if (!p || !['accepted', 'rejected'].includes(p.status)) return out;
    out.push({ to: [p.member], title: p.status === 'accepted' ? 'Ваше предложение принято' : 'Ваше предложение отклонено', body: describe(p, doc), url: url('tab=tix'), tag: 'prop-' + p.id });
  } else if (ev.type === 'join') {
    const part = ev.scope === 'part' ? (D.parts.find(x => x.id === ev.ref) || {}).title : (findEv(doc, ev.ref) || {}).t;
    if (!part) return out;
    out.push({ to: hosts.filter(h => h !== ev.member), title: ev.mode === 'in' ? `${name(ev.member)} едет` : `${name(ev.member)} не едет`, body: part, url: url('tab=day'), tag: `join-${ev.member}-${ev.ref}` });
  } else if (ev.type === 'plan') {
    out.push({ to: guests, title: 'План поездки обновился', body: 'Откройте «Мой план» — там уже новая версия.', url: url('tab=day'), tag: 'plan' });
  } else if (ev.type === 'deadlines') {
    const today = almaty(now).slice(0, 10), in3 = almaty(now + 3 * 864e5).slice(0, 10);
    for (const r of D.recipes) {
      const b = (doc.bookings || []).find(x => x.id === r.bk); if (!b || b.st === 'fixed') continue;
      const opensToday = r.opens && almaty(Date.parse(r.opens)).slice(0, 10) === today;
      const kind = r.buy_by === in3 ? 'in3' : r.buy_by === today ? 'today' : opensToday ? 'opens' : null;
      if (!kind) continue;
      const days = new Set(b.days || []);
      const joined = guests.filter(g => D.joins.some(j => j.member === g && j.scope === 'part' && j.mode === 'in'
        && ((D.parts.find(p => p.id === j.ref) || {}).days || []).some(n => days.has(n))));
      const done = new Set(D.task_state.filter(t => t.ref === 'bk:' + r.bk && t.done).map(t => t.member));
      const to = hosts.concat(joined).filter(m => !done.has(m));
      const what = String(r.what || b.t).replace(/\s*:\s*выбрать и забронировать\s*$/i, '');
      const title = kind === 'in3' ? `Осталось 3 дня: ${what}` : kind === 'today' ? `Сегодня последний день: ${what}` : `Сегодня открываются продажи: ${what}`;
      const body = kind === 'opens' ? `В ${almaty(Date.parse(r.opens)).slice(11, 16)} по Алматы${r.site ? ' · ' + r.site : ''}` : `Купить до ${dm(r.buy_by)}${r.site ? ' · ' + r.site : ''}`;
      if (to.length) out.push({ to, title, body, url: url('task=bk:' + r.bk), tag: 'deadline-' + r.bk });
    }
  }
  return out.filter(m => m.to.length);
}
