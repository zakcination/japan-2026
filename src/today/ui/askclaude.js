/* ---------- «Спросить в Claude»: the question goes to the Claude app with this trip as context ----------
   No server, no key: each person asks with their own Claude account. The prompt is built on the phone from what
   the app already knows (the day on screen, my plan, profile, rates, emergency basics) and is also copied, in case
   the Claude app opens without the question filled in. Nothing personal beyond what the traveller typed in ⚙. */
const CLAUDE_NEW = 'https://claude.ai/new?q=';
const CLAUDE_MAX = 6000;                                         // characters of prompt; long links break on some phones
const CLAUDE_CHIPS = [
  'Что у меня сегодня и что стоит не пропустить?',
  'Где поесть халяль или без свинины рядом со следующим пунктом?',
  'Как лучше добраться до следующего пункта?',
  'Идёт дождь — чем заменить план на сегодня?',
  'Переведи на японский и напиши, как это прочитать: ',
  'Помоги с ситуацией: ',
];

function claudeContext(question) {
  const x = ctx(), d = x.day, p = (typeof askProfile === 'function' && askProfile()) || {};
  const lang = { ru: 'по-русски', kk: 'по-казахски', en: 'in English' }[p.lang] || 'по-русски';
  const evs = (x.evs || []).filter(e => e.st !== 'skip').map(e =>
    `- ${e.s}${e.e ? '–' + e.e : ''} ${e.t}${e.loc ? ' (' + e.loc + ')' : ''}${e.note ? ' — ' + String(e.note).slice(0, 120) : ''}`);
  const rate = +SET.rate > 0 ? `1 ¥ = ${SET.rate} ${SET.cur || 'KZT'}` : '';
  const lines = [
    `Я в поездке по Японии: ${T.name || 'группа из Казахстана'}, ${Core.ddmmyyyy(dateOf(T.days[0]))}–${Core.ddmmyyyy(dateOf(T.days[T.days.length - 1]))}.`,
    `Отвечай ${lang}, коротко и по делу (1–5 предложений), тон ${({ fun: 'с юмором', strict: 'строгий' })[p.tone] || 'спокойный'}.`,
    `Не выдумывай расписания поездов, цены и часы работы — дай ссылку Google Maps и скажи «проверьте».`,
    `${p.name ? 'Меня зовут ' + p.name + '. ' : ''}${p.food ? 'Еда: ' + p.food + '. ' : ''}${p.interests ? 'Интересы: ' + p.interests + '. ' : ''}${p.notes ? 'О себе: ' + p.notes : ''}`.trim(),
    `День ${d.n}, ${Core.ddmmyyyy(dateOf(d))}, ${d.city || d.label || ''}.${d.hotel ? ' Ночёвка: ' + d.hotel + '.' : ''}`,
    evs.length ? 'Мой план на этот день:\n' + evs.join('\n') : 'Плана на этот день нет.',
    rate ? `Курс в приложении: ${rate}.` : '',
    'На всякий случай: Япония 110 полиция, 119 скорая; страховка от карты Mastercard (Forte Travel), assistance +44 1273 765321.',
  ].filter(Boolean);
  let head = lines.join('\n');
  const q = String(question || '').trim();
  if (head.length + q.length + 20 > CLAUDE_MAX) head = head.slice(0, Math.max(0, CLAUDE_MAX - q.length - 40)) + '…';
  return head + '\n\nВопрос: ' + q;
}

/* hosts: the same question as a Claude Code session on the trip's repo (claude.ai/code, the owner's own subscription).
   It can change the plan and publish; CLAUDE.md in the repo tells it how. The link only fills the form — you press send. */
const CODE_REPO = 'zakcination/japan-2026';
const claudeHost = () => { try { const me = typeof Api !== 'undefined' && Api.enabled() && Api.me(); return !!me && me.role === 'host'; } catch (e) { return false; } };
function codeUrl(question) {
  const x = ctx(), d = x.day;
  const prompt = `Режим ассистента поездки (CLAUDE.md). Сейчас на экране день ${d.n}, ${Core.ddmmyyyy(dateOf(d))}, ${d.city || d.label || ''}`
    + `. Запрос: ${String(question || '').trim()}`;
  return 'https://claude.ai/code?prompt=' + encodeURIComponent(prompt.slice(0, 1800)) + '&repositories=' + encodeURIComponent(CODE_REPO);
}

function openClaude(prefill) {
  sheet('Спросить в Claude', `
    <p class="tc-sub">Вопрос откроется в приложении Claude вместе с планом дня, вашим профилем и курсом — объяснять ничего не нужно.</p>
    <div class="cl-chips">${CLAUDE_CHIPS.map((c, i) => `<button type="button" class="cl-chip" data-cl-chip="${i}">${esc(c.replace(/: $/, '…'))}</button>`).join('')}</div>
    <label class="tc-f" for="clText"><span>Ваш вопрос</span>
      <textarea id="clText" rows="3" maxlength="1500" placeholder="Например: где рядом рамен без свинины? · 🎤 на клавиатуре">${esc(prefill || '')}</textarea></label>
    <div class="tc-actions two"><button type="button" class="tc-btn primary" id="clGo">${icon('spark')}Открыть в Claude</button>
      <button type="button" class="tc-btn" id="clProf">Профиль</button></div>
    ${claudeHost() ? `<button type="button" class="tc-btn wide" id="clCode">${icon('edit')}Claude Code — изменить план</button>
      <p class="tc-foot">Сессия на вашей подписке: правит план и публикует, приложение обновится у всех. Откроется форма — нажмите «отправить».</p>` : ''}
    <details class="tc-more"><summary>Что уйдёт в Claude</summary><pre class="cl-pre" id="clPre"></pre></details>
    <p class="tc-foot" id="clMsg" role="status">Текст ещё и копируется: если Claude открылся с пустым полем — вставьте. Номера карт, паспорта и коды не пишите.</p>
    ${typeof openSos === 'function' ? '<button type="button" class="tc-btn wide" data-cl-sos>SOS — экстренная помощь без интернета</button>' : ''}`, m => {
    fullSheet(m);
    const ta = m.querySelector('#clText'), pre = m.querySelector('#clPre');
    const show = () => { pre.textContent = claudeContext(ta.value); };
    show(); ta.addEventListener('input', show);
    m.querySelectorAll('[data-cl-chip]').forEach(b => b.addEventListener('click', () => {
      ta.value = CLAUDE_CHIPS[+b.dataset.clChip]; show(); ta.focus(); ta.setSelectionRange(ta.value.length, ta.value.length);
    }));
    m.querySelector('#clProf').addEventListener('click', () => openAskProfile());
    const code = m.querySelector('#clCode');
    if (code) code.addEventListener('click', () => {
      if (!ta.value.trim()) { m.querySelector('#clMsg').textContent = 'Напишите, что изменить: например, «перенеси Тэнрю-дзи на 11:00».'; ta.focus(); return; }
      window.open(codeUrl(ta.value), '_blank', 'noopener');
    });
    const sos = m.querySelector('[data-cl-sos]'); if (sos) sos.addEventListener('click', () => openSos());
    m.querySelector('#clGo').addEventListener('click', () => {
      if (!ta.value.trim()) { m.querySelector('#clMsg').textContent = 'Напишите вопрос или выберите готовый.'; ta.focus(); return; }
      const text = claudeContext(ta.value);
      try { if (navigator.clipboard) navigator.clipboard.writeText(text).catch(() => {}); } catch (e) {}
      window.open(CLAUDE_NEW + encodeURIComponent(text), '_blank', 'noopener');
    });
  });
}
