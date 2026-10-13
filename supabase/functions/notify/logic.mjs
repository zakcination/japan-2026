// Who gets which push, and what it says — pure, so it is tested with Node (src/tests/test_push_logic.py).
// Input: the event from the database trigger or the daily cron, and the trip's rows. Output: messages with recipients.
const APP = 'https://zakcination.github.io/japan-2026/?trip=';
const dm = iso => { const d = String(iso || '').slice(0, 10); return d ? `${d.slice(8, 10)}.${d.slice(5, 7)}` : ''; };
const almaty = (ms) => new Date(ms + 5 * 3600e3).toISOString();               // Asia/Almaty is UTC+5 all year
const findEv = (doc, ref) => { for (const d of (doc && doc.days) || []) for (const e of d.ev || []) if (String(e.id) === String(ref)) return e; return null; };

const cut = (s, n) => { s = String(s == null ? '' : s); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
function describe(p, doc) {
  const pl = Object.fromEntries(Object.entries(p.payload || {}).map(([k, v]) => [k, cut(v, 120)])), e = p.ref ? findEv(doc, p.ref) : null, what = e ? `«${e.t}»` : 'пункт';
  if (p.kind === 'time') return `${what}: другое время ${pl.s}–${pl.e}`;
  if (p.kind === 'remove') return `${what}: убрать из плана`;
  if (p.kind === 'add') return `Новый пункт: ${pl.s}–${pl.e} ${pl.t || ''}`.trim();
  return `${what}: ${p.note || 'комментарий'}`;
}

// countdown to the first flight, said in the departure city's clock; the hourly cron asks, we answer at 36/24/12/5 h
const TZ = { ALA: 5, NQZ: 5, TSE: 5, PVG: 8, SHA: 8, HND: 9, NRT: 9, KIX: 9, NGO: 9 };
const COUNTDOWN = {
  36: ['36 часов до вылета', 'Сегодня — бумаги: Visit Japan Web, карта прибытия в Китай, письмо о страховке. Всё в «Подготовке».'],
  24: ['Сутки до вылета', 'Онлайн-регистрация на рейс и посадочный офлайн. Проверьте «Перед выходом из дома».'],
  12: ['12 часов до вылета', 'Паспорт, карты, наличные, зарядка и лекарства — в ручную кладь.'],
  5: ['5 часов до вылета', 'Перед выходом: паспорт, телефон, ключи; газ, вода, окна. Список — в приложении.'],
};
function firstDeparture(doc) {
  const f = ((doc && doc.flights) || []).filter(x => x && x.date && x.dep && TZ[x.frm] != null)
    .map(x => Date.parse(`${x.date}T${x.dep}:00Z`) - TZ[x.frm] * 3600e3).filter(Number.isFinite).sort((a, b) => a - b);
  return f.length ? f[0] : null;
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
  } else if (ev.type === 'countdown') {
    const dep = firstDeparture(doc); if (dep == null) return out;
    const h = Math.round((dep - now) / 3600e3), c = COUNTDOWN[h];
    if (c) out.push({ to: D.members.map(m => m.id), title: c[0], body: c[1], url: url(h >= 24 ? 'prep=money' : 'prep=door'), tag: 'countdown' });
  } else if (ev.type === 'deadlines') {
    const today = almaty(now).slice(0, 10), in3 = almaty(now + 3 * 864e5).slice(0, 10);
    // tasks due today: to their assignee (everyone when unassigned), unless already ticked
    for (const t of D.tasks || []) {
      if (t.due !== today) continue;
      const done = new Set(D.task_state.filter(x => x.ref === 't:' + t.id && x.done).map(x => x.member));
      const to = (t.assignee ? [t.assignee] : D.members.map(m => m.id)).filter(m => !done.has(m));
      if (to.length) out.push({ to, title: 'Сегодня: ' + t.title, body: t.note || 'Задача в «Делах»', url: url('task=t:' + t.id), tag: 'task-' + t.id });
    }
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
  return out.filter(m => m.to.length).map(m => ({ ...m, title: cut(m.title, 120), body: cut(m.body, 200) }));
}
