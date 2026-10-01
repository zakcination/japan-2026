/* ---------- tab «День»: pick a day (tap or swipe), tick stops off, open a stop ---------- */

function dayStrip(x) {
  return `<div class="tc-days" id="tcDays" role="tablist" aria-label="Дни поездки">` + T.days.map(d => {
    const iso = dateOf(d), w = new Date(iso + 'T12:00:00Z').getUTCDay();
    const on = d.n === x.day.n, today = !x.quiet && d.n === x.cday.n;
    return `<button type="button" role="tab" class="tc-daypick${on ? ' on' : ''}${today ? ' today' : ''}" data-day="${d.n}"
      aria-selected="${on}" aria-label="${Core.ddmmyyyy(iso)}"><small>${WD2[w]}</small><b>${+iso.slice(8)}</b></button>`;
  }).join('') + '</div>';
}

function itemRow(x, e, ov) {
  const isNow = !x.quiet && x.day === x.cday && x.c.min != null && e.ns <= x.c.min && x.c.min < e.ne && !e.skip && !e.auto;
  const lm = m => hm(Core.localMin(e, m));       // a Shanghai stop shows Shanghai time
  const moved = !e.skip && (e.ns !== e.S || e.ne !== e.E);
  const bits = [e.e ? `до ${lm(e.ne)}` : '', e.cost ? money(e.cost) : '', e.ride ? `дорога ${e.ride} мин` : ''].filter(Boolean).join(' · ');
  return `<div class="tc-item${e.done ? ' done' : ''}${e.skip || e.auto ? ' skip' : ''}${isNow ? ' now' : ''}" data-id="${esc(e.id)}">
    <label class="tc-check"><input type="checkbox" switch data-done="${esc(e.id)}"${e.done ? ' checked' : ''}
      aria-label="Сделано: ${esc(e.t)}"><span aria-hidden="true">${icon('check')}</span></label>
    <button type="button" class="tc-open" aria-label="${lm(e.ns)}${e.sh ? ' по Шанхаю' : ''} ${esc(e.t)} — подробнее">
      <span class="tc-itime">${lm(e.ns)}${moved ? `<s>${lm(e.S)}</s>` : ''}${e.sh ? '<small>по Шанхаю</small>' : ''}</span>
      <span class="tc-ibody"><span class="tc-ititle">${esc(e.t)}${isNow ? ' · сейчас' : ''}</span>
        <span class="tc-imeta">${stDot(e.st)}${bits ? `<span>${bits}</span>` : ''}${e.conflict ? `<span class="tc-bad">не успеваете на ${e.conflict} мин</span>` : ''}${e.auto ? '<span>убрано ради расписания</span>' : ''}${e.from === 'mine' ? `<span class="tc-mine">${e.sharedBy ? esc(e.sharedBy) : 'моё'}</span>` : ''}${ov && ov.get(e.id) ? `<span class="tc-bad">пересекается с ${esc(ov.get(e.id))}</span>` : ''}</span></span>
    </button></div>`;
}

RENDER.day = (x, root) => {
  // signed in: own stops that overlap the rest get a warning (my schedule only)
  const ov = new Map();
  if (typeof Api !== 'undefined' && Api.me() && S.viewMode !== 'group') {
    const t = new Map(x.evs.map(e => [e.id, e.t]));
    Group.overlaps(x.evs.filter(e => !e.skip && !e.auto)).forEach(([a, b]) => { if (!ov.has(a)) ov.set(a, t.get(b)); if (!ov.has(b)) ov.set(b, t.get(a)); });
  }
  const counted = x.evs.filter(e => !e.skip && !e.bad && e.cat !== 'routine');
  const doneN = counted.filter(e => e.done).length;
  const budget = x.evs.filter(e => !e.skip && !e.auto).reduce((s, e) => s + (+e.cost || 0), 0);
  root.innerHTML = `<div class="tc-page">
    ${dayStrip(x)}
    ${typeof joinBarHTML === 'function' ? joinBarHTML(x) : ''}
    ${!x.canPreview || x.c.live ? '' : `<button type="button" class="tc-btn" id="tcPreviewDay">▶ Как «Сейчас»</button>`}
    <div class="tc-row tc-daysum"><span>${doneN} из ${counted.length} выполнено</span><span>${budget ? money(budget) : ''}</span></div>
    <div class="tc-list" id="tcList">${x.evs.length ? x.evs.map(e => itemRow(x, e, ov)).join('') : '<p class="tc-empty">Нет пунктов</p>'}</div>
    <div class="tc-actions two"><button type="button" class="tc-btn" id="tcAdd">${icon('plus')}Пункт</button>
      <button type="button" class="tc-btn" id="tcDayEdit">${icon('edit')}День</button></div>
  </div>`;
  if (typeof wireJoinBar === 'function') wireJoinBar(root);
  const pick = n => { viewDay = n; renderShell(); };
  root.querySelectorAll('.tc-daypick').forEach(b => b.addEventListener('click', () => pick(+b.dataset.day)));
  const on = root.querySelector('.tc-daypick.on'); if (on) on.scrollIntoView({ inline: 'center', block: 'nearest' });
  root.querySelectorAll('[data-done]').forEach(inp => inp.addEventListener('change', () => {
    const id = inp.dataset.done; if (inp.checked) S.done[id] = true; else delete S.done[id]; save(); renderShell();
  }));
  root.querySelectorAll('.tc-open').forEach(b => b.addEventListener('click', () => openStop(x.day, b.closest('.tc-item').dataset.id)));
  const pv = root.querySelector('#tcPreviewDay');
  if (pv) pv.addEventListener('click', () => { S.preview = true; S.prevDay = x.day.n; S.prevTime = S.prevTime || '09:00'; save(); go('now'); });
  root.querySelector('#tcAdd').addEventListener('click', () => openEditor(x.day, null));
  root.querySelector('#tcDayEdit').addEventListener('click', () => openDayEditor(x.day));
};

/* swipe left / right on the list changes the day; listened on the document so a re-render
   in the middle of a gesture (weather arriving, the minute tick) doesn't lose it */
let swipe = null;
document.addEventListener('pointerdown', e => {
  swipe = tab === 'day' && e.target.closest && e.target.closest('#tcList') ? { x: e.clientX, y: e.clientY } : null;
});
document.addEventListener('pointerup', e => {
  if (!swipe || tab !== 'day') return;
  const dx = e.clientX - swipe.x, dy = e.clientY - swipe.y; swipe = null;
  if (Math.abs(dx) < 60 || Math.abs(dx) < Math.abs(dy) * 1.5) return;
  const n = (viewDay || 1) + (dx < 0 ? 1 : -1);
  if (T.days.some(d => d.n === n)) { viewDay = n; renderShell(); }
});
document.addEventListener('pointercancel', () => { swipe = null; });

/* the stop sheet: details and every action for one stop */
function openStop(day, id) {
  const x = ctx();
  const evs = day.n === x.cday.n ? x.cevs : plan(day, null);
  const e = evs.find(v => v.id === id);
  if (!e) return;
  const fixed = e.st === 'fixed' || Core.isAnchor(e);
  const me = typeof Api !== 'undefined' && Api.me();
  const canEdit = !me || me.role === 'host' || String(e.id).startsWith('m-');
  const hasTravel = Core.travel(e) > 0, lm = m => hm(Core.localMin(e, m));
  const act = (ic, txt, sub, attrs) => `<button type="button" class="tc-act" ${attrs}>${icon(ic)}<span>${txt}${sub ? `<small>${sub}</small>` : ''}</span></button>`;
  const link = (ic, txt, sub, href) => `<a class="tc-act" href="${href}" target="_blank" rel="noopener">${icon(ic)}<span>${txt}${sub ? `<small>${sub}</small>` : ''}</span></a>`;
    sheet(e.t, `
    <p class="tc-sub">${lm(e.ns)} → ${lm(e.ne)}${e.sh ? ' по Шанхаю' : ''} · ${dur(e.ne - e.ns)}${hasTravel ? ` · выйти в ${lm(e.leave)}` : ''}${e.cost ? ` · ${money(e.cost)}` : ''}</p>
    <div class="tc-row">${stDot(e.st)}${e.bound ? `<span class="tc-sub">📅 только ${esc(Core.ddmmyyyy(e.bound))}</span>` : ''}</div>
    ${e.note ? `<p class="tc-notepara">${esc(e.note)}</p>` : ''}
    <div class="tc-group">
      ${link('pin', Ios.isIOS() ? 'Маршрут в Apple Картах' : 'Маршрут', 'общественный транспорт', routeUrl(e))}
      ${link('walk', 'Пешком', '', Ios.walkUrl(e))}
      ${e.loc ? act('globe', e.locLang === 'zh' ? 'Показать по-китайски' : 'Показать по-японски', 'для такси и прохожих', 'data-local') : ''}
      ${link('map', 'Открыть в Google Maps', '', gmap(e))}
      ${e.bk ? act('tix', 'Билет', '', `data-ticket="${esc(e.bk)}"`) : ''}
      ${Core.safeUrl(e.link) ? link('share', 'Официальный сайт', '', Core.safeUrl(e.link)) : ''}
    </div>
    ${typeof stopJoinHTML === 'function' ? stopJoinHTML(day, e) : ''}
    <div class="tc-grid4">
      ${fixed ? '' : `<button type="button" class="tc-tile" data-delay="15">${icon('plus')}+15</button>
      <button type="button" class="tc-tile" data-delay="30">${icon('plus')}+30</button>
      <button type="button" class="tc-tile" data-skip>${icon('skip')}${e.skip ? 'Вернуть' : 'Пропустить'}</button>`}
      ${e.delay ? `<button type="button" class="tc-tile" data-delay="0">${icon('clock')}сброс</button>` : ''}
      ${canEdit ? `<button type="button" class="tc-tile" data-edit>${icon('edit')}Изменить</button>` : ''}
    </div>
    <div class="tc-group">${act('cal', 'Весь день — в Календарь', 'с напоминаниями «пора выходить»', 'data-cal')}</div>`,
  m => {
    m.querySelectorAll('[data-delay]').forEach(b => b.addEventListener('click', () => {
      const by = +b.dataset.delay;
      if (!by) delete S.delay[id]; else S.delay[id] = (S.delay[id] || 0) + by;
      save(); closeSheet(); renderShell();
    }));
    const sk = m.querySelector('[data-skip]');
    if (sk) sk.addEventListener('click', () => { if (S.skip[id]) delete S.skip[id]; else S.skip[id] = true; save(); closeSheet(); renderShell(); });
    const ed = m.querySelector('[data-edit]'); if (ed) ed.addEventListener('click', () => { closeSheet(); openEditor(day, id); });
    if (typeof wireStopJoin === 'function') wireStopJoin(m, day, e);
    const lc = m.querySelector('[data-local]'); if (lc) lc.addEventListener('click', () => { closeSheet(); showLocal(e); });
    const tk = m.querySelector('[data-ticket]'); if (tk) tk.addEventListener('click', () => { closeSheet(); showTicket(tk.dataset.ticket); });
    m.querySelector('[data-cal]').addEventListener('click', () => Ios.calendarForDay(day));
  });
}

/* «Показать по-японски»: the place full screen, big, for a taxi driver or a passer-by; one tap anywhere closes it */
const LOCAL_ASK = { ja: 'ここまでお願いします。', zh: '请带我去这里。' };
function showLocal(e) {
  const lang = e.locLang === 'zh' ? 'zh' : 'ja';
  let m = document.getElementById('tcLocal');
  if (!m) { m = document.createElement('div'); m.id = 'tcLocal'; m.className = 'tc-local'; document.body.appendChild(m); }
  m.setAttribute('role', 'dialog'); m.setAttribute('aria-modal', 'true'); m.setAttribute('aria-label', e.t);
  m.innerHTML = `<p class="tc-local-ask" lang="${lang}">${esc(LOCAL_ASK[lang])}</p>
    <p class="tc-local-name" lang="${lang}">${esc(e.loc)}</p>
    <p class="tc-local-ru">${esc(e.t)}</p>
    <div class="tc-local-acts"><button type="button" class="tc-btn" id="tcLocalCopy">${icon('share')}Скопировать</button>
      <button type="button" class="tc-btn primary" id="tcLocalClose">Закрыть</button></div>`;
  m.hidden = false; Ios.keepAwake(true);
  const close = () => { m.hidden = true; Ios.keepAwake(false); };
  m.querySelector('#tcLocalClose').addEventListener('click', close);
  m.querySelector('#tcLocalCopy').addEventListener('click', ev => {
    ev.stopPropagation(); const b = ev.currentTarget;
    (navigator.clipboard ? navigator.clipboard.writeText(e.loc) : Promise.reject()).then(() => { b.textContent = 'Скопировано'; }, () => { b.textContent = 'Не получилось'; });
  });
  m.onclick = ev => { if (!ev.target.closest('button')) close(); };
  m.querySelector('#tcLocalClose').focus();
}
