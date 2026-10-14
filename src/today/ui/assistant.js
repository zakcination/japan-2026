/* ---------- the assistant: a chat with Claude (Edge Function «assistant»), signed-in members only ----------
   It only proposes: plan changes and expenses come back as cards, and nothing changes until «Применить».
   Also: a profile kept on this phone (how to call me, language, tone…), photos, dictation, a voice translator. */
const ASK_PROFILE = 'japan2026.assistant.profile.v1';
const ASK_CHAT = 'japan2026.assistant.chat.v1';
const ASK = { turns: (() => { try { const t = JSON.parse(localStorage.getItem(ASK_CHAT) || '[]'); return Array.isArray(t) ? t.slice(-30) : []; } catch (e) { return []; } })(),
              busy: false, view: 'chat', pics: [], rec: null, req: 0 };
/* the conversation stays on this phone (text only, last 30 turns) — reopening the chat continues it */
function askSaveChat() {
  try { localStorage.setItem(ASK_CHAT, JSON.stringify(ASK.turns.slice(-30).map(t => ({ ...t, images: null, thumbs: [] })))); } catch (e) {}
}
ICONS.spark = '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/><path d="M19 15l.7 2.3L22 18l-2.3.7L19 21l-.7-2.3L16 18l2.3-.7z"/>';
ICONS.mic = '<rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5 11a7 7 0 0 0 14 0M12 18v3"/>';
ICONS.cam = '<path d="M4 8h3l2-3h6l2 3h3v11H4z"/><circle cx="12" cy="13" r="3.5"/>';
ICONS.speak = '<path d="M4 9h4l5-4v14l-5-4H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/>';
ICONS.send = '<path d="M12 19V5M6 11l6-6 6 6"/>';

const askOn = () => typeof Api !== 'undefined' && Api.enabled() && !!Api.me();
/* the in-app assistant needs the owner's API key on the server; until the trip says so, ✦ opens «Спросить в Claude» for everyone */
const askServer = () => { try { if (/^(1|all)$/.test(localStorage.getItem('japan2026.assistant.server') || '')) return true; } catch (e) {} return !!(T.group && T.group.assistant); };
/* T.group.assistant: true for everyone, or a list of member names who may use it (the server checks the same list) */
const askMine = () => { const a = T.group && T.group.assistant, me = Api.me();
  if (!Array.isArray(a)) return true;
  try { if (localStorage.getItem('japan2026.assistant.server') === 'all') return true; } catch (e) {}   // tests; the server still checks
  const norm = s => String(s || '').trim().toLowerCase();
  return !!me && a.some(n => norm(n) === norm(me.name)); };
/* photos need a model that reads images (Claude); the trip turns them off for DeepSeek */
const askPhotos = () => { try { if (localStorage.getItem('japan2026.assistant.photos') === '1') return true; } catch (e) {} return !(T.group && T.group.assistant_photos === false); };
/* the Edge Function's name in Supabase (the owner deployed it as «clever-handler») */
const askFn = () => (T.group && /^[a-z][a-z0-9_-]{0,62}$/.test(T.group.assistant_fn || '') ? T.group.assistant_fn : 'assistant');
const askFull = () => askServer() && askOn() && askMine();
/* a round button above the tab bar, bottom right (the header is full: SOS, capsule, gear); rendered with the header, on every tab */
const askHTML = () => { if (!askFull()) return '';
  const link = askCompanion();
  if (link) return `<a class="tc-askfab" id="tcAsk" href="${link}" target="_blank" rel="noopener" aria-label="Спутник: ассистент на claude.ai">${icon('spark')}</a>`;
  const n = askPending().length;
  return `<button type="button" class="tc-askfab" id="tcAsk" data-ask aria-label="Ассистент${n ? ': оценить ' + n : ''}">${icon('spark')}${n ? `<span class="as-dot" aria-hidden="true">${n}</span>` : ''}</button>`; };
/* the companion on claude.ai (owner's own Claude account) replaces the in-app chat; a phone that set the server flag keeps the chat */
const askCompanion = () => { try { if (localStorage.getItem('japan2026.assistant.server') === 'all') return ''; } catch (e) {}
  return (T.group && Core.safeUrl(T.group.companion)) || ''; };
document.getElementById('today').addEventListener('click', e => { if (e.target.closest('[data-ask]') && !askCompanion()) openAssistant(); });

function askProfile() { try { return JSON.parse(localStorage.getItem(ASK_PROFILE) || 'null'); } catch (e) { return null; } }
function putProfile(p) { try { localStorage.setItem(ASK_PROFILE, JSON.stringify(p)); } catch (e) {} }
const LANG_SR = { ru: 'ru-RU', kk: 'kk-KZ', en: 'en-US', ja: 'ja-JP' };
const myLang = () => ((askProfile() || {}).lang) || 'ru';
const askRates = () => { try { const r = expRates(); return { KZT: +r.KZT, USD: +r.USD }; } catch (e) { return null; } };

function openAskProfile() { askLoadSeed(); ASK.view = 'profile'; askRender(); }
function openAssistant() {
  if (!askOn()) return;
  askSyncProfile(); askLoadAi(); askLoadSeed();
  ASK.view = askProfile() ? 'chat' : 'profile';
  askRender();
}
function askRender() {
  const title = ASK.view === 'profile' ? 'Профиль' : ASK.view === 'translate' ? 'Переводчик' : ASK.view === 'journal' ? 'Журнал и заявки' : ASK.view === 'request' ? 'Улучшить приложение' : 'Спутник';
  sheet(title, `<div class="as-wrap" id="asWrap">${ASK.view === 'profile' ? profileHTML() : ASK.view === 'translate' ? translateHTML() : ASK.view === 'journal' ? journalHTML() : ASK.view === 'request' ? requestHTML() : chatHTML()}</div>`, m => {
    fullSheet(m);
    m.querySelector('.tc-sheet').classList.toggle('as-chat', ASK.view === 'chat');
    if (ASK.view === 'journal') { wireJournal(m); return; }
    if (ASK.view === 'request') { wireRequest(m); return; }
    if (ASK.view === 'profile') wireProfile(m); else if (ASK.view === 'translate') wireTranslate(m); else wireChat(m);
  });
}

/* ---------- profile ---------- */
const seg = (name, val, opts) => `<div class="as-seg" role="radiogroup" data-seg="${name}">${opts.map(([k, l]) =>
  `<button type="button" role="radio" data-v="${k}" aria-checked="${k === val}">${esc(l)}</button>`).join('')}</div>`;
/* the questionnaire (28.09) seeded a profile on the server: offer it to confirm, never apply it silently */
function askLoadSeed() {
  if (askProfile() || ASK.seedTried || !navigator.onLine || !Api.me()) return;
  ASK.seedTried = true;
  Api.run('my_ai', {}).then(r => {
    const p = r && r.profile;
    if (!p || askProfile()) return;
    ASK.seed = p; if (ASK.view === 'profile' && document.getElementById('asWrap')) askRender();
  }).catch(() => {});
}
function profileHTML() {
  const seed = !askProfile() && ASK.seed ? ASK.seed : null;
  const p = askProfile() || seed || {}, n = p.notify || {};
  const sw = (k, l, sub) => `<label class="tc-act"><span>${l}<small>${sub}</small></span><input type="checkbox" switch data-notify="${k}"${n[k] === false ? '' : ' checked'}></label>`;
  return `${seed ? `<div class="tc-card tc-note" id="asSeed"><b>Заполнили по вашей анкете</b>
      <span class="tc-sub">Проверьте и поправьте: как к вам обращаться, язык и тон — в анкете их не было.</span></div>` : ''}
    <p class="tc-sub">Пара вопросов, чтобы отвечать по-вашему. ${askP1() ? 'Видите вы и Спутник; хозяева — нет.' : 'Хранится только на этом телефоне и отправляется вместе с вопросом.'}</p>
    ${fld('asName', 'Как к вам обращаться', p.name || (Api.me() || {}).name || '', 'text', 'maxlength="40" autocomplete="nickname"')}
    <span class="tc-lbl">Язык ответов</span>${seg('lang', p.lang || 'ru', [['ru', 'Русский'], ['kk', 'Қазақша'], ['en', 'English']])}
    <span class="tc-lbl">Тон</span>${seg('tone', p.tone || 'calm', [['calm', 'Спокойно'], ['fun', 'С юмором'], ['strict', 'Строго']])}
    <span class="tc-lbl">Энергия</span>${seg('energy', p.energy || 'mid', [['low', 'Бережно'], ['mid', 'Средне'], ['high', 'На максимум']])}
    ${fld('asInterests', 'Что интересно (храмы, еда, шопинг, фото…)', p.interests || '', 'text', 'maxlength="200"')}
    ${fld('asFood', 'Еда: ограничения (халяль, без свинины, аллергия…)', p.food || '', 'text', 'maxlength="200"')}
    <label class="tc-f" for="asNotes"><span>О себе: ритм дня, что не любите, здоровье — что учитывать</span><textarea id="asNotes" rows="3" maxlength="500">${esc(p.notes || '')}</textarea></label>
    ${askP1() ? `<span class="tc-sech">Сообщения от ассистента</span>
    <div class="tc-group">${sw('morning', 'Утром', 'настрой и первые пункты дня')}${sw('place', 'После каждого места', 'оценка в пять звёзд')}${sw('evening', 'Вечером', 'как прошёл день')}</div>` : ''}
    <div class="tc-actions two"><button type="button" class="tc-btn primary" id="asProfSave">Сохранить</button>
      <button type="button" class="tc-btn" id="asProfLater">${askProfile() ? 'Отмена' : 'Позже'}</button></div>`;
}
function wireProfile(m) {
  m.querySelectorAll('[data-seg]').forEach(g => g.addEventListener('click', e => {
    const b = e.target.closest('[data-v]'); if (!b) return;
    g.querySelectorAll('[data-v]').forEach(x => x.setAttribute('aria-checked', String(x === b)));
  }));
  const segVal = k => (m.querySelector(`[data-seg="${k}"] [aria-checked="true"]`) || {}).dataset.v;
  m.querySelector('#asProfSave').addEventListener('click', () => {
    const v = id => m.querySelector('#' + id).value.trim(), notify = {};
    const was = (askProfile() || {}).notify || {};
    Object.assign(notify, was); m.querySelectorAll('[data-notify]').forEach(i => { notify[i.dataset.notify] = i.checked; });
    putProfile({ name: v('asName').slice(0, 40), lang: segVal('lang') || 'ru', tone: segVal('tone') || 'calm', energy: segVal('energy') || 'mid',
                 interests: v('asInterests').slice(0, 200), food: v('asFood').slice(0, 200), notes: v('asNotes').slice(0, 500), notify, at: Date.now() });
    if (typeof askSyncProfile === 'function') askSyncProfile();
    ASK.view = 'chat'; askRender();
  });
  m.querySelector('#asProfLater').addEventListener('click', () => { if (!askProfile()) putProfile({ lang: 'ru', skipped: true, at: Date.now() });
    ASK.view = 'chat'; askRender(); });
}

/* ---------- chat ---------- */
const nl = s => esc(s).replace(/\n/g, '<br>');
/* suggestions for right now: the trip phase, the time of day, what is on and what is next in my plan */
function askSuggest() {
  const out = [], add = q => { if (q && !out.includes(q) && out.length < 6) out.push(q); };
  let x; try { x = ctx(); } catch (e) { return EXAMPLES; }
  const ph = (x.ph && x.ph.phase) || 'live', min = x.c ? x.c.min : null, h = min == null ? 12 : Math.floor(min / 60);
  const evs = (x.cevs || []).filter(e => !e.skip && !e.auto && !e.bad && !e.done);
  const cut = t => { t = String(t || ''); return t.length > 24 ? t.slice(0, 23) + '…' : t; };
  if (ph === 'pre') {
    add('Что осталось сделать до вылета?'); add('Что взять в ручную кладь?'); add('Как пройти пересадку в Пудуне?');
    add('Что посмотреть в первый день?'); add('Сколько наличных иен взять?'); return out;
  }
  if (ph === 'departure' || ph === 'transit') {
    add('Что делать на пересадке в Шанхае?'); add('Как добраться из Ханэды до рёкана?'); add('Что сказать на паспортном контроле?');
    add('Где поесть в аэропорту без свинины?'); return out;
  }
  if (ph === 'post') { add('Как вернуть tax-free при вылете?'); add('Что купить в аэропорту?'); return out; }
  const cur = min == null ? null : evs.find(e => e.ns <= min && min < e.ne);
  const next = min == null ? evs[0] : evs.find(e => e.ns > min);
  if (next) {
    if (next.cat === 'transport') add(`Где сесть на «${cut(next.t)}» в ${next.s}?`);
    else add(`Как добраться до «${cut(next.t)}» к ${next.s}?`);
  }
  if (cur && cur.cat !== 'transport') add(`Что не пропустить в «${cut(cur.t)}»?`);
  if (h >= 6 && h < 10) add('Где позавтракать рядом?');
  else if (h >= 11 && h < 14) add('Где пообедать халяль рядом?');
  else if (h >= 17 && h < 21) add('Где поужинать всем пятерым?');
  if (h >= 20) { add('Что завтра и во сколько выходить?'); add('Как вернуться в отель последним поездом?'); }
  if (!next && h < 20) add('Чем заняться до вечера рядом?');
  add('Идёт дождь — что поменять?'); add('Сколько это в тенге: ¥3 500?'); add('Как сказать «без свинины»?');
  return out;
}
const EXAMPLES = ['Что у меня сегодня?', 'Идёт дождь — что поменять?', 'Как сказать «без свинины»?', 'Сколько это в тенге: ¥3 500?'];
ICONS.person = '<circle cx="12" cy="8" r="4"/><path d="M4 21c1.5-4 4.5-6 8-6s6.5 2 8 6"/>';
function chatHeadHTML() {
  const x = ctx(), d = x.day, p = askProfile() || {}, who = String(p.name || (Api.me() || {}).name || '').split(/\s+/)[0];
  return `<div class="as-head"><span class="as-orb" aria-hidden="true">${icon('spark')}</span>
    <span class="as-ttl"><b>Спутник</b><small>${esc(who ? who + ' · ' : '')}день ${d.n} · ${esc(d.city || d.label || '')}</small></span>
    <button type="button" class="as-hb" id="asToTr" aria-label="Переводчик">${icon('translate')}</button>
    <button type="button" class="as-hb" id="asToProf" aria-label="Профиль">${icon('person')}</button>
    ${typeof openSos === 'function' ? '<button type="button" class="as-hb as-sosb" data-sos aria-label="SOS">SOS</button>' : ''}</div>`;
}
/* anyone: a request to improve or fix the app — goes to the hosts' queue (app_requests), then to Claude Code as a task */
function requestHTML() {
  return `<p class="tc-sub">Что поменять или починить в приложении? Опишите своими словами — хозяева передадут это разработке отдельной задачей.</p>
    <label class="tc-f" for="asReqText"><span>Ваша просьба</span><textarea id="asReqText" rows="4" maxlength="500" placeholder="Например: кнопка «Пешком» не видна в тёмной теме"></textarea></label>
    <div class="tc-actions two"><button type="button" class="tc-btn primary" id="asReqGo">Отправить</button><button type="button" class="tc-btn" id="asReqBack">Назад к чату</button></div>
    <p class="as-note" id="asReqMsg" role="status"></p>`;
}
function wireRequest(m) {
  m.querySelector('#asReqBack').addEventListener('click', () => { ASK.view = 'chat'; askRender(); });
  m.querySelector('#asReqGo').addEventListener('click', () => {
    const t = m.querySelector('#asReqText').value.trim(), msg = m.querySelector('#asReqMsg');
    if (t.length < 3) { msg.textContent = 'Напишите, что поменять.'; return; }
    Api.call('file_request', { p_body: t.slice(0, 500), p_source: 'user' }, null);
    m.querySelector('#asReqText').value = ''; msg.textContent = 'Отправлено — спасибо! Уйдёт, как только будет интернет.';
  });
}
/* hosts: what people ask (last 7 days) — the hot questions and the tokens, read from ai_journal */
function journalHTML() {
  const J = ASK.journal;
  if (!J) return '<p class="tc-sub" id="asJ">Загружаю…</p><button type="button" class="tc-btn" id="asJBack">Назад к чату</button>';
  if (J.error) return `<p class="as-note bad">${esc(J.error)}</p><button type="button" class="tc-btn" id="asJBack">Назад к чату</button>`;
  const rows = J.rows || [], by = {}, words = {};
  let tin = 0, tout = 0;
  rows.forEach(r => { by[r.who] = (by[r.who] || 0) + 1; tin += +r.in || 0; tout += +r.out || 0;
    String(r.q || '').toLowerCase().replace(/[^a-zа-яё0-9\s]/gi, ' ').split(/\s+/).filter(w => w.length > 4).forEach(w => { words[w] = (words[w] || 0) + 1; }); });
  const top = Object.entries(words).sort((a, b) => b[1] - a[1]).slice(0, 10);
  return `<div class="tc-card"><span class="tc-lbl">За 7 дней</span><b>${rows.length} ${Core.plural(rows.length, 'вопрос', 'вопроса', 'вопросов')} · объём ${tin.toLocaleString('ru-RU')} → ${tout.toLocaleString('ru-RU')}</b>
      <span class="tc-sub">${Object.entries(by).map(([k, v]) => `${esc(k)} — ${v}`).join(' · ') || 'пока пусто'}</span>
      ${top.length ? `<span class="tc-sub">Частые слова: ${top.map(([w, n]) => `${esc(w)} (${n})`).join(', ')}</span>` : ''}</div>
    <div class="tc-group">${rows.slice(0, 100).map(r => `<div class="tc-act"><span>${esc(r.q || '—')}<small>${esc(r.who || '')} · ${esc(japan(r.at))}${r.ok ? '' : ' · ошибка'}</small></span></div>`).join('')}</div>
    <span class="tc-sech">Заявки на улучшение · ${(n => n + ' ' + Core.plural(n, 'новая', 'новые', 'новых'))((J.reqs || []).filter(r => r.status === 'new').length)}</span>
    <div class="tc-group">${(J.reqs || []).slice(0, 60).map(r => `<div class="tc-act"><span>${esc(r.body)}<small>${esc(r.who || '')} · ${esc(japan(r.at))} · ${r.source === 'assistant' ? 'через Спутника' : 'сам'} · ${esc({ new: 'новая', queued: 'передана', done: 'сделано', dropped: 'отклонена' }[r.status] || r.status)}</small></span></div>`).join('') || '<p class="tc-sub" style="padding:12px 16px">Пока заявок нет.</p>'}</div>
    ${(J.reqs || []).some(r => r.status === 'new') ? '<button type="button" class="tc-btn primary" id="asJCopy">Скопировать новые для Claude Code</button>' : ''}
    <p class="as-note" id="asJMsg" role="status"></p>
    <button type="button" class="tc-btn" id="asJBack">Назад к чату</button>`;
}
function wireJournal(m) {
  m.querySelector('#asJBack').addEventListener('click', () => { ASK.view = 'chat'; askRender(); });
  const cp = m.querySelector('#asJCopy');
  if (cp) cp.addEventListener('click', () => {
    const news = (ASK.journal.reqs || []).filter(r => r.status === 'new');
    const txt = 'Заявки на улучшение приложения (из Спутника), оформи каждую отдельной задачей:\n' + news.map(r => `- [#${r.id}] ${r.who}: ${r.body}`).join('\n');
    const mark = () => news.forEach(r => { Api.call('set_request_status', { p_id: r.id, p_status: 'queued' }, null); r.status = 'queued'; });
    (navigator.clipboard ? navigator.clipboard.writeText(txt) : Promise.reject()).then(() => {
      mark(); m.querySelector('#asJMsg').textContent = `Скопировано: ${news.length}. Вставьте в Claude Code — заявки отмечены «передана».`;
    }, () => {                                                   // no clipboard here: show the text to copy by hand
      mark(); const ta = document.createElement('textarea'); ta.className = 'as-jtxt'; ta.rows = 6; ta.readOnly = true; ta.value = txt;
      cp.replaceWith(ta); ta.focus(); ta.select();
      m.querySelector('#asJMsg').textContent = 'Выделите текст и скопируйте вручную — заявки отмечены «передана».';
    });
  });
  if (ASK.journal) return;
  Promise.all([Api.run('ai_journal', { p_days: 7 }), Api.run('app_requests_list', {}).catch(() => [])])
    .then(([r, q]) => { ASK.journal = { rows: Array.isArray(r) ? r : [], reqs: Array.isArray(q) ? q : [] }; if (ASK.view === 'journal') askRender(); })
    .catch(e => { ASK.journal = { error: 'Журнал недоступен' + (e && e.status ? ` (${e.status})` : '') + ' — выполните обновлённую миграцию в Supabase.' }; if (ASK.view === 'journal') askRender(); });
}
function chatHTML() {
  return `${chatHeadHTML()}
    <div id="asRate">${rateHTML()}</div>
    <div class="as-log" id="asLog" role="log" aria-live="polite">${logHTML()}</div>
    <div class="as-pics" id="asPics">${picsHTML()}</div>
    <div class="as-dock">
      <button type="button" class="as-newpill" id="asNew" hidden>Новый ответ ↓</button>
      <div class="as-ex" id="asEx">${askSuggest().slice(0, 4).map(x => `<button type="button" class="as-chip" data-ex="${esc(x)}">${esc(x)}</button>`).join('')}</div>
      <form class="as-form" id="asForm">
        <div class="as-field">
          ${!askPhotos() ? '' : `<label class="as-ib" aria-label="Фото: меню, вывеска, билет">${icon('cam')}<input type="file" id="asPhoto" accept="image/*" hidden></label>`}
          <textarea id="asText" rows="1" maxlength="2000" placeholder="Спросите Спутника…" aria-label="Вопрос ассистенту"></textarea>
          <button type="button" class="as-ib" id="asMic" aria-label="Сказать голосом">${icon('mic')}</button>
        </div>
        <button type="submit" class="as-ib as-send" id="asSend" aria-label="Отправить"${ASK.busy ? ' disabled' : ''}>${icon('send')}</button>
      </form>
    </div>`;
}
const picsHTML = () => ASK.pics.map((p, i) => `<span class="as-pic"><img src="${p.thumb}" alt="Фото ${i + 1}"><button type="button" class="tc-x" data-unpic="${i}" aria-label="Убрать фото">${icon('close')}</button></span>`).join('');
function logHTML() {
  if (!ASK.turns.length) { const h = new Date(Date.now() + 9 * 3600e3).getUTCHours(), p = askProfile() || {};
    const hi = h < 5 ? 'Доброй ночи' : h < 12 ? 'Доброе утро' : h < 18 ? 'Добрый день' : 'Добрый вечер', who = String(p.name || (Api.me() || {}).name || '').split(/\s+/)[0];
    return `<div class="as-hello"><b>${hi}${who ? ', ' + esc(who) : ''}</b><span class="tc-sub">Спросите про план, места, еду, дорогу или деньги — подскажу и, если нужно, предложу правку плана. Ничего не меняется без «Применить».</span>
      <span class="as-fine">Номера карт, паспорта и коды не пишите. Вопросы сохраняются в журнал — его видят хозяева.</span>
      <button type="button" class="tc-link as-jbtn" id="asReq">Предложить улучшение приложения ›</button>
      ${(Api.me() || {}).role === 'host' ? '<button type="button" class="tc-link as-jbtn" id="asJournal">Журнал вопросов и заявки ›</button>' : ''}</div>`; }
  return '<button type="button" class="tc-link as-clear" id="asClear">Очистить чат</button>' + ASK.turns.map((t, ti) => {
    if (t.role === 'note') return `<p class="as-note${t.bad ? ' bad' : ''}" role="status">${esc(t.text)}${t.retry ? ` <button type="button" class="tc-link as-retry" data-retry="${ti}">Повторить</button>` : ''}</p>`;
    if (t.role === 'user') return `<div class="as-msg me">${(t.thumbs || []).map(s => `<img class="as-thumb" src="${s}" alt="Фото">`).join('')}${t.text ? `<p>${nl(t.text)}</p>` : ''}</div>`;
    return `<div class="as-msg ai"><p>${nl(t.text)}</p><button type="button" class="as-copy" data-copy="${ti}" aria-label="Скопировать ответ">Копировать</button>
      ${(t.cards || []).map((c, ci) => cardHTML(c, ti, ci)).join('')}
      ${t.sos && typeof openSos === 'function' ? '<button type="button" class="tc-btn primary wide as-sos" data-sos>Открыть SOS: номера и страховка</button>' : ''}
      ${(t.actions || []).map(a => actionHTML(a, ti)).join('')}
      ${(t.sources || []).length ? `<p class="as-src">Источники: ${t.sources.map(s => Core.safeUrl(s.url) ? `<a href="${esc(Core.safeUrl(s.url))}" target="_blank" rel="noopener">${esc(s.title || 'ссылка')}</a>` : '').filter(Boolean).join(' · ')}</p>` : ''}</div>`;
  }).join('') + (ASK.busy ? `<p class="as-msg ai as-wait" id="asWait"><span id="asWaitT">${esc(ASK.waitText || 'Думаю…')}</span>${ASK.slow ? ' <button type="button" class="tc-link as-cancel" id="asCancel">Отменить</button>' : ''}</p>` : '');
}
function cardHTML(c, ti, ci) {
  if (c.kind === 'ja') return `<div class="as-card as-ja"><p class="as-ja-t" lang="ja">${esc(c.ja)}</p>${c.reading ? `<p class="tc-sub">${esc(c.reading)}</p>` : ''}<p>${esc(c.meaning)}</p>
    <div class="tc-actions two"><button type="button" class="tc-btn primary" data-jafull="${ti}:${ci}">Показать по-японски</button>
      <button type="button" class="tc-btn" data-jasay="${ti}:${ci}">${icon('speak')}Озвучить</button></div></div>`;
  if (c.kind === 'place') { const u = Core.safeUrl(c.url);
    return `<div class="as-card as-place"><b>${esc(c.name)}</b>${c.note ? `<span class="tc-sub">${esc(c.note)}</span>` : ''}
      ${u ? `<a class="tc-btn" href="${esc(u)}" target="_blank" rel="noopener">${icon('pin')}${c.route ? 'Маршрут в Google Maps' : 'Открыть в Google Maps'}</a>` : ''}</div>`; }
  return '';
}
const dmOf = n => { const d = planDoc().days.find(x => x.n === n); return d ? Core.ddmmyyyy(dateOf(d)).slice(0, 5) : 'день ' + n; };
function actionText(a) {
  if (a.kind === 'move') return [`Перенести «${a.title}» (${dmOf(a.day_n)}): ${a.from_s}${a.from_e ? '–' + a.from_e : ''} → ${a.start}–${a.end}`,
    a.how === 'propose' ? 'станет предложением хозяевам' : a.how === 'plan' ? 'изменит план группы для всех' : 'в вашем плане'];
  if (a.kind === 'skip') return [`Не идти: «${a.title}» (${dmOf(a.day_n)})`, a.scope === 'mine' ? 'пометка «Пропустить», можно вернуть' : '«Без меня» — только для вас'];
  if (a.kind === 'add') { const note = String(a.note || '').trim(), short = note.length > 140 ? note.slice(0, 139) + '…' : note;
    return [`Добавить ${dmOf(a.day_n)} ${a.start}–${a.end}: «${a.title}»${a.place ? ' · ' + a.place : ''}${short ? ' — ' + short : ''}${a.lat != null ? ' · с точкой на карте' : ''}`,
      a.scope === 'mine' ? 'в ваш план' : a.how === 'propose' ? 'предложение хозяевам в план группы' : 'в план группы для всех']; }
  if (a.kind === 'request') return [`Передать разработчикам: «${a.text}»`, 'в очередь улучшений приложения — хозяева увидят'];
  if (a.kind === 'task') return [`${a.done ? 'Отметить сделанным' : 'Вернуть в несделанные'}: «${a.title}»`, 'в «Делах», только у вас'];
  if (a.kind === 'edit') { const c = a.changes || {}, parts = [];
    if (c.t) parts.push(`название → «${c.t}»`); if (c.pname) parts.push(`место → ${c.pname}`); if (c.note) parts.push(`заметка → ${c.note.length > 120 ? c.note.slice(0, 119) + '…' : c.note}`);
    return [`Изменить «${a.title}» (${dmOf(a.day_n)}): ${parts.join('; ')}`,
      a.how === 'propose' ? 'станет предложением хозяевам' : a.how === 'plan' ? 'изменит план группы для всех' : 'в вашем плане']; }
  if (a.kind === 'expense') { const c = Exp.cat(a.category);
    return [`Расход: ${Exp.fmt(a.amount, a.currency)} · ${c.icon} ${c.name}${a.title ? ' · ' + a.title : ''}`, 'откроется окно расхода — проверите и сохраните']; }
  return ['Неизвестное действие', ''];
}
function actionHTML(a, ti) {
  const [what, how] = actionText(a), key = `${ti}:${a.id}`;
  const state = a.status === 'applied' ? '<p class="as-done">Применено</p>' : a.status === 'dismissed' ? '<p class="as-done">Не надо</p>'
    : a.status === 'failed' ? `<p class="as-done bad">${esc(a.error || 'Не получилось')}</p>`
    : `<div class="tc-actions two"><button type="button" class="tc-btn primary" data-apply="${esc(key)}">Применить</button><button type="button" class="tc-btn" data-dismiss="${esc(key)}">Не надо</button></div>`;
  return `<div class="as-card as-act" data-act="${esc(key)}"><b>${esc(what)}</b>${how ? `<span class="tc-sub">${esc(how)}</span>` : ''}${a.reason ? `<span class="tc-sub">${esc(a.reason)}</span>` : ''}${state}</div>`;
}
function askLogRefresh() {
  const log = document.getElementById('asLog'); if (!log) return;
  const near = ASK.atBottom !== false || log.scrollHeight - log.scrollTop - log.clientHeight < 80;
  const keep = log.scrollTop;
  log.innerHTML = logHTML();
  const s = document.getElementById('asSend'); if (s) s.disabled = ASK.busy;
  const pill = document.getElementById('asNew');
  if (near) { log.scrollTop = log.scrollHeight; ASK.atBottom = false; if (pill) pill.hidden = true; }
  else { log.scrollTop = keep; if (pill) pill.hidden = false; }
}
/* suggestions refresh after every answer and hide while typing */
function askChips() { const ex = document.getElementById('asEx'); if (!ex) return;
  ex.innerHTML = askSuggest().slice(0, 4).map(x => `<button type="button" class="as-chip" data-ex="${esc(x)}">${esc(x)}</button>`).join(''); }
function wireChat(m) {
  wireRate(m);
  const ta = m.querySelector('#asText'), form = m.querySelector('#asForm');
  m.querySelector('#asToTr').addEventListener('click', () => { ASK.view = 'translate'; askRender(); });
  m.querySelector('#asToProf').addEventListener('click', () => { ASK.view = 'profile'; askRender(); });
  m.querySelector('#asWrap').addEventListener('click', e => { if (e.target.closest('[data-sos]') && typeof openSos === 'function') { closeSheet(); openSos(); } });
  form.addEventListener('submit', e => { e.preventDefault(); askSend(ta.value); });
  const desk = typeof matchMedia === 'function' && matchMedia('(hover: hover) and (pointer: fine)').matches;   // phones: Enter = new line
  ta.addEventListener('keydown', e => { if (desk && e.key === 'Enter' && !e.shiftKey && !e.isComposing) { e.preventDefault(); askSend(ta.value); } });
  const grow = () => { ta.style.height = 'auto'; ta.style.height = Math.min(140, ta.scrollHeight) + 'px'; m.querySelector('#asEx').hidden = !!ta.value.trim(); };
  ta.addEventListener('input', grow);
  const log0 = m.querySelector('#asLog'), pill = m.querySelector('#asNew');
  log0.addEventListener('scroll', () => { if (log0.scrollHeight - log0.scrollTop - log0.clientHeight < 40) pill.hidden = true; }, { passive: true });
  pill.addEventListener('click', () => { log0.scrollTop = log0.scrollHeight; pill.hidden = true; });
  const jb = m.querySelector('#asJournal'); if (jb) jb.addEventListener('click', () => { ASK.view = 'journal'; ASK.journal = null; askRender(); });
  const rq = m.querySelector('#asReq'); if (rq) rq.addEventListener('click', () => { ASK.view = 'request'; askRender(); });
  m.querySelector('#asEx').addEventListener('click', e => { const ex = e.target.closest('[data-ex]'); if (ex) askSend(ex.dataset.ex); });
  m.querySelector('#asLog').addEventListener('click', e => {
    if (e.target.closest('#asCancel')) { ASK.req++; ASK.busy = false; ASK.slow = false; ASK.turns.push({ role: 'note', text: 'Отменено.' }); askSaveChat(); askLogRefresh(); return; }
    const rt = e.target.closest('[data-retry]');
    if (rt) { const n = ASK.turns[+rt.dataset.retry]; if (n && n.retry) { const q = n.retry; ASK.turns.splice(+rt.dataset.retry - 1, 2); askSend(q); } return; }
    const cpb = e.target.closest('[data-copy]');
    if (cpb) { const t = ASK.turns[+cpb.dataset.copy]; if (t) (navigator.clipboard ? navigator.clipboard.writeText(t.text) : Promise.reject())
      .then(() => { cpb.textContent = 'Скопировано'; }, () => { cpb.textContent = 'Не вышло'; }); return; }
    if (e.target.closest('#asClear')) { if (!ASK.clearArmed) { ASK.clearArmed = true; e.target.textContent = 'Точно очистить?'; return; }
      ASK.clearArmed = false; ASK.turns = []; askSaveChat(); askLogRefresh(); return; }
    const ap = e.target.closest('[data-apply]'), dm = e.target.closest('[data-dismiss]');
    if (ap || dm) { const [ti, id] = (ap || dm).dataset[ap ? 'apply' : 'dismiss'].split(':'); const t = ASK.turns[+ti], a = t && (t.actions || []).find(x => x.id === id);
      if (a && !a.status) { if (ap) askApply(a); else { a.status = 'dismissed'; askLogRefresh(); } } return; }
    const jf = e.target.closest('[data-jafull]'), js = e.target.closest('[data-jasay]');
    if (jf || js) { const [ti, ci] = (jf || js).dataset[jf ? 'jafull' : 'jasay'].split(':').map(Number); const c = ((ASK.turns[ti] || {}).cards || [])[ci];
      if (c) { if (jf) askShowJa(c); else askSpeak(c.ja, 'ja'); } }
  });
  const ph = m.querySelector('#asPhoto'); if (ph) ph.addEventListener('change', e => { const f = e.target.files && e.target.files[0]; e.target.value = ''; if (f) askAddPhoto(f); });
  m.querySelector('#asPics').addEventListener('click', e => { const b = e.target.closest('[data-unpic]'); if (b) { ASK.pics.splice(+b.dataset.unpic, 1); m.querySelector('#asPics').innerHTML = picsHTML(); } });
  m.querySelector('#asMic').addEventListener('click', () => askListen(myLang(), txt => { ta.value = (ta.value ? ta.value + ' ' : '') + txt; ta.focus(); }));
  const log = m.querySelector('#asLog'); log.scrollTop = log.scrollHeight;
}

/* photos: shrunk on the phone to ≤1568 px (what the model uses anyway), JPEG */
function askAddPhoto(file) {
  if (ASK.pics.length >= 2) { askNote('Не больше двух фото за раз.', true); return; }
  const url = URL.createObjectURL(file), img = new Image();
  img.onload = () => {
    const k = Math.min(1, 1568 / Math.max(img.naturalWidth, img.naturalHeight)), w = Math.max(1, Math.round(img.naturalWidth * k)), h = Math.max(1, Math.round(img.naturalHeight * k));
    const c = document.createElement('canvas'); c.width = w; c.height = h; c.getContext('2d').drawImage(img, 0, 0, w, h);
    const data = c.toDataURL('image/jpeg', 0.82).split(',')[1];
    const t = document.createElement('canvas'), tk = 120 / Math.max(w, h); t.width = Math.round(w * tk); t.height = Math.round(h * tk);
    t.getContext('2d').drawImage(c, 0, 0, t.width, t.height);
    URL.revokeObjectURL(url);
    ASK.pics.push({ media_type: 'image/jpeg', data, w, h, thumb: t.toDataURL('image/jpeg', 0.7) });
    const p = document.getElementById('asPics'); if (p) p.innerHTML = picsHTML();
  };
  img.onerror = () => { URL.revokeObjectURL(url); askNote('Не получилось открыть фото.', true); };
  img.src = url;
}

/* why the assistant didn't answer: the function's own words when it answered, else what the Supabase gateway said */
function askErrorText(e) {
  const b = (e && e.body) || {}, st = e && e.status;
  if (!st) return 'Нет связи с ассистентом — проверьте интернет и повторите.';
  if (typeof b.error === 'string' && b.error) return b.error;
  const said = String(b.message || b.msg || b.code || '').slice(0, 140);
  if (st === 403) return 'Ассистент — только для участников группы. Войдите заново в ⚙.';
  if (st === 404) return 'Функция assistant не найдена (404): в Supabase она должна называться ровно «assistant».';
  if (st === 401) return 'Supabase не принял вход (401' + (said ? ': ' + said : '') + '). Войдите заново в ⚙; если не помогло — у функции включите или выключите Verify JWT, см. инструкцию.';
  if (st === 546 || /WORKER|BOOT/i.test(said)) return 'Функция assistant не запустилась (' + st + (said ? ': ' + said : '') + '). Вставьте one_file.ts заново и нажмите Deploy; подробности — Edge Functions → assistant → Logs.';
  return 'Ассистент не ответил (код ' + st + (said ? ': ' + said : '') + '). Подробности — Supabase → Edge Functions → assistant → Logs.';
}
function askNote(text, bad) { ASK.turns.push({ role: 'note', text, bad: !!bad }); askLogRefresh(); }
const askHistory = () => ASK.turns.filter(t => t.role === 'user' || t.role === 'assistant').slice(-20)
  .map((t, i, xs) => ({ role: t.role, text: t.text || '', ...(i === xs.length - 1 && t.images ? { images: t.images } : {}) }));
async function askSend(text0) {
  const text = String(text0 || '').trim().slice(0, 2000);
  if (ASK.busy || (!text && !ASK.pics.length)) return;
  if (!navigator.onLine) { askNote('Нужен интернет — ассистент работает только онлайн. Расписание и билеты в приложении доступны и без сети.', true); return; }
  const pics = ASK.pics.splice(0);
  const turn = { role: 'user', text, thumbs: pics.map(p => p.thumb), images: pics.length ? pics.map(p => ({ media_type: p.media_type, data: p.data })) : null };
  ASK.turns.push(turn); ASK.busy = true; ASK.slow = false; ASK.waitText = 'Думаю…'; ASK.atBottom = true;
  const id = ++ASK.req;                       // a newer request or «Отменить» makes this one's answer stale
  const stage = (ms, t, slow) => setTimeout(() => { if (ASK.req !== id || !ASK.busy) return; ASK.waitText = t; if (slow) ASK.slow = true;
    const w = document.getElementById('asWaitT'); if (w && !slow) w.textContent = t; else askLogRefresh(); }, ms);
  const timers = [stage(4000, 'Смотрю план и карту…'), stage(10000, 'Почти готово…', true), stage(25000, 'Долго отвечает — можно отменить и спросить короче.', true)];
  const ta = document.getElementById('asText'); if (ta) { ta.value = ''; ta.style.height = ''; }
  const exs = document.getElementById('asEx'); if (exs) exs.hidden = false;
  const pp = document.getElementById('asPics'); if (pp) pp.innerHTML = '';
  askLogRefresh();
  try {
    const r = await Api.invoke(askFn(), { trip: T.id, view_day: viewDay, messages: askHistory(), profile: askProfile(), rates: askRates() }, 60000);
    if (ASK.req !== id) return;
    ASK.turns.push({ role: 'assistant', text: String((r && r.reply) || 'Нет ответа.'), actions: Array.isArray(r && r.actions) ? r.actions.slice(0, 6) : [],
      cards: Array.isArray(r && r.cards) ? r.cards.slice(0, 6) : [], sources: Array.isArray(r && r.sources) ? r.sources.slice(0, 4) : [], sos: !!(r && r.sos) });
  } catch (e) {
    if (ASK.req !== id) return;
    ASK.turns.push({ role: 'note', text: askErrorText(e), bad: true, retry: text || null });
  } finally {
    timers.forEach(clearTimeout);
    turn.images = null;                       // photos go once; the thumbnails stay on screen
    if (ASK.req === id) { ASK.busy = false; ASK.slow = false; askSaveChat(); askLogRefresh(); askChips(); }
  }
}

/* ---------- «Применить»: through the app's own paths; the server re-checks everything ---------- */
function askApply(a) {
  try { const say = askDo(a); a.status = 'applied'; askSaveChat(); renderShell(); if (a.kind !== 'expense') { ASK.turns.push({ role: 'note', text: say }); askLogRefresh(); } }
  catch (e) { a.status = 'failed'; a.error = e.message || 'Не получилось'; askLogRefresh(); }
}
function askDo(a) {
  const s = Api.state(), me = Api.me(), HMok = (x, y) => Proposals.HM.test(x || '') && Proposals.HM.test(y || '') && y > x;
  if (!s || !me) throw new Error('Войдите в группу.');
  if (a.kind === 'expense') {
    if (!Exp.CURS.includes(a.currency) || !(+a.amount > 0)) throw new Error('Странная сумма — добавьте расход сами.');
    closeSheet(); openAdd({ amount: +a.amount, currency: a.currency, cat: Exp.CATS.some(c => c.code === a.category) ? a.category : null, title: String(a.title || '').slice(0, 80) });
    ASK.turns.push({ role: 'note', text: 'Открыл расход — проверьте и нажмите «Сохранить».' });
    return '';
  }
  if (a.kind === 'request') {
    const body = String(a.text || '').trim().slice(0, 500);
    if (body.length < 3) throw new Error('Пустая просьба.');
    Api.call('file_request', { p_body: body, p_source: 'assistant' }, null);
    return 'Передал разработчикам — спасибо!';
  }
  if (a.kind === 'task') {
    const ref = String(a.ref || ''), done = a.done === true;
    if (!/^(t|bk):[\w.-]{1,80}$/.test(ref)) throw new Error('Дело не найдено.');
    Api.call('set_task_state', { p_ref: ref, p_done: done }, st => { st.task_state = (st.task_state || []).filter(x => x.ref !== ref).concat([{ ref, done }]); });
    return done ? `Отметил: «${a.title}».` : `Вернул в несделанные: «${a.title}».`;
  }
  const own = a.stop_id ? (s.my_stops || []).find(x => x.id === a.stop_id) : null;
  const G = s.plan, hit = a.stop_id && G ? Proposals.findEv(G.doc, a.stop_id) : null;
  if (a.kind === 'move') {
    if (!HMok(a.start, a.end)) throw new Error('Неверное время.');
    if (own) {
      if (own.member !== me.id) throw new Error('Это чужой пункт — его меняет автор.');
      const next = { id: own.id, day: own.day, ev: { ...own.ev, s: a.start, e: a.end }, shared: !!own.shared };
      Api.call('save_my_stop', { p_stop: next }, st => { st.my_stops = (st.my_stops || []).filter(q => q.id !== next.id).concat([{ ...next, member: me.id }]); });
      return `Перенёс «${own.ev.t}» на ${a.start}–${a.end}.`;
    }
    if (!hit) throw new Error('Пункт не найден — план уже изменился.');
    if (me.role === 'host') {
      const doc = Proposals.apply(G.doc, { kind: 'time', ref: a.stop_id, payload: { s: a.start, e: a.end } }), v = G.version;
      Api.call('save_plan', { p_doc: doc, p_version: v }, st => { st.plan = { doc, version: v + 1 }; });
      return `Перенёс «${hit.e.t}» в плане группы на ${a.start}–${a.end}.`;
    }
    askPropose('time', a.stop_id, hit.d.n, { s: a.start, e: a.end }, a.reason);
    return `Отправил хозяевам предложение: «${hit.e.t}» на ${a.start}–${a.end}. Ответ — в «Делах».`;
  }
  if (a.kind === 'edit') {
    const c = a.changes || {}, ch = {};
    if (typeof c.t === 'string' && c.t.trim()) ch.t = c.t.trim().slice(0, 120);
    if (typeof c.note === 'string' && c.note.trim()) ch.note = c.note.trim().slice(0, 500);
    if (typeof c.pname === 'string' && c.pname.trim()) ch.pname = c.pname.trim().slice(0, 120);
    if (!Object.keys(ch).length) throw new Error('Нечего менять.');
    if (own) {
      if (own.member !== me.id) throw new Error('Это чужой пункт — его меняет автор.');
      const next = { id: own.id, day: own.day, ev: { ...own.ev, ...ch }, shared: !!own.shared };
      Api.call('save_my_stop', { p_stop: next }, st => { st.my_stops = (st.my_stops || []).filter(q => q.id !== next.id).concat([{ ...next, member: me.id }]); });
      return `Изменил «${own.ev.t}».`;
    }
    if (!hit) throw new Error('Пункт не найден — план уже изменился.');
    if (me.role === 'host') {
      const doc = JSON.parse(JSON.stringify(G.doc)), v = G.version;
      const e = (doc.days.find(d => d.n === hit.d.n) || { ev: [] }).ev.find(x => String(x.id) === String(a.stop_id));
      if (!e) throw new Error('Пункт не найден — план уже изменился.');
      Object.assign(e, ch);
      Api.call('save_plan', { p_doc: doc, p_version: v }, st => { st.plan = { doc, version: v + 1 }; });
      return `Изменил «${hit.e.t}» в плане группы.`;
    }
    const say = [ch.t && `название: «${ch.t}»`, ch.pname && `место: ${ch.pname}`, ch.note && `заметка: ${ch.note}`].filter(Boolean).join('; ');
    askPropose('comment', a.stop_id, hit.d.n, {}, (say + (a.reason ? ' — ' + a.reason : '')).slice(0, 500));
    return `Отправил хозяевам предложение изменить «${hit.e.t}». Ответ — в «Делах».`;
  }
  if (a.kind === 'skip') {
    if (own && own.member === me.id) { S.skip[own.id] = true; save(); return `«${own.ev.t}» пропущен — вернуть можно в пункте.`; }
    if (own) { setJoin('mine', own.id, 'out'); return `«${own.ev.t}» — не пойду.`; }
    if (!hit) throw new Error('Пункт не найден — план уже изменился.');
    setJoin('stop', a.stop_id, 'out'); return `«${hit.e.t}» — «Без меня».`;
  }
  if (a.kind === 'add') {
    const n = +a.day_n, title = String(a.title || '').trim().slice(0, 120);
    if (!HMok(a.start, a.end) || !title || !planDoc().days.some(d => d.n === n)) throw new Error('Неполный пункт — добавьте сами.');
    const num = v => typeof v === 'number' && Number.isFinite(v) ? v : null;
    const ev = { t: title, s: a.start, e: a.end, st: 'planned', cat: 'activity', pname: String(a.place || '').slice(0, 120), lat: num(a.lat), lng: num(a.lng),
                 walk: 0, ride: 0, buf: 0, note: String(a.note || '').slice(0, 500) };
    if (a.scope !== 'group') {
      const stop = { id: 'm-' + (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36)), day: n, ev, shared: typeof shareAllOn === 'function' ? shareAllOn() : false };
      Api.call('save_my_stop', { p_stop: stop }, st => { st.my_stops = (st.my_stops || []).concat([{ ...stop, member: me.id }]); });
      return `Добавил в ваш план: ${dmOf(n)} ${a.start} «${title}».`;
    }
    if (me.role === 'host') {
      const doc = JSON.parse(JSON.stringify(G.doc)), d = doc.days.find(x => x.n === n), v = G.version;
      d.ev.push({ id: 'u' + Date.now().toString(36), ...ev }); d.ev.sort((x, y) => (toMin(x.s) || 0) - (toMin(y.s) || 0));
      Api.call('save_plan', { p_doc: doc, p_version: v }, st => { st.plan = { doc, version: v + 1 }; });
      return `Добавил в план группы: ${dmOf(n)} ${a.start} «${title}».`;
    }
    askPropose('add', null, n, { s: a.start, e: a.end, t: title }, ev.note);
    return `Отправил хозяевам предложение добавить «${title}». Ответ — в «Делах».`;
  }
  throw new Error('Неизвестное действие.');
}
function askPropose(kind, ref, day, payload, note) {
  const me = Api.me().id, tmp = 'tmp-' + Date.now().toString(36), n = String(note || '').slice(0, 500);
  Api.call('propose', { p_kind: kind, p_ref: ref, p_day: day, p_payload: payload, p_note: n }, s => {
    s.proposals = [{ id: tmp, member: me, kind, ref, day, payload, note: n, status: 'open' }].concat(s.proposals || []);
  });
}

/* ---------- voice: dictation, speech, the Japanese card ---------- */
const DICTATE = 'Нажмите 🎤 на клавиатуре iPhone и говорите — текст появится в поле.';
const canListen = () => !!(window.SpeechRecognition || window.webkitSpeechRecognition) && !(typeof Ios !== 'undefined' && Ios.standalone());
function askListen(lang, done, fallback) {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  const hint = () => { if (fallback) fallback(); else { askNote(DICTATE); const t = document.getElementById('asText'); if (t) t.focus(); } };
  if (!canListen()) { hint(); return; }
  try { if (ASK.rec) ASK.rec.abort(); } catch (e) {}
  const r = new SR(); ASK.rec = r;
  r.lang = LANG_SR[lang] || 'ru-RU'; r.interimResults = false; r.maxAlternatives = 1;
  document.querySelectorAll('[data-listening]').forEach(b => b.removeAttribute('data-listening'));
  r.onresult = e => { const t = Array.from(e.results).map(x => x[0].transcript).join(' ').trim(); if (t) done(t); };
  r.onerror = () => hint();
  r.onend = () => { if (ASK.rec === r) ASK.rec = null; };
  try { r.start(); } catch (e) { hint(); }
}
function askSpeak(text, lang) {
  if (!('speechSynthesis' in window) || !text) return false;
  try {
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text), L = LANG_SR[lang] || 'ja-JP';
    u.lang = L; u.rate = lang === 'ja' ? 0.9 : 1;
    const v = (speechSynthesis.getVoices ? speechSynthesis.getVoices() : []).find(x => String(x.lang || '').replace('_', '-').toLowerCase().startsWith(L.slice(0, 2).toLowerCase()));
    if (v) u.voice = v;                        // a Japanese voice when the phone lists one; otherwise the lang is enough
    speechSynthesis.speak(u); return true;
  }
  catch (e) { return false; }
}
function askShowJa(c) {
  let m = document.getElementById('asLocal');
  if (!m) { m = document.createElement('div'); m.id = 'asLocal'; m.className = 'tc-local'; document.body.appendChild(m); }
  m.setAttribute('role', 'dialog'); m.setAttribute('aria-modal', 'true'); m.setAttribute('aria-label', c.meaning || 'По-японски');
  m.innerHTML = `<p class="tc-local-name" lang="ja">${esc(c.ja)}</p>${c.reading ? `<p class="tc-local-ru">${esc(c.reading)}</p>` : ''}<p class="tc-local-ru">${esc(c.meaning || '')}</p>
    <div class="tc-local-acts"><button type="button" class="tc-btn" id="asLocalSay">${icon('speak')}Озвучить</button><button type="button" class="tc-btn primary" id="asLocalClose">Закрыть</button></div>`;
  m.hidden = false; Ios.keepAwake(true);
  const close = () => { m.hidden = true; Ios.keepAwake(false); };
  m.querySelector('#asLocalClose').addEventListener('click', close);
  m.querySelector('#asLocalSay').addEventListener('click', ev => { ev.stopPropagation(); askSpeak(c.ja, 'ja'); });
  m.onclick = ev => { if (!ev.target.closest('button')) close(); };
  m.querySelector('#asLocalClose').focus();
}

/* ---------- the voice translator: I speak → Japanese out loud; the Japanese speaker answers → my language ---------- */
const TR_NAME = { ru: 'Русский', kk: 'Қазақша', en: 'English' };
function translateHTML() {
  const l = myLang();
  return `<p class="tc-sub">Скажите или напишите фразу (🎤 на клавиатуре) — переведу и озвучу по-японски. Потом дайте телефон собеседнику: вторая кнопка — для него.</p>
    <button type="button" class="tc-btn primary wide" id="trMe">${icon('mic')}Я говорю · ${esc(TR_NAME[l] || 'Русский')}</button>
    <button type="button" class="tc-btn wide" id="trThem" lang="ja">${icon('mic')}日本語で話してください</button>
    <div class="as-form"><textarea id="trText" rows="2" maxlength="500" placeholder="Или напишите фразу" aria-label="Фраза для перевода"></textarea>
      <button type="button" class="as-ib as-send" id="trGo" aria-label="Перевести на японский">${icon('send')}</button></div>
    <div id="trOut" class="as-trout" aria-live="polite"></div>
    <button type="button" class="tc-btn" id="trBack">Назад к чату</button>`;
}
function wireTranslate(m) {
  const out = m.querySelector('#trOut'), my = myLang();
  const run = async (text, from, to) => {
    text = String(text || '').trim(); if (!text) return;
    if (!navigator.onLine) { out.innerHTML = '<p class="as-note bad">Нужен интернет для перевода.</p>'; return; }
    out.innerHTML = `<p class="as-msg me">${esc(text)}</p><p class="as-msg ai as-wait">Перевожу…</p>`;
    try {
      const r = await Api.invoke(askFn(), { trip: T.id, mode: 'translate', text, from, to }, 30000);
      const t = r && typeof r.text === 'string' ? r.text : '';
      if (!t) throw Object.assign(new Error('x'), { status: 200 });
      const card = { ja: to === 'ja' ? t : text, meaning: to === 'ja' ? text : t };
      out.innerHTML = `<p class="as-msg me">${esc(text)}</p><div class="as-card as-ja"><p class="${to === 'ja' ? 'as-ja-t' : 'as-tr-t'}"${to === 'ja' ? ' lang="ja"' : ''}>${esc(t)}</p>
        <div class="tc-actions two"><button type="button" class="tc-btn" data-trsay>${icon('speak')}Ещё раз</button>${to === 'ja' ? '<button type="button" class="tc-btn primary" data-trfull>На весь экран</button>' : ''}</div></div>`;
      out.querySelector('[data-trsay]').addEventListener('click', () => askSpeak(t, to));
      const f = out.querySelector('[data-trfull]'); if (f) f.addEventListener('click', () => askShowJa(card));
      askSpeak(t, to);
    } catch (e) { out.innerHTML = `<p class="as-note bad">${!e.status ? 'Нет связи — повторите.' : 'Не получилось перевести — попробуйте сказать иначе.'}</p>`; }
  };
  const ta = m.querySelector('#trText'), dir = d => { ASK.trDir = d; ta.lang = d === 'ja' ? 'ja' : '';
    ta.placeholder = d === 'ja' ? '日本語で入力してください（キーボードの🎤）' : 'Или напишите фразу (🎤 на клавиатуре)'; };
  dir(ASK.trDir || 'me');
  const typed = d => () => { dir(d); out.innerHTML = `<p class="as-note">${d === 'ja' ? '🌐で日本語キーボードに切り替えて、🎤を押して話してください。' : esc(DICTATE)}</p>`; ta.focus(); };
  m.querySelector('#trMe').addEventListener('click', () => { dir('me'); askListen(my, t => run(t, my, 'ja'), typed('me')); });
  m.querySelector('#trThem').addEventListener('click', () => { dir('ja'); askListen('ja', t => run(t, 'ja', my), typed('ja')); });
  m.querySelector('#trGo').addEventListener('click', () => ASK.trDir === 'ja' ? run(ta.value, 'ja', my) : run(ta.value, my, 'ja'));
  m.querySelector('#trBack').addEventListener('click', () => { ASK.view = 'chat'; askRender(); });
}

/* ---------- profile on the server (for the scheduled messages), ratings, the assistant's messages ---------- */
const ASK_FB = 'japan2026.assistant.fb.v1';
const RATE_CATS = ['activity', 'food', 'event'];
ASK.ai = (() => { try { return JSON.parse(localStorage.getItem(ASK_FB) || 'null') || { fb: {}, inbox: [] }; } catch (e) { return { fb: {}, inbox: [] }; } })();
const putAi = () => { try { localStorage.setItem(ASK_FB, JSON.stringify(ASK.ai)); } catch (e) {} };
/* P1 (scheduled messages, ratings) waits for the owner's design approval: off unless this phone turns it on */
const askP1 = () => { try { return localStorage.getItem('japan2026.assistant.p1') !== '0'; } catch (e) { return true; } };   // on since 14.10; '0' turns it off on a phone
function askSyncProfile() {
  if (!askP1()) return;
  const p = askProfile(), me = Api.me && Api.me();
  if (!p || p.skipped || !me || p.synced === me.id + ':' + p.at) return;
  const { name, lang, tone, energy, interests, food, notes, notify } = p;
  Api.call('save_ai_profile', { p_p: { name: name || '', lang: lang || 'ru', tone: tone || 'calm', energy: energy || 'mid', interests: interests || '', food: food || '', notes: notes || '', notify: notify || {} } }, null);
  putProfile({ ...p, synced: me.id + ':' + p.at });
}
let aiLoading = null;
function askLoadAi() {
  if (!askP1() || aiLoading || !navigator.onLine || !Api.me()) return;
  aiLoading = Api.run('my_ai', {}).then(r => {
    if (!r) return;
    const fb = {}; (r.feedback || []).forEach(f => { fb[f.ref] = f.stars; });
    ASK.ai = { fb: { ...ASK.ai.fb, ...fb }, inbox: Array.isArray(r.inbox) ? r.inbox.slice(0, 20) : [] }; putAi();
    const box = document.getElementById('asRate'); if (box) { box.innerHTML = rateHTML(); }
  }).catch(() => {}).finally(() => { aiLoading = null; });
}
/* what to rate now: today's places that have ended (my own plan), and after 21:00 the day; a link (#rate=…) adds its own */
function askPending() {
  if (!askOn() || !askP1()) return [];
  let x; try { x = ctx(); } catch (e) { return []; }
  if (!x.c.live && !ASK.focus) return [];
  const out = [], fb = ASK.ai.fb || {};
  if (x.c.live) {
    x.cevs.filter(e => RATE_CATS.includes(e.cat) && !e.skip && !e.auto && !e.bad && e.ne <= x.c.min && !fb[e.id]).slice(-3)
      .forEach(e => out.push({ ref: String(e.id), kind: 'place', day: x.cday.n, title: e.t }));
    if (x.c.min >= 21 * 60 && !fb['day:' + x.cday.n]) out.push({ ref: 'day:' + x.cday.n, kind: 'day', day: x.cday.n, title: x.cday.label || 'день' });
  }
  const f = ASK.focus;
  if (f && !fb[f] && !out.some(o => o.ref === f)) {
    const m = /^day:(\d+)$/.exec(f), V = TV();
    if (m) { const d = V.days.find(z => z.n === +m[1]); if (d) out.unshift({ ref: f, kind: 'day', day: d.n, title: d.label || 'день' }); }
    else for (const d of V.days) { const e = d.ev.find(z => String(z.id) === f); if (e) { out.unshift({ ref: f, kind: 'place', day: d.n, title: e.t }); break; } }
  }
  return out;
}
const INBOX_LBL = { morning: 'Утро', evening: 'Вечер', place: 'После места' };
function rateHTML() {
  if (!askP1()) return '';
  const today = japanNow().date, inbox = (ASK.ai.inbox || []).filter(m => String(m.day) === today && m.kind !== 'place').slice(0, 2);
  const items = askPending();
  return inbox.map(m => `<div class="as-msg ai as-inbox"><small class="tc-sub">${esc(INBOX_LBL[m.kind] || 'Ассистент')}</small><b>${esc(m.title || '')}</b><p>${nl(m.body || '')}</p></div>`).join('')
    + items.map(it => `<div class="as-card as-rate" data-rate="${esc(it.ref)}" data-kind="${it.kind}" data-day="${it.day}">
      <b>${it.kind === 'day' ? 'Как прошёл день: ' + esc(it.title) + '?' : 'Как вам «' + esc(it.title) + '»?'}</b>
      <div class="as-stars" role="radiogroup" aria-label="Оценка">${[1, 2, 3, 4, 5].map(n => `<button type="button" role="radio" aria-checked="false" data-star="${n}" aria-label="${n} из 5">★</button>`).join('')}</div>
      <input type="text" maxlength="${it.kind === 'day' ? 300 : 120}" placeholder="${it.kind === 'day' ? 'Пара слов о дне (по желанию)' : 'Одной строкой (по желанию)'}" aria-label="Комментарий">
      <button type="button" class="tc-btn primary" data-rate-save disabled>Сохранить</button></div>`).join('');
}
function wireRate(m) {
  const box = m.querySelector('#asRate'); if (!box) return;
  box.addEventListener('click', e => {
    const st = e.target.closest('[data-star]'), card = e.target.closest('[data-rate]'); if (!card) return;
    if (st) { const n = +st.dataset.star; card.dataset.stars = n;
      card.querySelectorAll('[data-star]').forEach(b => { b.setAttribute('aria-checked', String(+b.dataset.star === n)); b.classList.toggle('on', +b.dataset.star <= n); });
      card.querySelector('[data-rate-save]').disabled = false; return; }
    if (e.target.closest('[data-rate-save]') && card.dataset.stars) {
      const ref = card.dataset.rate, stars = +card.dataset.stars, comment = card.querySelector('input').value.trim();
      Api.call('save_feedback', { p_ref: ref, p_kind: card.dataset.kind, p_stars: stars, p_comment: comment, p_day: +card.dataset.day || null }, null);
      ASK.ai.fb = { ...(ASK.ai.fb || {}), [ref]: stars }; putAi();
      if (ASK.focus === ref) ASK.focus = null;
      box.innerHTML = rateHTML(); askNote('Спасибо! Оценка сохранена — её видите только вы, группе видно лишь среднее.');
      renderShell();
    }
  });
}
/* a push opens the app: #briefing (morning, evening) or #rate=<stop id> / #rate=day:<n>; called from handleDeepLink */
function askDeepLink(hash) {
  const m = /^#(?:rate=([A-Za-z0-9:_-]{1,80})|briefing)$/.exec(hash || '');
  if (!m) return false;
  try { history.replaceState(null, '', location.pathname + location.search); } catch (e) {}
  ASK.focus = m[1] || null; ASK.view = 'chat';
  const go = () => { if (!askOn()) return false; const sh = document.getElementById('tcSheet'); if (sh && !sh.hidden) return false; openAssistant(); return true; };
  if (!go()) { const h = () => { if (go()) window.removeEventListener('japan2026:group', h); }; window.addEventListener('japan2026:group', h); }
  return true;
}
