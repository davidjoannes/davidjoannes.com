import fs from 'fs';
import * as ts from 'topojson-simplify';
import * as tc from 'topojson-client';
const t = JSON.parse(fs.readFileSync('node_modules/world-atlas/countries-50m.json'));
let p = ts.presimplify(t);
console.log('transform', !!p.transform, p.arcs[0].slice(0,2));
let kept=0;
for (const a of p.arcs) {
  let x0=1e9,x1=-1e9,y0=1e9,y1=-1e9;
  for (const q of a){x0=Math.min(x0,q[0]);x1=Math.max(x1,q[0]);y0=Math.min(y0,q[1]);y1=Math.max(y1,q[1]);}
  if (Math.max(x1-x0,y1-y0) < 1.2) { for (const q of a) if (q[2] < 0.01) q[2] = Math.max(q[2], 0.0004 > q[2] ? Math.min(0.0101, q[2]*30) : q[2]); kept++; }
}
p = ts.simplify(p, 0.01);
p = tc.quantize(p, 1e4); delete p.bbox;
const s = JSON.stringify(p); fs.writeFileSync('world2.json', s);
console.log(kept, s.length);
// small rings can flip direction when simplified, which makes them cover the whole globe; turn those back
import * as tsv from 'topojson-server';
import * as d3 from 'd3-geo';
const fc = tc.feature(p, p.objects.countries);
let fixed = 0;
for (const f of fc.features) {
  const g = f.geometry; if (!g) continue;
  const polys = g.type === 'Polygon' ? [g.coordinates] : g.coordinates;
  const keep = [];
  for (const poly of polys) {
    const a = d3.geoArea({type: 'Polygon', coordinates: poly});
    if (a > 2 * Math.PI) { poly.forEach(r => r.reverse()); fixed++; }
    const a2 = d3.geoArea({type: 'Polygon', coordinates: poly});
    if (a2 > 1e-9 && a2 < 2 * Math.PI) keep.push(poly);
  }
  f.geometry = keep.length ? {type: 'MultiPolygon', coordinates: keep} : null;
}
let out = tsv.topology({countries: {type: 'FeatureCollection', features: fc.features.filter(f => f.geometry)}}, 1e4);
const s2 = JSON.stringify(out); fs.writeFileSync('world.json', s2);
console.log('fixed', fixed, s2.length);
