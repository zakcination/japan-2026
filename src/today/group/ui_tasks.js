/* ---------- «Дела»: what to buy (recipes), what to do (tasks) ---------- */
const almaty = iso => { const t = Date.parse(iso); if (!Number.isFinite(t)) return ''; const d = new Date(t + 5 * 3600e3), p = v => String(v).padStart(2, '0');
  return `${p(d.getUTCDate())}.${p(d.getUTCMonth() + 1)} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`; };
const japan = iso => { const t = Date.parse(iso); if (!Number.isFinite(t)) return ''; const d = new Date(t + 9 * 3600e3), p = v => String(v).padStart(2, '0');
  return `${p(d.getUTCDate())}.${p(d.getUTCMonth() + 1)} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}`; };
function taskHTML(t, host) {
  const r = t.recipe || {}, k = t.task || {};
  const opens = r.opens ? `продажи: ${japan(r.opens)} по Японии = ${almaty(r.opens)} по Алматы` : r.opens_note ? `продажи: ${esc(r.opens_note)}` : '';
  const by = r.buy_by || k.due ? `купить до ${Core.ddmmyyyy(r.buy_by || k.due).slice(0, 5)}` : '';
  const url = Core.safeUrl(r.url || k.url);
  return `<div class="tc-card tc-task${t.done ? ' done' : ''}" data-ref="${esc(t.ref)}">
    <div class="tc-row"><b>${t.dropped ? 'Вы отписались — сдайте или перенесите билет: ' : ''}${esc(t.title)}</b>
      <label class="tc-check"><input type="checkbox" switch data-done="${esc(t.ref)}"${t.done ? ' checked' : ''} aria-label="${t.kind === 'task' ? 'Сделано' : 'Куплено'}"><span aria-hidden="true">${icon('check')}</span></label></div>
    ${[opens, by, r.price_pp ? money(r.price_pp) : ''].filter(Boolean).map(s => `<span class="tc-sub">${s}</span>`).join('')}
    ${r.tips || k.note ? `<p class="tc-notepara">${esc(r.tips || k.note)}</p>` : ''}
    ${r.host_ref ? `<p class="tc-note tc-hostref"><b>Бронь хозяев:</b> ${esc(r.host_ref)}</p>` : ''}
    <div class="tc-actions two">${url ? `<a class="tc-btn primary" href="${url}" target="_blank" rel="noopener">${icon('share')}${esc(r.site || Group.siteOf(url).site)}</a>` : ''}
      ${t.kind !== 'task' ? `<button type="button" class="tc-btn" data-attach-ref="${esc(t.ref)}">${icon('clip')}Билет</button>` : ''}
      ${host && t.kind === 'recipe' ? `<button type="button" class="tc-btn" data-recipe="${esc(r.bk)}">${icon('edit')}Рецепт</button>` : ''}</div>
  </div>`;
}
function tasksHTML(nowMs) {
  if (!Api.me()) return '';
  const all = Group.tasks(planDoc(), Api.state(), Api.me().id, nowMs), host = Api.me().role === 'host';
  const buy = all.filter(t => t.kind !== 'task'), todo = all.filter(t => t.kind === 'task');
  return `<section id="grTasks"><h2 class="tc-sech">Мне купить</h2>${buy.length ? buy.map(t => taskHTML(t, host)).join('') : '<p class="tc-empty">Присоединитесь к части поездки — здесь появятся билеты.</p>'}
    <h2 class="tc-sech">Сделать</h2>${todo.map(t => taskHTML(t, host)).join('') || '<p class="tc-empty">Пусто.</p>'}
    ${host ? '<button type="button" class="tc-btn wide" id="tkImport">Импорт задач из старого трекера</button>' : ''}</section>`;
}
function wireTasks(root) {
  if (!Api.me()) return;
  root.querySelectorAll('[data-done]').forEach(i => i.addEventListener('change', () => {
    const ref = i.dataset.done, done = i.checked;
    Api.call('set_task_state', { p_ref: ref, p_done: done }, s => { s.task_state = s.task_state.filter(x => x.ref !== ref).concat([{ ref, done }]); });
    renderShell();
  }));
  root.querySelectorAll('[data-recipe]').forEach(b => b.addEventListener('click', () => openRecipeEditor(b.dataset.recipe)));
  const im = root.querySelector('#tkImport'); if (im) im.addEventListener('click', importTasksSheet);
}
function openRecipeEditor(bk) {
  const r = { ...(Api.state().recipes.find(x => x.bk === bk) || { bk }) };
  sheet('Рецепт покупки', `<div class="tc-form">${fld('rcWhat', 'Что купить', r.what || '')}${fld('rcUrl', 'Сайт (https)', r.url || '', 'url')}
    ${fld('rcSite', 'Название сайта', r.site || '')}${fld('rcOpens', 'Продажи открываются (ISO, с поясом)', r.opens || '')}
    ${fld('rcOpensNote', 'Про продажи — текстом', r.opens_note || '')}${fld('rcBy', 'Купить до', r.buy_by || '', 'date')}
    ${fld('rcPrice', 'Цена на человека, ¥', r.price_pp ?? '', 'number', 'inputmode="numeric"')}</div>
    <label class="tc-f" for="rcTips"><span>Советы</span><textarea id="rcTips" rows="2">${esc(r.tips || '')}</textarea></label>
    <label class="tc-f" for="rcHost"><span>Наша бронь (видят только участники): рейс, места</span><textarea id="rcHost" rows="2">${esc(r.host_ref || '')}</textarea></label>
    <p class="tc-warn" id="rcMsg"></p><button type="button" class="tc-btn primary wide" id="rcSave">Сохранить</button>`, m => {
    m.querySelector('#rcSave').addEventListener('click', () => {
      const v = id => m.querySelector('#' + id).value.trim();
      if (v('rcUrl') && !Core.safeUrl(v('rcUrl'))) { m.querySelector('#rcMsg').textContent = 'Ссылка должна начинаться с https://'; return; }
      const next = { ...r, what: v('rcWhat'), url: v('rcUrl'), site: v('rcSite'), opens: v('rcOpens') || null, opens_note: v('rcOpensNote'),
        buy_by: v('rcBy') || null, price_pp: v('rcPrice') === '' ? null : +v('rcPrice'), tips: v('rcTips'), host_ref: v('rcHost') };
      Api.call('save_recipe', { p_r: next }, s => { s.recipes = s.recipes.filter(x => x.bk !== bk).concat([next]); });
      closeSheet(); renderShell();
    });
  });
}
function importTasksSheet() {
  sheet('Импорт задач', `<p class="tc-sub">Вставьте JSON-список задач: [{"title": "…", "due": "2026-10-15", "note": "…", "url": "https://…"}].</p>
    <label class="tc-f" for="tkJson"><span>JSON</span><textarea id="tkJson" rows="6" spellcheck="false"></textarea></label>
    <p class="tc-warn" id="tkMsg"></p><button type="button" class="tc-btn primary wide" id="tkImportGo">Импортировать</button>`, m => {
    m.querySelector('#tkImportGo').addEventListener('click', () => {
      let xs; try { xs = JSON.parse(m.querySelector('#tkJson').value); } catch (e) { m.querySelector('#tkMsg').textContent = 'Это не JSON.'; return; }
      xs = (Array.isArray(xs) ? xs : []).filter(t => t && String(t.title || '').trim()).map(t => ({ title: String(t.title).slice(0, 200),
        note: String(t.note || '').slice(0, 1000), due: /^\d{4}-\d{2}-\d{2}$/.test(t.due || '') ? t.due : null, url: Core.safeUrl(t.url) || null, assignee: null }));
      if (!xs.length) { m.querySelector('#tkMsg').textContent = 'Нет задач с названием.'; return; }
      Api.call('import_tasks', { p_tasks: xs }, null); closeSheet();
    });
  });
}
