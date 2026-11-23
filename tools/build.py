#!/usr/bin/env python3
"""Static site generator for davidjoannes.com from a WordPress export.
usage: build.py <export.xml> <out_dir> [base]   (base e.g. /davidjoannes.com for a preview)"""
import sys, re, os, html, base64, shutil, datetime, collections
from urllib.parse import unquote
import xml.etree.ElementTree as ET

XML, OUT = sys.argv[1], sys.argv[2]
B = (sys.argv[3] if len(sys.argv) > 3 else '').rstrip('/')
HERE = os.path.dirname(os.path.abspath(__file__))
SITE = 'https://davidjoannes.com'
WRG = 'https://withinreachglobal.org'
ns = {'wp': 'http://wordpress.org/export/1.2/', 'content': 'http://purl.org/rss/1.0/modules/content/',
      'excerpt': 'http://wordpress.org/export/1.2/excerpt/'}
ch = ET.parse(XML).getroot().find('channel')
items = ch.findall('item')
def g(i, k): return i.findtext(k, namespaces=ns) or ''
def meta(i): return {m.findtext('wp:meta_key', namespaces=ns): (m.findtext('wp:meta_value', namespaces=ns) or '') for m in i.findall('wp:postmeta', ns)}
esc = lambda s: html.escape(s or '', quote=True)

# ---------- attachments
ATT = {}
for i in items:
    if g(i, 'wp:post_type') == 'attachment':
        m = meta(i); url = g(i, 'wp:attachment_url'); sizes = {}
        md = m.get('_wp_attachment_metadata', '')
        for sm in re.finditer(r's:\d+:"(medium|medium_large|large)";a:\d+:\{s:4:"file";s:\d+:"([^"]+)"', md):
            sizes[sm.group(1)] = url.rsplit('/', 1)[0] + '/' + sm.group(2)
        ATT[g(i, 'wp:post_id')] = {'url': url, 'sizes': sizes, 'alt': m.get('_wp_attachment_image_alt', '')}
USED = set()
import json, glob as _glob
MJ = {}
for _f in sorted(_glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mj-*.json'))):
    for _e in json.load(open(_f)): MJ['/' + _e['slug'].strip('/') + '/'] = _e
MJFILES = {}
def mj_img(path, small=False):
    e = MJ.get(path)
    if not e: return ''
    name = path.strip('/').replace('/', '-')
    base = f"https://cdn.midjourney.com/{e['job']}/0_{e.get('variant', 0)}"
    if e['job'] != 'custom':
        MJFILES[base + '.webp'] = f'assets/featured/{name}.webp'
        MJFILES[base + '_640_N.webp'] = f'assets/featured/{name}-640.webp'
    rel = f'/assets/featured/{name}-640.webp' if small else f'/assets/featured/{name}.webp'
    return (B + rel) if os.path.exists(OUT + rel) else ''
HAVE_UP = os.path.isdir(os.path.join(OUT, 'wp-content'))
def have(u):
    m = re.match(r'https?://(?:www\.)?davidjoannes\.com(/wp-content/uploads/.+)', u or '')
    if not m or not HAVE_UP: return True
    return os.path.exists(OUT + unquote(m.group(1)))
DEAD = r'(?:googleusercontent\.com|gawkerassets\.com|withinreachglobal\.org/wp-content|feeds\.feedburner\.com|pixel\.wp\.com)'
DEADHOST = r'(?:blab\.im|feeds\.feedburner\.com|plus\.google\.com)'
MOVED = {'/donation': '/donate/', '/donation/': '/donate/', '/donate/donation/': '/donate/', '/live': '/missionspulse/', '/live/': '/missionspulse/'}
def site_has(h):
    p = h[len(B):] if B and h.startswith(B) else h
    p = p.split('#')[0].split('?')[0]
    if p in ('', '/'): return True
    if p.startswith('/wp-content/'): return os.path.exists(OUT + unquote(p))
    return p.rstrip('/') + '/' in LIVE
def fix_links(t):
    def one(m):
        attrs_, inner = m.group(1), m.group(2)
        h = re.search(r'href="([^"]*)"', attrs_); h = h.group(1) if h else ''
        img = '<img' in inner
        wrg = re.match(r'https?://(?:www\.)?withinreachglobal\.org/([^"]*)', h)
        if wrg and wrg.group(1).strip('/') and not re.match(r'(?:book-|books|donate|go\b|founders|hubfs|spiritual-gifts|gospel-access|[\w-]+-course)', wrg.group(1)):
            return '' if img else f'<a href="{WRG}">{inner}</a>'
        if re.match(r'https?://(?:www\.)?' + DEADHOST, h): return '' if img else inner
        if h.startswith(B + '/') or h == B:
            p = (h[len(B):] if B else h).split('#')[0].split('?')[0]
            if p in MOVED: return f'<a href="{B}{MOVED[p]}">{inner}</a>'
            if not site_has(h): return '' if img else inner
        return m.group(0)
    return re.sub(r'<a\b([^>]*)>(.*?)</a>', one, t, flags=re.S)
def strip_broken(t):
    def chk(m):
        s = re.search(r'src="([^"]*)"', m.group(0)); u = s.group(1) if s else ''
        if not u or re.search(DEAD, u): return ''
        if u.startswith(B + '/wp-content/') and HAVE_UP and not os.path.exists(OUT + unquote(u[len(B):])): return ''
        return m.group(0)
    t = re.sub(r'<img\b[^>]*>', chk, t)
    t = re.sub(r'<a\b[^>]*>\s*</a>', '', t)
    t = re.sub(r'<figure>\s*<figcaption>.*?</figcaption></figure>', '', t, flags=re.S)
    t = re.sub(r'<p[^>]*>(?:\s|&nbsp;|\xa0|<br\s*/?>|</?(?:span|strong|em|b|i)\b[^>]*>)*</p>', '', t)
    return t
def local(u):
    """site upload URL -> local path (and remember it for the image fetch list)"""
    m = re.match(r'https?://(?:www\.)?davidjoannes\.com(/wp-content/uploads/[^\s"\'<>)]+)', u or '')
    if not m: return u
    USED.add(SITE + m.group(1)); return B + m.group(1)
def att(aid, size=None):
    a = ATT.get(str(aid))
    if not a: return ''
    u = a['url']
    if size:
        for s in ([size] if isinstance(size, str) else size):
            if s in a['sizes'] and have(a['sizes'][s]): u = a['sizes'][s]; break
    if not have(u): USED.add(u) if u.startswith(SITE) else None; return ''
    return local(u)

# ---------- posts & pages
CATS = [  # (wp nicenames, label, listing url)
    (['missions-pulse-podcast'], 'Missions Pulse', '/blog/missions-pulse-podcast-posts/'),
    (['tmoamdevotional', 'the-mind-of-a-missionary', 'davids-books'], "David's Books", '/blog/davids-books-blogs/'),
    (['davids-book-reviews'], 'Book Reviews', '/blog/book-reviews-by-david/'),
    (['podcast-appearances'], 'Podcast Appearances', '/blog/podcast-appearances-posts/'),
    (['within-reach-global'], 'Within Reach Global', '/blog/within-reach-global-posts/'),
    (['missions-blogs'], 'Missions', '/blog/missions-blogs/'),
]
TERM = {t.findtext('wp:term_id', namespaces=ns): t.findtext('wp:category_nicename', namespaces=ns) for t in ch.findall('wp:category', ns)}
SMALL = {'a','an','the','and','but','or','nor','for','as','at','by','in','of','on','per','to','via','vs','vs.','with','from','into','onto'}
def _cap(w):
    m = re.match(r"^([\W_]*)(.*)$", w)
    pre, core = m.group(1), m.group(2)
    if not core: return w
    if re.search(r'[A-Z]', core[1:]) or re.search(r'\d', core) and core.upper() == core: return w   # iPhone, WRG, 10/40
    return pre + core[0].upper() + core[1:]
def titlecase(t):
    t = html.unescape(t).strip()
    words = t.split(' ')
    letters = [c for c in t if c.isalpha()]
    shout = letters and sum(c.isupper() for c in letters) / len(letters) > 0.8
    out = []
    for i, w in enumerate(words):
        if not w: continue
        if shout and not re.fullmatch(r'[A-Z]{2,4}[:,.!?]?', w): w = w.lower()
        core = re.sub(r"^[\W_]+|[\W_]+$", '', w).lower()
        first = i == 0 or out and re.search(r'[:?!.–—-]$|^[–—-]$', out[-1]) or re.match(r'^[“"‘\'(\[]', w)
        last = i == len(words) - 1
        if core in SMALL and not first and not last and not re.search(r'[A-Z]{2,}', w) and not re.search(r'[,;:?!.)]$', w):
            out.append(w.lower())
        elif '-' in w and not w.startswith('-'):
            out.append('-'.join(_cap(p) if (j == 0 or p.lower() not in SMALL) else p.lower() for j, p in enumerate(w.split('-'))))
        else:
            out.append(_cap(w))
    return ' '.join(out)
class P: pass
POSTS, PAGES = [], {}
for i in items:
    t, st = g(i, 'wp:post_type'), g(i, 'wp:status')
    if st != 'publish' or t not in ('post', 'page'): continue
    p = P(); p.title = titlecase(g(i, 'title')) if t == 'post' else g(i, 'title'); p.raw = g(i, 'content:encoded'); p.id = g(i, 'wp:post_id')
    p.path = '/' + g(i, 'link').replace(SITE, '').strip('/') + '/'
    if p.path == '//': p.path = '/'
    p.date = g(i, 'wp:post_date'); p.meta = meta(i); p.thumb = p.meta.get('_thumbnail_id', '')
    p.cats = [c.get('nicename') for c in i.findall('category') if c.get('domain') == 'category']
    p.excerpt = g(i, 'excerpt:encoded')
    p.is_post = (t == 'post')
    if t == 'post':
        p.cat = next((c for c in CATS if any(n in p.cats for n in c[0])), CATS[-1]); POSTS.append(p)
    else: PAGES.setdefault(p.path, p)
FEATURED_FIRST = {'/missions-history-today-what-happened-on-every-day-of-the-year/': '2026-11-21 12:00:01',   # republished as the newest posts
                  '/the-most-epic-monster-list-of-missionary-quotes-on-the-internet/': '2026-11-21 12:00:00'}
for p in POSTS:
    if p.path in FEATURED_FIRST: p.date = FEATURED_FIRST[p.path]
POSTS.sort(key=lambda p: p.date, reverse=True)
LIVE = set()
def nice_date(d):
    try: return datetime.datetime.strptime(d[:10], '%Y-%m-%d').strftime('%B %-d, %Y')
    except Exception: return ''

# ---------- testimonials
TEST = collections.defaultdict(list)
for i in items:
    t = g(i, 'wp:post_type')
    if g(i, 'wp:status') != 'publish' or t not in ('testimonial', 'stars_testimonial'): continue
    m = meta(i)
    d = {'name': m.get('grve_testimonial_name') or g(i, 'title'), 'who': m.get('grve_testimonial_identity') or m.get('testimonial_company_name', ''), 'body': g(i, 'content:encoded')}
    for c in i.findall('category'): TEST[c.get('nicename')].append(d)
    TEST['_' + t].append(d)
BOOKTEST = {'/books/the-mind-of-a-missionary/': ['themindofamissionary-topsliders', 'themindofamissionary'],
            '/books/gospel-privilege/': ['gospel-privilege-top-sliders', 'gospelprivilege'],
            '/books/the-space-between-memories/': ['thespacebetweenmemoriestopsliders', 'thespacebetweenmemories'],
            '/books/see-the-city/': ['see-the-city-top-sliders', 'seethecity']}
def titlecase_name(n): return n.title() if n.isupper() else n

PTV = {'d00bfd9j8d': ['davids-books', 'the-mind-of-a-missionary'], 'c6dafd6uj6': ['missions-blogs'], 'f0d6512ryl': ['tmoamdevotional'],
       '1459d73wt9': ['missions-pulse-podcast'], '14fe417ij7': ['missions-pulse-podcast'], 'a29682coyv': ['davids-books', 'the-mind-of-a-missionary'],
       'abbd803xwl': ['missions-blogs'], '712967eqz4': ['davids-book-reviews'], 'd7034d0ld1': ['missions-pulse-podcast'], '8a0d3b04di': ['podcast-appearances'], 'e43957dafm': ['within-reach-global']}
# ---------- content conversion
def attrs(s): return dict(re.findall(r'([\w-]+)="([^"]*)"', s or ''))
def vclink(v):
    if not v: return ''
    v = v.strip()
    m = re.match(r'url:([^|]*)', v)
    return unquote(m.group(1)) if m else v
def yt_id(u):
    m = re.search(r'(?:youtu\.be/|youtube\.com/(?:watch\?(?:[^"\s]*&)?v=|embed/|live/|shorts/))([\w-]{11})', u or '')
    return m.group(1) if m else None
def video(u):
    y = yt_id(u)
    if y: return f'\n\n<div class="embed"><iframe src="https://www.youtube-nocookie.com/embed/{y}" title="YouTube video" loading="lazy" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen></iframe></div>\n\n'
    m = re.search(r'vimeo\.com/(?:video/)?(\d+)', u or '')
    if m: return f'\n\n<div class="embed"><iframe src="https://player.vimeo.com/video/{m.group(1)}" title="Vimeo video" loading="lazy" allowfullscreen></iframe></div>\n\n'
    return f'<p><a href="{esc(u)}">{esc(u)}</a></p>' if u else ''
def button(text, link, cls=''):
    link = vclink(link)
    if not text or not link: return ''
    return f'<a class="btn {cls}" href="{esc(link)}">{esc(text)}</a> '
def img_sc(a):
    src = att(a.get('image', ''), ['large'])
    if not src: return ''
    alt = ATT.get(a.get('image', ''), {}).get('alt', '')
    tag = f'<img src="{src}" alt="{esc(alt)}" loading="lazy">'
    link = vclink(a.get('link', ''))
    if link: tag = f'<a href="{esc(link)}">{tag}</a>'
    return f'\n\n<p data-a="c">{tag}</p>\n\n'
def post_card(p, k=None):
    im = mj_img(p.path, True) or att(p.thumb, ['medium_large', 'large'])
    if not im:
        y = yt_id(p.meta.get('grve_post_video_embed', '') or p.meta.get('cb_video_embed_code_post', '')) or yt_id(p.raw)
        if y: im = f'https://i.ytimg.com/vi/{y}/hqdefault.jpg'
    pic = f'<img src="{im}" alt="" loading="lazy">' if im else ''
    return (f'<a class="card" href="{B}{p.path}" data-t="{esc((p.title + ' ' + p.cat[1] + ' ' + re.sub(r'<[^>]+>|\[[^\]]*\]', ' ', p.excerpt or p.raw)[:260]).lower())}"><div class="im">{pic}</div>'
            f'<div class="k">{esc(k or p.cat[1])} · {nice_date(p.date)}</div><h3>{esc(p.title)}</h3></a>')
def blog_sc(a):
    n = int(a.get('posts_per_page') or 8)
    ps = POSTS
    if a.get('categories'):
        want = {TERM.get(x.strip()) for x in a['categories'].split(',')}
        ps = [p for p in POSTS if want & set(p.cats)]
    return '\n\n<div class="grid">' + ''.join(post_card(p) for p in ps[:n]) + '</div>\n\n'
def test_html(lst, limit=None):
    out = []
    for d in lst[:limit]:
        who = f' <span>· {esc(titlecase_name(d["who"]))}</span>' if d['who'] else ''
        out.append(f'<div class="tq">{autop(clean_inline(d["body"]))}<cite>{esc(titlecase_name(d["name"]))}{who}</cite></div>')
    return '\n\n' + ''.join(out) + '\n\n'

BLOCK = r'(?:div|section|p|h[1-6]|ul|ol|li|blockquote|figure|figcaption|iframe|table|thead|tbody|tr|td|th|hr|script|style|audio|video|details|summary|form|pre|noscript|center|aside|header|footer|nav|dl|dt|dd)'
def autop(t):
    t = t.replace('\r\n', '\n')
    out = []
    for chunk in re.split(r'\n\s*\n', t):
        c = chunk.strip()
        if not c: continue
        if re.match(r'</?' + BLOCK + r'\b', c, re.I) or c.startswith('<!--'):
            out.append(c)
        else:
            out.append('<p>' + c.replace('\n', '<br>\n') + '</p>')
    return '\n'.join(out)

def fix_style(m):
    tag, rest = m.group(1), m.group(2)
    if tag.lower() in ('iframe', 'script', 'audio', 'video', 'source'): return m.group(0)
    sm = re.search(r'\sstyle="([^"]*)"', rest)
    if sm and sm.group(1).startswith('--w'): return m.group(0)
    if sm:
        al = re.search(r'text-align:\s*(center|right)', sm.group(1))
        rest = rest.replace(sm.group(0), f' data-a="{al.group(1)[0]}"' if al else '')
    rest = re.sub(r'\s(?:align|bgcolor|color|face|size)="[^"]*"', '', rest) if tag.lower() in ('p', 'span', 'font', 'div', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'td') else rest
    return f'<{tag}{rest}>'
def clean_inline(t):
    t = re.sub(r'<!--\s*/?wp:.*?-->', '', t, flags=re.S)
    t = re.sub(r'<(\w+)((?:\s[^<>]*)?)>', fix_style, t)
    t = re.sub(r'</?(?:font|span)\b[^>]*>', '', t)
    def cls(m):
        keep = [c for c in m.group(1).split() if c in ('alignleft', 'alignright', 'aligncenter', 'pull', 'notes')]
        return f' class="{" ".join(keep)}"' if keep else ''
    t = re.sub(r'\sclass="([^"]*)"', cls, t)
    t = re.sub(r'\s(?:id="(?:attachment_|fb-root|more-)[^"]*"|data-(?!a=)[\w-]+="[^"]*")', '', t)
    t = re.sub(r'<(/?)h1\b', r'<\1h2', t)
    t = re.sub(r'(?:&nbsp;|\xa0)+', ' ', t)
    return t
def rewrite_urls(t):
    t = re.sub(r'https?://(?:www\.)?withinreachglobal\.org/1040-window/?', WRG + '/why-the-unreached', t)
    t = re.sub(r'https?://(?:www\.)?davidjoannes\.com/wp-content/uploads/[^\s"\'<>)\]]+', lambda m: local(m.group(0)), t)
    t = re.sub(r'(href=")https?://(?:www\.)?davidjoannes\.com/?(?=["#/])', lambda m: m.group(1) + B + '/', t)
    t = re.sub(r'(href="' + re.escape(B) + r')//+', r'\1/', t)
    t = re.sub(r'(<iframe[^>]+src=")http://', r'\1https://', t)
    t = re.sub(r'(<iframe[^>]+src=")//', r'\1https://', t)
    return t

KNOWN = r'(?:vc_\w+|grve_\w+|ezcol_\w+|one_\w+|two_\w+|three_\w+|four_\w+|column\w*|divider|button|maxbutton|testimonial_stars|contact-form-7|mc4wp_form|gallery|embed|audio|video|playlist|caption|note|dropcap|mashshare|accordions|player|toggle|tabs?|box|highlight|pullquote|row|col|spacer|social\w*|et_pb_\w+|cb_\w+|googlemaps?|learn_more|toc|fusion_\w+|su_\w+|review|wpforms|ninja_form|yikes-mailchimp|soundcloud|youtube|vimeo|x_\w+)'

def convert(p):
    t = p.raw
    notes = []
    # raw html blocks
    def raw(m):
        try: return '\n\n' + unquote(base64.b64decode(m.group(1).strip() + '===').decode('utf-8', 'ignore')) + '\n\n'
        except Exception: return ''
    t = re.sub(r'\[vc_raw_html[^\]]*\](.*?)\[/vc_raw_html\]', raw, t, flags=re.S)
    t = re.sub(r'\[vc_raw_js[^\]]*\].*?\[/vc_raw_js\]', '', t, flags=re.S)
    # dark rows (white text) decided before styles are stripped
    def row(m):
        a = attrs(m.group(1)); body = m.group(2)
        dk = ' dk' if re.search(r'color:\s*#(?:fff|ffffff)\b', body, re.I) else ''
        rid = a.get('section_id') or a.get('el_id') or ''
        return f'\n\n<section class="vrow{dk}"' + (f' id="{esc(rid)}"' if rid else '') + f'>\n\n<div class="vcols">\n\n{body}\n\n</div>\n\n</section>\n\n'
    t = re.sub(r'\[vc_row(?!_inner)([^\]]*)\](.*?)\[/vc_row\]', row, t, flags=re.S)
    def col(m):
        w = attrs(m.group(1)).get('width', '1/1')
        try: n, d = w.split('/'); f = round(int(n) / int(d), 3)
        except Exception: f = 1
        return f'\n\n<div class="vcol" style="--w:{f}">\n\n'
    t = re.sub(r'\[vc_column(?:_inner)?(?!_text)([^\]]*)\]', col, t)
    t = re.sub(r'\[/vc_column(?:_inner)?\]', '\n\n</div>\n\n', t)
    t = re.sub(r'\[vc_row_inner[^\]]*\]', '\n\n<div class="vcols inner">\n\n', t)
    t = t.replace('[/vc_row_inner]', '\n\n</div>\n\n')
    t = re.sub(r'\[/?vc_column_text[^\]]*\]', '\n\n', t)
    # footnotes
    def note(m):
        notes.append(m.group(1).strip()); n = len(notes)
        return f'<sup><a href="#fn{n}" id="fnr{n}">{n}</a></sup>'
    t = re.sub(r'\[note\](.*?)\[/note\]', note, t, flags=re.S)
    # tweets / captions / media
    t = re.sub(r'\[Tweet\s+["“”](.*?)["“”]\s*\]', lambda m: f'\n\n<blockquote class="pull">{m.group(1)}</blockquote>\n\n', t, flags=re.S)
    t = re.sub(r'\s*\[CLICK TO TWEET\]', '', t)
    def cap(m):
        inner = m.group(1).strip(); im = re.match(r'((?:<a[^>]*>)?\s*<img[^>]*>\s*(?:</a>)?)(.*)', inner, re.S)
        if not im: return inner
        return f'\n\n<figure>{im.group(1)}<figcaption>{im.group(2).strip()}</figcaption></figure>\n\n'
    t = re.sub(r'\[caption[^\]]*\](.*?)\[/caption\]', cap, t, flags=re.S)
    def audio(m):
        a = attrs(m.group(1)); src = a.get('mp3') or a.get('src') or a.get('m4a') or ''
        return f'\n\n<audio controls preload="none" src="{esc(src)}"></audio>\n\n' if src else ''
    t = re.sub(r'\[audio([^\]]*)\](?:\[/audio\])?', audio, t)
    t = re.sub(r'\[(?:grve_video|vc_video)([^\]]*)\](?:\[/(?:grve_video|vc_video)\])?', lambda m: video(attrs(m.group(1)).get('video_link') or attrs(m.group(1)).get('link', '')), t)
    t = re.sub(r'\[embed[^\]]*\](.*?)\[/embed\]', lambda m: video(m.group(1).strip()), t, flags=re.S)
    t = re.sub(r'\[(?:youtube|vimeo)[^\]]*\](.*?)\[/(?:youtube|vimeo)\]', lambda m: video(m.group(1).strip()), t, flags=re.S)
    t = re.sub(r'(?m)^\s*(https?://(?:www\.)?(?:youtu\.be|youtube\.com|vimeo\.com)/\S+)\s*$', lambda m: video(m.group(1)), t)
    # images
    t = re.sub(r'\[(?:vc_single_image|grve_single_image)([^\]]*)\]', lambda m: img_sc(attrs(m.group(1))), t)
    def gallery(m):
        ids = attrs(m.group(1)).get('ids') or attrs(m.group(1)).get('images') or ''
        ims = ''.join(f'<img src="{att(x.strip(), ["medium_large", "large"])}" alt="" loading="lazy">' for x in ids.split(',') if att(x.strip()))
        return f'\n\n<div class="grid">{ims}</div>\n\n' if ims else ''
    t = re.sub(r'\[(?:grve_slider|grve_gallery|gallery|vc_gallery)([^\]]*)\](?:\[/(?:grve_slider|grve_gallery|vc_gallery)\])?', gallery, t)
    # buttons, slogans, boxes
    t = re.sub(r'\[grve_button([^\]]*)\](?:\[/grve_button\])?', lambda m: '\n\n<p data-a="c">' + button(attrs(m.group(1)).get('button_text'), attrs(m.group(1)).get('button_link')) + '</p>\n\n', t)
    def slogan(m):
        a = attrs(m.group(1)); h = a.get('heading', 'h3') if re.match(r'h[1-6]$', a.get('heading', '')) else 'h3'
        out = (f'<{h}>{esc(a["title"])}</{h}>\n\n' if a.get('title') else '') + (m.group(2) or '')
        bt = button(a.get('button_text'), a.get('button_link')) + button(a.get('button2_text'), a.get('button2_link'), 'ghost')
        return f'\n\n{out}\n\n' + (f'<p>{bt}</p>\n\n' if bt else '')
    t = re.sub(r'\[(?:grve_slogan|grve_callout|grve_message_box|grve_promo)([^\]]*)\](?:(.*?)\[/(?:grve_slogan|grve_callout|grve_message_box|grve_promo)\])?', slogan, t, flags=re.S)
    def title(m):
        a = attrs(m.group(1)); h = a.get('heading', 'h2') if re.match(r'h[1-6]$', a.get('heading', '')) else 'h2'
        txt = a.get('title') or (m.group(2) or '')
        return f'\n\n<{h}>{txt}</{h}>\n\n' if txt.strip() else ''
    t = re.sub(r'\[grve_title([^\]]*)\](?:(.*?)\[/grve_title\])?', title, t, flags=re.S)
    def mbox(m):
        a = attrs(m.group(1)); media = video(a['video_link']) if a.get('video_link') else img_sc(a)
        link = vclink(a.get('title_link') or a.get('link'))
        ttl = esc(a.get('title', ''))
        if link and ttl: ttl = f'<a href="{esc(link)}">{ttl}</a>'
        return f'\n\n{media}<div class="ibox"><h4>{ttl}</h4>\n\n{(m.group(2) or "").strip()}\n\n</div>\n\n'
    t = re.sub(r'\[(?:grve_media_box|grve_icon_box)([^\]]*)\](?:(.*?)\[/(?:grve_media_box|grve_icon_box)\])?', mbox, t, flags=re.S)
    t = re.sub(r'\[button([^\]]*)\](.*?)\[/button\]', lambda m: button(re.sub(r'<[^>]+>', '', m.group(2)).strip(), attrs(m.group(1)).get('url')), t, flags=re.S)
    t = re.sub(r'\[(?:vc_accordion_tab|vc_tta_section|vc_tab|toggle)([^\]]*)\](.*?)\[/(?:vc_accordion_tab|vc_tta_section|vc_tab|toggle)\]', lambda m: f'\n\n<details><summary>{esc(attrs(m.group(1)).get("title", "More"))}</summary>\n\n{m.group(2)}\n\n</details>\n\n', t, flags=re.S)
    t = re.sub(r'\[(?:vc_separator|grve_divider|divider)[^\]]*\]', '\n\n<hr>\n\n', t)
    # listings and testimonials
    t = re.sub(r'\[grve_blog([^\]]*)\]', lambda m: blog_sc(attrs(m.group(1))), t)
    def ptv(m):
        want = PTV.get(attrs(m.group(1)).get('id', ''))
        if not want: return ''
        ps = [q for q in POSTS if set(want) & set(q.cats)]
        if want == ['tmoamdevotional']: ps = sorted(ps, key=lambda q: int((re.search(r'day-(\d+)', q.path) or [0, 0])[1]))
        return '\n\n<div class="grid">' + ''.join(post_card(q) for q in ps) + '</div>\n\n'
    t = re.sub(r'\[pt_view([^\]]*)\]', ptv, t)
    bt = iter(BOOKTEST.get(p.path, []))
    def stars(m):
        c = next(bt, None)
        if c is None: return ''
        return test_html(TEST.get(c, []), 3 if 'slider' in c else None)
    t = re.sub(r'\[testimonial_stars[^\]]*\]', stars, t)
    t = re.sub(r'\[grve_testimonial[^\]]*\]', lambda m: test_html(TEST.get('_testimonial', [])), t)
    t = re.sub(r'\[(?:contact-form-7|mc4wp_form|wpforms|ninja_form)[^\]]*\]', f'\n\n<p><a class="btn" href="{B}/meet/">Book a meeting with David</a></p>\n\n<p>To get in touch with David, reach out through <a href="{WRG}">Within Reach Global</a> or message him on <a href="https://instagram.com/davidjoannes">Instagram</a> or <a href="https://www.facebook.com/davidjoannesofficial/">Facebook</a>.</p>\n\n', t)
    # anything left that is a known shortcode: drop the tag, keep inner text
    t = re.sub(r'\[/?' + KNOWN + r'(?:\s[^\]]*)?\]', '\n\n', t)
    t = clean_inline(t)
    t = rewrite_urls(t)
    # responsive video iframes
    def ifr(m):
        s = re.search(r'src="([^"]+)"', m.group(0))
        if s and (yt_id(s.group(1)) or 'vimeo.com' in s.group(1)): return video(s.group(1))
        return '\n\n' + re.sub(r'\swidth="[^"]*"', ' width="100%"', m.group(0)) + '\n\n'
    t = re.sub(r'<iframe[^>]*>.*?</iframe>', ifr, t, flags=re.S)
    t = autop(t)
    t = re.sub(r'<p>(?:\s|&nbsp;|<br\s*/?>)*</p>', '', t)
    t = re.sub(r'<p[^>]*>\s*(<div class="embed">.*?</div>)\s*</p>', r'\1', t, flags=re.S)
    if getattr(p, 'is_post', False): t = fix_links(t)
    t = strip_broken(t)
    for _ in range(3):
        t = re.sub(r'<(p|h[1-6]|div|strong|em|b|i|u|a|li|blockquote|center)\b[^>]*>(?:\s|<br\s*/?>)*</\1>', '', t)
    t = re.sub(r'(?:<br\s*/?>\s*){2,}', '<br>\n', t)
    t = re.sub(r'(<(?:p|h[1-6])\b[^>]*>)\s*(?:<br\s*/?>\s*)+', r'\1', t)
    t = re.sub(r'(?:\s*<br\s*/?>)+\s*(</(?:p|h[1-6])>)', r'\1', t)
    if notes:
        t += '<ol class="notes">' + ''.join(f'<li id="fn{n}">{rewrite_urls(clean_inline(x))} <a href="#fnr{n}" aria-label="Back to text">↩</a></li>' for n, x in enumerate(notes, 1)) + '</ol>'
    return t
def plain(t, n=155):
    t = re.sub(r'\[[^\]]*\]', ' ', t); t = re.sub(r'<[^>]+>', ' ', t); t = html.unescape(re.sub(r'\s+', ' ', t)).strip()
    return (t[:n].rsplit(' ', 1)[0] + '…') if len(t) > n else t

# ---------- layout
NAV = [('About', '/about/'), ('Books', '/books/'), ('Podcast', '/missionspulse/'), ('Blog', '/blog/'), ('Resources', '/resources/'), ('Within Reach Global', WRG)]
SOCIAL = [('Instagram', 'https://instagram.com/davidjoannes'), ('Facebook', 'https://www.facebook.com/davidjoannesofficial/'), ('YouTube', 'https://www.youtube.com/channel/UCP6KeC0GSoA2JJZwxIg3c3Q'), ('X', 'https://twitter.com/davidjoannes'), ('LinkedIn', 'https://www.linkedin.com/in/davidjoannes')]
IC = {'Instagram': '<svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="5"/><circle cx="12" cy="12" r="4.2"/><circle cx="17.4" cy="6.6" r="1.1" fill="currentColor" stroke="none"/></svg>',
 'Facebook': '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M13.5 22v-8h2.7l.4-3.2h-3.1V8.7c0-.9.3-1.6 1.6-1.6h1.7V4.2C16.5 4.1 15.5 4 14.4 4 12 4 10.3 5.5 10.3 8.3v2.5H7.5V14h2.8v8z"/></svg>',
 'YouTube': '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M21.6 7.2a2.5 2.5 0 0 0-1.8-1.8C18.2 5 12 5 12 5s-6.2 0-7.8.4A2.5 2.5 0 0 0 2.4 7.2C2 8.8 2 12 2 12s0 3.2.4 4.8a2.5 2.5 0 0 0 1.8 1.8C5.8 19 12 19 12 19s6.2 0 7.8-.4a2.5 2.5 0 0 0 1.8-1.8c.4-1.6.4-4.8.4-4.8s0-3.2-.4-4.8zM10 15V9l5.2 3z"/></svg>',
 'X': '<svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" aria-hidden="true"><path d="M17.5 3h3.1l-6.8 7.8L22 21h-6.3l-4.9-6.4L5.2 21H2.1l7.3-8.3L2 3h6.4l4.4 5.9zm-1.1 16.1h1.7L7.7 4.8H5.9z"/></svg>',
 'LinkedIn': '<svg viewBox="0 0 24 24" width="22" height="22" fill="currentColor" aria-hidden="true"><path d="M4.98 3.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5zM3 9.75h4V21H3zM9.5 9.75h3.8v1.6h.1c.5-1 1.9-2 3.8-2 4.1 0 4.8 2.7 4.8 6.1V21h-4v-4.9c0-1.2 0-2.7-1.6-2.7s-1.9 1.3-1.9 2.6V21h-4z"/></svg>'}
SOCIAL_ICONS = ''.join(f'<a href="{u}" aria-label="{n}" title="{n}">{IC[n]}</a>' for n, u in SOCIAL)
WRITTEN = []
VER = datetime.datetime.now().strftime('%m%d%H%M')
def page(path, title, body, desc='', image='', home=False, redirect='', head=''):
    full = 'David Joannes | Missiologist, Author, and Founder of Within Reach Global' if home else f'{title} | David Joannes'
    nav = ''.join(f'<a href="{u if u.startswith("http") else B + u}"' + (' target="_blank" rel="noopener"' if u.startswith('http') else '') + (' aria-current="page"' if path.startswith(u) else '') + f'>{n}</a>' for n, u in NAV)
    og = f'<meta property="og:image" content="{SITE}{image[len(B):]}">' if image else ''
    fcol = lambda h, links: f'<div><h4>{h}</h4>' + ''.join(f'<a href="{u if u.startswith("http") else B + u}">{n}</a>' for n, u in links) + '</div>'
    def _bk(m):
        slug, anc = m.group(1), m.group(2) or ''
        t = {'#devotional': 'book-the-mind-of-a-missionary-devotional', '#glorioushope': 'glorious-hope-coloring-book'}.get(anc, 'book-' + slug)
        return f'href="{WRG}/{t}"'
    if not redirect: body = re.sub(r'href="' + re.escape(B) + r'/books/(the-mind-of-a-missionary|gospel-privilege|the-space-between-memories|see-the-city)/(#[\w-]*)?"', _bk, body)
    doc = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{redirect or SITE + path}">
{f'<meta http-equiv="refresh" content="0; url={redirect}">' if redirect else ''}
<meta property="og:title" content="{esc(title if not home else full)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="{'website' if home else 'article'}">
<meta property="og:url" content="{SITE}{path}">
{og}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;500;600;700&family=Inter:wght@300;400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{B}/assets/site.css?v={VER}">
{head}
</head>
<body>
<header class="hdr"><div class="wrap">
<a class="brand" href="{B}/">David Joannes</a>
<button class="burger" type="button" aria-label="Menu" aria-expanded="false" aria-controls="mainnav"><span></span><span></span><span></span></button>
<nav class="nav" id="mainnav" aria-label="Main">{nav}<a class="cta" href="{B}/donate/">Give</a></nav>
</div></header>
<main>
{body}
</main>
<footer class="ftr dark">
<div class="wrap">
<a class="igband" href="https://instagram.com/davidjoannes"><span class="igic">{IC['Instagram']}</span><span class="igtxt"><b>Follow @davidjoannes on Instagram</b><span>Stories, photos, and updates from the mission field.</span></span><span class="btn white">Follow on Instagram ↗</span></a>
<div class="fcols">
<div class="fabout"><a class="brand" href="{B}/">David Joannes</a><p>Missiologist, author, podcaster, and Founder of Within Reach Global, giving gospel access to unreached people groups in the 10/40 Window.</p></div>
{fcol('Explore', [('About', '/about/'), ('Books', '/books/'), ('Missions Pulse', '/missionspulse/'), ('Blog', '/blog/'), ('Resources', '/resources/')])}
{fcol('Connect', [('Book a meeting', '/meet/#personal'), ('Be a podcast guest', '/contact/'), ('Contact', '/contact/')])}
{fcol('Give', [('Support David and Lorna', '/donate/'), ('Within Reach Global', WRG), ('Give to WRG', WRG + '/donate')])}
</div>
<div class="bar"><span>© {datetime.date.today().year} David Joannes</span><span class="soc">{SOCIAL_ICONS}<a href="{AMAZON_AUTHOR}" aria-label="Books on Amazon" title="Books on Amazon"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 6.5C10.2 5.2 7.6 4.8 4 5v13c3.6-.2 6.2.2 8 1.5 1.8-1.3 4.4-1.7 8-1.5V5c-3.6-.2-6.2.2-8 1.5z"/><path d="M12 6.5v13"/></svg></a></span></div>
</div>
</footer>
<script>(function(){{var b=document.querySelector('.burger'),n=document.getElementById('mainnav');if(!b||!n)return;b.addEventListener('click',function(){{var o=n.classList.toggle('open');b.classList.toggle('open',o);b.setAttribute('aria-expanded',o?'true':'false')}});function c(){{n.classList.remove('open');b.classList.remove('open');b.setAttribute('aria-expanded','false')}}n.addEventListener('click',function(e){{if(e.target.closest('a'))c()}});document.addEventListener('click',function(e){{if(n.classList.contains('open')&&!e.target.closest('.hdr'))c()}});document.addEventListener('keydown',function(e){{if(e.key==='Escape')c()}})}})();</script>
<script src="{B}/assets/pulse.js?v={VER}" data-base="{B}" defer></script>
<script>document.addEventListener('error',function(e){{var t=e.target;if(t.tagName==='IMG'){{var p=t.closest('.im');if(p)p.classList.add('noimg');t.remove()}}}},true);</script>
</body>
</html>'''
    d = os.path.join(OUT, path.strip('/'))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f: f.write(doc)
    if not redirect: WRITTEN.append(path)
def phead(eyebrow, title, sub='', lede=''):
    return (f'<section class="phead dark"><div class="wrap"><p class="eyebrow">{eyebrow}</p><h1>{esc(title)}</h1>'
            + (f'<p class="lede">{lede}</p>' if lede else '') + (f'<p class="meta">{sub}</p>' if sub else '') + '</div></section>')
CTA = f'''<section class="band"><div class="wrap"><div><p class="eyebrow">David's ministry</p><h2>Help give gospel access to the unreached.</h2><p>Within Reach Global brings the gospel to unreached people groups in the 10/40 Window through compassion ministries, evangelism, discipleship, and church planting.</p></div><a class="btn white" href="{WRG}">Visit withinreachglobal.org ↗</a></div></section>'''
def sec(inner, cls='', id=''): return f'<section class="sec {cls}"' + (f' id="{id}"' if id else '') + f'><div class="wrap">{inner}</div></section>'
def shead(eyebrow, title, more='', lede=''):
    return f'<div class="shead"><div><p class="eyebrow">{eyebrow}</p><h2>{title}</h2>' + (f'<p class="lede">{lede}</p>' if lede else '') + f'</div>{more}</div>'

# ---------- shared data
EXTRA = {}
def extra(url, name):
    EXTRA[url] = 'assets/' + name; return f'{B}/assets/{name}'
H = 'https://withinreachglobal.org/hubfs/'
U = SITE + '/wp-content/uploads/'
BOOKS = [  # same list and order as withinreachglobal.org/books
    ('The Mind of a Missionary', '2024', U + '2024/05/tmoam-001b-1024x1024.png', 'https://a.co/d/3s8SEsu', 'book-the-mind-of-a-missionary'),
    ('The Space Between Memories', '2016/2026', H + 'TSBM-transparent-1.png', 'https://www.amazon.com/dp/1970645016', 'book-the-space-between-memories'),
    ('Faith for Firebrands', '2025', U + '2025/11/fff-front-and-back-1024x1024.png', 'https://bit.ly/faithforfirebrands', 'book-faith-for-firebrands'),
    ('That Lasting Joy', '2025', U + '2025/11/tlj-front-and-back-1024x1024.png', 'https://bit.ly/thatlastingjoy', 'book-that-lasting-joy'),
    ('See the City', '2023', U + '2023/08/gp-038-6x9-Paperback-Upright-Front-Back-COVERVAULT-square-small-1024x1024.png', 'https://a.co/d/5H8AO9O', 'book-see-the-city'),
    ('Glorious Hope', 'Coloring book · 2023', U + '2023/09/gh010.png', 'https://a.co/d/gLZpy4F', 'glorious-hope-coloring-book'),
    ('Gospel Privilege', '2021', U + '2021/05/gp-038-6x9-Paperback-Upright-Front-Back-COVERVAULT-small-2-1001x1024.png', 'https://www.amazon.com/dp/B093FQP6LT', 'book-gospel-privilege'),
    ('The Mind of a Missionary Devotional', '2024', U + '2024/05/tmoam-devotional-001.png', 'https://a.co/d/8TQZzVh', 'book-the-mind-of-a-missionary-devotional'),
    ('A mente de um missionário', 'Português · 2025', H + 'amdum-small.png', 'https://www.amazon.com/mente-mission%C3%A1rio-Mind-Missionary-transculturais-ebook/dp/B0FWRMLP2S', 'book-a-mente-de-um-mission%C3%A1rio'),
    ('La mente de un misionero', 'Español · 2025', H + 'lmdum-small.png', 'https://www.amazon.com/mente-misionero-Mind-Missionary-transculturais-ebook/dp/B0FYX6K4MZ', 'book-la-mente-de-un-misionero'),
]
AMAZON_AUTHOR = 'https://www.amazon.com/stores/David-Joannes/author/B01L36WYVC'
FLAT = {  # flat front covers from the Amazon author page (image ids)
    'The Mind of a Missionary': '71hoj0tlZ6L', 'The Space Between Memories': '81gQKb1iiVL', 'Faith for Firebrands': '61mlevNAmvL',
    'That Lasting Joy': '71jfo+ujCDL', 'See the City': '914zoen8UoL', 'Glorious Hope': '71n0mXLBNlL', 'Gospel Privilege': '71LDOmkWdDS',
    'The Mind of a Missionary Devotional': '716+ns7Zo0L', 'A mente de um missionário': '71jpH9zxEML', 'La mente de un misionero': '71QCtRRKS5L'}
BOOKS = [(t, yr, f'https://m.media-amazon.com/images/I/{FLAT[t]}._SL900_.jpg', buy, slug) for t, yr, img, buy, slug in BOOKS]
def cover(u):
    if 'media-amazon.com' in u: return extra(u, 'books/flat/' + u.rsplit('/', 1)[1].split('.')[0].replace('+', '-') + '.jpg')
    return local(u) if u.startswith(SITE) else extra(u, 'books/' + u.rsplit('/', 1)[1])
def bk(t, yr, img, buy, slug):
    return f'<a class="cover" href="{WRG}/{slug}" title="{esc(t)}"><img src="{cover(img)}" alt="{esc(t)}" loading="lazy"></a>'
SHELF = '<div class="shelf">' + ''.join(bk(*x) for x in BOOKS) + '</div>'
_six = [next(b for b in BOOKS if b[0] == ('Gospel Privilege' if x[0] == 'Glorious Hope' else x[0])) for x in BOOKS[:6]]
HOME_SHELF = '<div class="shelf six">' + ''.join(bk(*x) for x in _six) + '</div>'
COURSES = [('The Mind of a Missionary', '13 lessons', 'the-mind-of-a-missionary-course'), ('Gospel Privilege', '9 lessons', 'gospel-privilege-course'), ('See the City', '12 lessons', 'see-the-city-course')]
portrait = extra(H + 'david-joannes-founder-2.jpg', 'david-joannes.jpg')
# Missions Pulse episodes come from withinreachglobal.org (tools/sync-pulse.py keeps assets/pulse.json current; pulse.js refreshes the pages)
PULSE = json.load(open(os.path.join(HERE, 'pulse.json')))
PULSE_ALL = WRG + '/missions-pulse'
def pulse_href(e): return (B + e['path']) if e.get('path') else esc(e['link'])
def pulse_card(e):
    pic = f'<img src="{esc(e["image"])}" alt="" loading="lazy">' if e.get('image') else ''
    return f'<a class="card" href="{pulse_href(e)}"><div class="im">{pic}</div><div class="k">Missions Pulse · {nice_date(e["date"])}</div><h3>{esc(e["title"])}</h3></a>'
def pulse_ep(e):
    m = re.match(r'#(\d+):\s*(.*)', e['title'])
    return f'<a href="{pulse_href(e)}"><span class="n">{"Episode " + m.group(1) if m else "Episode"}</span><span class="t">{esc(m.group(2) if m else e["title"])}</span></a>'
def pulse_list(kind, n):
    f = pulse_ep if kind == 'ep' else pulse_card
    return ''.join(f(e) for e in PULSE['episodes'][:n])
STATS = ('''<div class="stats"><div><b>30</b><span>years serving in China and Thailand</span></div><div><b>85</b><span>churches planted through Within Reach Global</span></div><div><b>10</b><span>titles in English, Portuguese, and Spanish</span></div><div><b data-pulse-count>PULSECOUNT</b><span>Missions Pulse podcast episodes</span></div></div>'''.replace('PULSECOUNT', str(PULSE['count'])))
def tiles(items): return '<div class="tiles">' + ''.join(f'<a class="tile" href="{u}"><h3>{t}</h3><p>{d}</p><span class="go">{g}</span></a>' for t, d, g, u in items) + '</div>'
RES = [('Spiritual Gifts Test', 'Discover how God has wired you to serve.', 'Take the test ↗', WRG + '/spiritual-gifts-test'),
       ('Gospel Access Score', 'See how much access to the gospel you have had, and who has none.', 'Get your score ↗', WRG + '/gospel-access-score'),
       ('Pray for Thailand', 'An interactive prayer map of all 77 provinces.', 'Open the map ↗', 'https://prayforthailand.com')]
CRS = [(f'{t} Course', f'Free course · {n}', 'Start free ↗', f'{WRG}/{u}') for t, n, u in COURSES]
RICON = {
 'gift': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3.5" y="9" width="17" height="11" rx="1.5"/><path d="M3.5 13h17M12 9v11"/><path d="M12 9c-1.500-3.500-5.500-4-5.500-1.800C6.500 9 9.500 9 12 9zM12 9c1.500-3.500 5.500-4 5.500-1.800C17.500 9 14.500 9 12 9z"/></svg>', 'gauge': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 17a8 8 0 1 1 16 0"/><path d="M12 17l4-6"/><circle cx="12" cy="17" r="1.2"/></svg>', 'pin': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-6.500-6.200-6.500-11a6.500 6.500 0 0 1 13 0c0 4.800-6.500 11-6.500 11z"/><circle cx="12" cy="10" r="2.300"/></svg>', 'mic': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="3" width="6" height="11" rx="3"/><path d="M5.500 11a6.500 6.500 0 0 0 13 0M12 17.500V21M9 21h6"/></svg>', 'book': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 6.500C10.200 5.200 7.600 4.800 4 5v13c3.600-.2 6.200.2 8 1.500 1.800-1.300 4.400-1.700 8-1.500V5c-3.600-.2-6.200.2-8 1.500zM12 6.500v13"/></svg>', 'map': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3.500 6.500l5.500-2 6 2 5.500-2v13l-5.500 2-6-2-5.500 2zM9 4.500v13M15 6.500v13"/></svg>'}
RIMG = {'gift': f'<img src="{extra(H + "wrg-spiritual-gifts-test-share.png", "res/spiritual-gifts-test.jpg")}" alt="" loading="lazy">',
        'gauge': f'<img src="{extra(H + "Gospel%20Access%20Score/gospel-access-score-featured.png", "res/gospel-access-score.png")}" alt="" loading="lazy">'}
def _ri(u, n): return f'<img src="{extra(H + u, "res/" + n)}" alt="" loading="lazy">'
RIMG['pin'] = _ri('general%2030.jpg', 'field-stories.jpg')
RIMG['mic'] = _ri('missions-pulse-008.jpg', 'missions-pulse.jpg')
RIMG['map'] = _ri('pray-for-thailand/hero2.jpg', 'pray-for-thailand.jpg')
RIMG['book'] = '<span class="rcovers">' + ''.join(f'<img src="{cover(b[2])}" alt="" loading="lazy">' for b in BOOKS[:4]) + '</span>'
RCARDS = [  # same modules as the Resources menu on withinreachglobal.org
    ('Spiritual Gifts Test', 'Free test', 'Discover how God has gifted you and where you fit in His mission.', 'Take the test ↗', WRG + '/spiritual-gifts-test', 'gift', 'c-teal'),
    ('Gospel Access Score', '18 questions', 'Eighteen quick questions. See how your access to the gospel compares worldwide.', 'Get your score ↗', WRG + '/gospel-access-score', 'gauge', 'c-dusk'),
    ('Field Stories', 'Stories', 'Real stories of the gospel reaching the unreached.', 'Read the stories ↗', WRG + '/field-stories', 'pin', 'c-navy'),
    ('Missions Pulse Podcast', 'Podcast', 'Conversations from the front lines of missions, hosted by David Joannes.', 'Watch and listen ↗', WRG + '/missions-pulse', 'mic', 'c-red'),
    ('Books', 'Books', 'David Joannes on missions, discipleship, and the unreached.', 'Browse the books ↗', WRG + '/books', 'book', 'c-gold'),
    ('Pray for Thailand', 'Prayer map', 'An interactive prayer map of all 77 provinces.', 'Open the map ↗', 'https://prayforthailand.com', 'map', 'c-sun'),
]
def rcards(items):
    return '<div class="cgrid">' + ''.join(
        f'<a class="ccard" href="{u}"><span class="cpanel ricon {k}"><span class="cbadge">{bd}</span>{RIMG.get(i) or RICON[i]}</span>'
        f'<span class="cbody"><h3>{t}</h3><p>{d}</p><span class="btn">{g}</span></span></a>'
        for t, bd, d, g, u, i, k in items) + '</div>'
RES_CARDS = rcards(RCARDS)
RIMG['course'] = '<span class="rcovers">' + ''.join(f'<img src="{cover(next(b[2] for b in BOOKS if b[0] == t))}" alt="" loading="lazy">' for t in ('The Mind of a Missionary', 'Gospel Privilege', 'See the City')) + '</span>'
HOME_CARDS = rcards(RCARDS[:2] + [('Free Online Courses', 'Courses', "Short lessons built from David's books, with editions for adults, youth, and kids.", 'See the courses →', B + '/resources/#courses', 'course', 'c-navy')])
def _cv(t): return cover(next(b[2] for b in BOOKS if b[0] == t))
_TM = f'{WRG}/the-mind-of-a-missionary-course'
YOUTH = ['elliot', 'studd', 'zinzendorf', 'moffat', 'pullinger', 'eubank', 'ripken', 'carey', 'taylor', 'carmichael', 'richardson', 'baker']
def _y(n): return extra(H + f'the-mind-of-a-missionary-course/youth-img/{n}.jpg', f'courses/youth/{n}.jpg')
def _k(n): return extra(H + f'kids-course/img/L{n}/portrait.jpg', f'courses/kids/L{n}.jpg')
import zlib
def _sq(u, n): return extra(H + u, 'res/' + n)
MODS = {  # inline promo bars for blog posts, modeled on the WRG field-story modules
    'tmoam': ('Free course · 13 lessons', 'The Mind of a Missionary', 'Start free →', lambda: _TM + '?edition=original', lambda: _cv('The Mind of a Missionary'), 'cov'),
    'gp': ('Free course · 9 lessons', 'Gospel Privilege', 'Start free →', lambda: WRG + '/gospel-privilege-course', lambda: _cv('Gospel Privilege'), 'cov'),
    'stc': ('Free course · 12 lessons', 'See the City', 'Start free →', lambda: WRG + '/see-the-city-course', lambda: _cv('See the City'), 'cov'),
    'gifts': ('Free test · 8 minutes', 'Spiritual Gifts Test', 'Take the test →', lambda: WRG + '/spiritual-gifts-test', lambda: _sq('wrg-spiritual-gifts-test-share.png', 'spiritual-gifts-test.jpg'), 'sq right'),
    'gas': ('18 quick questions', 'Gospel Access Score', 'Get your score →', lambda: WRG + '/gospel-access-score', lambda: _sq('Gospel%20Access%20Score/gospel-access-score-featured.png', 'gospel-access-score.png'), 'sq right'),
    'pray': ('Prayer map · 77 provinces', 'Pray for Thailand', 'Open the map →', lambda: 'https://prayforthailand.com', lambda: _sq('pray-for-thailand/hero2.jpg', 'pray-for-thailand.jpg'), 'sq'),
    'youth': ('Free course · Ages 11–18', 'The Mind of a Missionary: Youth Edition', 'Start youth →', lambda: _TM + '?edition=youth', lambda: _y('pullinger'), 'sq'),
    'kids': ('Free course · Ages 5–10', 'The Mind of a Missionary: Kids Edition', 'Start kids →', lambda: _TM + '?edition=kids', lambda: _k(1), 'sq'),
}
ROT = ['tmoam', 'gifts', 'gp', 'gas', 'stc', 'pray', 'youth', 'kids']
def modbar(k):
    eb, t, cta, url, img, cls = MODS[k]
    return (f'<a class="inmod" href="{url()}"><img class="{cls}" src="{img()}" alt="" loading="lazy">'
            f'<span class="im-t"><i>{eb}</i><b>{t}</b></span><span class="im-b">{cta}</span></a>')
_OLD_PROMO = [
    re.compile(r'<p>\s*(?:<a[^>]*>)?\s*<img[^>]*011-Spiritual-Book-Set[^>]*>.*\Z', re.S),            # three-book promo tail
    re.compile(r'<p>\s*(?:<a[^>]*>)?\s*<img[^>]*(?:tmoam-001b|COVERVAULT|gp-phones)[^>]*>\s*(?:</a>)?\s*</p>', re.S),
    re.compile(r'<p>\s*<a[^>]*>\s*(?:Buy the book on Amazon|Get the book)\s*</a>\s*</p>', re.S),
    re.compile(r'<p>\s*Buy <a[^>]*>(?:<em>)?(?:Gospel Privilege|The Mind of a Missionary|The Space Between Memories)[^<]*(?:</em>)?</a>[^<]{0,40}</p>', re.S),
    re.compile(r'<p>(?:(?!</p>).)*Shareables Package(?:(?!</p>).)*</p>', re.S),
    re.compile(r'<p>\s*(?:<a[^>]*>\s*)?<img[^>]*(?:/amazon(?:-\d+x\d+)?\.png|David-Joannes-default|All-Books|MemorySpace-BookCover|Memories-ebook|FRONT-COVER|book001d)[^>]*>\s*(?:</a>)?\s*(?:<br\s*/?>\s*)?</p>', re.S),   # David's own book ads and Amazon buttons
    re.compile(r'<a[^>]*>\s*<img[^>]*(?:/amazon(?:-\d+x\d+)?\.png|David-Joannes-default|All-Books|MemorySpace-BookCover|Memories-ebook|FRONT-COVER|book001d)[^>]*>\s*</a>', re.S),
    re.compile(r'<img[^>]*(?:/amazon(?:-\d+x\d+)?\.png|David-Joannes-default|All-Books|MemorySpace-BookCover|Memories-ebook|FRONT-COVER|book001d)[^>]*>', re.S),
    re.compile(r'<a[^>]*href="https?://(?:www\.)?(?:themindofamissionary|thespacebetweenmemories|gospelprivilege)\.com[^"]*"[^>]*>\s*<img[^>]*>\s*</a>', re.S),
    re.compile(r'<blockquote class="pull">(?:(?!</blockquote>).)*?(?:@\w|#\w|SHARE THIS|Click to)(?:(?!</blockquote>).)*?</blockquote>', re.S),   # old tweet prompts
    re.compile(r'\s*\[?\s*<a[^>]*href="https?://(?:ctt\.ec|ctt\.ac|(?:www\.)?clicktotweet\.com)[^"]*"[^>]*>(?:(?!</a>).)*</a>\s*\]?', re.S),
    re.compile(r'<(p|div)>\s*(?:<em>|<a[^>]*>|\s)*See this post at(?:(?!</\1>).)*</\1>', re.S | re.I),
    re.compile(r'<strong>\s*</strong>'),
    re.compile(r'<p>\s*</p>'),
]
_OWN = [(r'the\s*mind\s*of\s*a\s*missionary|tmoam', 'book-the-mind-of-a-missionary'), (r'space\s*between\s*memories', 'book-the-space-between-memories'),
        (r'gospel\s*privilege', 'book-gospel-privilege'), (r'see[\s-]*the[\s-]*city', 'book-see-the-city')]
_A = re.compile(r'<a\b([^>]*?)href="([^"]+)"([^>]*)>((?:(?!</a>).)*)</a>', re.S)
def own_book_link(m):
    pre, href, post, inner = m.groups()
    if '<img' in inner: return m.group(0)
    text = re.sub(r'<[^>]+>', '', inner).strip()
    h = re.sub(r'^https?://(www\.)?', '', href).lower()
    slug = None
    if re.match(r'(bit\.ly/|themindofamissionary\.com|thespacebetweenmemories\.com|gospelprivilege\.com)', h) or h.startswith('/books/') and h.strip('/') != 'books':
        slug = next((sl for rx, sl in _OWN if re.search(rx, h.replace('-', ' ').replace('/', ' '))), None)
    if not slug and re.match(r'(a\.co|amzn\.to|amazon\.com)/', h) and re.match(r'(?i)(the mind of a missionary|the space between memories|gospel privilege|see the city)', text) and 'devotional' not in text.lower():
        slug = next((sl for rx, sl in _OWN if re.search(rx, text.lower())), None)
    if not slug: return m.group(0)
    if re.fullmatch(r'(?i)(www\.)?(themindofamissionary|thespacebetweenmemories|gospelprivilege)\.com/?', text): inner = 'withinreachglobal.org'
    elif re.fullmatch(r'(?i)purchase this book at amazon today\.?', text): inner = 'Get this book today.'
    elif text.lower() == 'amazon': inner = 'Within Reach Global'
    return f'<a href="{WRG}/{slug}">{inner}</a>'
QUOTES_ADD = {  # added Nov 2026: widely attributed quotes from missionaries
    'Carey, William': [('I can plod. I can persevere in any definite pursuit. To this I owe everything.', 'William Carey, 1761-1834, Missionary to India'),
                       ('When I am gone, say nothing about Dr. Carey; speak about Dr. Carey’s Saviour.', 'William Carey, 1761-1834, Missionary to India'),
                       ('Prayer, secret, fervent, believing prayer, lies at the root of all personal godliness.', 'William Carey, 1761-1834, Missionary to India')],
    'Judson, Adoniram': [('The prospects are as bright as the promises of God.', 'Adoniram Judson, 1788-1850, Missionary to Burma'),
                         ('The motto of every missionary, whether preacher, printer, or schoolmaster, ought to be “Devoted for life.”', 'Adoniram Judson, 1788-1850, Missionary to Burma'),
                         ('I am not tired of my work, neither am I tired of the world; yet when Christ calls me home, I shall go with the gladness of a boy bounding away from his school.', 'Adoniram Judson, 1788-1850, Missionary to Burma')],
    'Taylor, J. Hudson': [('China is not to be won for Christ by quiet, ease-loving men and women.', 'J. Hudson Taylor, 1832-1905, Missionary to China'),
                          ('All our difficulties are only platforms for the manifestations of His grace, power, and love.', 'J. Hudson Taylor, 1832-1905, Missionary to China'),
                          ('There are three stages in every great work of God: first it is impossible, then it is difficult, then it is done.', 'J. Hudson Taylor, 1832-1905, Missionary to China'),
                          ('Do not have your concert first, and then tune your instrument afterwards. Begin the day with the Word of God and prayer.', 'J. Hudson Taylor, 1832-1905, Missionary to China')],
    'Livingstone, David': [('I will place no value on anything I have or may possess, except in relation to the kingdom of Christ.', 'David Livingstone, 1813-1873, Missionary to Africa'),
                           ('Fear God and work hard.', 'David Livingstone, 1813-1873, Missionary to Africa')],
    'Martyn, Henry': [('Now let me burn out for God.', 'Henry Martyn, 1781-1812, Missionary to India and Persia')],
    'Moon, Lottie': [('How many there are who imagine that because Jesus paid it all, they need pay nothing, forgetting that the prime object of their salvation was that they should follow in the footsteps of Jesus Christ in bringing back a lost world to God.', 'Lottie Moon, 1840-1912, Missionary to China'),
                     ('If I had a thousand lives, I would give them all for the women of China.', 'Lottie Moon, 1840-1912, Missionary to China'),
                     ('Surely there can be no deeper joy than that of saving souls.', 'Lottie Moon, 1840-1912, Missionary to China')],
    'Studd, C.T.': [('Only one life, ’twill soon be past; only what’s done for Christ will last.', 'C.T. Studd, 1860-1931, Missionary to China, India, and Africa')],
    'Von Zinzendorf, Nicolaus Ludwig': [('Preach the gospel, die, and be forgotten.', 'Nicolaus Ludwig von Zinzendorf, 1700-1760, Moravian missions leader')],
    'Slessor, Mary': [('Christ sent me to preach the gospel, and He will look after the results.', 'Mary Slessor, 1848-1915, Missionary to Calabar, Nigeria'),
                      ('Prayer is the greatest power God has put into our hands for service. Praying is harder than doing, at least I find it so, but the dynamic lies that way to advance the Kingdom.', 'Mary Slessor, 1848-1915, Missionary to Calabar, Nigeria'),
                      ('God plus one are always a majority.', 'Mary Slessor, 1848-1915, Missionary to Calabar, Nigeria')],
    'Chalmers, James': [('Recall the twenty-one years, give me back all its experience, give me its shipwrecks, give me its standing in the face of death, give it me surrounded with savages with spears and clubs, give it me back again with spears flying about me, with the club knocking me to the ground, give it me back, and I will still be your missionary.', 'James Chalmers, 1841-1901, Missionary to New Guinea')],
    'Mackay, Alexander': [('Within six months you will probably hear that one of us is dead. When the news comes, do not be cast down, but send someone else immediately to take the vacant place.', 'Alexander Mackay, 1849-1890, Missionary to Uganda')],
    'Cox, Melville': [('Let a thousand fall before Africa be given up.', 'Melville Cox, 1799-1833, Missionary to Liberia')],
    'Lull, Raymond': [('He who loves not, lives not; he who lives by the Life cannot die.', 'Raymond Lull, c. 1232-1315, Missionary to North Africa')],
    'Hannington, James': [('I have purchased the road to Uganda with my life.', 'James Hannington, 1847-1885, Missionary bishop in East Africa')],
    'Eliot, John': [('Prayer and pains, through faith in Christ Jesus, will do anything.', 'John Eliot, 1604-1690, Missionary to the Algonquin peoples of New England')],
    'Mills, Samuel J.': [('We can do it if we will.', 'Samuel J. Mills, 1783-1818, at the Haystack Prayer Meeting, 1806')],
    'Trotter, Lilias': [('Take the very hardest thing in your life, the place of difficulty, outward or inward, and expect God to triumph gloriously in that very spot.', 'Lilias Trotter, 1853-1928, Missionary to Algeria')],
}
MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
HIST_HOME = '/missions-history-today-what-happened-on-every-day-of-the-year/'
def hist_entries(b, month):
    out = []
    for x in re.findall(r'<p[^>]*>(.*?)</p>', re.sub(r'<a class="inmod".*?</a>', '', b, flags=re.S), re.S):
        t = re.sub(r'\s+', ' ', x).strip()
        m = re.match(r'(?:<[^>]+>\s*)*%s\s+(\d{1,2})\s*,?\s*((?:ca?\.\s*)?\d{3,4})?\s*(?:,|--|–|—|-)?\s*(.+)$' % month, t, re.S)
        if m: out.append((int(m.group(1)), (m.group(2) or '').strip(), m.group(3).strip()))
    return out
HIST = {}
HIST_ADD = [  # dated events drawn from The Mind of a Missionary (2nd ed.), written fresh for this page
    ('January', 3, '1956', 'The five missionaries of Operation Auca set up camp on a sandbar of the Curaray River in Ecuador, hoping to make peaceful contact with the Waorani.'),
    ('January', 13, '1817', 'Robert Moffat, twenty-two years old, arrives in Cape Town, South Africa, to begin his life’s work.'),
    ('January', 14, '1892', 'Amy Carmichael writes to her mother that everything seems to be saying “Go,” describing her call to people who have never heard of Jesus.'),
    ('January', 18, '1951', 'Amy Carmichael dies in Dohnavur, India, at age eighty-three, after fifty-five years of service without once returning home.'),
    ('January', 30, '1956', 'LIFE magazine runs a ten-page article on the five missionaries killed in Ecuador, “Go Ye and Preach the Gospel: Five Do and Die.”'),
    ('February', 5, '1885', 'The Cambridge Seven, C. T. Studd among them, leave London’s Victoria Station for China with the China Inland Mission.'),
    ('February', 10, '1728', 'Count Zinzendorf presents plans at Herrnhut for evangelism in the West Indies, Greenland, Turkey, and Lapland. The next day, twenty-six Moravians volunteer for world missions.'),
    ('February', 10, '1779', 'William Carey, a shoemaker’s apprentice, comes to faith in Christ.'),
    ('March', 3, '1893', 'Amy Carmichael sails for Japan as the first missionary sent out by the Keswick Convention.'),
    ('March', 6, '1901', 'A seven-year-old girl named Preena runs to Amy Carmichael for refuge. Her arrival marks the beginning of the rescue work that became the Dohnavur Fellowship.'),
    ('March', 13, '1976', 'Heidi Baker comes to Christ after hearing a Navajo preacher at a revival meeting on a reservation where she was serving.'),
    ('March', 18, '1885', 'The Cambridge Seven arrive in Shanghai and continue inland with Hudson Taylor.'),
    ('March', 19, '1962', 'Don and Carol Richardson sail from Vancouver for New Guinea, where they will live among the Sawi people.'),
    ('April', 18, '1874', 'David Livingstone is buried in Westminster Abbey, London. Robert Moffat, his father-in-law, is among the mourners.'),
    ('April', 23, '1900', 'Hudson Taylor addresses the Ecumenical Missionary Conference at Carnegie Hall in New York with a message titled “The Source of Power.”'),
    ('May', 12, '1727', 'Revival begins in the Moravian community at Herrnhut after its members enter the “Brotherly Agreement.” It reaches its height on August 13.'),
    ('May', 12, '1792', 'William Carey publishes An Enquiry Into the Obligations of Christians to Use Means for the Conversion of the Heathens.'),
    ('May', 24, '1980', 'Rolland and Heidi Baker marry. Two weeks later they leave for Indonesia with a one-way ticket and thirty dollars.'),
    ('May', 26, '1700', 'Nikolaus Ludwig von Zinzendorf, future leader of the Moravian missionary movement, is born.'),
    ('May', 26, '1866', 'Hudson and Maria Taylor, their four children, and sixteen of the China Inland Mission’s first missionaries leave London for China.'),
    ('May', 30, '1792', 'William Carey preaches the sermon remembered for the line “Expect great things from God; attempt great things for God.”'),
    ('June', 2, '2017', 'David Eubank of the Free Burma Rangers runs through ISIS gunfire in Mosul, Iraq, to rescue a little girl who had hidden for two days beside her dead mother.'),
    ('June', 6, '1838', 'Robert Moffat arrives in Britain after a three-month voyage from South Africa and is met with an enthusiastic welcome.'),
    ('June', 9, '1834', 'William Carey dies in India after forty-one years of service without a furlough.'),
    ('June', 23, '2012', 'Don Richardson, seventy-seven, returns with his three sons to the Sawi village of Kamur, fifty years after the family first arrived.'),
    ('June', 25, '1865', 'On the beach at Brighton, England, Hudson Taylor surrenders to God’s call to begin a mission to inland China. It becomes the China Inland Mission.'),
    ('June', 30, '1880', 'Dr. Harold Schofield and his wife arrive in China, where he becomes the first foreign doctor in Shanxi.'),
    ('July', 7, '1963', 'Hato becomes the first of the Sawi people to receive Christ, telling Don Richardson that he wants to receive “the Peace Child of God.”'),
    ('July', 13, '1962', 'The Richardson family travels up the Kronkel River to make their home among the Sawi of New Guinea.'),
    ('July', 16, '1931', 'C. T. Studd dies in Ibambi, in what is now the Democratic Republic of the Congo. Two thousand Africans gather the next day to honor him.'),
    ('July', 23, '1870', 'Maria Taylor, wife of Hudson Taylor, dies in China just days after the death of their newborn son, Noel.'),
    ('August', 1, '1883', 'Dr. Harold Schofield dies of typhus after three years in China. His prayers for more workers preceded the coming of the Cambridge Seven.'),
    ('August', 9, '1883', 'Robert Moffat, pioneer missionary to southern Africa, dies.'),
    ('August', 16, '1868', 'A mob of thousands riots against Hudson Taylor’s mission in Yangzhou, China. The unrest lasts a week.'),
    ('August', 23, '1867', 'Grace Taylor, the young daughter of Hudson and Maria Taylor, dies near Hangzhou, China.'),
    ('September', 19, '1853', 'Hudson Taylor, twenty-one years old, sails from England for China.'),
    ('October', 8, '1732', 'Johann Leonhard Dober and David Nitschmann, the first Moravian missionaries, begin their voyage to the West Indies.'),
    ('October', 8, '1958', 'Elisabeth Elliot, her three-year-old daughter Valerie, and Rachel Saint move in with the Waorani, the people who had killed Jim Elliot and Nate Saint.'),
    ('October', 11, '1895', 'Amy Carmichael, twenty-seven, leaves England for India. She never returns.'),
    ('October', 28, '1949', 'Jim Elliot writes in his journal, “He is no fool who gives what he cannot keep to gain that which he cannot lose.”'),
    ('November', 11, '1793', 'William Carey and his family arrive in Calcutta, India.'),
    ('November', 13, '1957', 'Several Waorani women come out of the jungle and invite Elisabeth Elliot to live with their tribe.'),
    ('November', 25, '1881', 'Hudson Taylor and fellow China Inland Mission workers meet in Wuhan and agree to pray daily for seventy more workers for China.'),
    ('November', 25, '2016', 'A three-day celebration of Jackie Pullinger’s fifty years in Hong Kong begins at Kowloon Walled City Park.'),
    ('December', 2, '1860', 'C. T. Studd, future missionary to China, India, and Africa, is born.'),
    ('December', 8, '1840', 'David Livingstone leaves London for Africa, carrying 500 copies of Robert Moffat’s newly printed Scripture translation for Kuruman.'),
    ('December', 15, '1910', 'C. T. Studd, in his fifties and against his doctor’s advice, sails from Liverpool for the heart of Africa.'),
    # from The Mind of a Missionary Devotional
    ('January', 16, '1837', 'Maria Dyer, later Maria Taylor and known as the “Mother” of the China Inland Mission, is born in Penang, Malaysia, to missionary parents.'),
    ('January', 22, '1862', 'Louise “Lulu” Fleming is born on a plantation in Hibernia, Florida. She will become the first African American woman appointed by the Woman’s Baptist Foreign Missionary Society.'),
    ('January', 23, '1821', 'Lott Cary sails for Sierra Leone, becoming the first black American missionary to Africa.'),
    ('February', 7, '1822', 'Lott Cary and his children settle in Monrovia, Liberia, where he begins preaching the gospel and hopes to reach the Bassa, Vey, and Kroo peoples.'),
    ('March', 15, '1807', 'Henry Martyn preaches his first sermon in Urdu, less than a year after arriving in India.'),
    ('March', 20, '1957', 'Isobel Kuhn, missionary to the Lisu people of southwest China, dies.'),
    ('April', 21, '1806', 'Henry Martyn, twenty-five, arrives in Calcutta after a voyage of nine and a half months.'),
    ('May', 18, '1870', 'James Gilmour arrives in Peking (now Beijing) on his way to the Mongols, landing in a country in crisis.'),
    ('May', 21, '1811', 'Henry Martyn arrives in Persia, the first Protestant missionary to live in the country. He finishes his Persian New Testament the following February.'),
    ('May', 23, '1887', 'Lulu Fleming reaches Palabala in the Congo and makes language study her first duty.'),
    ('June', 3, '1905', 'Hudson Taylor, founder of the China Inland Mission, dies in China.'),
    ('June', 12, '1843', 'James Gilmour, future missionary to Mongolia, is born in Glasgow, Scotland.'),
    ('June', 20, '1899', 'Lulu Fleming, pioneer missionary to the Congo, dies.'),
    ('June', 27, '1886', 'The Woman’s Baptist Foreign Missionary Society asks Lulu Fleming to be its first representative to the Congo.'),
    ('July', 5, '1856', 'Ion Keith-Falconer, future missionary to Arabia, is born into Scottish nobility in Edinburgh.'),
    ('July', 10, '1805', 'Henry Martyn sails from England for India.'),
    ('August', 5, '1870', 'James Gilmour sets out across the Gobi Desert for the plains of Mongolia.'),
    ('August', 28, '1727', 'The Moravian community at Herrnhut keeps watch in prayer around the clock, with pairs taking turns through the night. The prayer watch goes on for a hundred years.'),
    ('September', 2, '1863', 'Archibald Forder, future missionary to the Bedouin, is born in Salisbury, England.'),
    ('September', 3, '1891', 'Archibald Forder and his wife sail for the Arabian desert. They later travel four days by camel to Kerak, Jordan.'),
    ('September', 19, '1955', 'Jim Elliot, Nate Saint, and their teammates fly over Waorani territory in Ecuador, dropping gifts to build trust.'),
    ('October', 6, '2023', 'Loren Cunningham, founder of Youth With A Mission, dies.'),
    ('October', 11, '1928', 'Isobel Kuhn leaves Canada for southwest China with the China Inland Mission.'),
    ('October', 16, '1812', 'Henry Martyn dies while traveling home from Persia. His Persian New Testament is later presented to the Shah.'),
    ('November', 6, '1914', 'Archibald Forder, missionary to Bedouin nomads, is jailed on suspicion of being a spy. He spends four years in prison in Damascus.'),
    ('November', 24, '1958', 'LIFE magazine reports on Elisabeth Elliot living among the Waorani under the headline “Child Among Her Father’s Killers.”'),
    ('December', 6, '1934', 'Red Army soldiers take John and Betty Stam and their infant daughter hostage in Anhui Province, China.'),
    ('December', 17, '1901', 'Isobel Kuhn is born in Toronto, Canada.'),
]
HIST_CREDIT = ('<p class="fine h-credit">Compiled by Howard Culbertson. For more original content like this, visit <a href="http://home.snu.edu/~hculbert">home.snu.edu/~hculbert</a>. '
               f'Additional entries are drawn from <a href="{WRG}/book-the-mind-of-a-missionary"><em>The Mind of a Missionary</em></a> and <a href="{WRG}/book-the-mind-of-a-missionary-devotional"><em>The Mind of a Missionary Devotional</em></a> by David Joannes.</p>')
def hist_home():
    tabs = ''.join(f'<button type="button" data-m="{m.lower()}">{m[:3]}</button>' for m in MONTHS)
    cards = ''.join(f'<a class="h-card" href="#{m.lower()}" data-m="{m.lower()}"><span class="h-num">{i + 1:02d}</span><h3>{m}</h3><p>{len(HIST[m])} days of missions history</p><span class="more">Open {m} →</span></a>' for i, m in enumerate(MONTHS))
    secs = ''
    for i, month in enumerate(MONTHS):
        ents = HIST[month]; ml = month.lower()
        days = ''.join(f'<a href="#{ml}-{d}">{d}</a>' for d in sorted({e[0] for e in ents}))
        rows = ''; _seen = set()
        for k, (d, y, t) in enumerate(ents):
            _id = f' id="{ml}-{d}"' if d not in _seen else ''; _seen.add(d)
            rows += f'<li class="h-row"{_id} data-d="{d}"><div class="h-date"><b>{d}</b><span>{month[:3]}</span></div><div class="h-body">' + (f'<i>{esc(y)}</i>' if y else '') + f'<p>{t}</p></div></li>'
            if k == len(ents) // 2: rows += f'<li class="h-mod">{modbar(ROT[i % len(ROT)])}</li>'
        prev, nxt = MONTHS[i - 1], MONTHS[(i + 1) % 12]
        secs += (f'<section class="h-month" id="{ml}" data-i="{i}" hidden><h2>{month}</h2>'
                 f'<div class="h-days"><span>Jump to a day</span>{days}</div><ol class="h-list">{rows}</ol>'
                 f'<div class="h-pn"><a href="#{prev.lower()}">← {prev}</a><a href="#{nxt.lower()}">{nxt} →</a></div></section>')
    js = """<script>(function(){var M=%s,S=[].slice.call(document.querySelectorAll('.h-month')),T=[].slice.call(document.querySelectorAll('.h-months button')),n=new Date(),tm=M[n.getMonth()].toLowerCase(),td=n.getDate();
var C=[].slice.call(document.querySelectorAll('.h-card'));
function show(m,scroll){S.forEach(function(s){s.hidden=s.id!=m});T.concat(C).forEach(function(b){b.classList.toggle('on',b.getAttribute('data-m')==m)});var ab=document.querySelector('#h-bar button.on'),hb=document.getElementById('h-bar');if(ab&&hb.scrollWidth>hb.clientWidth)hb.scrollLeft=ab.offsetLeft-hb.clientWidth/2+ab.offsetWidth/2;if(scroll){var e=scroll==m?document.getElementById('h-bar'):document.getElementById(scroll);if(e)e.scrollIntoView({block:scroll==m?'start':'center'})}}
function route(first){var h=decodeURIComponent(location.hash.slice(1)).toLowerCase(),m=h.split('-')[0];if(M.map(function(x){return x.toLowerCase()}).indexOf(m)>-1)show(m,h);else if(first)show(tm)}
T.concat(C).forEach(function(b){b.addEventListener('click',function(e){e.preventDefault();var m=b.getAttribute('data-m');history.replaceState(null,'','#'+m);show(m,m)})});
window.addEventListener('hashchange',function(){route(false)});
var r=document.getElementById(tm+'-'+td),d=td;for(var k=1;k<4&&!r;k++){r=document.getElementById(tm+'-'+(td-k));if(r)d=td-k}
if(r){r.classList.add('today');var x=document.getElementById('h-otd'),y=r.querySelector('.h-body i');x.querySelector('.h-otd-date').textContent=M[n.getMonth()]+' '+d+(y?', '+y.textContent:'');x.querySelector('.h-otd-text').textContent=r.querySelector('.h-body p').textContent;x.querySelector('a').href='#'+tm+'-'+d;x.hidden=false}
route(true)})();</script>""" % json.dumps(MONTHS)
    return ('<div class="h-page">' + SHARE.split('<script>')[0].replace('class="share"', 'class="share top"') + '<div class="h-intro"><p>God has called simple men and women throughout history to leave a mark of his glory on his storyline, and you are part of it. Here is a look back at what happened in missions history on every day of the year.</p>'
            '<p class="soft-t"><em>“All the days ordained for me were written in your book before one of them came to be.”</em> Psalm 139:16</p></div>'
            '<div id="h-otd" class="h-otd" hidden><p class="eyebrow">On this day in missions history</p><h2 class="h-otd-date"></h2><p class="h-otd-text"></p><a class="btn" href="#">See it in the month →</a></div>'
            f'<h2 class="h-pick" id="h-pick">Pick a month</h2><div class="h-months" id="h-bar">{tabs}</div>{secs}{HIST_CREDIT}{SHARE}</div>{js}')
SHARE = ('<div class="share"><span>Share this</span><a data-s="fb" href="#">Facebook</a><a data-s="x" href="#">X</a><a data-s="wa" href="#">WhatsApp</a><a data-s="in" href="#">LinkedIn</a><a data-s="em" href="#">Email</a><button type="button" data-s="cp">Copy link</button></div>'
         """<script>(function(){var u=encodeURIComponent(location.href.split('#')[0].split('?')[0]),t=encodeURIComponent(document.title.replace(/ \\| David Joannes$/,'')),L={fb:'https://www.facebook.com/sharer/sharer.php?u='+u,x:'https://twitter.com/intent/tweet?url='+u+'&text='+t,wa:'https://wa.me/?text='+t+'%20'+u,'in':'https://www.linkedin.com/sharing/share-offsite/?url='+u,em:'mailto:?subject='+t+'&body='+u};
[].forEach.call(document.querySelectorAll('.share [data-s]'),function(a){var k=a.getAttribute('data-s');if(L[k]){a.href=L[k];if(k!='em'){a.target='_blank';a.rel='noopener'}}else a.addEventListener('click',function(){var v=decodeURIComponent(u);(navigator.clipboard?navigator.clipboard.writeText(v):Promise.reject()).then(function(){a.textContent='Link copied';setTimeout(function(){a.textContent='Copy link'},1800)},function(){prompt('Copy this link',v)})})})})();</script>""")
QREFS = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'quote-refs.json')))   # references as cited in The Mind of a Missionary (2nd ed.)
QFIX = {  # wording checked against The Mind of a Missionary (2nd ed.)
    'he is no fool who gives': '“He is no fool who gives what he cannot keep to gain that which he cannot lose.”',
    'god i pray thee light these idle sticks': '“God, I pray, light these idle sticks of my life, and may I burn up for Thee. Consume my life, my God, for it is Thine. I seek not a long life but a full one like Yours, Lord Jesus.”',
    'god s work done in god s way': '“God’s work done in God’s way will never lack God’s supplies.”',
    'some wish to live within the sound': '“Some wish to live within the sound of church or chapel bell; I want to run a rescue shop within a yard of hell.”',
    'there are three stages in every great work': '“I have found that there are three stages in every great work of God. First, it is impossible, then it is difficult, then it is done.”',
}
def quotes_page(b):
    paras = re.findall(r'<p[^>]*>(.*?)</p>', b, re.S)
    intro, people, cur, seen = [], [], None, False
    for x in paras:
        t = re.sub(r'<[^>]+>', '', x).strip()
        if not seen:
            if x.count('#') > 20: seen = True
            elif 'leave me a comment' not in x: intro.append(x)
            continue
        if not t or re.fullmatch(r'(?i)back to top', t): continue
        m = re.fullmatch(r'\s*<strong>(.*?)</strong>\s*', x, re.S)
        if m and len(t) < 60 and t[0] not in '"“':
            cur = (re.sub(r'<[^>]+>', '', m.group(1)).strip(), []); people.append(cur); continue
        if cur: cur[1].append(x.strip())
    people = [x for x in people if x[0] not in ('Bickle, Mike', 'Anonymous', 'Rankin, Jerry', 'Ravenhill, Leonard')]
    byname = {n: qs for n, qs in people}
    for n, qs in QUOTES_ADD.items():
        new = [f'“{t}” - {a}' for t, a in qs]
        if n in byname: byname[n].extend(new)
        else: people.append((n, new))
    people.sort(key=lambda x: x[0].lower())
    def card(q):
        m = re.match(r'^(.*[”"’\'.!?])\s*(?:<br\s*/?>)?\s*[-–—]{1,2}\s*(.{2,400})$', q, re.S)
        text, attr = (m.group(1).strip(), m.group(2).strip()) if m else (q, '')
        key = re.sub(r'[^a-z0-9]+', ' ', html.unescape(re.sub(r'<[^>]+>', '', text)).lower()).strip()
        ref = QREFS.get(key[:80]) or next((v for k, v in QREFS.items() if key.startswith(k[:60])), '')
        text = next((v for k, v in QFIX.items() if key.startswith(k)), text)
        return (f'<figure class="q"><blockquote>{text}</blockquote>' + (f'<figcaption>{attr}</figcaption>' if attr else '')
                + (f'<cite class="q-ref">Source: {esc(ref)}</cite>' if ref else '') + '<button class="q-copy" type="button">Copy</button></figure>')
    letters = collections.OrderedDict()
    for name, qs in people: letters.setdefault(name[0].upper(), []).append((name, re.sub(r'[^A-Za-z0-9]', '', name), qs))
    nq = sum(len(q) for _, q in people)
    az = ''.join(f'<a href="#q-{L}">{L}</a>' if L in letters else f'<span>{L}</span>' for L in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ')
    index = ''.join(f'<div><h4>{L}</h4>' + ''.join(f'<a href="#{i}">{esc(n)}</a>' for n, i, _ in ppl) + '</div>' for L, ppl in letters.items())
    mods = {'C': 'tmoam', 'L': 'gifts', 'R': 'gas'}
    secs = ''
    for L, ppl in letters.items():
        secs += (f'<section class="q-letter" id="q-{L}"><h2>{L}</h2><div class="q-cols">'
                 + ''.join(f'<div class="q-person" id="{i}"><h3>{esc(n)}</h3>{"".join(card(q) for q in qs)}</div>' for n, i, qs in ppl) + '</div></section>')
        if L in mods: secs += f'<div class="q-mod">{modbar(mods[L])}</div>'
    js = """<script>
(function(){var s=document.getElementById('qq'),o=document.getElementById('qqc'),P=[].slice.call(document.querySelectorAll('.q-person')),Ls=[].slice.call(document.querySelectorAll('.q-letter'));
function r(){var w=s.value.toLowerCase().trim().split(/\\s+/).filter(Boolean),n=0;P.forEach(function(p){var nm=p.querySelector('h3').textContent.toLowerCase(),hit=0;[].forEach.call(p.querySelectorAll('.q'),function(q){var t=nm+' '+q.textContent.toLowerCase(),ok=w.every(function(x){return t.indexOf(x)>-1});q.classList.toggle('hide',!ok);if(ok)hit++});p.classList.toggle('hide',!hit);n+=hit});
Ls.forEach(function(l){l.classList.toggle('hide',!l.querySelector('.q-person:not(.hide)'))});document.body.classList.toggle('q-filtering',w.length>0);o.textContent=w.length?(n?n+(n==1?' quote matches':' quotes match'):'No quotes match. Try a shorter word.'):''}
s.addEventListener('input',r);
document.addEventListener('click',function(e){var b=e.target.closest('.q-copy');if(!b)return;var f=b.parentNode,t=f.querySelector('blockquote').textContent.trim(),c=f.querySelector('figcaption');t+=c?' — '+c.textContent.trim():'';
(navigator.clipboard?navigator.clipboard.writeText(t):Promise.reject()).then(function(){b.textContent='Copied';setTimeout(function(){b.textContent='Copy'},1600)},function(){b.textContent='Select and copy'})});
var h=decodeURIComponent(location.hash.slice(1));if(h&&!document.getElementById(h)){var m=P.filter(function(p){return p.id.toLowerCase()==h.toLowerCase()})[0];if(m)m.scrollIntoView()}
var t=document.getElementById('qtop');window.addEventListener('scroll',function(){t.classList.toggle('on',window.scrollY>900)},{passive:true});t.addEventListener('click',function(){window.scrollTo({top:0,behavior:'smooth'})})})();
</script>"""
    return (f'<div class="q-page">{SHARE.split('<script>')[0].replace('class="share"', 'class="share top"')}<div class="q-intro prose">{"".join(f"<p>{x}</p>" for x in intro)}</div>'
            f'<p class="q-stats"><b>{nq}</b> quotes<span>·</span><b>{len(people)}</b> voices<span>·</span>A to Z</p>'
            f'<div class="q-tools"><input id="qq" class="search" type="search" placeholder="Search a name or a word, like Carey or prayer" aria-label="Search the quotes"><nav class="q-az" aria-label="Jump to a letter">{az}</nav></div>'
            f'<p id="qqc" class="fine" aria-live="polite"></p>'
            f'<details class="q-index"><summary>Browse all {len(people)} names</summary><div class="q-names">{index}</div></details>'
            f'{secs}{SHARE}<button id="qtop" type="button" aria-label="Back to top">↑</button></div>{js}')
def promote(body, p):
    fn = ''
    m = re.search(r'<(?:ol|div|section)[^>]*class="[^"]*\b(?:fn|footnotes|notes)\b', body)
    if m: body, fn = body[:m.start()], body[m.start():]
    for rx in _OLD_PROMO: body = rx.sub('', body)
    body = _A.sub(own_book_link, body)
    txt = re.sub(r'<[^>]+>', '', body)
    seed = zlib.crc32(p.path.encode())
    first = 'gp' if re.search(r'gospel privilege', p.title + txt[:4000], re.I) else 'stc' if re.search(r'see the city', txt, re.I) else None
    order = ROT[seed % len(ROT):] + ROT[:seed % len(ROT)]
    if first: order = [first] + [k for k in order if k != first]
    # candidate insert points: top-level paragraph or heading boundaries
    cands, depth = [], 0
    for t in re.finditer(r'<(/?)(blockquote|ul|ol|table|div|figure|p|h2|h3)\b[^>]*>', body):
        close, tag = t.group(1), t.group(2)
        if tag in ('p', 'h2', 'h3'):
            if not close and depth == 0 and t.start() > 0: cands.append((t.start(), tag != 'p'))
        else: depth += -1 if close else 1
    n = len(body)
    def pick(frac, taken=()):
        ok = [(abs(pos / n - frac) - (0.06 if head else 0), pos) for pos, head in cands if 0.2 < pos / n < 0.93 and all(abs(pos - x) > 1200 for x in taken)]
        return min(ok)[1] if ok else None
    spots = []
    if len(txt) > 1200:
        a = pick(0.42)
        if a is not None: spots.append(a)
        if len(txt) > 6500 and spots:
            b = pick(0.78, spots)
            if b is not None: spots.append(b)
    if not spots: return body + modbar(order[0]) + fn
    for i, pos in sorted(enumerate(sorted(spots)), key=lambda x: -x[1]):
        body = body[:pos] + modbar(order[i]) + body[pos:]
    return body + fn
COURSE_CARDS = (
    '<div class="edgrid">'
    # original
    f'<a class="ed ed-orig" href="{_TM}?edition=original"><span class="ed-vis"><img src="{_cv("The Mind of a Missionary")}" alt="" loading="lazy">'
    '<span class="ring"><b>13</b><i>lessons</i></span></span>'
    '<span class="ed-eyebrow">Free course · Adults &amp; groups</span><h3>The Mind of a Missionary</h3>'
    '<p>The full course for adults, small groups, and anyone exploring a call to missions.</p><span class="pill">Start free →</span></a>'
    # youth
    f'<a class="ed ed-youth" href="{_TM}?edition=youth"><span class="ed-vis"><img class="yhero" src="{_y("pullinger")}" alt="" loading="lazy">'
    '<span class="yside"><span class="yguide">Guide 05 / 12</span><span class="yname">Jackie Pullinger</span><span class="ybar"></span>'
    '<span class="ythumbs">' + ''.join(f'<img src="{_y(n)}" alt="" loading="lazy">' for n in YOUTH) + '</span></span></span>'
    '<span class="ed-eyebrow">[ New · Ages 11–18 ]</span><h3>Youth Edition</h3>'
    '<p>Same twelve guides, made for teens: guide cards, hot takes, weekly challenges, and XP.</p><span class="pill">Start youth →</span></a>'
    # kids
    f'<a class="ed ed-kids" href="{_TM}?edition=kids"><span class="ed-vis"><span class="kfan"><img src="{_k(3)}" alt="" loading="lazy"><img src="{_k(4)}" alt="" loading="lazy"><img src="{_k(1)}" alt="" loading="lazy"></span>'
    '<span class="kstamp"><i>Hero</i><b>1</b><i>of 12</i></span></span>'
    '<span class="ed-eyebrow"><span>New · Ages 5–10</span></span><h3>Kids Edition</h3>'
    '<p>Twelve missionary heroes as read-aloud stories, with passport stamps, hero cards, and coloring pages.</p><span class="pill">Start kids ▶</span></a>'
    '</div><div class="cbanners">'
    + ''.join(f'<a class="cbanner" href="{WRG}/{u}"><img src="{_cv(t)}" alt="" loading="lazy"><span class="cb-txt"><b>Free course</b>{t} — {d}</span><span class="pill">Start free →</span></a>'
              for t, u, d in (('Gospel Privilege', 'gospel-privilege-course', "9 short lessons on the unearned advantage that's meant for everyone."),
                              ('See the City', 'see-the-city-course', '12 short lessons on carrying hope to people who are hurting.')))
    + '</div>')

# ---------- posts
LIVE.update(p.path for p in POSTS)
LIVE.update(['/about/', '/books/', '/missionspulse/', '/blog/', '/resources/', '/donate/', '/meet/', '/contact/', '/books/the-mind-of-a-missionary/', '/books/the-mind-of-a-missionary/notes/',
             '/books/gospel-privilege/', '/books/gospel-privilege/launchteam/', '/books/the-space-between-memories/', '/books/see-the-city/', '/missions-blab/', '/subscribe/', '/fbr/', '/instagram/',
             '/the-memories-i-made-up-chapter-1/', '/thanks/', '/thank-you/'] + [c[2] for c in CATS])
HIST_POSTS = []
for p in POSTS:
    _m = re.fullmatch(r'/missions-history-today-([a-z]+)/', p.path)
    if _m and _m.group(1).capitalize() in MONTHS:
        HIST[_m.group(1).capitalize()] = hist_entries(convert(p), _m.group(1).capitalize()); HIST_POSTS.append(p)
for _hm, _hd, _hy, _ht in HIST_ADD: HIST[_hm].append((_hd, _hy, _ht))
for _hm in HIST: HIST[_hm].sort(key=lambda e: (e[0], int(re.sub(r'\D', '', e[1]) or 0)))
POSTS = [p for p in POSTS if p not in HIST_POSTS]     # the twelve month posts are compiled into the one Missions History Today page
by_cat = collections.defaultdict(list)
for p in POSTS: by_cat[p.cat[2]].append(p)
for p in POSTS:
    body = promote(convert(p), p)
    QP = p.path == '/the-most-epic-monster-list-of-missionary-quotes-on-the-internet/'
    if QP: body = quotes_page(convert(p))
    if p.path == HIST_HOME: body, QP = hist_home(), True
    body = re.sub(r'href="' + re.escape(B) + r'/\?s=', f'href="{B}/blog/?s=', body)
    body = re.sub(r'href="' + re.escape(B) + r'/missions-history-today-(' + '|'.join(m.lower() for m in MONTHS) + r')/?"', lambda m: f'href="{B}{HIST_HOME}#{m.group(1)}"', body)
    body = re.sub(r'href="' + re.escape(B) + r'/blog/\?s=missions(?:\+|%20| )history(?:\+|%20| )today[^"]*"', f'href="{B}{HIST_HOME}"', body, flags=re.I)
    hero = mj_img(p.path) or att(p.thumb, ['large'])
    has_media_top = bool(re.match(r'\s*(<p[^>]*>\s*)?(<div class="embed"|<img|<a[^>]*>\s*<img|<figure)', body))
    fi = f'<img class="featimg" src="{hero}" alt="">' if hero and not has_media_top else ''
    vm = p.meta.get('grve_post_video_embed') or p.meta.get('cb_video_embed_code_post') or ''
    vsrc = re.search(r'https?://[^\s"\'<>]+', vm)
    if vsrc and (yt_id(vsrc.group(0)) or 'vimeo.com' in vsrc.group(0)):
        vid = yt_id(vsrc.group(0))
        if not (vid and vid in body): fi = video(vsrc.group(0)).strip().replace('class="embed"', 'class="embed top"')
    more = [q for q in by_cat[p.cat[2]] if q is not p][:3]
    rel = sec(shead(f'More from {esc(p.cat[1])}', 'Keep reading', f'<a class="more" href="{B}{p.cat[2]}">See all →</a>') + f'<div class="grid">{"".join(post_card(q) for q in more)}</div>', 'soft') if more else ''
    page(p.path, p.title,
         phead(f'<a href="{B}{p.cat[2]}">{esc(p.cat[1])}</a>', p.title, nice_date(p.date))
         + (f'<div class="wrap">{body}</div>' if QP else f'<div class="wrap"><article class="article">{fi}<div class="prose">{body}</div>{SHARE}</article></div>') + CTA + rel,
         desc=plain(p.excerpt or p.raw), image=mj_img(p.path) or att(p.thumb, ['large']))

# ---------- about (native layout, bio text from the old page)
def conv_raw(raw, path='/x/'):
    q = P(); q.raw = raw; q.path = path; return convert(q)
ab = PAGES['/about/']
bio = re.search(r'\[vc_column_text\](.*?)\[/vc_column_text\]', ab.raw, re.S).group(1)
bio = re.sub(r'<span[^>]*>You can find David on.*?</span>', '', bio, flags=re.S).replace('For the last 25 years', 'For the last 30 years')
page('/about/', 'About David',
     f'''<section class="phead dark"><div class="wrap aboutgrid"><div><p class="eyebrow">About</p><h1>David Joannes</h1><p class="lede">Missiologist, author, podcaster, and Founder and CEO of Within Reach Global.</p>
<div class="btns"><a class="btn" href="{B}/meet/#personal">Book a meeting</a></div></div><img src="{portrait}" alt="David Joannes"></div></section>'''
     + f'<div class="wrap"><article class="article"><div class="prose">{conv_raw(bio)}</div></article>{STATS}</div><div style="height:80px"></div>'
     + sec(shead('Books', 'Books by David', f'<a class="more" href="{B}/books/">All books →</a>') + HOME_SHELF, 'soft') + CTA,
     desc=plain(bio), image=portrait)

# ---------- books
DESC = {'book-the-mind-of-a-missionary': 'A practical and inspiring guide to developing the mindset, endurance, and passion needed to thrive in God’s mission.',
 'book-the-space-between-memories': 'A gripping missionary memoir filled with adventure, sacrifice, and the unfolding story of God’s work among the unreached.',
 'book-faith-for-firebrands': 'A bold 31-day devotional inspired by C. T. Studd that calls readers to radical faith, wholehearted surrender, and passionate mission.',
 'book-that-lasting-joy': 'A 31-day devotional inspired by Amy Carmichael that invites readers into deeper joy, devotion to Christ, and a heart for the nations.',
 'book-see-the-city': "A hope-filled journey through suffering, eternity, and the promise of God’s coming city, inspired by a refugee girl's dream in Myanmar.",
 'glorious-hope-coloring-book': 'A meditative coloring book for adults and teens, and a companion to See the City, filled with Scripture, reflection, and creative encouragement.',
 'book-gospel-privilege': 'A compelling call to recognize the privilege of gospel access and live as a bold witness of Christ’s kingdom.',
 'book-the-mind-of-a-missionary-devotional': 'Thirty-one inspiring readings that draw from missionary heroes to strengthen faith and ignite courage for God’s calling.',
 'book-a-mente-de-um-mission%C3%A1rio': 'Um guia prático e inspirador para desenvolver a mentalidade, a perseverança e a paixão necessárias para prosperar na missão de Deus.',
 'book-la-mente-de-un-misionero': 'Una guía práctica e inspiradora para desarrollar la mentalidad, la perseverancia y la pasión necesarias para prosperar en la misión de Dios.'}
def bookcard(t, yr, img, buy, slug):
    more = 'Color it online' if 'coloring' in slug else ('Saiba mais' if 'mente-de-um' in slug else ('Más información' if 'misionero' in slug else 'Learn more'))
    return (f'<div class="bcard"><a class="bcard-cover" href="{WRG}/{slug}"><img src="{cover(img)}" alt="{esc(t)}" loading="lazy"></a><div class="bcard-body"><h3>{esc(t)}</h3>'
            f'<div class="bcard-year">{yr.split(" · ")[-1]} <span aria-label="Five stars">★★★★★</span></div><p>{DESC[slug]}</p>'
            f'<div class="bcard-btns"><a class="btn ink" href="{buy}">Get the book</a><a class="btn outline" href="{WRG}/{slug}">{more} →</a></div></div></div>')
books_bio = 'David Joannes is the Founder and CEO of Within Reach Global and host of the Missions Pulse podcast. He has a love for language, culture, and creative writing, and for the last 30 years he has witnessed God’s kingdom established in forgotten parts of the globe.'
page('/books/', 'Books by David Joannes',
     phead('Books', 'Books by David Joannes', lede='Writing to stir a missions zeal in the Church, particularly for the remaining unreached people groups of the 10/40 Window.')
     + sec(shead('Resources', 'Browse the books', lede='Books to help you discover your God-given calling and find your role in the Great Commission.') + '<div class="bgrid">' + ''.join(bookcard(*x) for x in BOOKS) + '</div>')
     + sec(f'<div class="authorrow"><img src="{portrait}" alt="David Joannes" loading="lazy"><div><p class="eyebrow">About</p><h2>David Joannes</h2><p class="soft-t" style="margin-top:14px">{books_bio}</p><a class="btn ink" href="{B}/about/">Learn more →</a></div></div>', 'soft')
     + sec(shead('Free online courses', "Go deeper with David's books", lede='Short lessons with quizzes and a certificate of completion, hosted by Within Reach Global.') + COURSE_CARDS) + CTA,
     desc='Books by David Joannes on missions, the unreached, and the Great Commission.')
OLDBOOKS = {'/books/the-mind-of-a-missionary/': (0, 'themindofamissionary'), '/books/gospel-privilege/': (6, 'gospelprivilege'),
            '/books/the-space-between-memories/': (1, 'thespacebetweenmemories'), '/books/see-the-city/': (4, 'seethecity')}
BOOK_FWD = {'/books/the-mind-of-a-missionary/': 'book-the-mind-of-a-missionary', '/books/gospel-privilege/': 'book-gospel-privilege',
            '/books/the-space-between-memories/': 'book-the-space-between-memories', '/books/see-the-city/': 'book-see-the-city',
            '/books/the-mind-of-a-missionary/notes/': 'book-the-mind-of-a-missionary#notes'}
for path, slug in BOOK_FWD.items():  # the book pages live on withinreachglobal.org; old addresses forward there
    page(path, 'Books by David Joannes', phead('Books', 'This book has moved') + f'<div class="wrap"><p class="lead" style="padding:48px 0">This page now lives at Within Reach Global. <a href="{WRG}/{slug}">Continue to the book page</a>.</p></div>',
         desc='Books by David Joannes.', redirect=f'{WRG}/{slug}')

# ---------- missions pulse (native layout)
mp = PAGES['/missionspulse/']
gm = re.search(r'Missions Pulse Guests</h2>\s*\[/vc_column_text\]\s*\[vc_column_text\](.*?)\[/vc_column_text\]', mp.raw, re.S)
guests = conv_raw(gm.group(1)) if gm else ''
eps_all = by_cat['/blog/missions-pulse-podcast-posts/']
SUBS = [('YouTube', 'https://www.youtube.com/channel/UCP6KeC0GSoA2JJZwxIg3c3Q'), ('Apple Podcasts', 'https://podcasts.apple.com/us/podcast/missions-pulse/id1820707547'), ('Spotify', 'https://open.spotify.com/show/0YtdYS10W5oTxEelu7wqPN')]
page('/missionspulse/', 'Missions Pulse',
     phead('The podcast', 'Missions Pulse', lede='Know God’s heart. Join His mission. An interview-style video podcast that displays God at work in the world and inspires believers toward their individual role in the Great Commission.')
     + sec(f'<div class="split"><div><div class="embed" style="margin:0"><iframe src="https://www.youtube-nocookie.com/embed/zHkcSetJswM" title="Missions Pulse" loading="lazy" allowfullscreen></iframe></div></div>'
           f'<div><p class="eyebrow">Watch and listen</p><h2>Subscribe wherever you listen.</h2><div class="btns" style="margin:20px 0 32px">{"".join(f"<a class=btn-s href={u}>{n} ↗</a>" for n, u in SUBS)}</div>'
           f'<p class="eyebrow">Be a guest</p><p class="soft-t">Have a story of God at work among the nations? Guests are by invitation, so contact David first and tell him about it. Once he confirms, schedule your interview.</p><div class="btns" style="margin-top:0"><a class="btn" href="{B}/contact/">Contact David first</a><a class="btn-s" href="{B}/meet/#missions-pulse">Interview calendar</a></div></div></div>')
     + sec(shead('Episodes', 'Recent episodes', f'<a class="more" href="{B}/blog/missions-pulse-podcast-posts/">All <span data-pulse-count>{PULSE["count"]}</span> episodes →</a>') + f'<div class="grid" data-pulse="card" data-n="9">{pulse_list("card", 9)}</div>', 'soft')
     + (sec(shead('Guests', 'Missions Pulse guests') + f'<div class="prose guests">{guests}</div>') if guests else '') + CTA,
     desc=plain(mp.raw))

# ---------- other carried-over pages (plain article layout)
KEEP = ['/books/gospel-privilege/launchteam/', '/missions-blab/', '/subscribe/', '/fbr/', '/instagram/',
        '/the-memories-i-made-up-chapter-1/', '/thanks/', '/thank-you/']
TITLES = {'/thank-you/': 'Thank you', '/instagram/': 'David Joannes on Instagram', '/thanks/': 'Thanks!'}
for path in KEEP:
    p = PAGES.get(path)
    if not p: print('missing page', path); continue
    title = TITLES.get(path) or html.unescape(p.title) or 'David Joannes'
    page(path, title, phead('David Joannes', title) + f'<div class="wrap"><article class="article"><div class="prose plain">{convert(p)}</div></article></div>' + CTA, desc=plain(p.raw))

# ---------- The Mind of a Missionary: notes and references (from the second edition; see scripts/parse_notes.py)
def notes_page():
    d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tmoam-notes.json')))
    def link(t):
        if '<a ' in t: return t
        return re.sub(r'(https?://[^\s<]+?)([.,;)]*)(?=\s|$|<)', lambda m: f'<a href="{m.group(1)}" rel="noopener" target="_blank">{m.group(1).replace("&amp;", "&amp;")}</a>{m.group(2)}', t)
    def cid(title):
        m = re.match(r'Chapter (\d+)', title)
        return f'ch{m.group(1)}' if m else ('in' if title.startswith('Intro') else 'con')
    def chip(title):
        m = re.match(r'Chapter (\d+)', title)
        return m.group(1) if m else ('Intro' if title.startswith('Intro') else 'End')
    nn = sum(len(c['notes']) for c in d['notes']); nr = sum(len(x['items']) for x in d['refs'])
    chips = ''.join(f'<a href="#{cid(c["title"])}" title="{esc(c["title"])}">{chip(c["title"])}</a>' for c in d['notes']) + '<a href="#ref" class="wide">References</a>'
    toc = ''.join(f'<a href="#{cid(c["title"])}"><b>{esc(c["title"])}</b><span>{len(c["notes"])} note{"s" if len(c["notes"]) != 1 else ""}</span></a>' for c in d['notes'])
    toc += f'<a href="#ref"><b>References</b><span>{nr} sources</span></a>'
    secs = ''
    for c in d['notes']:
        i = cid(c['title'])
        secs += (f'<section class="n-ch" id="{i}"><h2>{esc(c["title"])}</h2><ol class="n-list">'
                 + ''.join(f'<li class="n-item" id="{i}-n{n["n"]}"><span class="n-num">{n["n"]}</span><span class="n-txt">{link(n["t"])}</span></li>' for n in c['notes']) + '</ol></section>')
    rid = lambda t: 'ref-' + re.sub(r'[^a-z]+', '-', t.lower()).strip('-')
    rchips = ''.join(f'<a href="#{rid(x["title"])}">{esc(x["title"])} <span>{len(x["items"])}</span></a>' for x in d['refs'])
    refs = (f'<section class="n-ch n-refs" id="ref"><h2>References</h2><p class="n-refintro">These resources are widely available wherever books are sold, on YouTube, or through online searches. Many of the older historical sources can be found in the Internet Archive.</p><div class="n-rchips">{rchips}</div>'
            + ''.join(f'<h3 id="{rid(x["title"])}">{esc(x["title"])}</h3><ul class="n-list n-rlist">' + ''.join(f'<li class="n-item"><span class="n-txt">{link(it)}</span></li>' for it in x['items']) + '</ul>' for x in d['refs']) + '</section>')
    js = """<script>(function(){var s=document.getElementById('nq'),o=document.getElementById('nqc'),I=[].slice.call(document.querySelectorAll('.n-item')),C=[].slice.call(document.querySelectorAll('.n-ch')),H=[].slice.call(document.querySelectorAll('.n-refs h3'));
function r(){var w=s.value.toLowerCase().trim().split(/\\s+/).filter(Boolean),n=0;I.forEach(function(e){var t=e.textContent.toLowerCase(),ok=w.every(function(x){return t.indexOf(x)>-1});e.classList.toggle('hide',!ok);if(ok)n++});
C.forEach(function(c){c.classList.toggle('hide',!c.querySelector('.n-item:not(.hide)'))});H.forEach(function(h){var u=h.nextElementSibling;h.classList.toggle('hide',!u.querySelector('.n-item:not(.hide)'))});
document.body.classList.toggle('n-filtering',w.length>0);o.textContent=w.length?(n?n+(n==1?' match':' matches'):'Nothing matches. Try a shorter word.'):''}
s.addEventListener('input',r);
var L=[].slice.call(document.querySelectorAll('.n-bar a')),t=document.getElementById('qtop');
function spy(){var y=window.scrollY+150,cur='';C.forEach(function(c){if(c.offsetTop<=y)cur=c.id});L.forEach(function(a){a.classList.toggle('on',a.getAttribute('href')=='#'+cur)});t.classList.toggle('on',window.scrollY>900);var a=document.querySelector('.n-bar a.on'),b=document.querySelector('.n-bar');if(a&&b.scrollWidth>b.clientWidth)b.scrollLeft=a.offsetLeft-b.clientWidth/2+a.offsetWidth/2}
window.addEventListener('scroll',spy,{passive:true});spy();t.addEventListener('click',function(){window.scrollTo({top:0})})})();</script>"""
    body = (f'<div class="wrap"><div class="n-page"><div class="n-intro"><p>Every note and citation from <a href="{WRG}/book-the-mind-of-a-missionary"><em>The Mind of a Missionary</em></a>, chapter by chapter, followed by the full list of references. '
            'There are many gems waiting in these books, archives, articles, journals, sermons, videos, and websites. Jump to a chapter, or search for a name, a title, or a word.</p>'
            f'<p class="q-stats"><b>{nn}</b> notes<span>·</span><b>{len(d["notes"])}</b> sections<span>·</span><b>{nr}</b> references</p></div>'
            f'<div class="n-tools"><input id="nq" class="search" type="search" placeholder="Search the notes, like Carmichael or Perspectives" aria-label="Search the notes"><nav class="n-bar" aria-label="Chapters">{chips}</nav></div>'
            f'<p id="nqc" class="fine" aria-live="polite"></p><div class="n-toc">{toc}</div>{secs}{refs}'
            f'<p class="fine" style="margin-top:32px">Notes and references are from the second edition of <em>The Mind of a Missionary</em> by David Joannes.</p>{SHARE}<button id="qtop" type="button" aria-label="Back to top">↑</button></div></div>{js}')
    page('/books/the-mind-of-a-missionary/notes/', 'The Mind of a Missionary: Notes and References', phead('The Mind of a Missionary', 'Notes and References') + body + CTA,
         desc='Every note, citation, and reference from The Mind of a Missionary by David Joannes, chapter by chapter.')

# ---------- donate + meeting
og_fam = extra(H + 'joannes-default-image.jpg', 'donate/joannes-family.jpg')
fam = extra(H + 'photo-41.jpg', 'donate/photo-41.jpg')
strip = ''.join(f'<img src="{extra(H + n + ".jpg", "donate/" + n + ".jpg")}" alt="{a}" loading="lazy">' for n, a in (('photo-21', 'David preaching with a Thai interpreter'), ('photo-31', 'David with a child in a village'), ('photo61', 'Lorna with a grandmother and child')))
venmo = extra(H + 'venmo_qrcode-joannes.jpg', 'donate/venmo-qr.jpg'); zelle = extra(H + 'zelle_qrcode-joannes.jpg', 'donate/zelle-qr.jpg'); bank = extra(H + 'union-bank-transfer.jpg', 'donate/union-bank-qr.jpg')
WHY = [('Lead and shepherd', 'Frees them to lead a growing team across Thailand and Southeast Asia.'), ('Stay on the ground', 'Sustains the relationships, language, and trust that 30 years on the field have built.'),
       ('Cast vision', 'Fuels new outreach, including new church plants and emerging leaders.'), ('Strengthen the foundation', 'Supports the ministry base, including the Chiang Mai House of Prayer and the Access Campaign.'),
       ('Mentor the next generation', 'Invests in indigenous missionaries who will carry the work forward.')]
donate = f'''<section class="phead dark"><div class="wrap aboutgrid"><div><p class="eyebrow">Partner with the Joannes family</p><h1>A family on mission, serving the unreached for 30 years.</h1>
<p class="lede">David and Lorna are the founders of Within Reach Global and full-time missionaries in Chiang Mai, Thailand, with their two daughters. For three decades they have planted churches, discipled leaders, and built a movement that keeps multiplying.</p>
<div class="btns"><a class="btn" href="#give">Become a monthly partner</a><a class="btn ghost" href="#other">Other ways to give</a></div></div><img src="{fam}" alt="David and Lorna Joannes with their two daughters"></div></section>
<div class="strip">{strip}</div>
''' + sec(f'<p class="eyebrow">The impact</p><h2>Why partner with David and Lorna.</h2><div class="whygrid">{"".join(f"<div><i>{n:02d}</i><b>{a}</b><span>{b}</span></div>" for n, (a, b) in enumerate(WHY, 1))}</div>') + sec(f'''<div class="split" style="align-items:flex-start"><div><p class="eyebrow">Give</p><h2>Become a monthly financial partner.</h2>
<p class="soft-t">Your monthly gift keeps David and Lorna on the field among the unreached.</p>
<p class="fine">Gifts made through this form go to Within Reach Global, Inc., a 501(c)(3) nonprofit (EIN 26-3499455), and are tax-deductible in the United States.</p></div>
<div class="dbox"><script src="https://donorbox.org/widget.js" paypalExpress="false"></script>
<iframe src="https://donorbox.org/embed/missionaries-joannes" name="donorbox" title="Donate to the Joannes family" allowpaymentrequest="allowpaymentrequest" seamless="seamless" frameborder="0" scrolling="no" height="900px" width="100%" style="max-width:500px;min-width:250px;max-height:none!important" allow="payment"></iframe></div></div>''', 'soft', 'give') + sec(shead('Other ways to give', 'Prefer another method?', lede='Gifts made by Venmo, Zelle, or bank transfer are not tax-deductible.') + f'''<div class="tiles ways">
<div class="tile"><h3>Venmo</h3><p>@davidjoannes</p><img src="{venmo}" alt="Venmo QR code for @davidjoannes" loading="lazy"></div>
<div class="tile"><h3>Zelle</h3><p>david@withinreachglobal.org</p><img src="{zelle}" alt="Zelle QR code for david@withinreachglobal.org" loading="lazy"></div>
<div class="tile"><h3>Philippines bank transfer</h3><p>For partners in the Philippines.<br>Union Bank<br>Lorna Macadangdang Joannes<br>1025 1004 8465</p><img src="{bank}" alt="Union Bank transfer QR code" loading="lazy"></div>
</div>''', '', 'other') + f'''<section class="band"><div class="wrap"><div><p class="eyebrow">Within Reach Global</p><h2>Send someone to the unreached.</h2><p>Local Thai and Asian missionaries reach the spiritually poorest communities. A monthly gift of $650 fully supports one missionary.</p></div><a class="btn white" href="{WRG}/donate">Give through Within Reach Global ↗</a></div></section>'''
page('/donate/', 'Partner with the Joannes family', donate, desc='Become a monthly partner with David and Lorna Joannes, founders of Within Reach Global and missionaries in Chiang Mai, Thailand.', image=og_fam)
MEET = 'https://meetings-na2.hubspot.com/david-joannes'
def cal(id, eyebrow, h, text, url):
    return sec(f'<p class="eyebrow">{eyebrow}</p><h2>{h}</h2><p class="soft-t">{text}</p><div class="calwrap"><span>Loading calendar…</span><iframe class="cal" src="{url}?embed=true" title="{h}"></iframe></div><p class="fine">Calendar not loading? <a href="{url}">Open the booking page ↗</a></p>', '', id)
page('/meet/', 'Book a meeting with David', phead('Book a meeting', 'Get time on David’s calendar', lede='Book a personal meeting, or schedule a Missions Pulse interview once you have connected with David.')
     + f'<div class="wrap"><nav class="chips" aria-label="Meeting types" style="margin-top:32px"><a href="#personal">Personal meeting</a><a href="#missions-pulse">Podcast interview</a></nav></div>'
     + cal('personal', 'Personal', 'Book a meeting with David', 'For partners, pastors, and anyone who wants to talk about missions, books, or serving with Within Reach Global.', MEET)
     + sec(f'<p class="eyebrow">Missions Pulse</p><h2>Schedule a podcast interview</h2><div class="notice"><b>Please connect with David first.</b> Missions Pulse guests are by invitation. <a href="{B}/contact/">Send David a note</a> about who you are and the story you would share, and schedule below once he has confirmed.</div><div class="calwrap"><span>Loading calendar…</span><iframe class="cal" src="{MEET}/missions-pulse?embed=true" title="Schedule a Missions Pulse interview" loading="lazy"></iframe></div><p class="fine">Calendar not loading? <a href="{MEET}/missions-pulse">Open the booking page ↗</a></p>', 'soft', 'missions-pulse')
     + CTA,
     desc='Book a personal meeting with David Joannes or schedule a Missions Pulse podcast interview.',
     head='<link rel="preconnect" href="https://meetings-na2.hubspot.com"><link rel="preconnect" href="https://static.hsappsstatic.net" crossorigin><link rel="preconnect" href="https://api-na2.hubspot.com" crossorigin>')

# ---------- contact (HubSpot form)
page('/contact/', 'Contact David', phead('Contact', 'Get in touch with David', lede='Questions about missions, books, speaking, or Within Reach Global? Send a note and David will get back to you.')
     + sec(f"""<div class="split" style="align-items:flex-start"><div style="flex:3 1 460px"><div class="hsform"><script charset="utf-8" src="https://js-na2.hsforms.net/forms/embed/v2.js"></script>
<script>hbspt.forms.create({{portalId: "245175322", formId: "5e54533c-c6ae-4e40-88c4-c3753a88e001", region: "na2"}});</script></div></div>
<div class="why" style="flex:2 1 300px"><div><b>Book a meeting</b><span>Pick a time on David's calendar for a call.</span><a class="more" href="{B}/meet/#personal">Open the calendar →</a></div>
<div><b>Be a podcast guest</b><span>Please connect with David here first. Once he confirms, schedule your Missions Pulse interview.</span><a class="more" href="{B}/meet/#missions-pulse">Interview calendar →</a></div>
<div><b>Follow along</b><span>Life and ministry on Instagram.</span><a class="more" href="https://instagram.com/davidjoannes">@davidjoannes ↗</a></div></div></div>""") + CTA,
     desc='Contact David Joannes about missions, books, speaking, or Within Reach Global.')

# ---------- the two evergreen posts, shown on the home and resources pages
_FEAT = [('/missions-history-today-what-happened-on-every-day-of-the-year/', 'On this day', 'Missions History Today', 'What happened on every day of the year in missions history, with today’s date ready when you land.', 'See today in missions history →'),
         ('/the-most-epic-monster-list-of-missionary-quotes-on-the-internet/', 'Quotes', 'The Most Epic Monster List of Missionary Quotes', 'Hundreds of quotes from missionaries past and present, A to Z, easy to search and share.', 'Browse the quotes →')]
def _feat(path, k, t, d, go):
    fp = next(q for q in POSTS if q.path == path)
    im = mj_img(path) or att(fp.thumb, ['large', 'medium_large'])
    return (f'<a class="feat" href="{B}{path}"><div class="im">' + (f'<img src="{im}" alt="" loading="lazy">' if im else '') + f'</div><div class="feat-b"><p class="eyebrow">{k}</p><h3>{t}</h3><p>{d}</p><span class="more">{go}</span></div></a>')
FEAT2 = '<div class="feat2">' + ''.join(_feat(*x) for x in _FEAT) + '</div>'
# ---------- resources
page('/resources/', 'Resources', phead('Resources', 'Tools to find your part in the Great Commission', lede='Free tests, maps, and courses from David and Within Reach Global.')
     + sec(shead('Free tools and stories', 'Start here') + RES_CARDS) + sec(shead('Free online courses', "Go deeper with David's books", lede='Short lessons with quizzes and a certificate of completion.') + COURSE_CARDS, 'soft', 'courses')
     + sec(shead('Reader favorites', 'Two posts worth bookmarking') + FEAT2, '', 'favorites')
     + CTA,
     desc='Free missions resources from David Joannes: spiritual gifts test, Gospel Access Score, Pray for Thailand, and online courses.')

# ---------- blog listings
def pulse_slot(posts, path):
    cards = [post_card(p) for p in posts]; slot = '<!--pulse-new--><!--/pulse-new-->'
    if path == '/blog/': k = sum(1 for p in posts[:4] if p.path in FEATURED_FIRST); return ''.join(cards[:k]) + slot + ''.join(cards[k:])
    if path == '/blog/missions-pulse-podcast-posts/': return slot + ''.join(cards)
    return ''.join(cards)
def listing(path, title, posts, active):
    chips = f'<a href="{B}/blog/"' + (' class="on"' if active == '/blog/' else '') + '>All</a>' + ''.join(f'<a href="{B}{u}"' + (' class="on"' if active == u else '') + f'>{esc(l)}</a>' for _, l, u in CATS[::-1])
    js = '''<script>
(function(){var c=[].slice.call(document.querySelectorAll('#posts .card')),n=24,q='',b=document.getElementById('morebtn'),s=document.getElementById('q');
var o=document.getElementById('qcount');
function r(){var k=0,m=0,w=q.split(/\\s+/).filter(Boolean);c.forEach(function(e){var t=e.getAttribute('data-t'),ok=w.every(function(x){return t.indexOf(x)>-1});if(ok)m++;var show=ok&&k<n;if(show)k++;e.classList.toggle('hide',!show)});b.classList.toggle('hide',k>=m);o.textContent=q?(m?m+(m==1?' post matches':' posts match')+' “'+s.value.trim()+'”':'No posts match “'+s.value.trim()+'”. Try a shorter word.'):''}
b.addEventListener('click',function(){n+=24;r()});s.addEventListener('input',function(){q=s.value.toLowerCase().trim();n=24;r()});
s.addEventListener('keydown',function(e){if(e.key=='Enter'){e.preventDefault();s.blur()}});
var u=new URLSearchParams(location.search).get('s')||new URLSearchParams(location.search).get('q');if(u){s.value=u.replace(/:$/,'');q=s.value.toLowerCase().trim()}r()})();
</script>'''
    body = (phead('Blog', title, f'{len(posts)} posts') + f'<section class="sec" style="padding-top:28px"><div class="wrap"><nav class="chips" aria-label="Categories">{chips}</nav>'
            f'<p style="margin:24px 0 32px"><label for="q" class="fine" style="display:block;font-weight:600;margin-bottom:6px">Search posts</label><input id="q" class="search" type="search" placeholder="Search posts by title or topic"><span id="qcount" class="fine" style="display:block;margin-top:8px;min-height:1.4em" aria-live="polite"></span></p>'
            f'<div class="grid" id="posts">{pulse_slot(posts, path)}</div><p class="center" style="margin-top:44px"><button id="morebtn" class="btn ink" type="button">Show more posts</button></p></div></section>' + js + CTA)
    page(path, title, body, desc=f'{title} by David Joannes.')
listing('/blog/', 'Essays, devotionals, and stories from the field', POSTS, '/blog/')
LT = {'/blog/missions-blogs/': 'Missions Blogs', '/blog/davids-books-blogs/': "Posts About David's Books", '/blog/book-reviews-by-david/': 'Book Reviews by David',
      '/blog/missions-pulse-podcast-posts/': 'Missions Pulse Podcast Episodes', '/blog/podcast-appearances-posts/': 'Podcast Appearances', '/blog/within-reach-global-posts/': 'Within Reach Global Posts'}
for _, l, u in CATS: listing(u, LT[u], by_cat[u], u)

# ---------- home
eps = eps_all[:4]
def ep(p):
    m = re.match(r'#(\d+):\s*(.*)', p.title)
    return f'<a href="{B}{p.path}"><span class="n">{"Episode " + m.group(1) if m else "Episode"}</span><span class="t">{esc(m.group(2) if m else p.title)}</span></a>'
nik = next((d for d in TEST.get('_testimonial', []) if 'ripken' in d['name'].lower()), None)
quote = f'<section class="sec"><div class="wrap quote"><blockquote>{clean_inline(nik["body"])}</blockquote><div class="by"><b>Nik Ripken</b><span>Author, The Insanity of God</span></div></div></section>' if nik else ''
latest = [p for p in POSTS if p.cat[2] != '/blog/missions-pulse-podcast-posts/' and p.path not in FEATURED_FIRST][:3]
home = f'''<section class="hero dark"><div class="wrap">
<div class="txt"><p class="eyebrow">Missiologist · Author · Podcaster</p>
<h1>Every people group deserves access to the gospel.</h1>
<p class="lede">David Joannes is the Founder and CEO of Within Reach Global. For three decades he has served in China and Thailand, writing and speaking on the Church's unfinished task among the unreached.</p>
<div class="btns"><a class="btn" href="{WRG}">Explore Within Reach Global ↗</a><a class="btn ghost" href="{B}/books/">Read David's books</a></div></div>
<div class="pic"><img src="{portrait}" alt="David Joannes"></div>
</div></section>
''' + sec(shead('Books', 'Books to stir the Church toward the unreached', f'<a class="more" href="{B}/books/">All books →</a>') + HOME_SHELF, 'soft', 'books') + f'''
<section class="sec" id="about"><div class="wrap"><div class="split"><div><p class="eyebrow">About David</p><h2>From Bible smuggler to mission leader.</h2><figure class="smug"><img src="{B}/assets/david-bible-smuggler.jpg" alt="A young David Joannes with stacks of Bibles bound for China" loading="lazy" width="744" height="418"><figcaption>David with Bibles bound for China.</figcaption></figure></div>
<div><p class="soft-t">David began his missionary journey by smuggling Bibles into China. After serving for 15 years in Southwest China, he now lives in Chiang Mai, Thailand, with his wife, Lorna, and their two daughters.</p>
<p class="soft-t">He has been interrogated for his faith over 20 times and has been apprehended by over 100 child soldiers carrying AK-47s. Today he leads Within Reach Global, hosts the Missions Pulse podcast, and writes to help the Church see the unreached.</p>
<a class="more" href="{B}/about/">Read David's story →</a></div></div>{STATS}</div></section>
<section class="sec red" id="mission"><div class="wrap split" style="align-items:center"><div><p class="eyebrow">David's ministry</p><h2 class="big">Within Reach Global</h2>
<p class="lede">Since 1997, Within Reach Global has brought gospel access to unreached people groups in the 10/40 Window through compassion ministries, evangelism, discipleship, and church planting.</p>
<a class="btn white" href="{WRG}">Visit withinreachglobal.org ↗</a></div>
<div class="rows"><a href="https://prayforthailand.com"><span class="t">Pray</span><span class="s">Pray for Thailand, province by province →</span></a><a href="{WRG}/project-local-missionaries"><span class="t">Give</span><span class="s">Empower indigenous missionaries →</span></a><a href="{WRG}/go"><span class="t">Go</span><span class="s">Apply to serve →</span></a></div></div></section>
''' + sec(shead('The podcast', 'Missions Pulse', f'<a class="more" href="{B}/missionspulse/">About the podcast →</a>', 'God at work in the world, and your role in the Great Commission.')
          + f'<div class="split"><div style="flex:3 1 460px"><div class="embed" style="margin:0"><iframe src="https://www.youtube-nocookie.com/embed/zHkcSetJswM" title="Missions Pulse" loading="lazy" allowfullscreen></iframe></div></div><div class="eps" style="flex:2 1 340px"><div data-pulse="ep" data-n="3" style="display:contents">{pulse_list("ep", 3)}</div><a class="more" href="{B}/blog/missions-pulse-podcast-posts/">All <span data-pulse-count>{PULSE["count"]}</span> episodes →</a></div></div>', 'dark', 'podcast') + sec(shead('Free resources', 'Tools to find your part in the Great Commission', f'<a class="more" href="{B}/resources/">All resources →</a>') + HOME_CARDS, 'soft', 'resources') + sec(shead('Blog', 'Essays, devotionals, and stories from the field', f'<a class="more" href="{B}/blog/">Read the blog →</a>') + f'<div class="grid">{"".join(post_card(p) for p in latest)}</div>', '', 'writing') + sec(shead('Reader favorites', 'Two posts worth bookmarking') + FEAT2, 'soft', 'favorites')
page('/', 'David Joannes', home, desc='David Joannes is a missiologist, author, podcaster, and the Founder and CEO of Within Reach Global, giving gospel access to unreached people groups in the 10/40 Window.', image=portrait, home=True)

# ---------- extras
os.makedirs(os.path.join(OUT, 'assets'), exist_ok=True)
shutil.copy(os.path.join(HERE, 'site.css'), os.path.join(OUT, 'assets', 'site.css'))
shutil.copy(os.path.join(HERE, 'pulse.js'), os.path.join(OUT, 'assets', 'pulse.js'))
if not os.path.exists(os.path.join(OUT, 'assets', 'pulse.json')): shutil.copy(os.path.join(HERE, 'pulse.json'), os.path.join(OUT, 'assets', 'pulse.json'))
page('/404/', 'Page not found', phead('404', 'This page has moved or no longer exists.') + f'<div class="wrap"><div class="article prose"><p>Try the <a href="{B}/blog/">blog</a>, the <a href="{B}/books/">books</a>, or head back <a href="{B}/">home</a>.</p></div></div>')
shutil.copy(os.path.join(OUT, '404', 'index.html'), os.path.join(OUT, '404.html'))
WRITTEN.remove('/404/')
_tp = '/_episode-template/'
page(_tp, '%%TITLE%%', phead(f'<a href="{B}/blog/missions-pulse-podcast-posts/">Missions Pulse</a>', '%%TITLE%%', '%%DATE%%')
     + f'<div class="wrap"><article class="article"><div class="prose">%%BODY%%</div>{SHARE}</article></div>' + CTA
     + sec(shead('More from Missions Pulse', 'Keep listening', f'<a class="more" href="{B}/blog/missions-pulse-podcast-posts/">See all →</a>') + '<div class="grid" data-pulse="card" data-n="3"></div>', 'soft'), desc='%%DESC%%')
WRITTEN.remove(_tp)
_t = open(os.path.join(OUT, _tp.strip('/'), 'index.html'), encoding='utf-8').read()
_t = _t.replace(f'<link rel="canonical" href="{SITE}{_tp}">', '<link rel="canonical" href="%%CANON%%">').replace(f'<meta property="og:url" content="{SITE}{_tp}">', f'<meta property="og:url" content="{SITE}%%PATH%%">\n<meta property="og:image" content="%%OGIMG%%">')
assert '%%CANON%%' in _t and '%%OGIMG%%' in _t
os.makedirs(os.path.join(OUT, 'tools'), exist_ok=True)
open(os.path.join(OUT, 'tools', 'episode-template.html'), 'w', encoding='utf-8').write(f'<!--base:{B}-->' + _t)
shutil.rmtree(os.path.join(OUT, _tp.strip('/')))
with open(os.path.join(OUT, 'sitemap.xml'), 'w') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f'<url><loc>{SITE}{esc(u)}</loc></url>\n' for u in WRITTEN) + '</urlset>\n')
open(os.path.join(OUT, 'robots.txt'), 'w').write(f'User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n')
open(os.path.join(OUT, '.nojekyll'), 'w').write('')
os.makedirs(os.path.join(OUT, 'tools'), exist_ok=True)
with open(os.path.join(OUT, 'tools', 'image-urls.txt'), 'w') as f: f.write('\n'.join(sorted(USED)) + '\n')
with open(os.path.join(OUT, 'tools', 'extra-files.txt'), 'w') as f: f.write(''.join(f'{u} {p}\n' for u, p in sorted(EXTRA.items())))
print('pages written', len(WRITTEN), '| posts', len(POSTS), '| upload files referenced', len(USED))
