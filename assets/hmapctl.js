/* Missions History Today maps: one map at a time. Picking a date (or tapping an entry) opens its map at once;
   while scrolling, the entry nearest the middle of the screen opens its map after it has stayed there for a second. */
(function () {
  var rows = [].slice.call(document.querySelectorAll('.h-row[data-geo]'));
  if (!rows.length || !window.fetch || !window.requestAnimationFrame) return;
  var me = document.currentScript, B = (me && me.getAttribute('data-base')) || '', V = (me && me.getAttribute('data-v')) || '1';
  var lib = null, active = null, timer = null, lock = 0;
  var still = window.matchMedia && matchMedia('(prefers-reduced-motion: reduce)').matches;
  function load() {
    if (!lib) lib = new Promise(function (ok, no) { var s = document.createElement('script'); s.src = B + '/assets/hmap.js?v=' + V; s.onload = function () { ok(window.HMap); }; s.onerror = no; document.head.appendChild(s); });
    return lib;
  }
  function geo(row) { var p = row.getAttribute('data-geo').split('|'); return {lat: +p[0], lon: +p[1], r: +p[2], n: p[3]}; }
  function close(keepView) {
    if (!active) return;
    var box = active.box, h = box.offsetHeight, top = box.getBoundingClientRect().top;
    active.row.classList.remove('h-mapped'); active = null;
    if (keepView && top < window.innerHeight * 0.45) { box.remove(); if (h) { lock = Date.now(); window.scrollBy(0, -h); } return; }
    if (still) { box.remove(); return; }
    box.style.height = h + 'px'; box.offsetHeight; box.classList.remove('on'); box.style.height = '0px';
    setTimeout(function () { box.remove(); }, 450);
  }
  function open(row) {
    if (active && active.row === row) return;
    close(true);
    var box = document.createElement('div'); box.className = 'h-map';
    row.querySelector('.h-body').appendChild(box); row.classList.add('h-mapped');
    var me = active = {row: row, box: box};
    load().then(function (H) {
      if (active !== me) return;
      return H.render(box, geo(row), B + '/assets/world.json?v=' + V).then(function () {
        if (active !== me) return;
        var inner = box.scrollHeight;
        if (still) { box.classList.add('on'); box.style.height = 'auto'; return; }
        requestAnimationFrame(function () { box.classList.add('on'); box.style.height = inner + 'px'; setTimeout(function () { if (active === me) box.style.height = 'auto'; }, 480); });
      });
    }).catch(function () { if (active === me) { box.remove(); active = null; } });
  }
  function firstOfDay(el) {
    if (!el) return null;
    var d = el.getAttribute('data-d'), r = el;
    while (r && r.classList && r.classList.contains('h-row') && r.getAttribute('data-d') === d) { if (r.hasAttribute('data-geo')) return r; r = r.nextElementSibling; while (r && !r.classList.contains('h-row')) r = r.nextElementSibling; }
    return null;
  }
  function fromHash() {
    var h = decodeURIComponent(location.hash.slice(1)).toLowerCase();
    if (!/^[a-z]+-\d+$/.test(h)) { if (active && active.row.offsetParent === null) close(false); return; }
    var r = firstOfDay(document.getElementById(h));
    if (r) setTimeout(function () { open(r); }, 60);
  }
  function pick() {
    if (Date.now() - lock < 600) return;
    var mid = window.innerHeight * 0.45, best = null, bd = 1e9;
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i]; if (r.offsetParent === null) continue;
      var b = r.getBoundingClientRect(); if (b.bottom < 0 || b.top > window.innerHeight) continue;
      var body = r.querySelector('p').getBoundingClientRect(), c = (body.top + body.bottom) / 2, d = Math.abs(c - mid);
      if (b.top <= mid && body.bottom >= mid) d = 0;
      if (d < bd) { bd = d; best = r; }
    }
    if (best && bd < window.innerHeight * 0.3) open(best);
  }
  window.addEventListener('scroll', function () { clearTimeout(timer); timer = setTimeout(pick, 1000); }, {passive: true});
  window.addEventListener('hashchange', fromHash);
  document.addEventListener('click', function (e) {
    var t = e.target; if (t.closest('a,button,.h-map')) return;
    var r = t.closest('.h-row[data-geo]'); if (r) open(r);
  });
  [].forEach.call(document.querySelectorAll('.h-months button, .h-card'), function (b) { b.addEventListener('click', function () { setTimeout(function () { if (active && active.row.offsetParent === null) close(false); }, 0); }); });
  if (location.hash) fromHash();
})();
