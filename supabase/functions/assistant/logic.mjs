// The travel assistant's pure parts: the prompt, the trip context, the tools, input checks and the agent loop.
// No I/O (the only import is the knowledge in kb.mjs) — index.ts passes in the Anthropic call; src/tests/test_assistant_logic.py runs this with Node.
// The assistant only PROPOSES changes: propose_* tools are never executed here, they come back as action cards
// that the traveller applies (or not) in the app.
import { emergencyInfo, cardPerks, FACTS } from './kb.mjs';

export const MODEL = 'claude-opus-5-5';
export const LIMITS = { iterations: 8, maxTokens: 4000, turns: 20, turnChars: 2000, actions: 6, cards: 6, images: 2, imageChars: 1600000, wallMs: 45000, webSearches: 3 };
export const CATS = ['food', 'transport', 'shopping_self', 'shopping_gifts', 'accommodation', 'attractions', 'coffee', 'groceries',
  'taxi', 'tickets', 'health', 'communication', 'other'];                       // Exp.CATS in src/today/expenses.js
export const CURS = ['JPY', 'KZT', 'USD'];                                       // what the expense sheet can show
export const MAX_JPY = 1e8;
const RATE = { JPY: 1, KZT: 3.6, USD: 0.0068 };                                  // rough, only to refuse absurd amounts
export const HM = /^([01]\d|2[0-3]):[0-5]\d$/;                                   // Proposals.HM in the app
const WD = ['вс', 'пн', 'вт', 'ср', 'чт', 'пт', 'сб'];

const str = (v, n) => String(v == null ? '' : v).replace(/\s+/g, ' ').trim().slice(0, n);
const cut = (v, n) => { const s = String(v == null ? '' : v).replace(/\s+/g, ' ').trim(); return s.length > n ? s.slice(0, n - 1) + '…' : s; };
const dm = iso => `${iso.slice(8, 10)}.${iso.slice(5, 7)}`;
const addDays = (iso, n) => { const d = new Date(iso + 'T12:00:00Z'); d.setUTCDate(d.getUTCDate() + n); return d.toISOString().slice(0, 10); };
const wd = iso => WD[new Date(iso + 'T12:00:00Z').getUTCDay()];
/* a booking code or a long reference number in a note never reaches the model */
const redact = s => String(s || '').replace(/\b(?=[A-Z0-9-]*\d)(?=[A-Z0-9-]*[A-Z])[A-Z0-9-]{8,}\b/g, '[скрыто]');

/* ---------- the app guide (also what app_help returns) ---------- */
export const GUIDE = {
  now: { title: 'Вкладка «Сейчас»', keys: ['сейчас', 'главн', 'капсул', 'выйти', 'пора', 'таймер', 'now'],
    text: 'Что происходит прямо сейчас и что дальше. Чёрная капсула сверху: «выйти через …» до следующего важного пункта; жёлтая — пора выходить (экран не гаснет). '
      + 'До поездки здесь отсчёт, рейсы и подготовка. Карточка «Мои рейсы» — свои рейсы, если летите не с группой.' },
  day: { title: 'Вкладка «День»', keys: ['день', 'расписан', 'пункт', 'план', 'свайп', 'отмет', 'галочк', 'day'],
    text: 'Расписание дня. Дни — полоска сверху (или свайп по списку). Переключатель «Мой план / План группы». Галочка слева — сделано. '
      + 'Нажмите на пункт: маршрут, «Пешком», «Показать по-японски», Google Maps, билет, +15/+30 мин (задержка сдвигает следующие пункты), «Пропустить», «Изменить», «Весь день — в Календарь». '
      + 'Внизу «＋ Пункт» — свой пункт (виден только вам, пока не включите «Показать группе»). «Карта дня» — места дня на карте.' },
  join: { title: 'Я еду / Без меня, части поездки', keys: ['еду', 'без меня', 'присоедин', 'часть', 'участв', 'join'],
    text: 'В пункте плана группы — «Я еду» или «Без меня». В «Плане группы» части поездки (например, Фудзи) — «Я с вами: …» или «Не еду». Хозяева по умолчанию едут везде, гости — туда, куда присоединились.' },
  follow: { title: '«Ехать вместе с»', keys: ['вместе', 'следовать', 'чужой план', 'план участник', 'follow'],
    text: '⚙ → «Ехать вместе с…» или кнопка «Ехать вместе» в плане участника: весь его маршрут, отдельные дни или отдельные места попадают в ваш план. Ваши «Без меня» и свои пункты остаются вашими.' },
  faces: { title: 'Лица и планы участников', keys: ['лиц', 'смайл', 'аватар', 'кто ид', 'участник', 'faces'],
    text: 'На «День» строка «Планы:» — смайлики участников; нажмите, чтобы посмотреть чужой план (только просмотр). В пункте видно, кто идёт. Свой смайлик — ⚙ → «Ваш смайлик».' },
  propose: { title: 'Предложения хозяевам', keys: ['предлож', 'хозя', 'гость', 'измен', 'propos'],
    text: 'Гость не меняет план группы напрямую: в пункте «Предложить изменение» (другое время, убрать, комментарий) или «Предложить пункт в план группы». Хозяева видят предложение в «Делах» и принимают или отклоняют; ответ придёт уведомлением. Своё открытое предложение можно отозвать в «Делах».' },
  tasks: { title: 'Вкладка «Дела»', keys: ['дела', 'задач', 'купить', 'брон', 'дедлайн', 'срок', 'tix'],
    text: '«Дела»: предложения, задачи и что купить (со сроками и подсказкой «Как купить»), брони на выбранный день и на всю поездку. Кружок у брони — отметка «куплено».' },
  tickets: { title: 'Билеты и вложения', keys: ['билет', 'qr', 'pdf', 'файл', 'вложен', 'скриншот', 'ticket'],
    text: 'В «Делах» у брони «Файл» — прикрепить PDF или скриншот QR: хранится на телефоне и открывается без интернета, кнопка «QR» показывает его на весь экран. «Ссылка» — ссылка на бронь; по умолчанию видна только вам, «Показать группе» — всем (ссылка на бронь часто работает как ключ — осторожно).' },
  money: { title: 'Вкладка «Деньги» и ＋ Расход', keys: ['деньг', 'расход', 'трат', 'бюджет', 'плюс', '＋', 'csv', 'курс', 'money', 'expense'],
    text: '＋ в центре нижней панели — новый расход: сумма → валюта (¥, ₸, $) → категория → «Сохранить»; «Добавить детали» — что/где, дата, город, оплата. '
      + '«Деньги» — траты по дням и категориям, фильтры, «Бюджет и курсы», «Экспорт CSV». Если вы с кем-то выбрали друг друга партнёрами по тратам — видите общие расходы.' },
  flights: { title: '«Мои рейсы»', keys: ['рейс', 'самолёт', 'перелёт', 'вылет', 'flight'],
    text: 'На «Сейчас» кнопка «Мои рейсы»: добавьте свои рейсы, если летите отдельно от группы — отсчёт и «В пути» будут по ним.' },
  local: { title: '«Показать по-японски»', keys: ['японск', 'такси', 'прохож', 'по-япон', 'адрес', 'китайск'],
    text: 'В пункте «Показать по-японски» — название места крупно на весь экран с фразой «Довезите сюда, пожалуйста» для таксиста или прохожего; «Скопировать» — в буфер. Нажатие по экрану закрывает.' },
  walk: { title: '«Пешком» и маршрут', keys: ['пешком', 'маршрут', 'дорог', 'карт', 'apple', 'google', 'walk'],
    text: 'В пункте: «Маршрут» (общественный транспорт, на iPhone — Apple Карты), «Пешком» — пеший маршрут, «Открыть в Google Maps».' },
  push: { title: 'Уведомления', keys: ['уведомл', 'push', 'пуш', 'оповещ', 'notification'],
    text: '⚙ → «Уведомления» → «Включить»: предложения, решения хозяев, сроки покупки. На iPhone работают только если приложение добавлено на экран «Домой».' },
  offline: { title: 'Без интернета', keys: ['офлайн', 'без интернет', 'без сети', 'нет сети', 'offline'],
    text: 'Расписание, карта, билеты-файлы и расходы работают без сети; изменения уйдут группе, когда появится связь (⚙ показывает «ждёт отправки»). Ассистенту нужен интернет.' },
  settings: { title: '⚙ Настройки', keys: ['настрой', 'шестер', '⚙', 'тема', 'тёмн', 'выйти из', 'pin', 'пин', 'settings'],
    text: '⚙ сверху справа: вход в группу и выход, уведомления, смайлик, «Показать мой план группе», «Ехать вместе с…», тема (авто: днём светлая, после заката тёмная), поделиться поездкой, перенос на другой телефон. Хозяева — участники, приглашения, сброс PIN.' },
  install: { title: 'На экран «Домой»', keys: ['домой', 'установ', 'иконк', 'home screen', 'приложен'],
    text: 'Safari → «Поделиться» → «На экран „Домой“». Так приложение открывается как обычное, работает без сети, билеты не стираются, приходят уведомления.' },
  assistant: { title: 'Ассистент', keys: ['ассистент', 'помощник', 'чат', 'применить', 'профиль', 'фото', 'микрофон', 'голос', 'переводчик'],
    text: 'Круглая кнопка со звёздочкой справа внизу, над вкладками. Ассистент только предлагает: изменение плана или расход появляется карточкой, и ничего не меняется, пока вы не нажмёте «Применить». '
      + 'Можно прислать фото (меню, вывеска, билет), надиктовать вопрос микрофоном (или 🎤 на клавиатуре iPhone), включить «Переводчик» — говорите, он озвучит по-японски, и обратно. «Профиль» — как к вам обращаться, язык, тон, еда. Нужен интернет.' },
};
export function appHelp(topic) {
  const q = str(topic, 80).toLowerCase();
  const hits = Object.entries(GUIDE).filter(([k, g]) => q && (k === q || g.keys.some(w => q.includes(w) || w.includes(q))));
  if (!hits.length) return 'Не нашёл такой темы. Темы: ' + Object.values(GUIDE).map(g => g.title).join('; ') + '.';
  return hits.slice(0, 3).map(([, g]) => `${g.title}: ${g.text}`).join('\n');
}
const guideText = () => Object.values(GUIDE).map(g => `- ${g.title}: ${g.text}`).join('\n');

/* ---------- the system prompt: stable (cached) part ---------- */
export const SYSTEM = `Ты — помощник группы из пяти человек в поездке по Японии (и пересадке в Шанхае), встроенный в их приложение-путеводитель.
Задачи: подсказать, как пользоваться приложением; найти места; объяснить день; перестроить план, если дождь, закрыто, устали или опаздывают; подсказать японские фразы (с записью японскими знаками и транскрипцией по-русски).

Правила:
- Отвечай на языке из профиля собеседника (по умолчанию по-русски), обращайся к нему так, как он просил, в выбранном тоне. Отвечай кратко: 1–4 предложения или короткий список, без вступлений и повторов; подробности — только если попросили.
- Формат — простой текст с переносами строк, без Markdown-разметки (никаких **, #, таблиц).
- Будь честен: если не уверен (часы работы, цены, погода), так и скажи и предложи проверить. Не выдумывай.
- Время — японское (JST), кроме пунктов с пометкой «время Шанхая».
- Ничего не меняй сам. Чтобы изменить план или добавить расход, вызови propose_* — у человека появится карточка «Применить / Не надо». Не пиши, что изменение сделано: пиши, что предложил и что нужно нажать «Применить».
- Если гость меняет пункт плана группы, это станет предложением хозяевам — скажи об этом. Свои пункты человек меняет сам. Чужой личный пункт изменить нельзя — можно только не идти.
- Перед переносом убедись, что новое время не пересекается с соседними пунктами (get_day), и учитывай дорогу.
- Никогда не раскрывай номера билетов, коды бронирования, точный адрес и инструкции заезда в частный дом в Киото — их в твоих данных нет, говори, что они в «Делах» у брони.
- Травма, болезнь, ДТП, кража, задержка или потеря багажа, задержка рейса: сначала emergency_info. При угрозе жизни первым делом 119 (в Китае 120); дальше — и во всех остальных случаях первым делом — страховка (звонок в ассистанс до больницы, какие документы сохранить), потом остальное.
- Карта Forte Travel (залы, eSIM, банкоматы, курс, бонусы) — card_perks. Никогда не проси и не принимай номер карты, CVV, коды из SMS, номер полиса; если прислали — попроси не присылать и не повторяй их.
- Пересчёт JPY/KZT/USD — convert_currency (курсы приложения).
- Перевод и фразы: японский текст покажи через show_japanese (крупная карточка «Показать по-японски»); в ответе — коротко смысл и произношение.
- Место, которое стоит посетить или найти, — suggest_place (ссылка на Google Maps), не больше трёх.
- Фото (меню, вывеска, ценник, билет): коротко — что написано и что это значит для собеседника. В меню отмечай свинину, алкоголь в соусах (мирин, саке) и частые аллергены. Если на фото паспорт или банковская карта — не пересказывай номера и попроси такие фото не присылать.
- Не выдумывай расписания поездов, цены и часы работы: для дороги — suggest_place с from (маршрут в Google Maps), остальное — «проверьте».
- web_search — только чтобы найти место, часы работы, цены или как добраться; называй источник.
- Если вопрос про приложение — отвечай по справке ниже (или app_help), называя кнопки так, как они подписаны.

${FACTS}

Справка по приложению:
${guideText()}`;

/* ---------- who is in which group stop (a port of Group.effective / followOn / mineIn in src/today/group/model.js) ---------- */
const byId = (xs, id) => (xs || []).find(x => x.id === id);
function followOn(st, mid, n) {
  const fs = (st.joins || []).filter(j => j.member === mid && j.scope === 'follow');
  const j = fs.find(x => String(x.ref).endsWith(':' + n)) || fs.find(x => !String(x.ref).includes(':'));
  if (!j || j.mode !== 'in') return null;
  const t = String(j.ref).split(':')[0];
  return t !== mid && byId(st.members, t) ? t : null;
}
export function effectiveIn(doc, st, mid, seen) {
  seen = seen || new Set(); seen.add(mid);
  const js = (st.joins || []).filter(j => j.member === mid), host = (byId(st.members, mid) || {}).role === 'host';
  const rule = (scope, ref) => { const j = js.find(x => x.scope === scope && x.ref === String(ref)); return j ? j.mode : null; };
  const partRule = (id, n) => { const ms = (st.parts || []).filter(p => p.stops ? p.stops.includes(id) : (p.days || []).includes(n)).map(p => rule('part', p.id)).filter(Boolean);
    return ms.includes('in') ? 'in' : ms.includes('out') ? 'out' : null; };
  const theirs = new Map();
  const followRule = (id, n) => { const t = followOn(st, mid, n); if (!t || seen.has(t)) return null;
    if (!theirs.has(t)) theirs.set(t, effectiveIn(doc, st, t, new Set(seen))); return theirs.get(t).has(id) ? 'in' : 'out'; };
  const out = new Set();
  for (const d of doc.days || []) for (const e of d.ev || []) {
    const m = rule('stop', e.id) || rule('day', d.n) || followRule(e.id, d.n) || partRule(e.id, d.n) || (host ? 'in' : null);
    if (m === 'in') out.add(String(e.id));
  }
  return out;
}
function mineIn(st, mid, s, seen) {
  if (s.member === mid) return true;
  if (!s.shared) return false;
  const j = (st.joins || []).find(x => x.member === mid && x.scope === 'mine' && x.ref === s.id);
  if (j) return j.mode === 'in';
  seen = seen || new Set(); seen.add(mid);
  const t = followOn(st, mid, s.day);
  return !!t && !seen.has(t) && mineIn(st, t, s, seen);
}

/* ---------- the trip as the assistant sees it: a whitelist of fields, never coordinates, links or attachments ---------- */
export function tripIndex(st) {
  const doc = (st.plan && st.plan.doc) || { days: [] }, me = st.me || {};
  const start = /^\d{4}-\d{2}-\d{2}$/.test(doc.start || '') ? doc.start : ((doc.days || [])[0] || {}).date || '2026-01-01';
  const names = new Map((st.members || []).map(m => [m.id, m.name]));
  const inSet = effectiveIn(doc, st, me.id);
  const days = (doc.days || []).map(d => ({ n: +d.n, date: addDays(start, +d.n - 1), city: str(d.city, 60), label: str(d.label, 80), summary: str(d.summary, 200), hotel: str(d.hotel, 80) }));
  const stops = new Map();
  for (const d of doc.days || []) for (const e of d.ev || []) {
    const id = String(e.id);
    stops.set(id, { id, day: +d.n, s: str(e.s, 5), e: str(e.e, 5), t: str(e.t, 120), loc: str(e.loc, 80), place: str(e.pname || e.to, 80),
      note: cut(redact(e.note), 220), cat: str(e.cat, 20), st: str(e.st, 10), sh: +e.off === 480, from: 'group', inMine: inSet.has(id) });
  }
  for (const s of st.my_stops || []) {
    if (!s || !/^m-/.test(String(s.id)) || !(s.member === me.id || s.shared)) continue;
    const e = s.ev || {};
    stops.set(String(s.id), { id: String(s.id), day: +s.day, s: str(e.s, 5), e: str(e.e, 5), t: str(e.t, 120), loc: str(e.loc, 80), place: str(e.pname, 80),
      note: cut(redact(e.note), 220), cat: str(e.cat, 20), st: str(e.st, 10), sh: false, from: 'mine', own: s.member === me.id,
      owner: names.get(s.member) || '', inMine: mineIn(st, me.id, s) });
  }
  const parts = (st.parts || []).filter(p => (st.joins || []).some(j => j.member === me.id && j.scope === 'part' && j.ref === p.id && j.mode === 'in')).map(p => str(p.title, 60));
  const done = new Set((st.task_state || []).filter(t => t.done).map(t => t.ref));
  const bookings = (doc.bookings || []).map(b => ({ id: str(b.id, 40), t: str(b.t, 120), when: cut(redact(b.when), 120), status: b.st === 'fixed' || done.has('bk:' + b.id) ? 'куплено' : 'надо купить',
    days: (b.days || []).map(Number).filter(Number.isFinite) }));
  const recipes = (st.recipes || []).map(r => ({ bk: str(r.bk, 40), what: str(r.what, 160), buy_by: str(r.buy_by, 10), opens: str(r.opens_note || r.opens, 60), site: str(r.site, 40),
    price_pp: Number.isFinite(+r.price_pp) ? +r.price_pp : null, tips: cut(redact(r.tips), 240) }));
  const tasks = (st.tasks || []).map(t => ({ title: str(t.title, 120), due: str(t.due, 10), done: done.has('t:' + t.id) }));
  return { me: { id: me.id, name: str(me.name, 40), role: me.role === 'host' ? 'host' : 'guest' }, start, days, stops, parts, bookings, recipes, tasks,
           members: (st.members || []).map(m => ({ name: str(m.name, 40), role: m.role === 'host' ? 'хозяин' : 'гость' })) };
}

export function japanNow(ms) { const iso = new Date(ms + 9 * 3600e3).toISOString(); return { date: iso.slice(0, 10), time: iso.slice(11, 16) }; }
/* which day is "today" for the context: the trip day in Japan, else the first (before) or the last (after) */
export function focusDay(idx, ms) {
  const { date } = japanNow(ms), ds = idx.days;
  if (!ds.length) return { n: null, phase: 'none' };
  const hit = ds.find(d => d.date === date);
  if (hit) return { n: hit.n, phase: 'live' };
  return date < ds[0].date ? { n: ds[0].n, phase: 'pre' } : { n: ds[ds.length - 1].n, phase: 'post' };
}

const tmin = s => { const m = HM.exec(s || ''); return m ? +s.slice(0, 2) * 60 + +s.slice(3) : 1e9; };
function stopLine(x) {
  const who = x.from === 'group' ? (x.inMine ? 'план группы, вы идёте' : 'план группы, без вас') : x.own ? `ваш пункт${x.inMine ? '' : ', скрыт'}` : `пункт ${x.owner}${x.inMine ? ', вы идёте' : ''}`;
  const where = [x.place, x.loc].filter(Boolean).join(' / ');
  return `  [${x.id}] ${x.s}${x.e ? '–' + x.e : ''}${x.sh ? ' (время Шанхая)' : ''} ${x.t}${where ? ' · ' + where : ''}${x.st === 'fixed' ? ' · время жёсткое' : ''} · ${who}${x.note ? ' · ' + x.note : ''}`;
}
export function dayStops(idx, n) { return [...idx.stops.values()].filter(x => x.day === n).sort((a, b) => tmin(a.s) - tmin(b.s)); }
export function dayText(idx, n) {
  const d = idx.days.find(x => x.n === n); if (!d) return '';
  const xs = dayStops(idx, n);
  return `День ${d.n} · ${dm(d.date)} ${wd(d.date)} · ${d.city} — ${d.label}${d.hotel ? ' · ночь: ' + d.hotel : ''}\n${xs.length ? xs.map(stopLine).join('\n') : '  (пунктов нет)'}`;
}
/* today ±2 days in full (and the day on screen), one line for every other day — keeps each request small */
export function contextText(idx, ms, viewDay) {
  const now = japanNow(ms), f = focusDay(idx, ms), total = idx.days.length;
  const full = new Set(idx.days.filter(d => f.n != null && Math.abs(d.n - f.n) <= 2).map(d => d.n));
  if (Number.isInteger(viewDay) && idx.days.some(d => d.n === viewDay)) full.add(viewDay);
  const head = f.phase === 'live' ? `идёт день ${f.n} из ${total}` : f.phase === 'pre'
    ? `до поездки ${Math.round((Date.parse(idx.days[0].date) - Date.parse(now.date)) / 864e5)} дн. (день 1 = ${dm(idx.days[0].date)})` : 'поездка закончилась';
  const lines = [
    `Сейчас в Японии: ${dm(now.date)}.${now.date.slice(0, 4)} (${wd(now.date)}) ${now.time}; ${head}.`,
    `Собеседник: ${idx.me.name}, ${idx.me.role === 'host' ? 'хозяин (может менять план группы)' : 'гость (изменения плана группы — только предложения хозяевам)'}.`,
    `Группа: ${idx.members.map(m => `${m.name} (${m.role})`).join(', ')}.`,
    idx.parts.length ? `Части поездки, к которым присоединился: ${idx.parts.join(', ')}.` : '',
    Number.isInteger(viewDay) ? `На экране сейчас день ${viewDay}.` : '',
    'Пункты: [id] время название · место · чей · заметка.',
    ...idx.days.map(d => full.has(d.n) ? dayText(idx, d.n)
      : `День ${d.n} · ${dm(d.date)} ${wd(d.date)} · ${d.city} — ${d.label}${d.summary ? ': ' + cut(d.summary, 140) : ''} (${dayStops(idx, d.n).length} пункт., подробно — get_day)`),
  ];
  return lines.filter(Boolean).join('\n');
}

/* ---------- the traveller's profile and the app's rates (sent by the phone with every question) ---------- */
export const LANGS = { ru: 'русский', kk: 'казахский', en: 'английский' };
const TONES = { calm: 'спокойный и тёплый', fun: 'с юмором, легко', strict: 'строго по делу' };
const ENERGY = { low: 'низкая — меньше ходьбы, больше пауз', mid: 'средняя', high: 'высокая — можно насыщенно' };
export function normaliseProfile(p) {
  p = p && typeof p === 'object' ? p : {};
  const pick = (v, set, d) => typeof v === 'string' && Object.prototype.hasOwnProperty.call(set, v) ? v : d;
  const n = p.notify && typeof p.notify === 'object' ? p.notify : {};
  return { name: str(p.name, 40), lang: pick(p.lang, LANGS, 'ru'), tone: pick(p.tone, TONES, 'calm'), energy: pick(p.energy, ENERGY, 'mid'),
           interests: str(p.interests, 200), food: str(p.food, 200),
           notify: { morning: n.morning !== false, place: n.place !== false, evening: n.evening !== false } };
}
export function normaliseRates(r) {
  r = r && typeof r === 'object' ? r : {};
  const ok = (v, lo, hi) => typeof v === 'number' && Number.isFinite(v) && v > lo && v < hi ? v : null;
  return { KZT: ok(r.KZT, 0.5, 20) || 3.4, USD: ok(r.USD, 0.001, 0.05) || 0.0067 };     // per 1 JPY
}
export function profileText(profile, rates) {
  const p = normaliseProfile(profile), r = normaliseRates(rates);
  return [`Профиль собеседника: ${p.name ? 'обращаться «' + p.name + '»; ' : ''}язык ответа — ${LANGS[p.lang]}; тон — ${TONES[p.tone]}; энергия — ${ENERGY[p.energy]}`
    + `${p.interests ? '; интересы: ' + p.interests : ''}${p.food ? '; еда: ' + p.food : ''}.`,
    `Курсы приложения: 1 ¥ = ${r.KZT} ₸ = ${r.USD} $.`].join('\n');
}
export function convert(amount, from, to, rates) {
  const r = { JPY: 1, ...normaliseRates(rates) };
  if (!CURS.includes(from) || !CURS.includes(to) || typeof amount !== 'number' || !Number.isFinite(amount) || amount < 0 || amount > 1e10) return null;
  const v = amount / r[from] * r[to], k = to === 'USD' ? 100 : 1;
  return Math.round(v * k) / k;
}
const gmapsUrl = (q, lat, lng, from) => {
  const to = lat != null && lng != null ? `${lat}%2C${lng}` : encodeURIComponent(q);
  return from ? `https://www.google.com/maps/dir/?api=1&origin=${encodeURIComponent(from)}&destination=${to}&travelmode=transit`
    : 'https://www.google.com/maps/search/?api=1&query=' + to;
};

/* ---------- tools ---------- */
const S = (props, req) => ({ type: 'object', properties: props, required: req, additionalProperties: false });
const T_ = { type: 'string', description: 'HH:MM, 24 часа, японское время' };
export const TOOLS = [
  { name: 'get_day', description: 'Все пункты дня поездки: id, время, место, чей пункт, заметки.', input_schema: S({ day_n: { type: 'integer', description: 'Номер дня поездки' } }, ['day_n']) },
  { name: 'find_stops', description: 'Найти пункты по слову в названии, месте или заметке (по всей поездке).', input_schema: S({ query: { type: 'string' } }, ['query']) },
  { name: 'get_bookings', description: 'Брони, билеты и задачи: что куплено, что купить и до какого числа. Без номеров и кодов.', input_schema: S({}, []) },
  { name: 'app_help', description: 'Короткая справка, как сделать что-то в приложении.', input_schema: S({ topic: { type: 'string', description: 'Тема или вопрос, например «билет», «расход», «уведомления»' } }, ['topic']) },
  { name: 'emergency_info', description: 'Экстренные номера (Япония, Китай), страховка Forte Travel (ассистанс, лимиты, документы), посольство, потеря паспорта.',
    input_schema: S({ topic: { type: 'string', description: 'Что случилось или что нужно: «болит зуб», «потерян багаж», «паспорт», «Шанхай»' } }, ['topic']) },
  { name: 'card_perks', description: 'Возможности карты Forte Travel в поездке: бизнес-залы, консьерж, eSIM, курс, банкоматы, бонусы.',
    input_schema: S({ topic: { type: 'string' } }, ['topic']) },
  { name: 'convert_currency', description: 'Пересчитать сумму между JPY, KZT и USD по курсам приложения.',
    input_schema: S({ amount: { type: 'number' }, from: { type: 'string', enum: CURS }, to: { type: 'string', enum: CURS } }, ['amount', 'from', 'to']) },
  { name: 'show_japanese', description: 'Показать японский текст крупной карточкой «Показать по-японски» (прохожему, таксисту, официанту).',
    input_schema: S({ japanese: { type: 'string' }, reading: { type: 'string', description: 'Произношение кириллицей' }, meaning: { type: 'string', description: 'Смысл на языке собеседника' } }, ['japanese', 'meaning']) },
  { name: 'suggest_place', description: 'Карточка места со ссылкой на Google Maps; с from — маршрут на общественном транспорте оттуда.',
    input_schema: S({ name: { type: 'string' }, query: { type: 'string', description: 'Запрос для карты, лучше по-английски или по-японски' }, note: { type: 'string' },
      from: { type: 'string', description: 'Откуда ехать (станция, место) — для маршрута' }, lat: { type: 'number' }, lng: { type: 'number' } }, ['name', 'query']) },
  { name: 'propose_move_stop', description: 'Предложить новое время пункта. Ничего не меняет, пока человек не нажмёт «Применить».',
    input_schema: S({ stop_id: { type: 'string' }, start: T_, end: T_, reason: { type: 'string', description: 'Коротко, зачем' } }, ['stop_id', 'start', 'end', 'reason']) },
  { name: 'propose_skip_stop', description: 'Предложить не идти на пункт (для плана группы — «Без меня»). Ничего не меняет до «Применить».',
    input_schema: S({ stop_id: { type: 'string' }, reason: { type: 'string' } }, ['stop_id', 'reason']) },
  { name: 'propose_add_stop', description: 'Предложить новый пункт: по умолчанию в личный план; target "group" — в план группы (у гостя станет предложением хозяевам).',
    input_schema: S({ day_n: { type: 'integer' }, start: T_, end: T_, title: { type: 'string' }, place_name: { type: 'string' },
      lat: { type: 'number' }, lng: { type: 'number' }, note: { type: 'string' }, target: { type: 'string', enum: ['mine', 'group'] } }, ['day_n', 'start', 'end', 'title', 'place_name', 'note']) },
  { name: 'propose_add_expense', description: 'Предложить записать расход; человек проверит и сохранит его в окне расхода.',
    input_schema: S({ amount: { type: 'number' }, currency: { type: 'string', enum: CURS }, category: { type: 'string', enum: CATS }, title: { type: 'string' } }, ['amount', 'currency', 'category', 'title']) },
];
export const WEB_SEARCH = { type: 'web_search_20260209', name: 'web_search', max_uses: LIMITS.webSearches,
  user_location: { type: 'approximate', country: 'JP', timezone: 'Asia/Tokyo' } };

/* the exact request body for one step of the loop (client.beta.messages.create) */
export function buildRequest(system, messages) {
  return {
    model: MODEL, max_tokens: LIMITS.maxTokens,
    output_config: { effort: 'low' },                          // short chat answers; thinking stays adaptive (always on for this model)
    betas: ['server-side-fallback-2026-07-01'], fallbacks: 'default',
    system, tools: [...TOOLS, WEB_SEARCH], messages,
  };
}
/* the voice translator: one short call, no tools */
const TR_LANG = ['ru', 'kk', 'en', 'ja'];
export function normaliseTranslate(b) {
  const t = str(b && b.text, 500);
  if (!t || !TR_LANG.includes(b.from) || !TR_LANG.includes(b.to) || b.from === b.to || (b.from !== 'ja' && b.to !== 'ja')) return null;
  return { text: t, from: b.from, to: b.to };
}
export function buildTranslateRequest(t) {
  const FROM = { ru: 'русского', kk: 'казахского', en: 'английского', ja: 'японского' }, TO = { ru: 'русский', kk: 'казахский', en: 'английский', ja: 'японский' };
  return { model: MODEL, max_tokens: 1000, output_config: { effort: 'low' }, betas: ['server-side-fallback-2026-07-01'], fallbacks: 'default',
    system: `Ты устный переводчик в поездке. Переведи реплику с ${FROM[t.from]} на ${TO[t.to]} — естественно и вежливо, как сказал бы местный. Верни только перевод: без кавычек, пояснений и транскрипции.`,
    messages: [{ role: 'user', content: t.text }] };
}
export const translationOf = res => !res || res.stop_reason === 'refusal' ? null : textOf(res) || null;
export function buildSystem(ctx) {
  return [{ type: 'text', text: SYSTEM, cache_control: { type: 'ephemeral' } }, { type: 'text', text: ctx }];
}

/* ---------- the conversation the app sends back: text turns; photos only on the last question ---------- */
const IMG = /^image\/(jpeg|png|webp)$/;
function imagesOf(t) {
  const xs = Array.isArray(t && t.images) ? t.images.slice(0, LIMITS.images) : [];
  return xs.filter(x => x && IMG.test(x.media_type) && typeof x.data === 'string' && x.data.length <= LIMITS.imageChars && /^[A-Za-z0-9+/]+=*$/.test(x.data))
    .map(x => ({ type: 'image', source: { type: 'base64', media_type: x.media_type, data: x.data } }));
}
export function normaliseHistory(turns) {
  const out = normaliseText(turns);
  if (!out) return out;
  const lastUser = [...turns].reverse().find(t => t && t.role === 'user');
  const imgs = imagesOf(lastUser);
  const l = out[out.length - 1];
  if (imgs.length) l.content = [...imgs, { type: 'text', text: l.content }];
  else if (l.content === '(фото)') return null;                 // only photos, and none of them usable
  return out;
}
function normaliseText(turns) {
  if (!Array.isArray(turns)) return null;
  const out = [];
  for (const t of turns.slice(-LIMITS.turns * 2)) {
    if (!t || (t.role !== 'user' && t.role !== 'assistant')) continue;
    let text = String(t.text == null ? '' : t.text).trim().slice(0, LIMITS.turnChars);
    if (!text && t.role === 'user' && Array.isArray(t.images) && t.images.length) text = '(фото)';
    if (!text) continue;
    if (out.length && out[out.length - 1].role === t.role) out[out.length - 1].content += '\n\n' + text;
    else out.push({ role: t.role, content: text });
  }
  while (out.length && out[0].role !== 'user') out.shift();
  const last = out.slice(-LIMITS.turns);
  while (last.length && last[0].role !== 'user') last.shift();
  return last.length && last[last.length - 1].role === 'user' ? last : null;
}

/* ---------- checks for the proposals ---------- */
const bad = msg => ({ error: msg });
const okTimes = (s, e) => !HM.test(s || '') ? 'Время начала — в формате HH:MM.' : !HM.test(e || '') ? 'Время конца — в формате HH:MM.' : e <= s ? 'Конец должен быть позже начала.' : null;
const text = (v, n, what, need) => {
  if (v == null || v === '') return need ? { error: `Нужно поле «${what}».` } : { v: '' };
  if (typeof v !== 'string') return { error: `«${what}» — строка.` };
  const s = v.replace(/\s+/g, ' ').trim();
  if (need && !s) return { error: `Нужно поле «${what}».` };
  if (s.length > n) return { error: `«${what}» длиннее ${n} символов — сократи.` };
  return { v: s };
};
export function validate(name, input, idx) {
  const a = input && typeof input === 'object' ? input : {};
  const role = idx.me.role;
  if (name === 'propose_move_stop' || name === 'propose_skip_stop') {
    const x = idx.stops.get(String(a.stop_id || ''));
    if (!x) return bad('Нет такого пункта. Возьми id из get_day или find_stops.');
    const reason = text(a.reason, 300, 'reason', false); if (reason.error) return reason;
    const base = { stop_id: x.id, day_n: x.day, title: x.t, reason: reason.v };
    if (name === 'propose_skip_stop') {
      if (!x.inMine) return bad('Этого пункта и так нет в плане человека.');
      return { action: { kind: 'skip', ...base, scope: x.from === 'group' ? 'group' : x.own ? 'mine' : 'shared' } };
    }
    if (x.from === 'mine' && !x.own) return bad(`Это личный пункт ${x.owner}: изменить время может только автор. Можно предложить не идти или добавить свой пункт.`);
    const t = okTimes(a.start, a.end); if (t) return bad(t);
    if (a.start === x.s && a.end === x.e) return bad('Время не изменилось.');
    return { action: { kind: 'move', ...base, from_s: x.s, from_e: x.e, start: a.start, end: a.end,
      scope: x.from === 'group' ? 'group' : 'mine', how: x.from !== 'group' ? 'save' : role === 'host' ? 'plan' : 'propose' } };
  }
  if (name === 'propose_add_stop') {
    const n = a.day_n;
    if (!Number.isInteger(n) || !idx.days.some(d => d.n === n)) return bad(`Нет дня ${a.day_n}: дни 1–${idx.days.length}.`);
    const t = okTimes(a.start, a.end); if (t) return bad(t);
    const title = text(a.title, 120, 'title', true); if (title.error) return title;
    const place = text(a.place_name, 120, 'place_name', false); if (place.error) return place;
    const note = text(a.note, 500, 'note', false); if (note.error) return note;
    const num = (v, lim) => v == null ? null : typeof v === 'number' && Number.isFinite(v) && Math.abs(v) <= lim ? Math.round(v * 1e5) / 1e5 : NaN;
    const lat = num(a.lat, 90), lng = num(a.lng, 180);
    if (Number.isNaN(lat) || Number.isNaN(lng) || (lat == null) !== (lng == null)) return bad('Координаты — оба числа (lat, lng) или ни одного.');
    if (a.target != null && a.target !== 'mine' && a.target !== 'group') return bad('target — "mine" или "group".');
    const scope = a.target === 'group' ? 'group' : 'mine';
    return { action: { kind: 'add', day_n: n, start: a.start, end: a.end, title: title.v, place: place.v, lat, lng, note: note.v, scope,
      how: scope === 'mine' ? 'save' : role === 'host' ? 'plan' : 'propose' } };
  }
  if (name === 'propose_add_expense') {
    if (!CURS.includes(a.currency)) return bad('Валюта — JPY, KZT или USD.');
    if (!CATS.includes(a.category)) return bad('Категория — одна из: ' + CATS.join(', ') + '.');
    const amt = a.amount;
    if (typeof amt !== 'number' || !Number.isFinite(amt) || amt <= 0) return bad('Сумма — положительное число.');
    if (amt / RATE[a.currency] > MAX_JPY) return bad('Слишком большая сумма.');
    const title = text(a.title, 80, 'title', false); if (title.error) return title;
    return { action: { kind: 'expense', amount: Math.round(amt * 100) / 100, currency: a.currency, category: a.category, title: title.v } };
  }
  return bad('Неизвестное действие.');
}

const QUEUED = 'Предложение показано человеку карточкой «Применить / Не надо» и ждёт его решения — пока ничего не изменилось.';
/* one tool call → { content, is_error? }; proposals are collected into `actions` */
export function runTool(name, input, idx, out, extra) {
  const a = input && typeof input === 'object' ? input : {}, actions = out.actions, cards = out.cards;
  if (name === 'emergency_info') { out.sos = true; return { content: emergencyInfo(a.topic) }; }
  if (name === 'card_perks') return { content: cardPerks(a.topic) };
  if (name === 'convert_currency') {
    const v = convert(a.amount, a.from, a.to, (extra || {}).rates);
    return v == null ? { content: 'Нужны сумма и валюты JPY, KZT или USD.', is_error: true } : { content: `${a.amount} ${a.from} ≈ ${v} ${a.to} (курс приложения)` };
  }
  if (name === 'show_japanese' || name === 'suggest_place') {
    if (cards.length >= LIMITS.cards) return { content: 'Карточек уже достаточно.', is_error: true };
    if (name === 'show_japanese') {
      const ja = text(a.japanese, 200, 'japanese', true), rd = text(a.reading, 200, 'reading', false), mn = text(a.meaning, 200, 'meaning', true);
      const e = ja.error || rd.error || mn.error; if (e) return { content: e, is_error: true };
      cards.push({ kind: 'ja', ja: ja.v, reading: rd.v, meaning: mn.v });
      return { content: 'Карточка показана.' };
    }
    const nm = text(a.name, 120, 'name', true), q = text(a.query, 200, 'query', true), note = text(a.note, 200, 'note', false), from = text(a.from, 120, 'from', false);
    const e = nm.error || q.error || note.error || from.error; if (e) return { content: e, is_error: true };
    const ll = (v, lim) => typeof v === 'number' && Number.isFinite(v) && Math.abs(v) <= lim ? Math.round(v * 1e5) / 1e5 : null;
    const lat = ll(a.lat, 90), lng = ll(a.lng, 180), both = lat != null && lng != null;
    cards.push({ kind: 'place', name: nm.v, note: note.v, route: !!from.v, url: gmapsUrl(q.v, both ? lat : null, both ? lng : null, from.v) });
    return { content: 'Карточка места показана.' };
  }
  if (name === 'get_day') {
    const n = a.day_n;
    return idx.days.some(d => d.n === n) ? { content: dayText(idx, n) } : { content: `Нет дня ${n}: дни 1–${idx.days.length}.`, is_error: true };
  }
  if (name === 'find_stops') {
    const q = str(a.query, 60).toLowerCase();
    if (q.length < 2) return { content: 'Слишком короткий запрос.', is_error: true };
    const hits = [...idx.stops.values()].filter(x => [x.t, x.place, x.loc, x.note].some(v => String(v || '').toLowerCase().includes(q))).slice(0, 15);
    return { content: hits.length ? hits.map(x => `День ${x.day}:` + stopLine(x)).join('\n') : 'Ничего не нашлось.' };
  }
  if (name === 'get_bookings') {
    const b = idx.bookings.map(x => `- ${x.t} · ${x.when} · ${x.status}${x.days.length ? ' · дни ' + x.days.join(',') : ''}`).join('\n');
    const r = idx.recipes.map(x => `- ${x.what}${x.buy_by ? ' · купить до ' + x.buy_by : ''}${x.opens ? ' · продажи: ' + x.opens : ''}${x.site ? ' · ' + x.site : ''}${x.price_pp ? ' · ¥' + x.price_pp + '/чел' : ''}${x.tips ? ' · ' + x.tips : ''}`).join('\n');
    const t = idx.tasks.map(x => `- ${x.title}${x.due ? ' · до ' + x.due : ''}${x.done ? ' · сделано' : ''}`).join('\n');
    return { content: `Брони:\n${b || '—'}\nКак купить:\n${r || '—'}\nЗадачи:\n${t || '—'}\n(Коды броней и билеты — только в «Делах» у брони.)` };
  }
  if (name === 'app_help') return { content: appHelp(a.topic) };
  if (/^propose_/.test(name)) {
    if (actions.length >= LIMITS.actions) return { content: 'Слишком много предложений за один ответ — остановись на главных.', is_error: true };
    const r = validate(name, a, idx);
    if (r.error) return { content: r.error, is_error: true };
    actions.push({ id: 'a' + (actions.length + 1), ...r.action });
    return { content: QUEUED + (r.action.how === 'propose' ? ' Если человек применит, это станет предложением хозяевам.' : '') };
  }
  return { content: 'Нет такого инструмента.', is_error: true };
}

/* ---------- the reply ---------- */
const textOf = res => ((res && res.content) || []).filter(b => b && b.type === 'text').map(b => b.text || '').join('').trim();
export function sourcesOf(res) {
  const out = [], seen = new Set();
  for (const b of (res && res.content) || []) for (const c of (b && b.type === 'text' && b.citations) || []) {
    const u = String(c.url || '');
    if (/^https:\/\/[^\s"'<>]+$/i.test(u) && !seen.has(u) && out.length < 4) { seen.add(u); out.push({ title: str(c.title || u, 80), url: u }); }
  }
  return out;
}
export const REFUSAL = 'С этим я помочь не могу. Спросите про поездку, места или приложение.';
const EMPTY = 'Не получилось ответить — переформулируйте вопрос.';

/* The agent loop. create(body) → the API's message; now() → ms. Thinking and server-tool blocks go back unchanged. */
export async function runAgent({ create, system, messages, idx, rates, now = Date.now }) {
  const t0 = now(), actions = [], cards = [], out = { actions, cards };
  const usage = { input_tokens: 0, output_tokens: 0, cache_read_input_tokens: 0, cache_creation_input_tokens: 0, web_search_requests: 0, iterations: 0 };
  let msgs = messages.slice(), res = null, why = 'done';
  for (;;) {
    if (usage.iterations >= LIMITS.iterations) { why = 'iterations'; break; }
    if (now() - t0 > LIMITS.wallMs) { why = 'time'; break; }
    res = await create(buildRequest(system, msgs));
    usage.iterations++;
    const u = res.usage || {};
    for (const k of ['input_tokens', 'output_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens']) usage[k] += +u[k] || 0;
    usage.web_search_requests += +((u.server_tool_use || {}).web_search_requests) || 0;
    if (res.stop_reason === 'refusal') return { reply: REFUSAL, actions: [], cards: [], sources: [], usage, stop: 'refusal' };
    if (res.stop_reason === 'pause_turn') { msgs = [...msgs, { role: 'assistant', content: res.content }]; continue; }
    if (res.stop_reason === 'tool_use') {
      const results = res.content.filter(b => b.type === 'tool_use').map(b => {
        const r = runTool(b.name, b.input, idx, out, { rates });
        return { type: 'tool_result', tool_use_id: b.id, content: r.content, ...(r.is_error ? { is_error: true } : {}) };
      });
      msgs = [...msgs, { role: 'assistant', content: res.content }, { role: 'user', content: results }];
      continue;
    }
    why = res.stop_reason === 'max_tokens' ? 'max_tokens' : 'done';
    break;
  }
  let reply = textOf(res);
  if (why === 'max_tokens') reply = (reply ? reply + '\n\n' : '') + '(Ответ оборвался — спросите короче.)';
  else if (why !== 'done') reply = (res && res.stop_reason === 'end_turn' && reply) ? reply
    : (actions.length ? 'Вот что я успел предложить — проверьте карточки ниже.' : 'Не успел всё проверить — уточните вопрос.');
  return { reply: reply || (actions.length ? 'Предложил изменения — проверьте карточки ниже.' : cards.length ? 'Смотрите карточки ниже.' : EMPTY),
           actions, cards, sources: sourcesOf(res), sos: !!out.sos, usage, stop: why };
}
