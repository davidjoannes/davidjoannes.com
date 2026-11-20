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
            if s in a['sizes']: u = a['sizes'][s]; break
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
class P: pass
POSTS, PAGES = [], {}
for i in items:
    t, st = g(i, 'wp:post_type'), g(i, 'wp:status')
    if st != 'publish' or t not in ('post', 'page'): continue
    p = P(); p.title = g(i, 'title'); p.raw = g(i, 'content:encoded'); p.id = g(i, 'wp:post_id')
    p.path = '/' + g(i, 'link').replace(SITE, '').strip('/') + '/'
    if p.path == '//': p.path = '/'
    p.date = g(i, 'wp:post_date'); p.meta = meta(i); p.thumb = p.meta.get('_thumbnail_id', '')
    p.cats = [c.get('nicename') for c in i.findall('category') if c.get('domain') == 'category']
    p.excerpt = g(i, 'excerpt:encoded')
    if t == 'post':
        p.cat = next((c for c in CATS if any(n in p.cats for n in c[0])), CATS[-1]); POSTS.append(p)
    else: PAGES.setdefault(p.path, p)
POSTS.sort(key=lambda p: p.date, reverse=True)
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
    im = att(p.thumb, ['medium_large', 'large'])
    pic = f'<img src="{im}" alt="" loading="lazy">' if im else ''
    return (f'<a class="card" href="{B}{p.path}" data-t="{esc(p.title.lower())}"><div class="im">{pic}</div>'
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
    t = re.sub(r'</?font[^>]*>', '', t)
    return t
def rewrite_urls(t):
    t = re.sub(r'https?://(?:www\.)?davidjoannes\.com/wp-content/uploads/[^\s"\'<>)\]]+', lambda m: local(m.group(0)), t)
    t = re.sub(r'(href=")https?://(?:www\.)?davidjoannes\.com/?(?=["#/])', lambda m: m.group(1) + B + ('/' if True else ''), t)
    t = t.replace(B + '//', B + '/')
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
    if notes:
        t += '<ol class="notes">' + ''.join(f'<li id="fn{n}">{rewrite_urls(clean_inline(x))} <a href="#fnr{n}" aria-label="Back to text">↩</a></li>' for n, x in enumerate(notes, 1)) + '</ol>'
    return t
def plain(t, n=155):
    t = re.sub(r'\[[^\]]*\]', ' ', t); t = re.sub(r'<[^>]+>', ' ', t); t = html.unescape(re.sub(r'\s+', ' ', t)).strip()
    return (t[:n].rsplit(' ', 1)[0] + '…') if len(t) > n else t

# ---------- layout
NAV = [('About', '/about/'), ('Books', '/books/'), ('Podcast', '/missionspulse/'), ('Resources', '/#resources'), ('Writing', '/blog/')]
SOCIAL = [('Instagram', 'https://instagram.com/davidjoannes'), ('Facebook', 'https://www.facebook.com/davidjoannesofficial/'), ('YouTube', 'https://www.youtube.com/channel/UCP6KeC0GSoA2JJZwxIg3c3Q'), ('X', 'https://twitter.com/davidjoannes'), ('LinkedIn', 'https://www.linkedin.com/in/davidjoannes')]
def page(path, title, body, desc='', image='', home=False):
    full = 'David Joannes | Missiologist, Author, and Founder of Within Reach Global' if home else f'{title} | David Joannes'
    nav = ''.join(f'<a href="{B}{u}">{n}</a>' for n, u in NAV)
    og = f'<meta property="og:image" content="{SITE}{image[len(B):]}">' if image else ''
    doc = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full)}</title>
<meta name="description" content="{esc(desc)}">
<link rel="canonical" href="{SITE}{path}">
<meta property="og:title" content="{esc(title if not home else full)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="{'website' if home else 'article'}">
<meta property="og:url" content="{SITE}{path}">
{og}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,400;9..144,500;9..144,600&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{B}/assets/site.css">
</head>
<body>
<header class="hdr pad">
<a class="brand" href="{B}/">David Joannes</a>
<nav class="nav" aria-label="Main">{nav}<a class="cta" href="{WRG}">Within Reach Global ↗</a></nav>
</header>
<main>
{body}
</main>
<footer class="ftr dark pad">
<div class="wrap">
<h2 class="d1" style="max-width:10em">The unreached are within reach.</h2>
<div style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:24px;margin-top:40px">
<p class="lede" style="margin:0;max-width:26em">Pray, give, and go with Within Reach Global, the ministry David and Lorna founded in 1997.</p>
<a class="btn" href="{WRG}">Visit withinreachglobal.org ↗</a>
</div>
<div class="btns" style="margin-top:28px"><a class="btn ghost" href="{B}/donate/">Support David and Lorna</a><a class="btn ghost" href="{B}/meet/">Book a meeting</a></div>
<div class="bar"><span>© {datetime.date.today().year} David Joannes</span><div>{''.join(f'<a href="{u}">{n}</a>' for n, u in SOCIAL)}</div></div>
</div>
</footer>
</body>
</html>'''
    d = os.path.join(OUT, path.strip('/'))
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'index.html'), 'w', encoding='utf-8') as f: f.write(doc)
    WRITTEN.append(path)
WRITTEN = []
def phead(eyebrow, title, sub=''):
    return f'<section class="phead dark pad"><div class="wrap"><p class="eyebrow">{eyebrow}</p><h1>{esc(title)}</h1>' + (f'<p class="meta">{sub}</p>' if sub else '') + '</div></section>'
CTA = f'''<section class="red pad sec"><div class="wrap split" style="align-items:flex-end"><div class="stack"><p class="eyebrow" style="margin:0">David's ministry</p><h2 class="d2">Help give gospel access to the unreached.</h2></div><div class="stack"><p class="lede" style="margin:0">Within Reach Global brings the gospel to unreached people groups in the 10/40 Window through compassion ministries, evangelism, discipleship, and church planting.</p><div class="btns"><a class="btn white" href="{WRG}">Visit withinreachglobal.org ↗</a></div></div></div></section>'''

# ---------- posts
by_cat = collections.defaultdict(list)
for p in POSTS: by_cat[p.cat[2]].append(p)
for p in POSTS:
    body = convert(p)
    hero = att(p.thumb, ['large'])
    has_media_top = bool(re.match(r'\s*(<p[^>]*>\s*)?(<div class="embed"|<img|<a[^>]*>\s*<img|<figure)', body))
    fi = f'<img class="featimg" src="{hero}" alt="">' if hero and not has_media_top else ''
    more = [q for q in by_cat[p.cat[2]] if q is not p][:3]
    rel = f'<section class="soft pad sec"><div class="wrap"><p class="eyebrow">More from {esc(p.cat[1])}</p><div class="grid">{"".join(post_card(q) for q in more)}</div><p style="margin-top:40px"><a class="more" href="{B}{p.cat[2]}">See all →</a></p></div></section>' if more else ''
    page(p.path, p.title,
         phead(f'<a href="{B}{p.cat[2]}" style="text-decoration:none">{esc(p.cat[1])}</a>', p.title, nice_date(p.date))
         + f'{fi}<div class="pad"><article class="article prose">{body}</article></div>' + CTA + rel,
         desc=plain(p.excerpt or p.raw), image=att(p.thumb, ['large']))

# ---------- converted pages
KEEP = ['/about/', '/books/', '/books/the-mind-of-a-missionary/', '/books/the-mind-of-a-missionary/notes/', '/books/gospel-privilege/',
        '/books/gospel-privilege/launchteam/', '/books/the-space-between-memories/', '/books/see-the-city/', '/missionspulse/',
        '/missions-blab/', '/contact/', '/subscribe/', '/fbr/', '/instagram/', '/the-memories-i-made-up-chapter-1/', '/thanks/', '/thank-you/']
TITLES = {'/books/': 'Books by David Joannes', '/missionspulse/': 'Missions Pulse', '/about/': 'About David', '/thank-you/': 'Thank you', '/instagram/': 'David Joannes on Instagram'}
for path in KEEP:
    p = PAGES.get(path)
    if not p: print('missing page', path); continue
    body = convert(p)
    title = TITLES.get(path) or html.unescape(p.title) or 'David Joannes'
    if path == '/missionspulse/': body = re.sub(r'href="[^"]*/missionspulse/#guest"', f'href="{B}/meet/#missions-pulse"', body)
    if path == '/books/': body = re.sub(r'<section class="vrow[^"]*">(?:(?!</section>).)*BOOKS BY DAVID JOANNES(?:(?!</section>).)*</section>', '', body, count=1, flags=re.S)
    built = '<section class="vrow' in body
    inner = f'<div class="builder prose">{body}</div>' if built else f'<div class="pad"><article class="article prose">{body}</article></div>'
    eyebrow = 'Books' if path.startswith('/books/') else ('The podcast' if 'missions' in path else 'David Joannes')
    page(path, title, phead(eyebrow, title) + inner + ('' if path in ('/thanks/', '/thank-you/') else CTA), desc=plain(p.raw))

# ---------- donate + meeting pages (new)
EXTRA = {}
def extra(url, name):
    EXTRA[url] = 'assets/' + name; return f'{B}/assets/{name}'
H = 'https://withinreachglobal.org/hubfs/'
fam = extra(H + 'joannes-default-image.jpg', 'donate/joannes-family.jpg')
venmo = extra(H + 'venmo_qrcode-joannes.jpg', 'donate/venmo-qr.jpg')
zelle = extra(H + 'zelle_qrcode-joannes.jpg', 'donate/zelle-qr.jpg')
bank = extra(H + 'union-bank-transfer.jpg', 'donate/union-bank-qr.jpg')
donate = f"""
<section class="hero dark pad"><div class="wrap">
<div class="txt">
<p class="eyebrow" style="margin:0">Partner with the Joannes family</p>
<h1 class="d1" style="font-size:clamp(46px,6.4vw,96px)">A family on mission, serving the unreached for 30 years.</h1>
<p class="lede" style="margin:0;max-width:32em">David and Lorna are the founders of Within Reach Global and full-time missionaries in Chiang Mai, Thailand, with their two daughters. For three decades they have planted churches, discipled leaders, and built a movement that keeps multiplying.</p>
<div class="btns"><a class="btn" href="#give">Become a monthly partner</a><a class="btn ghost" href="#other">Other ways to give</a></div>
</div>
<div class="pic"><img src="{fam}" alt="David and Lorna Joannes with their two daughters"></div>
</div></section>

<section class="pad sec"><div class="wrap split">
<div><p class="eyebrow">The impact</p><h2 class="d2">Why partner with David and Lorna.</h2></div>
<div class="rows why">
<div><b>Lead and shepherd</b><span>Frees them to lead a growing team across Thailand and Southeast Asia.</span></div>
<div><b>Stay on the ground</b><span>Sustains the relationships, language, and trust that 30 years on the field have built.</span></div>
<div><b>Cast vision</b><span>Fuels new outreach, including new church plants and emerging leaders.</span></div>
<div><b>Strengthen the foundation</b><span>Supports the ministry base, including the Chiang Mai House of Prayer and the Access Campaign.</span></div>
<div><b>Mentor the next generation</b><span>Invests in indigenous missionaries who will carry the work forward.</span></div>
</div>
</div></section>

<section class="soft pad sec" id="give"><div class="wrap split" style="align-items:flex-start">
<div class="stack"><p class="eyebrow" style="margin:0">Give</p><h2 class="d2">Become a monthly financial partner.</h2>
<p class="lede" style="margin:0;max-width:26em">Your monthly gift keeps David and Lorna on the field among the unreached.</p>
<p class="dim" style="margin:0;max-width:30em;font-size:16px">Gifts made through this form go to Within Reach Global, Inc., a 501(c)(3) nonprofit (EIN 26-3499455), and are tax-deductible in the United States.</p></div>
<div class="dbox"><script src="https://donorbox.org/widget.js" paypalExpress="false"></script>
<iframe src="https://donorbox.org/embed/missionaries-joannes" name="donorbox" title="Donate to the Joannes family" allowpaymentrequest="allowpaymentrequest" seamless="seamless" frameborder="0" scrolling="no" height="900px" width="100%" style="max-width:500px;min-width:250px;max-height:none!important" allow="payment"></iframe></div>
</div></section>

<section class="pad sec" id="other"><div class="wrap">
<p class="eyebrow">Other ways to give</p><h2 class="d2" style="margin-bottom:12px">Prefer another method?</h2>
<p class="dim" style="margin:0 0 clamp(32px,4vw,48px)">Gifts made by Venmo, Zelle, or bank transfer are not tax-deductible.</p>
<div class="tiles ways">
<div class="tile"><div><h3>Venmo</h3><p>@davidjoannes</p></div><img src="{venmo}" alt="Venmo QR code for @davidjoannes" loading="lazy"></div>
<div class="tile"><div><h3>Zelle</h3><p>david@withinreachglobal.org</p></div><img src="{zelle}" alt="Zelle QR code for david@withinreachglobal.org" loading="lazy"></div>
<div class="tile"><div><h3>Philippines bank transfer</h3><p>For partners in the Philippines.<br>Union Bank<br>Lorna Macadangdang Joannes<br>1025 1004 8465</p></div><img src="{bank}" alt="Union Bank transfer QR code" loading="lazy"></div>
</div>
</div></section>
<section class="red pad sec"><div class="wrap split" style="align-items:flex-end"><div class="stack"><p class="eyebrow" style="margin:0">Within Reach Global</p><h2 class="d2">Send someone to the unreached.</h2></div><div class="stack"><p class="lede" style="margin:0">Local Thai and Asian missionaries reach the spiritually poorest communities. A monthly gift of $650 fully supports one missionary.</p><div class="btns"><a class="btn white" href="{WRG}/donate">Give through Within Reach Global ↗</a></div></div></div></section>
"""
page('/donate/', 'Partner with the Joannes family', donate, desc='Become a monthly partner with David and Lorna Joannes, founders of Within Reach Global and missionaries in Chiang Mai, Thailand.')
MEET = 'https://meetings-na2.hubspot.com/david-joannes'
meet = phead('Book a meeting', 'Get time on David’s calendar.') + f"""
<section class="pad sec" style="padding-top:40px"><div class="wrap">
<nav class="chips" aria-label="Meeting types"><a href="#missions-pulse">Missions Pulse podcast interview</a><a href="#personal">Personal meeting</a></nav>
<div id="missions-pulse" style="padding-top:clamp(40px,5vw,64px)">
<p class="eyebrow">Missions Pulse</p><h2 class="d2">Schedule a podcast interview.</h2>
<p class="lede dim" style="max-width:34em">For Missions Pulse guests: pick a time to record your episode with David.</p>
<div class="meetings-iframe-container" data-src="{MEET}/missions-pulse?embed=true"></div>
<p class="dim" style="font-size:16px">Calendar not loading? <a href="{MEET}/missions-pulse">Open the Missions Pulse booking page ↗</a></p>
</div>
<div id="personal" style="padding-top:clamp(56px,7vw,96px)">
<p class="eyebrow">Personal</p><h2 class="d2">Book a meeting with David.</h2>
<p class="lede dim" style="max-width:34em">For partners, pastors, and anyone who wants to talk about missions, books, or serving with Within Reach Global.</p>
<div class="meetings-iframe-container" data-src="{MEET}?embed=true"></div>
<p class="dim" style="font-size:16px">Calendar not loading? <a href="{MEET}">Open the booking page ↗</a></p>
</div>
</div></section>
<script src="https://static.hsappsstatic.net/MeetingsEmbed/ex/MeetingsEmbedCode.js"></script>""" + CTA
page('/meet/', 'Book a meeting with David', meet, desc='Schedule a Missions Pulse podcast interview or a personal meeting with David Joannes.')

# ---------- blog listings
def listing(path, title, posts, active):
    chips = f'<a href="{B}/blog/"' + (' class="on"' if active == '/blog/' else '') + '>All</a>' + ''.join(f'<a href="{B}{u}"' + (' class="on"' if active == u else '') + f'>{esc(l)}</a>' for _, l, u in CATS[::-1])
    cards = ''.join(post_card(p) for p in posts)
    js = '''<script>
(function(){var c=[].slice.call(document.querySelectorAll('#posts .card')),n=24,q='',b=document.getElementById('morebtn'),s=document.getElementById('q');
function r(){var k=0,m=0;c.forEach(function(e){var ok=!q||e.getAttribute('data-t').indexOf(q)>-1;if(ok)m++;var show=ok&&k<n;if(show)k++;e.classList.toggle('hide',!show)});b.classList.toggle('hide',k>=m)}
b.addEventListener('click',function(){n+=24;r()});s.addEventListener('input',function(){q=s.value.toLowerCase().trim();n=24;r()});r()})();
</script>'''
    body = (phead('Writing', title, f'{len(posts)} posts') + f'<section class="pad sec" style="padding-top:40px"><div class="wrap"><nav class="chips" aria-label="Categories">{chips}</nav>'
            f'<p style="margin:28px 0 36px"><label for="q" class="dim" style="display:block;font-size:14px;font-weight:600;margin-bottom:8px">Search posts</label><input id="q" class="search" type="search" placeholder="Search by title"></p>'
            f'<div class="grid" id="posts">{cards}</div><p class="center" style="margin-top:48px"><button id="morebtn" class="btn ink" type="button">Show more posts</button></p></div></section>' + js + CTA)
    page(path, title, body, desc=f'{title} by David Joannes.')
listing('/blog/', 'Essays, devotionals, and stories from the field', POSTS, '/blog/')
LT = {'/blog/missions-blogs/': 'Missions Blogs', '/blog/davids-books-blogs/': "Posts About David's Books", '/blog/book-reviews-by-david/': 'Book Reviews by David',
      '/blog/missions-pulse-podcast-posts/': 'Missions Pulse Podcast Episodes', '/blog/podcast-appearances-posts/': 'Podcast Appearances', '/blog/within-reach-global-posts/': 'Within Reach Global Posts'}
for _, l, u in CATS: listing(u, LT[u], by_cat[u], u)

# ---------- home
def find_att(name):
    for k, a in ATT.items():
        if a['url'].endswith(name): return k
    return ''
portrait = extra(H + 'david-joannes-founder-2.jpg', 'david-joannes.jpg')
BOOKS = [('The Mind of a Missionary Devotional', '10728', '/books/the-mind-of-a-missionary/#devotional'), ('The Space Between Memories', '9456', '/books/the-space-between-memories/'),
         ('Gospel Privilege', '9190', '/books/gospel-privilege/'), ('See the City', '10257', '/books/see-the-city/'), ('Glorious Hope', '10471', '/books/see-the-city/#glorioushope'),
         ('Faith for Firebrands', '11043', 'https://faithforfirebrands.com/'), ('That Lasting Joy', '11044', 'https://thatlastingjoy.com/')]
def bk(t, i, u):
    href = u if u.startswith('http') else B + u
    return f'<a class="book" href="{href}"><div class="im"><img src="{att(i, ["medium", "large"])}" alt="{esc(t)} cover" loading="lazy"></div><b>{esc(t)}</b></a>'
eps = by_cat['/blog/missions-pulse-podcast-posts/'][:4]
def ep(p):
    m = re.match(r'#(\d+):\s*(.*)', p.title)
    return f'<a href="{B}{p.path}" style="display:block"><span class="s dim" style="display:block;font-size:13px;font-weight:600;letter-spacing:.14em">{"EPISODE " + m.group(1) if m else "EPISODE"}</span><span style="font-family:var(--serif);font-size:22px;line-height:1.25">{esc(m.group(2) if m else p.title)}</span></a>'
nik = next((d for d in TEST.get('_testimonial', []) if 'ripken' in d['name'].lower()), None)
quote = ''
if nik:
    quote = f'<section class="pad sec"><div class="quote"><div class="mark" aria-hidden="true">“</div><blockquote>{clean_inline(nik["body"])}</blockquote><div class="by"><b>Nik Ripken</b><span class="dim">Author, The Insanity of God</span></div></div></section>'
latest = POSTS[:0] + [p for p in POSTS if p.cat[2] != '/blog/missions-pulse-podcast-posts/'][:3]
home = f'''
<section class="hero dark pad"><div class="wrap">
<div class="txt">
<p class="eyebrow" style="margin:0">Missiologist · Author · Podcaster</p>
<h1 class="d1">Every people group deserves access to the gospel.</h1>
<p class="lede" style="margin:0;max-width:32em">David Joannes is the Founder and CEO of Within Reach Global. For three decades he has served in China and Thailand, writing and speaking on the church's unfinished task among the unreached.</p>
<div class="btns"><a class="btn" href="{WRG}">Explore Within Reach Global ↗</a><a class="btn ghost" href="{B}/books/">Read David's books</a></div>
</div>
<div class="pic"><img src="{portrait}" alt="David Joannes"></div>
</div></section>
<div class="endorsed dark pad"><div class="wrap"><span class="lbl">Endorsed by</span><span>Heidi Baker</span><span>Nik Ripken</span><span>Ron Luce</span><span>Matthew Ellison</span><span>Craig Greenfield</span><span>Mark Buchanan</span></div></div>

<section class="pad sec" id="about"><div class="wrap">
<div class="split">
<div><p class="eyebrow">About David</p><h2 class="d2">From Bible smuggler to mission leader.</h2></div>
<div class="stack" style="font-size:19px;color:var(--ink2)">
<p style="margin:0">David began his missionary journey by smuggling Bibles into China. After serving for 15 years in Southwest China, he now lives in Chiang Mai, Thailand, with his wife, Lorna, and their two daughters.</p>
<p style="margin:0">He has been interrogated for his faith over 20 times and has been apprehended by over 100 child soldiers carrying AK-47s. Today he leads Within Reach Global, hosts the Missions Pulse podcast, and writes to help the church see the unreached.</p>
<p style="margin:0"><a class="more" href="{B}/about/">Read David's story →</a></p>
</div></div>
<div class="stats">
<div><b>30</b><span>years serving in China and Thailand</span></div>
<div><b>85</b><span>churches planted through Within Reach Global</span></div>
<div><b>8</b><span>books on missions and the unreached</span></div>
<div><b>110+</b><span>Missions Pulse podcast episodes</span></div>
</div>
</div></section>

<section class="red pad sec" id="mission"><div class="wrap split" style="align-items:flex-end">
<div class="stack" style="flex:1 1 480px;gap:28px"><p class="eyebrow" style="margin:0">David's ministry</p><h2 class="d1">Within Reach Global</h2>
<p class="lede" style="margin:0;max-width:30em">Since 1997, Within Reach Global has brought gospel access to unreached people groups in the 10/40 Window through compassion ministries, evangelism, discipleship, and church planting.</p>
<div class="btns"><a class="btn white" href="{WRG}">Visit withinreachglobal.org ↗</a></div></div>
<div class="rows" style="flex:1 1 360px">
<a href="{WRG}/monthly-prayer-and-financial-support-team/"><span class="t">Pray</span><span class="s">Join the prayer and support team →</span></a>
<a href="{WRG}/giftcatalog"><span class="t">Give</span><span class="s">Empower indigenous missionaries →</span></a>
<a href="{WRG}"><span class="t">Go</span><span class="s">Serve with Within Reach Global →</span></a>
</div>
</div></section>

<section class="soft pad sec" id="books"><div class="wrap">
<div style="display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:clamp(40px,5vw,64px)">
<div><p class="eyebrow">Books</p><h2 class="d2" style="max-width:14em">Books to stir the church toward the unreached.</h2></div>
<a class="more" href="{B}/books/">See all books →</a></div>
<div class="feature dark">
<div class="cover"><img src="{att('10663', ['large'])}" alt="The Mind of a Missionary cover"></div>
<div class="body stack"><p class="eyebrow" style="margin:0">Featured</p><h3 class="d3">The Mind of a Missionary</h3>
<p class="dim" style="margin:0;max-width:32em">In the 2nd edition of <em>The Mind of a Missionary</em>, author David Joannes draws upon history, psychology, life experience, and powerful storytelling to reshape your perception of God’s global work.</p>
<div class="btns"><a class="btn" href="{B}/books/the-mind-of-a-missionary/">About the book</a><a class="btn ghost" href="{B}/books/the-mind-of-a-missionary/#freechapter">Read a free chapter</a></div></div>
</div>
<div class="grid books" style="margin-top:clamp(40px,5vw,64px)">{''.join(bk(*b) for b in BOOKS)}</div>
</div></section>
{quote}
<section class="dark pad sec" id="podcast"><div class="wrap">
<div style="display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:clamp(40px,5vw,64px)">
<div><p class="eyebrow">The podcast</p><h2 class="d1">Missions Pulse</h2></div>
<p class="lede" style="margin:0;max-width:26em">Missions Pulse video podcast exists to display God at work in the world and inspire believers toward their individual role in the Great Commission call.</p></div>
<div class="split" style="gap:40px clamp(32px,4vw,56px)">
<div style="flex:3 1 480px"><div class="embed" style="margin-top:0"><iframe src="https://www.youtube-nocookie.com/embed/zHkcSetJswM" title="Missions Pulse" loading="lazy" allowfullscreen></iframe></div><div class="btns"><a class="btn" href="{B}/missionspulse/">Watch Missions Pulse →</a></div></div>
<div class="rows" style="flex:2 1 360px">{''.join(ep(p) for p in eps)}<p style="margin:20px 0 0"><a class="more" href="{B}/blog/missions-pulse-podcast-posts/" style="border-top:0;display:inline-block;padding:10px 0 4px">All episodes →</a></p></div>
</div></div></section>

<section class="soft pad sec" id="resources"><div class="wrap">
<p class="eyebrow">Free resources</p><h2 class="d2" style="max-width:14em;margin-bottom:clamp(32px,4vw,56px)">Tools to find your part in the Great Commission.</h2>
<div class="tiles">
<a class="tile" href="{WRG}"><div><h3>Spiritual Gifts Test</h3><p>Discover how God has wired you to serve.</p></div><span class="go">Take the test ↗</span></a>
<a class="tile" href="{WRG}"><div><h3>Gospel Access Score</h3><p>See how much access to the gospel you have had, and who has none.</p></div><span class="go">Get your score ↗</span></a>
<a class="tile" href="https://prayforthailand.com"><div><h3>Pray for Thailand</h3><p>An interactive prayer map of all 77 provinces.</p></div><span class="go">Open the map ↗</span></a>
<a class="tile" href="{B}/books/the-mind-of-a-missionary/#freechapter"><div><h3>Free book chapters</h3><p>Start reading The Mind of a Missionary and Gospel Privilege.</p></div><span class="go">Read a chapter →</span></a>
</div>
<div class="feature dark" style="margin-top:20px;align-items:flex-start">
<div class="stack" style="flex:1 1 300px;gap:16px"><p class="eyebrow" style="margin:0">Free online courses</p><h3 class="d3">Go deeper with David's books.</h3><p class="dim" style="margin:0">Short lessons with quizzes and a certificate of completion, hosted by Within Reach Global.</p></div>
<div class="rows" style="flex:2 1 420px">
<a href="https://themindofamissionary.com"><span class="t" style="font-size:28px">The Mind of a Missionary Course</span><span class="s dim">Adult, youth, and kids editions ↗</span></a>
<a href="{WRG}/gospel-privilege-course"><span class="t" style="font-size:28px">Gospel Privilege Course</span><span class="s dim">Start the course ↗</span></a>
<a href="{WRG}/see-the-city-course"><span class="t" style="font-size:28px">See the City Course</span><span class="s dim">Start the course ↗</span></a>
</div></div>
</div></section>

<section class="pad sec" id="writing"><div class="wrap">
<div style="display:flex;flex-wrap:wrap;align-items:flex-end;justify-content:space-between;gap:24px;margin-bottom:clamp(32px,4vw,48px)">
<div><p class="eyebrow">Writing</p><h2 class="d2">Essays, devotionals, and stories from the field.</h2></div><a class="more" href="{B}/blog/">Read the blog →</a></div>
<div class="grid">{''.join(post_card(p) for p in latest)}</div>
</div></section>
'''
page('/', 'David Joannes', home, desc='David Joannes is a missiologist, author, podcaster, and the Founder and CEO of Within Reach Global, giving gospel access to unreached people groups in the 10/40 Window.', image=portrait, home=True)

# ---------- extras
os.makedirs(os.path.join(OUT, 'assets'), exist_ok=True)
shutil.copy(os.path.join(HERE, 'site.css'), os.path.join(OUT, 'assets', 'site.css'))
page('/404/', 'Page not found', phead('404', 'This page has moved or no longer exists.') + f'<div class="pad"><div class="article prose"><p>Try the <a href="{B}/blog/">blog</a>, the <a href="{B}/books/">books</a>, or head back <a href="{B}/">home</a>.</p></div></div>')
shutil.copy(os.path.join(OUT, '404', 'index.html'), os.path.join(OUT, '404.html'))
WRITTEN.remove('/404/')
with open(os.path.join(OUT, 'sitemap.xml'), 'w') as f:
    f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + ''.join(f'<url><loc>{SITE}{esc(u)}</loc></url>\n' for u in WRITTEN) + '</urlset>\n')
open(os.path.join(OUT, 'robots.txt'), 'w').write(f'User-agent: *\nAllow: /\nSitemap: {SITE}/sitemap.xml\n')
open(os.path.join(OUT, '.nojekyll'), 'w').write('')
os.makedirs(os.path.join(OUT, 'tools'), exist_ok=True)
with open(os.path.join(OUT, 'tools', 'image-urls.txt'), 'w') as f: f.write('\n'.join(sorted(USED)) + '\n')
with open(os.path.join(OUT, 'tools', 'extra-files.txt'), 'w') as f: f.write(''.join(f'{u} {p}\n' for u, p in sorted(EXTRA.items())))
print('pages written', len(WRITTEN), '| posts', len(POSTS), '| upload files referenced', len(USED))
