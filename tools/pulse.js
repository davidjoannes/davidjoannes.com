(function(){
  var lists=document.querySelectorAll('[data-pulse]'), counts=document.querySelectorAll('[data-pulse-count]');
  if(!lists.length&&!counts.length) return;
  var s=document.currentScript, base=s?s.getAttribute('data-base')||'':'';
  function esc(t){return String(t).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
  var M=['January','February','March','April','May','June','July','August','September','October','November','December'];
  function nice(d){var p=(d||'').split('-');return p.length===3?M[+p[1]-1]+' '+(+p[2])+', '+p[0]:'';}
  function href(e){return e.path?base+e.path:e.link;}
  function card(e){return '<a class="card" href="'+esc(href(e))+'"><div class="im">'+(e.image?'<img src="'+esc(e.image)+'" alt="" loading="lazy">':'')+'</div><div class="k">Missions Pulse · '+nice(e.date)+'</div><h3>'+esc(e.title)+'</h3></a>';}
  function ep(e){var m=e.title.match(/^#(\d+):\s*(.*)/);return '<a href="'+esc(href(e))+'"><span class="n">'+(m?'Episode '+m[1]:'Episode')+'</span><span class="t">'+esc(m?m[2]:e.title)+'</span></a>';}
  fetch(base+'/assets/pulse.json',{cache:'no-cache'}).then(function(r){return r.ok?r.json():null;}).then(function(d){
    if(!d||!d.episodes||!d.episodes.length) return;
    [].forEach.call(lists,function(el){
      var n=+el.getAttribute('data-n')||3, f=el.getAttribute('data-pulse')==='ep'?ep:card;
      el.innerHTML=d.episodes.slice(0,n).map(f).join('');
    });
    if(d.count) [].forEach.call(counts,function(el){el.textContent=d.count;});
  }).catch(function(){});
})();
