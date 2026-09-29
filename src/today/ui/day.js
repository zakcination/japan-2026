/* ---------- tab «День»: pick a day (tap or swipe), tick stops off, open a stop ---------- */

function dayStrip(x) {
  return `<div class="tc-days" id="tcDays" role="tablist" aria-label="Дни поездки">` + T.days.map(d => {
    const iso = dateOf(d), w = new Date(iso + 'T12:00:00Z').getUTCDay();
    const on = d.n === x.day.n, today = d.n === x.cday.n;
    return `<button type="button" role="tab" class="tc-daypick${on ? ' on' : ''}${today ? ' today' : ''}" data-day="${d.n}"
      aria-selected="${on}" aria-label="${Core.ddmmyyyy(iso)}"><small>${WD2[w]}</small><b>${+iso.slice(8)}</b></button>`;
  }).join('') + '</div>';
}

function itemRow(x, e) {
  const isNow = x.day === x.cday && x.c.min != null && e.ns <= x.c.min && x.c.min < e.ne && !e.skip && !e.auto;
  const moved = !e.skip && (e.ns !== e.S || e.ne !== e.E);
  const bits = [e.e ? `до ${hm(e.ne)}` : '', e.cost ? money(e.cost) : '', e.ride ? `дорога ${e.ride} мин` : ''].filter(Boolean).join(' · ');
  return `<div class="tc-item${e.done ? ' done' : ''}${e.skip || e.auto ? ' skip' : ''}${isNow ? ' now' : ''}" data-id="${esc(e.id)}">
    <label class="tc-check"><input type="checkbox" switch data-done="${esc(e.id)}"${e.done ? ' checked' : ''}
      aria-label="Сделано: ${esc(e.t)}"><span aria-hidden="true">${icon('check')}</span></label>
    <button type="button" class="tc-open" aria-label="${hm(e.ns)} ${esc(e.t)} — подробнее">
      <span class="tc-itime">${hm(e.ns)}${moved ? `<s>${hm(e.S)}</s>` : ''}</span>
      <span class="tc-ibody"><span class="tc-ititle">${esc(e.t)}${isNow ? ' · сейчас' : ''}</span>
        <span class="tc-imeta">${stDot(e.st)}${bits ? `<span>${bits}</span>` : ''}${e.conflict ? `<span class="tc-bad">не успеваете на ${e.conflict} мин</span>` : ''}${e.auto ? '<span>убрано ради расписания</span>' : ''}</span></span>
    </button></div>`;
}

RENDER.day = (x, root) => {
  const counted = x.evs.filter(e => !e.skip && !e.bad && e.cat !== 'routine');
  const doneN = counted.filter(e => e.done).length;
  const budget = x.evs.filter(e => !e.skip && !e.auto).reduce((s, e) => s + (+e.cost || 0), 0);
  root.innerHTML = `<div class="tc-page">
    ${dayStrip(x)}
    <div class="tc-row tc-daysum"><span>${doneN} из ${counted.length} выполнено</span><span>${budget ? money(budget) : ''}</span></div>
    <div class="tc-list" id="tcList">${x.evs.length ? x.evs.map(e => itemRow(x, e)).join('') : '<p class="tc-empty">Нет пунктов</p>'}</div>
    <div class="tc-actions two"><button type="button" class="tc-btn" id="tcAdd">${icon('plus')}Пункт</button>
      <button type="button" class="tc-btn" id="tcDayEdit">${icon('edit')}День</button></div>
  </div>`;
  const pick = n => { viewDay = n; renderShell(); };
  root.querySelectorAll('.tc-daypick').forEach(b => b.addEventListener('click', () => pick(+b.dataset.day)));
  const on = root.querySelector('.tc-daypick.on'); if (on) on.scrollIntoView({ inline: 'center', block: 'nearest' });
  root.querySelectorAll('[data-done]').forEach(inp => inp.addEventListener('change', () => {
    const id = inp.dataset.done; if (inp.checked) S.done[id] = true; else delete S.done[id]; save(); renderShell();
  }));
  root.querySelectorAll('.tc-open').forEach(b => b.addEventListener('click', () => openStop(x.day, b.closest('.tc-item').dataset.id)));
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
  const hasTravel = Core.travel(e) > 0;
  const act = (ic, txt, sub, attrs) => `<button type="button" class="tc-act" ${attrs}>${icon(ic)}<span>${txt}${sub ? `<small>${sub}</small>` : ''}</span></button>`;
  const link = (ic, txt, sub, href) => `<a class="tc-act" href="${href}" target="_blank" rel="noopener">${icon(ic)}<span>${txt}${sub ? `<small>${sub}</small>` : ''}</span></a>`;
  const iosCal = typeof Ios !== 'undefined' && Ios.calendarForDay;
  sheet(e.t, `
    <p class="tc-sub">${hm(e.ns)} → ${hm(e.ne)} · ${dur(e.ne - e.ns)}${hasTravel ? ` · выйти в ${hm(e.leave)}` : ''}${e.cost ? ` · ${money(e.cost)}` : ''}</p>
    <div class="tc-row">${stDot(e.st)}${e.bound ? `<span class="tc-sub">📅 только ${Core.ddmmyyyy(e.bound)}</span>` : ''}</div>
    ${e.note ? `<p class="tc-notepara">${esc(e.note)}</p>` : ''}
    <div class="tc-group">
      ${link('pin', typeof Ios !== 'undefined' && Ios.isIOS ? 'Маршрут в Apple Картах' : 'Маршрут', 'общественный транспорт', routeUrl(e))}
      ${link('map', 'Открыть в Google Maps', '', gmap(e))}
      ${e.bk ? act('tix', 'Билет', '', `data-ticket="${esc(e.bk)}"`) : ''}
      ${Core.safeUrl(e.link) ? link('share', 'Официальный сайт', '', Core.safeUrl(e.link)) : ''}
    </div>
    <div class="tc-grid4">
      ${fixed ? '' : `<button type="button" class="tc-tile" data-delay="15">${icon('plus')}+15</button>
      <button type="button" class="tc-tile" data-delay="30">${icon('plus')}+30</button>
      <button type="button" class="tc-tile" data-skip>${icon('skip')}${e.skip ? 'Вернуть' : 'Пропустить'}</button>`}
      ${e.delay ? `<button type="button" class="tc-tile" data-delay="0">${icon('clock')}сброс</button>` : ''}
      <button type="button" class="tc-tile" data-edit>${icon('edit')}Изменить</button>
    </div>
    ${iosCal ? `<div class="tc-group">${act('cal', 'Весь день — в Календарь', 'с напоминаниями «пора выходить»', 'data-cal')}</div>` : ''}`,
  m => {
    m.querySelectorAll('[data-delay]').forEach(b => b.addEventListener('click', () => {
      const by = +b.dataset.delay;
      if (!by) delete S.delay[id]; else S.delay[id] = (S.delay[id] || 0) + by;
      save(); closeSheet(); renderShell();
    }));
    const sk = m.querySelector('[data-skip]');
    if (sk) sk.addEventListener('click', () => { if (S.skip[id]) delete S.skip[id]; else S.skip[id] = true; save(); closeSheet(); renderShell(); });
    m.querySelector('[data-edit]').addEventListener('click', () => { closeSheet(); openEditor(day, id); });
    const tk = m.querySelector('[data-ticket]'); if (tk) tk.addEventListener('click', () => { closeSheet(); showTicket(tk.dataset.ticket); });
    const cal = m.querySelector('[data-cal]'); if (cal) cal.addEventListener('click', () => Ios.calendarForDay(day));
  });
}
