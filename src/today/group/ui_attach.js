/* ---------- tickets: a file or a link; private unless shared ---------- */
const LINKS = 'japan2026.links.v1';
const localLinks = () => { try { return JSON.parse(localStorage.getItem(LINKS) || '{}') || {}; } catch (e) { return {}; } };
const putLocalLinks = v => { try { localStorage.setItem(LINKS, JSON.stringify(v)); } catch (e) {} };
const uid = () => (crypto.randomUUID ? crypto.randomUUID() : Date.now().toString(36) + Math.random().toString(36).slice(2));

function openAttach(ref) {                     // ref: 'bk:<id>' | 'mb:<id>'
  const me = Api.me(), bk = ref.slice(3);
  const mine = me ? (Api.state().attachments || []).filter(a => a.ref === ref && a.member === me.id) : (localLinks()[bk] || []).map(l => ({ ...l, kind: 'link' }));
  const others = me ? (Api.state().attachments || []).filter(a => a.ref === ref && a.member !== me.id && a.shared) : [];
  const nameOf = id => ((Api.state() || { members: [] }).members.find(m => m.id === id) || {}).name || '';
  const row = (a, own) => `<div class="tc-flrow"><button type="button" class="tc-act" data-open="${esc(a.id)}">${icon(a.kind === 'link' ? 'share' : 'tix')}
      <span>${esc(a.kind === 'link' ? a.site || a.name : a.name)}<small>${own ? (a.shared ? 'видит группа' : 'только вы') : 'от ' + esc(nameOf(a.member))}</small></span></button>
      ${own && me ? `<label class="tc-share"><input type="checkbox" switch data-share="${esc(a.id)}"${a.shared ? ' checked' : ''} aria-label="Показать группе"></label>` : ''}
      ${own ? `<button type="button" class="tc-x" data-del="${esc(a.id)}" aria-label="Удалить">${icon('close')}</button>` : ''}</div>`;
  sheet('Билет', `
    ${mine.length ? `<div class="tc-group">${mine.map(a => row(a, true)).join('')}</div>` : ''}
    ${others.length ? `<span class="tc-sech">От группы</span><div class="tc-group">${others.map(a => row(a, false)).join('')}</div>` : ''}
    <div id="atWarn" class="tc-card tc-note" hidden><b>Ссылка на бронь часто работает как ключ</b>
      <span class="tc-sub">По ней можно открыть и иногда отменить бронь. Лучше покажите PDF без QR или данные текстом.</span>
      <button type="button" class="tc-btn" id="atWarnGo">Всё равно показать группе<span id="atWarnName"></span></button></div>
    <label class="tc-btn wide">${icon('clip')}Файл — PDF или картинка<input type="file" id="atFile" accept="image/*,application/pdf" hidden></label>
    <div class="tc-form2">${fld('atUrl', 'Или ссылка на бронь', '', 'url', 'placeholder="https://www.highwaybus.com/…"')}<button type="button" class="tc-btn primary" id="atAdd">${icon('plus')}Добавить</button></div>
    <p class="tc-warn" id="atMsg" role="status"></p>`, m => {
    const msg = t => { m.querySelector('#atMsg').textContent = t; };
    m.querySelector('#atAdd').addEventListener('click', () => {
      const url = m.querySelector('#atUrl').value.trim(), s = Group.siteOf(url);
      if (!s) { msg('Нужна ссылка, начинающаяся с https://'); return; }
      const a = { id: 'a-' + uid(), ref, kind: 'link', url, name: s.site, site: s.site, shared: false };
      if (me) Api.call('save_attachment', { p_a: a }, st => { st.attachments.push({ ...a, member: me.id }); });
      else { const all = localLinks(); all[bk] = (all[bk] || []).concat([{ id: a.id, url, name: s.site, site: s.site }]); putLocalLinks(all); }
      openAttach(ref); renderShell();
    });
    m.querySelector('#atFile').addEventListener('change', async e => {
      const f = e.target.files && e.target.files[0]; if (!f) return;
      if (!/^(image\/|application\/pdf$)/.test(f.type)) { msg('Только PDF или картинка.'); return; }
      if (!me) { await ticketPut(bk, f); await refreshTickets(); closeSheet(); renderShell(); return; }
      const id = 'a-' + uid(), path = `${me.id}/${ref.replace(':', '-')}/${id}.${f.type === 'application/pdf' ? 'pdf' : 'img'}`;
      try { await ticketPut('att:' + id, f); } catch (err) {}
      try { await Api.upload(path, f); } catch (err) { msg('Нет сети — файл сохранён на телефоне, отправьте позже.'); return; }
      const a = { id, ref, kind: 'file', path, name: f.name.slice(0, 80), site: '', shared: false };
      Api.call('save_attachment', { p_a: a }, st => { st.attachments.push({ ...a, member: me.id }); });
      openAttach(ref); renderShell();
    });
    let pending = null;
    m.querySelectorAll('[data-share]').forEach(sw => sw.addEventListener('change', () => {
      const a = Api.state().attachments.find(x => x.id === sw.dataset.share);
      if (sw.checked && a.kind === 'link' && !a.shared) { sw.checked = false; pending = a;      // the warning names the link it is about: a second tap elsewhere retargets it visibly
        m.querySelector('#atWarnName').textContent = ': «' + (a.name || a.site || 'ссылка') + '»'; m.querySelector('#atWarn').hidden = false; return; }
      const next = { ...a, shared: sw.checked }; Api.call('save_attachment', { p_a: next }, st => { Object.assign(st.attachments.find(x => x.id === a.id), next); });
    }));
    m.querySelector('#atWarnGo').addEventListener('click', () => {
      if (!pending) return; const next = { ...pending, shared: true };
      Api.call('save_attachment', { p_a: next }, st => { Object.assign(st.attachments.find(x => x.id === next.id), next); }); openAttach(ref);
    });
    m.querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', () => twoTap(b, '?', () => {
      if (me) {
        const a = Api.state().attachments.find(x => x.id === b.dataset.del);
        if (a && a.kind === 'file' && a.path && a.member === me.id) Api.remove(a.path).catch(() => {});   // the file goes too, not just the row
        Api.call('delete_attachment', { p_id: b.dataset.del }, st => { st.attachments = st.attachments.filter(x => x.id !== b.dataset.del); });
      }
      else { const all = localLinks(); all[bk] = (all[bk] || []).filter(x => x.id !== b.dataset.del); putLocalLinks(all); }
      openAttach(ref);
    })));
    m.querySelectorAll('[data-open]').forEach(b => b.addEventListener('click', async () => {
      const a = [...mine, ...others].find(x => x.id === b.dataset.open);
      if (a.kind === 'link') { const u = Core.safeUrl(a.url); if (u) window.open(u, '_blank', 'noopener'); return; }
      let rec = null; try { rec = await ticketGet('att:' + a.id); } catch (e) {}
      if (!rec) { try { const blob = await Api.download(a.path); await ticketPut('att:' + a.id, new File([blob], a.name, { type: blob.type })); } catch (e) { msg('Нет сети — файл ещё не на телефоне.'); return; } }
      closeSheet(); showTicket('att:' + a.id);
    }));
  });
}
function wireAttach(root) {
  root.querySelectorAll('[data-attach-ref]').forEach(b => b.addEventListener('click', () => openAttach(b.dataset.attachRef)));
  root.querySelectorAll('[data-link]').forEach(b => b.addEventListener('click', () => openAttach('bk:' + b.dataset.link)));
}

/* links saved for a booking: mine and the group's shared ones when signed in, else the ones kept on this phone */
function attachLinksFor(bk) {
  const me = typeof Api !== 'undefined' && Api.me();
  if (me) return ((Api.state() || {}).attachments || []).filter(a => a.ref === 'bk:' + bk && a.kind === 'link' && (a.member === me.id || a.shared));
  return (localLinks()[bk] || []);
}
