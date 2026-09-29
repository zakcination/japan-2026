/* ---------- weather tile on «Сейчас»: the day hour by hour, like the Weather app ----------
   Hourly forecast from open-meteo (free, no key) for the day's place, cached on the phone for an hour.
   Hourly data exists only ~16 days ahead; before that the tile shows the typical weather for the date. */
const HW_KEY = 'japan2026.hourly.v1', HW_AHEAD = 16;
const WX_ICON = c => c == null ? '·' : c === 0 ? '☀️' : c <= 2 ? '🌤' : c === 3 ? '☁️' : c <= 48 ? '🌫' : c <= 57 ? '🌦'
  : c <= 67 ? '🌧' : c <= 77 ? '❄️' : c <= 82 ? '🌧' : '⛈';
const WX_WORD = c => c == null ? '' : c === 0 ? 'ясно' : c <= 2 ? 'малооблачно' : c === 3 ? 'облачно' : c <= 48 ? 'туман'
  : c <= 57 ? 'морось' : c <= 67 ? 'дождь' : c <= 77 ? 'снег' : c <= 82 ? 'ливни' : 'гроза';
const hwAll = () => { try { return JSON.parse(localStorage.getItem(HW_KEY) || '{}') || {}; } catch (e) { return {}; } };
const hwKey = day => `${dateOf(day)}@${day.sun ? day.sun.join(',') : ''}`;
let hwBusy = {};

/* the cached hours for a day: {h: [0..23], t: [°C], p: [% rain], c: [code]} or null; refreshes in the background */
function hourlyFor(day) {
  if (!day.sun) return null;
  const k = hwKey(day), all = hwAll(), hit = all[k];
  const days = Math.round((Date.parse(dateOf(day)) - Date.parse(japanNow().date)) / 864e5);
  const due = !hit || Date.now() - hit.at > 3600e3;
  if (due && days >= 0 && days <= HW_AHEAD && !hwBusy[k] && navigator.onLine !== false) {
    hwBusy[k] = true;
    const q = `latitude=${day.sun[0]}&longitude=${day.sun[1]}&hourly=temperature_2m,precipitation_probability,weather_code`
      + `&timezone=Asia%2FTokyo&start_date=${dateOf(day)}&end_date=${dateOf(day)}`;
    fetch('https://api.open-meteo.com/v1/forecast?' + q).then(r => r.ok ? r.json() : null).then(j => {
      const H = j && j.hourly;
      if (!H || !Array.isArray(H.time) || H.time.length < 24) return;
      const a = hwAll();
      a[k] = { at: Date.now(), h: H.time.map(t => +String(t).slice(11, 13)), t: H.temperature_2m.map(v => v == null ? null : Math.round(v)),
               p: (H.precipitation_probability || []).map(v => v == null ? null : Math.round(v)), c: H.weather_code || [] };
      Object.keys(a).filter(x => x.slice(0, 10) < japanNow().date).forEach(x => delete a[x]);   // drop past days
      try { localStorage.setItem(HW_KEY, JSON.stringify(a)); } catch (e) {}
      window.dispatchEvent(new Event('japan2026:wx'));
    }).catch(() => {}).finally(() => { delete hwBusy[k]; });
  }
  return hit || null;
}

function weatherTileHTML(x) {
  const day = x.cday, evs = x.cevs.filter(e => !e.skip && !e.auto && !e.bad);
  const H = hourlyFor(day);
  const now = Math.max(0, Math.min(23, Math.floor(((x.c.min % 1440) + 1440) % 1440 / 60)));
  if (!H) {                                     // no hourly forecast yet: the day's typical weather
    const d = weatherFor(day);
    if (!d) return '';
    const on = Core.addDays(dateOf(day), -HW_AHEAD);
    return `<div class="tc-mini tc-wx" id="tcWx" role="group" aria-label="Погода: ${d.hi}°, ночью ${d.lo ?? '—'}°">
      <span class="tc-mini-lbl">${WX_ICON(d.code)} Погода</span><b>${d.hi}°<span class="lo">/${d.lo ?? '—'}°</span></b>
      <small>${d.forecast ? esc(WX_WORD(d.code)) : 'обычно в эти дни'}${d.prob != null ? ' · дождь ' + d.prob + '%' : ''}</small>
      <small class="tc-wx-note">по часам — с ${Core.ddmmyyyy(on).slice(0, 5)}</small></div>`;
  }
  // the day's span: from the first stop (or now) to the last one, 4 steps across it
  const first = evs.length ? Math.floor(evs[0].ns / 60) : 7, last = evs.length ? Math.ceil(evs[evs.length - 1].ne / 60) : 21;
  const from = Math.max(now, Math.min(first, 23)), to = Math.max(from + 1, Math.min(last, 23));
  const step = Math.max(1, Math.round((to - from) / 3));
  const hours = [0, 1, 2, 3].map(i => Math.min(23, from + i * step)).filter((h, i, a) => a.indexOf(h) === i);
  const rainAt = H.h.findIndex((h, i) => h >= now && h <= to && (H.p[i] || 0) >= 50);
  const stopAt = h => evs.find(e => Math.floor(e.ns / 60) <= h && h < Math.ceil(e.ne / 60));
  const hint = rainAt >= 0 ? `дождь с ${String(H.h[rainAt]).padStart(2, '0')}:00 — зонт` : 'без дождя до вечера';
  return `<div class="tc-mini tc-wx" id="tcWx" role="group" aria-label="Погода: сейчас ${H.t[now]}°, ${esc(WX_WORD(H.c[now]))}; ${hint}">
    <span class="tc-mini-lbl">${WX_ICON(H.c[now])} Погода</span><b>${H.t[now]}°</b>
    <div class="tc-wx-hours">${hours.map(h => { const s = stopAt(h);
      return `<span class="${h === now ? 'now' : ''}${s ? ' stop' : ''}" title="${s ? esc(s.t) : ''}"><small>${h === now ? 'сейч.' : h}</small>
        <i>${WX_ICON(H.c[h])}</i><em>${H.t[h]}°</em></span>`; }).join('')}</div>
    <small>${hint}</small></div>`;
}
