const fs = require('fs');
const topo = require('topojson-client');
const bboxClip = require('@turf/bbox-clip').default;

const t = JSON.parse(fs.readFileSync('package/countries-10m.json', 'utf8'));
const geo = topo.feature(t, t.objects.countries);
const BBOX = [126.0, 28.5, 148.0, 46.5];   // the window the guide ever shows

// Douglas-Peucker, done here so degenerate rings from clipping are dropped, not thrown on
function perp(p, a, b) {
  const [x, y] = p, [x1, y1] = a, [x2, y2] = b;
  const dx = x2 - x1, dy = y2 - y1;
  if (dx === 0 && dy === 0) return Math.hypot(x - x1, y - y1);
  const tt = ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy);
  const cx = x1 + Math.max(0, Math.min(1, tt)) * dx;
  const cy = y1 + Math.max(0, Math.min(1, tt)) * dy;
  return Math.hypot(x - cx, y - cy);
}
function dp(pts, tol) {
  if (pts.length < 3) return pts;
  let idx = 0, max = 0;
  for (let i = 1; i < pts.length - 1; i++) {
    const d = perp(pts[i], pts[0], pts[pts.length - 1]);
    if (d > max) { max = d; idx = i; }
  }
  if (max <= tol) return [pts[0], pts[pts.length - 1]];
  return dp(pts.slice(0, idx + 1), tol).slice(0, -1).concat(dp(pts.slice(idx), tol));
}
const TOL = 0.006;                                   // ~600 m — fine for a country outline
function ring(r) {
  let s = dp(r, TOL);
  if (s.length && (s[0][0] !== s[s.length - 1][0] || s[0][1] !== s[s.length - 1][1])) s.push(s[0]);
  return s.length >= 4 ? s : null;                   // a polygon ring needs 4 points
}
function polys(coords) {
  const out = [];
  for (const poly of coords) {
    const rings = poly.map(ring).filter(Boolean);
    if (rings.length) out.push(rings);
  }
  return out;
}

const features = [];
for (const f of geo.features) {
  let clipped;
  try { clipped = bboxClip(f, BBOX); } catch (e) { continue; }
  const g = clipped && clipped.geometry;
  if (!g || !g.coordinates || !g.coordinates.length) continue;
  const multi = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
  const kept = polys(multi);
  if (!kept.length) continue;
  features.push({
    type: 'Feature',
    properties: { name: f.properties && f.properties.name },
    geometry: { type: 'MultiPolygon', coordinates: kept }
  });
}

const round = c => Array.isArray(c[0]) ? c.map(round) : [Math.round(c[0] * 1000) / 1000, Math.round(c[1] * 1000) / 1000];
features.forEach(f => { f.geometry.coordinates = round(f.geometry.coordinates); });

const fc = { type: 'FeatureCollection', features };
const json = JSON.stringify(fc);
fs.writeFileSync('japan_basemap.json', json);
const pts = JSON.stringify(features).match(/\[/g).length;
console.log('countries:', features.map(f => f.properties.name).join(', '));
console.log('size KB:', Math.round(json.length / 1024));
