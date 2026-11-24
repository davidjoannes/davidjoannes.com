#!/usr/bin/env python3
"""Build David Joannes's media kit PDF from content.json (letter size, site colors and fonts)."""
import json, os, sys, html
HERE = os.path.dirname(os.path.abspath(__file__))
FONTS = sys.argv[1] if len(sys.argv) > 1 else '/tmp/fi/node_modules/@fontsource'
COVERS = sys.argv[2] if len(sys.argv) > 2 else '/home/claude/djrepo/assets/books/flat'
OUT = sys.argv[3] if len(sys.argv) > 3 else os.path.join(HERE, 'david-joannes-media-kit.pdf')
C = json.load(open(os.path.join(HERE, 'content.json')))
e = html.escape
P = 'file://' + os.path.join(HERE, 'photos') + '/'
def face(fam, w, f, style='normal'): return f"@font-face{{font-family:{fam};font-weight:{w};font-style:{style};src:url(file://{FONTS}/{f})}}"
css = '\n'.join([face('Sora', 600, 'sora/files/sora-latin-600-normal.woff2'), face('Sora', 700, 'sora/files/sora-latin-700-normal.woff2'), face('Sora', 800, 'sora/files/sora-latin-800-normal.woff2'),
                 face('Inter', 400, 'inter/files/inter-latin-400-normal.woff2'), face('Inter', 500, 'inter/files/inter-latin-500-normal.woff2'), face('Inter', 600, 'inter/files/inter-latin-600-normal.woff2'), face('Inter', 700, 'inter/files/inter-latin-700-normal.woff2'),
                 face('Serif4', 400, 'source-serif-4/files/source-serif-4-latin-400-normal.woff2'), face('Serif4', 600, 'source-serif-4/files/source-serif-4-latin-600-normal.woff2'), face('Serif4', 400, 'source-serif-4/files/source-serif-4-latin-400-italic.woff2', 'italic')]) + '''
@page{size:8.5in 11in;margin:0}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:Inter;color:#0B1622;font-size:11.2pt;line-height:1.55;-webkit-print-color-adjust:exact;print-color-adjust:exact}
.pg{width:8.5in;height:11in;position:relative;overflow:hidden;page-break-after:always;background:#fff}
.pg.soft{background:#F4F5F7}
.rail{position:absolute;left:0;top:0;bottom:0;width:.34in;background:#D12B1F}
.rail.r{left:auto;right:0;background:#0B1622}
.in{position:absolute;left:.95in;right:.8in;top:.8in;bottom:.9in}
.ft{position:absolute;left:.95in;right:.8in;bottom:.42in;display:flex;justify-content:space-between;font-family:Inter;font-weight:700;font-size:7.6pt;letter-spacing:.16em;text-transform:uppercase;color:#8a93a0}
h2{font-family:Sora;font-weight:800;font-size:25pt;line-height:1.08;letter-spacing:-.02em;color:#0B1622;margin-bottom:.16in}
h2 span{color:#D12B1F}
h3{font-family:Sora;font-weight:700;font-size:13.5pt;line-height:1.25;margin-bottom:.05in}
.eye{font-family:Inter;font-weight:700;font-size:8.4pt;letter-spacing:.2em;text-transform:uppercase;color:#D12B1F;margin-bottom:.1in}
p{margin-bottom:.13in}
.lede{font-family:Serif4;font-size:13.5pt;line-height:1.45;color:#27323f;margin-bottom:.2in}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:.34in}
/* cover */
.cover{background:#0B1622;color:#fff}
.cover .grid,.end .grid{position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.045) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.045) 1px,transparent 1px);background-size:.55in .55in}
.cover .glow,.end .glow{position:absolute;right:-3in;top:-3.4in;width:8in;height:8in;border-radius:50%;background:radial-gradient(circle,#D12B1F 0%,rgba(209,43,31,.3) 40%,rgba(209,43,31,0) 68%);opacity:.6}
.cover .top{position:absolute;left:0;right:0;top:0;height:.62in;background:#000;display:flex;align-items:center;justify-content:center;font-family:Inter;font-weight:700;font-size:9.5pt;letter-spacing:.3em;text-transform:uppercase}
.cover .ph{position:absolute;right:0;top:.62in;width:4.3in;bottom:1.05in;background:url(PHOTOheadshot) 60% 18%/cover}
.cover .ph:after{content:"";position:absolute;inset:0;background:linear-gradient(90deg,#0B1622 0%,rgba(11,22,34,.5) 26%,rgba(11,22,34,0) 60%),linear-gradient(0deg,#0B1622 0%,rgba(11,22,34,0) 22%)}
.cover .tx{position:absolute;left:.75in;top:3.2in;width:4.6in}
.cover .eye{color:#e0b25a;font-size:9.5pt;margin-bottom:.2in}
.cover h1{font-family:Sora;font-weight:800;font-size:62pt;line-height:.96;letter-spacing:-.03em}
.cover h1 span{color:#ff5a4d}
.cover .mk{display:inline-block;margin-top:.34in;background:#D12B1F;color:#fff;font-family:Inter;font-weight:700;font-size:11pt;letter-spacing:.24em;text-transform:uppercase;padding:.1in .22in;border-radius:999px}
.cover .tag{margin-top:.3in;font-family:Serif4;font-weight:600;font-size:15pt;line-height:1.35;color:rgba(255,255,255,.9)}
.cover .bot,.end .bot{position:absolute;left:0;right:0;bottom:0;height:1.05in;background:#000;display:flex;align-items:center;justify-content:space-between;padding:0 .75in;font-family:Inter;font-weight:700;font-size:9pt;letter-spacing:.18em;text-transform:uppercase;color:rgba(255,255,255,.85);border-top:.07in solid #D12B1F}
/* contents */
.toc{list-style:none;margin:.05in 0 .32in;columns:2;column-gap:.4in}
.toc li{padding:.055in 0;border-bottom:1px solid #e2e5ea;font-weight:600;font-size:10.6pt;break-inside:avoid;display:flex;gap:.12in}
.toc li b{color:#D12B1F;font-family:Sora;font-weight:700;width:.26in}
.sig{font-family:Serif4;font-style:italic;font-size:17pt;margin-top:.06in}
.card{background:#0B1622;color:#fff;border-radius:.16in;padding:.24in .28in;display:flex;gap:.24in;align-items:center;position:absolute;left:0;right:0;bottom:0}
.card img{width:1.05in;height:1.05in;border-radius:50%;object-fit:cover;object-position:50% 12%;flex:none;border:3px solid #D12B1F}
.card p{margin:0;font-size:9.8pt;line-height:1.5;color:rgba(255,255,255,.9)}
.card b{display:block;font-family:Inter;font-size:7.6pt;letter-spacing:.18em;text-transform:uppercase;color:#e0b25a;margin-bottom:.05in}
/* about */
.facts{background:#F4F5F7;border-radius:.14in;padding:.2in .24in}
.facts div{padding:.065in 0;border-bottom:1px solid #dfe3e8;font-size:9.6pt;line-height:1.4}
.facts div:last-child{border-bottom:0}
.facts b{display:block;font-size:7.2pt;letter-spacing:.16em;text-transform:uppercase;color:#D12B1F}
.about{display:grid;grid-template-columns:1fr 2.25in;gap:.34in}
.about p{font-size:11pt;line-height:1.6}
.shot{width:100%;height:2.25in;object-fit:cover;object-position:50% 10%;border-radius:.14in;margin-bottom:.18in;display:block}
/* intro bios */
.bio{border-left:.05in solid #D12B1F;padding:.02in 0 .02in .22in;margin-bottom:.4in}
.bio p{margin:0;font-family:Serif4;font-size:14pt;line-height:1.5}
.bio b{display:block;font-family:Inter;font-size:7.6pt;letter-spacing:.18em;text-transform:uppercase;color:#D12B1F;margin-bottom:.06in}
.hd{display:flex;gap:.14in;align-items:baseline;padding:.07in 0;border-top:1px solid #dfe3e8;font-family:Sora;font-weight:700;font-size:11.5pt}
.hd b{flex:none;width:.85in;font-family:Inter;font-size:7.4pt;letter-spacing:.16em;text-transform:uppercase;color:#D12B1F}
.note{font-size:9.6pt;line-height:1.45;color:#3a4654;margin:.08in 0 0;padding-top:.08in;border-top:1px solid #dfe3e8}
/* work */
.shelf{display:grid;grid-template-columns:repeat(6,1fr);gap:.14in;margin:.2in 0 .3in}
.shelf img{width:100%;display:block;border-radius:3px;box-shadow:0 6px 14px rgba(11,22,34,.25)}
.bl{list-style:none;margin-bottom:.4in}
.bl li{font-size:10.8pt;line-height:1.4;padding:.085in 0;border-bottom:1px solid #e2e5ea}
.bl li i{font-style:normal;color:#5b6672}
.box{background:#0B1622;color:#fff;border-radius:.14in;padding:.22in .26in}
.box h3{color:#fff}.box .eye{color:#e0b25a;margin-bottom:.06in}.box p{font-size:10.8pt;margin:0;color:rgba(255,255,255,.88)}
/* topics */
.topic{display:flex;gap:.22in;padding:.155in 0;border-bottom:1px solid #dfe3e8}
.topic:last-child{border-bottom:0}
.topic .n{flex:none;width:.46in;height:.46in;border-radius:50%;background:#D12B1F;color:#fff;font-family:Sora;font-weight:800;font-size:13pt;display:flex;align-items:center;justify-content:center}
.topic p{margin:0;font-size:11pt;color:#27323f}
/* questions */
.qs{list-style:none;columns:2;column-gap:.4in}
.qs li{break-inside:avoid;padding:.14in 0 .14in .3in;position:relative;font-size:11.6pt;line-height:1.45;border-bottom:1px solid #dfe3e8}
.qs li:before{content:"";position:absolute;left:.04in;top:.245in;width:.1in;height:.1in;border-radius:50%;background:#D12B1F}
/* images */
.imgs{display:grid;grid-template-columns:repeat(6,1fr);gap:.12in;margin:.08in 0 .1in}
.imgs figure{margin:0}.imgs img{width:100%;aspect-ratio:1;object-fit:cover;object-position:50% 15%;border-radius:.1in;display:block}
.imgs figcaption{font-size:7pt;line-height:1.3;font-weight:600;color:#5b6672;margin-top:.06in}
.btn{display:inline-block;background:#D12B1F;color:#fff;text-decoration:none;font-family:Inter;font-weight:700;font-size:9.5pt;letter-spacing:.14em;text-transform:uppercase;padding:.11in .26in;border-radius:999px;margin:.04in 0 .3in}
/* quotes */
.q{display:flex;gap:.2in;padding:.17in 0;border-bottom:1px solid #dfe3e8}
.q:last-child{border-bottom:0}
.q .m{flex:none;font-family:Serif4;font-weight:600;font-size:44pt;line-height:.8;color:#D12B1F;width:.4in}
.q p{font-family:Serif4;font-size:12pt;line-height:1.45;margin-bottom:.07in}
.q cite{font-style:normal;font-size:8.8pt;color:#5b6672}.q cite b{color:#0B1622;letter-spacing:.1em;text-transform:uppercase;font-size:8.4pt}
/* end */
.end .eph{position:absolute;right:0;bottom:1.05in;width:3.3in;height:2.75in;background:url(PHOTOaway) 50% 34%/cover;-webkit-mask-image:linear-gradient(90deg,transparent 0%,#000 45%),linear-gradient(0deg,#000 60%,transparent 100%);-webkit-mask-composite:source-in;mask-composite:intersect;opacity:.9}
.end{background:#0B1622;color:#fff}
.end .in{top:1.3in}
.end h2{color:#fff;font-size:34pt}.end h2 span{color:#ff5a4d}
.end .lede{color:rgba(255,255,255,.88)}
.ct{display:grid;grid-template-columns:1fr 1fr;gap:.2in;margin-top:.3in}
.ct div{border:1px solid rgba(255,255,255,.18);border-radius:.14in;padding:.2in .24in;background:rgba(255,255,255,.04)}
.ct b{display:block;font-size:7.6pt;letter-spacing:.18em;text-transform:uppercase;color:#e0b25a;margin-bottom:.05in}
.ct span{font-family:Sora;font-weight:700;font-size:12.5pt;word-break:break-word}
.ct small{display:block;margin-top:.05in;font-size:8.8pt;line-height:1.4;color:rgba(255,255,255,.72)}
a{color:inherit}
'''.replace('PHOTOheadshot', P + 'david-joannes-portrait.jpg').replace('PHOTOaway', P + 'david-joannes-portrait-2.jpg')

def foot(n): return f'<div class="ft"><span>David Joannes · Media Kit</span><span>{n}</span></div>'
toc = ['A Letter from David', 'About David', 'Introducing David', 'Books, Ministry, and Podcast', 'Talking Points', 'Questions for Podcasters and Interviews', 'Images and Media', 'What Others Say', 'Contact Information']
ct = C['contact']
pages = []
pages.append(f'''<section class="pg cover"><div class="grid"></div><div class="top">Media Kit</div><div class="ph"></div>
<div class="tx"><div class="eye">Missiologist · Author · Podcaster</div><h1>David<br><span>Joannes</span></h1><div class="mk">Media Kit</div>
<div class="tag">Bios, talking points, interview questions, and photos for podcasts and interviews.</div></div>
<div class="bot"><span>{e(ct["site"])}</span><span>Within Reach Global</span></div></section>''')
pages.append(f'''<section class="pg"><div class="rail"></div><div class="in"><div class="eye">Inside this kit</div><h2>Contents</h2>
<ol class="toc">{"".join(f"<li><b>{i + 1:02d}</b>{e(t)}</li>" for i, t in enumerate(toc))}</ol>
<div class="eye">A letter from David</div><h2>Thank you for <span>having me</span></h2>
{"".join(f"<p>{e(p)}</p>" for p in C["letter"])}<div class="sig">David Joannes</div>
<div class="card"><img src="{P}david-joannes-headshot.jpg"><div><b>At a glance</b><p>{e(C["intro"])}</p></div></div></div>{foot(2)}</section>''')
pages.append(f'''<section class="pg"><div class="rail r"></div><div class="in"><div class="eye">The full bio</div><h2>About <span>David</span></h2>
<div class="about"><div>{"".join(f"<p>{e(p)}</p>" for p in C["long"])}</div>
<div><img class="shot" src="{P}david-joannes-speaking.jpg"><div class="facts">{"".join(f"<div><b>{e(k)}</b>{e(v)}</div>" for k, v in C["facts"])}</div></div></div></div>{foot(3)}</section>''')
pages.append(f'''<section class="pg soft"><div class="rail"></div><div class="in"><div class="eye">Ready to read on air</div><h2>Introducing <span>David</span></h2>
<p class="lede">Use either bio as written when you introduce David or write your show notes.</p>
<div class="bio"><b>Short introduction · about 20 seconds</b><p>{e(C["intro"])}</p></div>
<div class="bio"><b>Standard bio · about 40 seconds</b><p>{e(C["short"])}</p></div>
<div class="eye" style="margin-top:.34in">Good to know</div>
<div class="cols"><div><h3>David Joannes</h3><p style="font-size:11pt">Founder and CEO of Within Reach Global. Author of The Mind of a Missionary. Host of the Missions Pulse podcast.</p>
<div class="hd"><b>Website</b>{e(ct["site"])}</div><div class="hd"><b>Instagram</b>{e(ct["instagram"])}</div><p class="note">{e(ct["collab"])}</p></div>
<div><h3>Within Reach Global</h3><p style="font-size:11pt">Send listeners here to learn about the ministry and to pray, give, or go.</p>
<div class="hd"><b>Website</b>{e(ct["wrg"])}</div><div class="hd"><b>Instagram</b>{e(ct["wrg_instagram"])}</div><div class="hd"><b>YouTube</b>{e(ct["youtube"])}</div></div></div></div>{foot(4)}</section>''')
pages.append(f'''<section class="pg"><div class="rail r"></div><div class="in"><div class="eye">The work</div><h2>Books, ministry, and <span>podcast</span></h2>
<div class="shelf">{"".join(f'<img src="file://{COVERS}/{b[2]}.jpg">' for b in C["books"])}</div>
<ul class="bl">{"".join(f"<li><b>{e(b[0])}</b> <i>· {e(b[1])}</i></li>" for b in C["books"])}</ul>
<div class="cols"><div class="box"><div class="eye">The ministry</div><h3>Within Reach Global</h3><p>{e(C["wrg"])}</p></div>
<div class="box"><div class="eye">The podcast</div><h3>Missions Pulse</h3><p>{e(C["podcast"])}</p></div></div></div>{foot(5)}</section>''')
pages.append(f'''<section class="pg soft"><div class="rail"></div><div class="in"><div class="eye">What David loves to talk about</div><h2>Talking <span>points</span></h2>
{"".join(f'<div class="topic"><div class="n">{i + 1}</div><div><h3>{e(t)}</h3><p>{e(d)}</p></div></div>' for i, (t, d) in enumerate(C["topics"]))}</div>{foot(6)}</section>''')
pages.append(f'''<section class="pg"><div class="rail r"></div><div class="in"><div class="eye">Suggested questions</div><h2>Questions for podcasters <span>and interviews</span></h2>
<p class="lede">Choose seven to ten questions from this list, and feel free to ask your own as well.</p>
<ul class="qs">{"".join(f"<li>{e(q)}</li>" for q in C["questions"])}</ul></div>{foot(7)}</section>''')
pages.append(f'''<section class="pg soft"><div class="rail"></div><div class="in"><div class="eye">Photos to download</div><h2>Images and <span>media</span></h2>
<p class="lede">Download headshots and field photos of David for your artwork, show notes, and social posts.</p>
<div class="imgs">{"".join(f'<figure><img src="{P}{f}"><figcaption>{e(c)}</figcaption></figure>' for f, c in C["photos"])}</div>
<a class="btn" href="https://{e(ct["media"])}/">Get images and media</a>
<div class="eye">What others say</div><h2>Endorsements</h2>
{"".join(f'<div class="q"><div class="m">“</div><div><p>{e(q)}</p><cite><b>{e(n)}</b> · {e(r)}</cite></div></div>' for q, n, r in C["quotes"][:3])}</div>{foot(8)}</section>''')
pages.append(f'''<section class="pg end"><div class="grid"></div><div class="glow"></div><div class="eph"></div><div class="in"><div class="eye" style="color:#e0b25a">Get in touch</div><h2>Contact <span>information</span></h2>
<p class="lede">To book David for a podcast or interview, or to ask for a review copy of one of his books, reach out by email. David is based in Chiang Mai, Thailand (UTC+7).</p>
<div class="ct"><div><b>Interviews and review copies</b><span>{e(ct["email"])}</span><small>Email David directly</small></div><div><b>Books</b><span>{e(ct["site"])}/books</span><small>All titles, with links to buy</small></div>
<div><b>Website and media downloads</b><span>{e(ct["media"])}</span><small>Bios to copy and photos to download</small></div><div><b>The ministry</b><span>{e(ct["wrg"])}</span><small>Within Reach Global</small></div>
<div><b>Instagram</b><span>{e(ct["instagram"])}</span><small>Within Reach Global: {e(ct["wrg_instagram"])}. David accepts most collaboration requests.</small></div><div><b>YouTube</b><span>{e(ct["youtube"])}</span><small>Within Reach Global</small></div></div></div>
<div class="bot"><span>David Joannes</span><span>{e(ct["site"])}</span></div></section>''')
doc = f'<!doctype html><meta charset="utf-8"><title>David Joannes Media Kit</title><style>{css}</style>' + ''.join(pages)
open(os.path.join(HERE, 'kit.html'), 'w', encoding='utf-8').write(doc)
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch(); pg = b.new_page()
    pg.goto('file://' + os.path.join(HERE, 'kit.html')); pg.wait_for_timeout(1200)
    pg.pdf(path=OUT, width='8.5in', height='11in', print_background=True, margin={'top': '0', 'right': '0', 'bottom': '0', 'left': '0'})
    b.close()
print('wrote', OUT, os.path.getsize(OUT) // 1024, 'KB')
