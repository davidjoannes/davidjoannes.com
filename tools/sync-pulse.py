#!/usr/bin/env python3
"""Keep davidjoannes.com in step with the Missions Pulse episodes on withinreachglobal.org.

Run from the repo root by .github/workflows/sync-pulse.yml:
  - reads the WRG feed and records every episode in assets/pulse.json (the pages read this in the browser)
  - gives each new episode its own full post on this site (kept in tools/pulse-posts.json, pages written from tools/episode-template.html)
  - adds the new posts to the blog listings
Use --render-only to rewrite the pages without reading the feed."""
import json, os, re, sys, html, urllib.request, email.utils
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
WRG = 'https://withinreachglobal.org'
FEED = WRG + '/missions-pulse/rss.xml'
PULSE, POSTS, TPL = 'assets/pulse.json', 'tools/pulse-posts.json', 'tools/episode-template.html'
LISTINGS = ['blog/index.html', 'blog/missions-pulse-podcast-posts/index.html']
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
esc = lambda t: html.escape(t, quote=True)
def load(p, d):
    try: return json.load(open(p))
    except Exception: return d
def nice(d):
    try: y, m, dd = d.split('-'); return f'{MONTHS[int(m) - 1]} {int(dd)}, {y}'
    except Exception: return ''
def absu(u):
    u = html.unescape(u or '').strip()
    if u.startswith('//'): u = 'https:' + u
    if u.startswith('/'): u = WRG + u
    return re.sub(r'[?&]hsLang=[\w-]+', '', u)

class Clean(HTMLParser):
    """Keep the post's text, links, pictures, and players; drop HubSpot wrappers and styling."""
    KEEP = {'p', 'h2', 'h3', 'h4', 'ul', 'ol', 'li', 'blockquote', 'strong', 'b', 'em', 'i', 'br'}
    def __init__(self):
        super().__init__(convert_charrefs=True); self.out = []; self.skip = 0; self.stack = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs); cls = a.get('class') or ''
        void = tag in ('img', 'br', 'iframe', 'hr', 'input', 'meta', 'link')
        if self.skip:
            if not void: self.skip += 1
            return
        if tag in ('script', 'style') or 'hs-featured-image-wrapper' in cls:
            self.skip = 1; return
        if tag == 'h1': tag = 'h2'
        if tag in self.KEEP: self.out.append(f'<{tag}>')
        elif tag == 'a':
            h = absu(a.get('href'))
            self.out.append(f'<a href="{esc(h)}">' if h.startswith('http') or h.startswith('mailto:') else '<a>')
        elif tag == 'img':
            s = absu(a.get('src'))
            if s.startswith('http') and 'track.hubspot' not in s and a.get('width') != '1':
                self.out.append(f'<img src="{esc(s)}" alt="{esc(a.get("alt") or "")}" loading="lazy">')
        elif tag == 'iframe':
            s = absu(a.get('src'))
            y = re.search(r'(?:youtube(?:-nocookie)?\.com/embed/|youtu\.be/)([\w-]{11})', s)
            if y: self.out.append(f'<div class="embed"><iframe src="https://www.youtube-nocookie.com/embed/{y.group(1)}" title="YouTube video" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>')
            elif 'podbean.com' in s: self.out.append(f'<iframe src="{esc(s)}" title="Podcast player" loading="lazy" scrolling="no" style="width:100%;height:150px;border:0;margin:8px 0 24px"></iframe>')
    def handle_endtag(self, tag):
        if self.skip:
            self.skip -= 1; return
        if tag == 'h1': tag = 'h2'
        if tag in self.KEEP and tag != 'br' or tag == 'a': self.out.append(f'</{tag}>')
    def handle_data(self, d):
        if not self.skip: self.out.append(esc(d).replace('&quot;', '"').replace('&#x27;', "'"))
def clean(body):
    c = Clean(); c.feed(body); c.close()
    t = ''.join(c.out)
    t = re.sub(r'<(p|h2|h3|h4|li|strong|em|b|i|a)>(\s|&nbsp;|\xa0|<br>)*</\1>', '', t)
    t = re.sub(r'<p>\s*(<div class="embed">.*?</div>|<iframe.*?</iframe>)\s*</p>', r'\1', t, flags=re.S)
    return re.sub(r'\n{3,}', '\n\n', t).strip()

def fetch():
    req = urllib.request.Request(FEED, headers={'User-Agent': 'Mozilla/5.0 (davidjoannes.com episode sync)'})
    root = ET.fromstring(urllib.request.urlopen(req, timeout=60).read())
    items = []
    for it in root.iter('item'):
        title = html.unescape((it.findtext('title') or '').strip())
        link = (it.findtext('link') or '').strip().split('?')[0].rstrip('/')
        if not title or '/missions-pulse/' not in link: continue
        try: date = email.utils.parsedate_to_datetime(it.findtext('pubDate') or '').strftime('%Y-%m-%d')
        except Exception: date = ''
        body = it.findtext('{http://purl.org/rss/1.0/modules/content/}encoded') or it.findtext('description') or ''
        m = re.search(r'<img[^>]+src="([^"]+)"', body)
        items.append({'title': title, 'link': link, 'date': date, 'image': absu(m.group(1)) if m else '', 'body': body})
    return items

def existing_post(slug, num, mine):
    """A post for this episode that came over from the old site, if there is one."""
    cands = [slug] + ([d for d in sorted(os.listdir('.')) if re.match(r'0*%d(\D|$)' % num, d)] if num else [])
    for d in cands:
        f = os.path.join(d, 'index.html')
        if d not in mine and os.path.isfile(f) and 'missions-pulse-podcast-posts' in open(f, encoding='utf-8', errors='ignore').read(): return d
    return None

def render(posts, pulse):
    if not os.path.exists(TPL): return
    tpl = open(TPL, encoding='utf-8').read()
    base = (re.search(r'<!--base:(.*?)-->', tpl) or [None, ''])[1]
    for slug, p in posts.items():
        text = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', p['body']))).strip()
        body = p['body']
        if not re.match(r'\s*(<div class="embed"|<img|<iframe)', body) and p.get('image'): body = f'<img class="featimg" src="{esc(p["image"])}" alt="">' + body
        page = tpl
        for k, v in {'%%TITLE%%': esc(p['title']), '%%DESC%%': esc(text[:158]), '%%DATE%%': nice(p['date']), '%%CANON%%': esc(p['link']), '%%OGIMG%%': esc(p.get('image') or ''), '%%PATH%%': f'/{slug}/', '%%BODY%%': body}.items():
            page = page.replace(k, v)
        os.makedirs(slug, exist_ok=True)
        open(os.path.join(slug, 'index.html'), 'w', encoding='utf-8').write(page)
    cards = ''
    for e in pulse.get('episodes', []):
        slug = (e.get('path') or '').strip('/')
        if slug not in posts: continue
        p = posts[slug]
        text = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', p['body']))).strip()
        pic = f'<img src="{esc(p["image"])}" alt="" loading="lazy">' if p.get('image') else ''
        cards += (f'<a class="card" href="{base}/{slug}/" data-t="{esc((p["title"] + " missions pulse " + text[:260]).lower())}"><div class="im">{pic}</div>'
                  f'<div class="k">Missions Pulse · {nice(p["date"])}</div><h3>{esc(p["title"])}</h3></a>')
    for f in LISTINGS:
        if not os.path.exists(f): continue
        s = open(f, encoding='utf-8').read()
        s2 = re.sub(r'<!--pulse-new-->.*?<!--/pulse-new-->', lambda m: '<!--pulse-new-->' + cards + '<!--/pulse-new-->', s, flags=re.S)
        if s2 != s: open(f, 'w', encoding='utf-8').write(s2)

def main():
    pulse = load(PULSE, {}); posts = load(POSTS, {})
    if '--render-only' not in sys.argv:
        items = fetch()
        if not items: sys.exit('No episodes found in the feed; leaving everything as it is.')
        old = {e['link'].rstrip('/'): e for e in pulse.get('episodes', [])}
        for it in items:
            slug = it['link'].rsplit('/', 1)[1]
            m = re.match(r'#(\d+)', it['title']); num = int(m.group(1)) if m else 0
            ex = existing_post(slug, num, posts)
            if ex: path = f'/{ex}/'
            else:
                body = clean(it['body'])
                if len(re.sub(r'<[^>]+>', '', body)) < 200 and slug not in posts: path = ''   # nothing worth a page yet; the card opens the WRG post
                else:
                    if len(re.sub(r'<[^>]+>', '', body)) >= 200: posts[slug] = {'title': it['title'], 'link': it['link'], 'date': it['date'], 'image': it['image'], 'body': body}
                    path = f'/{slug}/'
            old[it['link']] = {'title': it['title'], 'link': it['link'], 'date': it['date'], 'image': it['image'], 'path': path}
        eps = sorted(old.values(), key=lambda e: e.get('date', ''), reverse=True)
        nums = [int(m.group(1)) for e in eps for m in [re.match(r'#(\d+)', e['title'])] if m]
        pulse = {'count': max(nums + [int(pulse.get('count') or 0)]), 'episodes': eps}
        os.makedirs('assets', exist_ok=True)
        json.dump(pulse, open(PULSE, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        json.dump(posts, open(POSTS, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('episodes:', pulse['count'], '| newest:', eps[0]['title'], '| full posts on this site:', len(posts))
    render(posts, pulse)
main()
