import {geoMercator, geoPath, geoContains, geoBounds, geoCentroid, geoArea, geoGraticule10} from 'd3-geo';
import {feature} from 'topojson-client';
const NS = 'http://www.w3.org/2000/svg';
let W = null;
function world(src) {
  if (!W) W = fetch(src).then(r => r.json()).then(t => {
    const f = feature(t, t.objects.countries).features.filter(x => x.geometry);
    f.forEach(x => { x.c = geoCentroid(x); x.a = geoArea(x); });
    return f;
  });
  return W;
}
const NAMES = {'United States of America': 'United States', 'Dem. Rep. Congo': 'DR Congo', 'Central African Rep.': 'Central African Rep.', 'Bosnia and Herz.': 'Bosnia', 'Dominican Rep.': 'Dominican Rep.', 'S. Sudan': 'South Sudan', 'Solomon Is.': 'Solomon Islands', 'Fr. Polynesia': 'French Polynesia', 'Eq. Guinea': 'Equatorial Guinea', 'W. Sahara': 'Western Sahara', 'Marshall Is.': 'Marshall Islands', 'Cook Is.': 'Cook Islands', 'eSwatini': 'Eswatini', 'Côte d\'Ivoire': 'Ivory Coast'};
const nm = f => NAMES[f.properties.name] || f.properties.name;
function el(tag, attrs, parent) { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; }
function spanFor(g, home, w, h) {
  if (g.r >= 3) return 20;
  if (g.r === 2) return 26;
  if (g.r === 1 && home) {
    const b = geoBounds(home); let dx = b[1][0] - b[0][0]; if (dx < 0) dx += 360;
    const dy = (b[1][1] - b[0][1]) * Math.min(1.6, w / h);
    return Math.max(12, Math.min(75, Math.max(dx, dy) * 1.5));
  }
  return g.r === 1 ? 30 : 62;
}
export async function render(box, g, src) {
  const feats = await world(src);
  const pt = [g.lon, g.lat];
  let home = feats.find(f => geoContains(f, pt)) || null;
  // coastal and island places can fall just outside the simplified outlines: look a little way around them
  for (let r = 0.25; !home && r <= 1.5; r += 0.25) for (let k = 0; k < 12 && !home; k++) {
    const q = [g.lon + r * Math.cos(k * Math.PI / 6) / Math.cos(g.lat * Math.PI / 180), g.lat + r * Math.sin(k * Math.PI / 6)];
    home = feats.find(f => geoContains(f, q)) || null;
  }
  let near = home;
  if (!near) { let d = 1e9; for (const f of feats) { const e = Math.hypot(f.c[0] - g.lon, f.c[1] - g.lat); if (e < d) { d = e; near = f; } } if (d > 8) near = null; }
  box.innerHTML = '';
  const wrap = document.createElement('div'); wrap.className = 'hm-wrap'; box.appendChild(wrap);
  const w = Math.max(260, box.clientWidth || wrap.clientWidth || 600), h = w < 560 ? 230 : 290;
  const svg = el('svg', {viewBox: `0 0 ${w} ${h}`, width: '100%', height: h, role: 'img', 'aria-label': 'Map showing ' + g.n + (near && nm(near) !== g.n ? ', ' + nm(near) : '')}, wrap);
  let span = spanFor(g, home, w, h);
  if (!home || home.a < 6e-5) span = Math.max(span, 34);  // small islands: zoom out enough to show neighbors
  const base = w / (span * Math.PI / 180);
  const st = {lon: g.lon, lat: Math.max(-70, Math.min(76, g.lat)), k: 1};
  const proj = geoMercator().clipExtent([[-4, -4], [w + 4, h + 4]]);
  const path = geoPath(proj);
  el('rect', {width: w, height: h, class: 'hm-sea'}, svg);
  const gr = el('path', {class: 'hm-grat'}, svg);
  const land = el('g', {}, svg);
  const paths = feats.map(f => el('path', {class: 'hm-land' + (f === home ? ' hm-home' : '')}, land));
  const labels = el('g', {class: 'hm-labels'}, svg);
  const pin = el('g', {class: 'hm-pin'}, svg);
  el('circle', {r: 14, class: 'hm-pulse'}, pin); el('circle', {r: 5.5, class: 'hm-dot'}, pin);
  const pl = el('text', {class: 'hm-place', dy: '0.35em'}, svg); pl.textContent = g.n;
  function draw() {
    proj.rotate([-st.lon, 0]).center([0, st.lat]).scale(base * st.k).translate([w / 2, h / 2]);
    gr.setAttribute('d', path(geoGraticule10()) || '');
    feats.forEach((f, i) => paths[i].setAttribute('d', path(f) || ''));
    labels.innerHTML = '';
    const p = proj(pt), taken = [[p[0], p[1]]];
    pin.setAttribute('transform', `translate(${p[0]},${p[1]})`);
    const right = p[0] < w - 120;
    pl.setAttribute('x', right ? p[0] + 11 : p[0] - 11); pl.setAttribute('y', p[1]); pl.setAttribute('text-anchor', right ? 'start' : 'end');
    pl.style.display = (p[0] > -20 && p[0] < w + 20 && p[1] > -20 && p[1] < h + 20) ? '' : 'none';
    const px = base * st.k * base * st.k;
    const cands = feats.filter(f => f === home || f.a * px > 2200).map(f => ({f, q: proj(f === home ? (f.c) : f.c)}))
      .filter(o => o.q && o.q[0] > 30 && o.q[0] < w - 30 && o.q[1] > 14 && o.q[1] < h - 10)
      .sort((a, b) => (b.f === home) - (a.f === home) || b.f.a - a.f.a);
    let n = 0;
    for (const o of cands) {
      if (n >= 9) break;
      if (taken.some(t => Math.abs(t[0] - o.q[0]) < 70 && Math.abs(t[1] - o.q[1]) < 18)) continue;
      const t = el('text', {x: o.q[0], y: o.q[1], class: 'hm-cn' + (o.f === home ? ' hm-cn-home' : ''), 'text-anchor': 'middle'}, labels);
      t.textContent = nm(o.f); taken.push(o.q); n++;
    }
  }
  draw();
  const ctr = document.createElement('div'); ctr.className = 'hm-ctr';
  ctr.innerHTML = '<button type="button" aria-label="Zoom in">+</button><button type="button" aria-label="Zoom out">&minus;</button><button type="button" aria-label="Recenter" class="hm-re"><svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><circle cx="12" cy="12" r="3" fill="currentColor"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4" stroke="currentColor" stroke-width="2"/></svg></button>';
  wrap.appendChild(ctr);
  const [zi, zo, re] = ctr.querySelectorAll('button');
  let raf = 0; const redraw = () => { if (!raf) raf = requestAnimationFrame(() => { raf = 0; draw(); }); };
  zi.onclick = () => { st.k = Math.min(st.k * 1.6, 12); redraw(); };
  zo.onclick = () => { st.k = Math.max(st.k / 1.6, 0.18); redraw(); };
  re.onclick = () => { st.lon = g.lon; st.lat = Math.max(-70, Math.min(76, g.lat)); st.k = 1; redraw(); };
  // drag to pan; on touch screens the map takes over touch only after a first tap, so page scrolling still works
  const touch = matchMedia('(pointer: coarse)').matches;
  if (touch) { const hint = document.createElement('div'); hint.className = 'hm-hint'; hint.textContent = 'Tap to explore'; wrap.appendChild(hint); }
  let drag = null;
  svg.addEventListener('pointerdown', e => {
    if (e.pointerType === 'touch' && !wrap.classList.contains('hm-live')) return;
    drag = {x: e.clientX, y: e.clientY, lon: st.lon, lat: st.lat}; svg.setPointerCapture(e.pointerId); wrap.classList.add('hm-drag');
  });
  svg.addEventListener('pointermove', e => {
    if (!drag) return;
    const s = base * st.k * (svg.getBoundingClientRect().width / w);
    st.lon = drag.lon - (e.clientX - drag.x) / s * 180 / Math.PI;
    st.lat = Math.max(-75, Math.min(80, drag.lat + (e.clientY - drag.y) / s * 180 / Math.PI * Math.cos(st.lat * Math.PI / 180)));
    redraw();
  });
  const end = () => { drag = null; wrap.classList.remove('hm-drag'); };
  svg.addEventListener('pointerup', end); svg.addEventListener('pointercancel', end);
  svg.addEventListener('click', () => { if (touch && !wrap.classList.contains('hm-live')) wrap.classList.add('hm-live'); });
  svg.addEventListener('dblclick', e => { e.preventDefault(); st.k = Math.min(st.k * 1.6, 12); redraw(); });
  const cap = document.createElement('p'); cap.className = 'hm-cap';
  const cn = near ? nm(near) : '';
  cap.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13" aria-hidden="true"><path d="M12 2a7 7 0 0 0-7 7c0 5 7 13 7 13s7-8 7-13a7 7 0 0 0-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z" fill="currentColor"/></svg>';
  cap.appendChild(document.createTextNode(cn && cn !== g.n ? g.n + ', ' + cn : g.n));
  box.appendChild(cap);
}
