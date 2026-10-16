/* ---------- «Документы в телефоне»: QR declarations, insurance letter, passport copy — offline, on this phone only ----------
   Files live in IndexedDB (never on the server, never in the page): open them at customs without a connection. */
const DocStore = (() => {
  const DB = 'japan2026-docs', ST = 'docs';
  let dbp = null;
  const open = () => dbp || (dbp = new Promise((ok, no) => {
    try {
      const r = indexedDB.open(DB, 1);
      r.onupgradeneeded = () => { if (!r.result.objectStoreNames.contains(ST)) r.result.createObjectStore(ST, { keyPath: 'id' }); };
      r.onsuccess = () => ok(r.result); r.onerror = () => no(r.error);
    } catch (e) { no(e); }
  }));
  const tx = (mode, fn) => open().then(db => new Promise((ok, no) => {
    const t = db.transaction(ST, mode), s = t.objectStore(ST), out = fn(s);
    t.oncomplete = () => ok(out && 'result' in out ? out.result : undefined); t.onerror = () => no(t.error);
  }));
  return {
    all: () => tx('readonly', s => s.getAll()).then(xs => (xs || []).sort((a, b) => (a.at || 0) - (b.at || 0))),
    put: d => tx('readwrite', s => s.put(d)),
    del: id => tx('readwrite', s => s.delete(id)),
  };
})();
const DOC_MAX = 15 * 1024 * 1024;                               // one file; QR receipts are ~100 KB

function openDocs() {
  sheet('Документы в телефоне', `
    <p class="tc-sub">QR для въезда в Китай, письмо страховки, копия паспорта — откроются без интернета. Хранятся только на этом телефоне, никуда не отправляются.</p>
    <div class="tc-group" id="docList"><p class="tc-sub" style="padding:12px 16px">Загружаю…</p></div>
    <label class="tc-btn primary wide">${icon('plus')}Добавить файлы<input type="file" id="docFile" accept="image/*,application/pdf" multiple hidden></label>
    <p class="tc-foot" id="docMsg" role="status">Картинка (PNG, JPG) открывается надёжнее, чем PDF. Удаление — только с этого телефона.</p>`, m => {
    const msg = t => { m.querySelector('#docMsg').textContent = t; };
    const render = () => DocStore.all().then(xs => {
      const list = m.querySelector('#docList'); if (!list) return;
      list.innerHTML = xs.length ? xs.map(d => `<div class="tc-flrow"><button type="button" class="tc-act" data-doc="${esc(d.id)}">${icon(d.type === 'application/pdf' ? 'tix' : 'cam')}
          <span>${esc(d.name)}<small>${(d.size / 1024).toFixed(0)} КБ · ${d.type === 'application/pdf' ? 'PDF' : 'картинка'}</small></span></button>
          <button type="button" class="tc-x" data-docdel="${esc(d.id)}" aria-label="Удалить ${esc(d.name)}">${icon('close')}</button></div>`).join('')
        : '<p class="tc-sub" style="padding:12px 16px">Пока пусто. Добавьте QR-квитанции для Шанхая — до вылета, пока есть интернет.</p>';
    }).catch(() => { msg('Хранилище недоступно в этом режиме браузера (например, приватном).'); });
    render();
    m.querySelector('#docFile').addEventListener('change', e => {
      const fs = [...(e.target.files || [])]; e.target.value = '';
      const ok = fs.filter(f => f.size <= DOC_MAX && (/^image\//.test(f.type) || f.type === 'application/pdf'));
      const skipped = ok.length < fs.length ? ' Часть файлов пропущена: только картинки и PDF до 15 МБ.' : '';
      if (!ok.length) { msg(skipped.trim()); return; }
      Promise.all(ok.map((f, i) => DocStore.put({ id: 'd-' + Date.now().toString(36) + i, name: f.name.replace(/\.[a-z0-9]+$/i, '').slice(0, 80),
        type: f.type, size: f.size, blob: f, at: Date.now() + i })))
        .then(() => { msg(`Сохранено на телефоне: ${ok.length}.` + skipped); render(); })
        .catch(() => msg('Не удалось сохранить — мало места или приватный режим.'));
    });
    m.querySelector('#docList').addEventListener('click', e => {
      const o = e.target.closest('[data-doc]'), d = e.target.closest('[data-docdel]');
      if (o) DocStore.all().then(xs => { const x = xs.find(y => y.id === o.dataset.doc); if (x) showDoc(x); });
      if (d) { if (d.dataset.armed !== '1') { d.dataset.armed = '1'; d.classList.add('armed'); d.setAttribute('aria-label', 'Нажмите ещё раз, чтобы удалить'); msg('Нажмите ✕ ещё раз, чтобы удалить.'); return; }
        DocStore.del(d.dataset.docdel).then(render); }
    });
  });
}

/* full screen, white, bright: what the officer sees */
function showDoc(d) {
  const url = URL.createObjectURL(d.blob);
  const v = document.createElement('div'); v.className = 'tc-docview'; v.setAttribute('role', 'dialog'); v.setAttribute('aria-label', d.name);
  v.innerHTML = `<div class="tc-docbar"><b>${esc(d.name)}</b><button type="button" class="tc-btn" id="docClose">Закрыть</button></div>
    ${d.type === 'application/pdf' ? `<iframe src="${url}" title="${esc(d.name)}"></iframe>` : `<img src="${url}" alt="${esc(d.name)}">`}
    <p class="tc-docfoot">Яркость экрана — на максимум, чтобы QR считался.</p>`;
  document.body.appendChild(v);
  v.querySelector('#docClose').addEventListener('click', () => { v.remove(); URL.revokeObjectURL(url); });
}
