/* ---------- «Подготовка»: the readiness list, ticks and own items kept on this phone ---------- */
const PREP_KEY = 'japan2026.prep.v1';
function prepLocal() {
  try { const j = JSON.parse(localStorage.getItem(PREP_KEY) || 'null'); if (j && typeof j === 'object') return { done: j.done || {}, own: Array.isArray(j.own) ? j.own : [] }; } catch (e) {}
  return { done: {}, own: [] };
}
const prepSave = l => { try { localStorage.setItem(PREP_KEY, JSON.stringify(l)); } catch (e) {} };
function prepItems() {
  const trip = typeof planDoc === 'function' ? planDoc() : T;
  const booked = new Set((trip.bookings || []).filter(b => b.st === 'fixed').map(b => b.id));
  return Prep.items(trip, prepLocal(), { installed: Ios.standalone(), booked, tickets: new Set(Object.keys(haveTicket || {})) });
}
function openPrep(focus) {
  const list = prepItems(), dm = v => v ? Core.ddmmyyyy(v.slice(0, 10)).slice(0, 5) : '';
  const row = i => `<div class="tc-prep-item${i.done ? ' done' : ''}" data-id="${esc(i.id)}">
      <label class="tc-check"><input type="checkbox" switch data-prep="${esc(i.id)}"${i.done ? ' checked' : ''}${i.checked === 'auto' ? ' disabled' : ''}
        aria-label="${esc(i.title)}"><span aria-hidden="true">${icon('check')}</span></label>
      <span class="tc-prep-t"><b>${esc(i.title)}</b>${i.checked === 'auto' ? '<small>проверено приложением</small>' : i.note ? `<small>${esc(i.note)}</small>` : ''}</span>
      <span class="tc-prep-r">${i.due ? `<small>до ${esc(dm(i.due))}</small>` : ''}${Core.safeUrl(i.url) ? `<a class="tc-x" href="${Core.safeUrl(i.url)}" target="_blank" rel="noopener" aria-label="Открыть сайт">${icon('share')}</a>` : ''}
        ${i.own ? `<button type="button" class="tc-x" data-prep-del="${esc(i.id)}" aria-label="Удалить свой пункт">${icon('close')}</button>` : ''}</span></div>`;
  sheet('Подготовка', Prep.groups(list).map(g => `<section class="tc-prep-sec" data-group="${g.key}"><h3 class="tc-sech">${esc(g.title)} · ${g.done}/${g.total}</h3>
      <div class="tc-group">${list.filter(i => i.group === g.key).map(row).join('')}</div>
      <button type="button" class="tc-btn" data-prep-add="${g.key}">${icon('plus')}Свой пункт</button></section>`).join('')
    + `<p class="tc-foot">Отметки и свои пункты — только на этом телефоне.</p>`, m => {
    const sec = focus && m.querySelector(`[data-group="${focus}"]`); if (sec) sec.scrollIntoView({ block: 'start' });
    m.querySelectorAll('[data-prep]').forEach(inp => inp.addEventListener('change', () => {
      const l = prepLocal(); if (inp.checked) l.done[inp.dataset.prep] = true; else delete l.done[inp.dataset.prep];
      prepSave(l); renderShell();
    }));
    m.querySelectorAll('[data-prep-add]').forEach(b => b.addEventListener('click', () => {
      b.outerHTML = `<div class="tc-form2">${fld('prAddTitle', 'Свой пункт', '', 'text', 'maxlength="80"')}
        <button type="button" class="tc-btn primary" id="prAddGo" data-g="${b.dataset.prepAdd}">Добавить</button></div>`;
      const go = m.querySelector('#prAddGo');
      go.addEventListener('click', () => {
        const t = m.querySelector('#prAddTitle').value.trim(); if (!t) return;
        const l = prepLocal(); l.own.push({ id: 'own-' + Date.now().toString(36), group: go.dataset.g, title: t.slice(0, 80) });
        prepSave(l); openPrep(go.dataset.g); renderShell();
      });
      m.querySelector('#prAddTitle').focus();
    }));
    m.querySelectorAll('[data-prep-del]').forEach(b => b.addEventListener('click', () => twoTap(b, '?', () => {
      const l = prepLocal(); l.own = l.own.filter(o => o.id !== b.dataset.prepDel); delete l.done[b.dataset.prepDel];
      prepSave(l); openPrep(); renderShell();
    })));
  });
}
