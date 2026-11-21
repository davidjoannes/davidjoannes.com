# Adds hyperlinks to the parsed notes (tmoam-notes-raw.json) using the archive links in the eBook .docx,
# and rebuilds the reference list from the .docx paragraphs. Links go on titles; raw URLs are removed from the text.
# usage: link_notes.py <unzipped-docx-dir> <raw.json> <out.json>
import re, json, sys, html
X, RAW, OUT = sys.argv[1:4]
def rels(name):
    r = open(f'{X}/word/_rels/{name}').read(); d = {}
    for m in re.finditer(r'<Relationship [^>]*>', r):
        i = re.search(r'Id="([^"]+)"', m.group(0)); t = re.search(r'Target="([^"]+)"', m.group(0))
        if i and t: d[i.group(1)] = html.unescape(t.group(1))
    return d
def fix(u):
    u = re.sub(r'(web\.archive\.org/web/\d+[a-z_]*/https?):/(?!/)', r'\1://', u.strip())
    return u if re.match(r'https?://', u) else 'http://' + u
def text(xml): return html.unescape(''.join(re.findall(r'<w:t(?: [^>]*)?>(.*?)</w:t>', xml, re.S)))
def segs(par, R):
    """paragraph -> list of (text, italic, href)"""
    out = []
    for m in re.finditer(r'<w:hyperlink [^>]*r:id="([^"]+)"[^>]*>(.*?)</w:hyperlink>|<w:r[ >].*?</w:r>', par, re.S):
        if m.group(1):
            out.append((text(m.group(2)), False, fix(R.get(m.group(1), ''))))
        else:
            r = m.group(0); t = text(r)
            if not t: continue
            it = bool(re.search(r'<w:i(?: w:val="(?:1|true)")?/>', r))
            out.append((t, it, None))
    return out
URLISH = re.compile(r'^(https?://|www\.)|\.(com|org|net|edu|gov|io|uk)(/|$)')
URL = re.compile(r'https?://[^\s<]+')
esc = lambda s: s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
def link_title(t, href):
    """wrap the first quoted title (else the first italic title) in a link; else append a link"""
    a = lambda inner: f'<a href="{esc(href)}" rel="noopener" target="_blank">{inner}</a>'
    for rx in (r'“(?![^”]*<a )([^”]{3,300}?)([.,?!]?)”', r'<em>(?![^<]*<a )([^<]{3,300}?)</em>'):
        for m in re.finditer(rx, t):
            if '</a>' in t[m.start():m.end()]: continue
            pre = t[:m.start()]
            if pre.count('<a ') != pre.count('</a>'): continue
            if rx.startswith('“'): return t[:m.start()] + '“' + a(m.group(1) + m.group(2)) + '”' + t[m.end():]
            return t[:m.start()] + '<em>' + a(m.group(1)) + '</em>' + t[m.end():]
    host = re.sub(r'^https?://(?:web\.archive\.org/web/\d+[a-z_]*/https?://)?(?:www\.|en\.)?', '', href).split('/')[0]
    label = {'wikipedia.org': 'Wikipedia', 'youtube.com': 'YouTube', 'youtu.be': 'YouTube', 'instagram.com': 'Instagram'}.get(host, host)
    t = t.rstrip()
    if re.search(r'see also\.?$', t, re.I): return re.sub(r'\.$', '', t) + ' ' + a(label) + '.'
    if re.search(r'(YouTube|Instagram)\.$', t) and label in t[-12:]: return re.sub(r'(YouTube|Instagram)\.$', lambda m: a(m.group(1)) + '.', t)
    return t + ' ' + a(label) + '.'
def strip_url(t, start, end):
    left, right = t[:start], t[end:]
    left = re.sub(r'[\s,]+$', '', left); right = right.lstrip()
    if right[:1] in '.,;' and re.search(r'[.!?”]$|</em>$', left) and right[:1] == '.': right = right[1:].lstrip()
    if not right: return left if re.search(r'[.!?”)]$', left) else left + '.'
    if right[:1] in '.,;)': return left + right
    return left + (' ' if re.search(r'[.!?”]$', left) else '. ' if right[:1].isupper() else ' ') + right
def apply(t, links):
    """t: html with <em>; links: [(display, href)] from the docx, in order"""
    for disp, href in links:
        d = disp.strip()
        if not d or not re.match(r'https?://[\w.\-]+\.[a-z]{2,}', href): continue
        if URLISH.search(d):
            key = esc(re.sub(r'^https?://', '', d))[:28]
            m = next((u for u in URL.finditer(t) if key[:20] in u.group(0)), None) or URL.search(t)
            if not m and '<a ' in t and re.sub(r'^https?://(www\.)?', '', d)[:14] in t.replace('www.', ''): continue
            if not m and '<a ' in t and href.rstrip('/').split('//')[-1].replace('www.', '')[:16] in t.replace('www.', ''): continue
            if m:
                end = m.end()
                g = m.group(0)
                while g and g[-1] in '.,;)': g = g[:-1]; end -= 1
                t = strip_url(t, m.start(), end)
            t = link_title(t, href)
        else:
            i = t.find(esc(d))
            if i > -1 and '<a ' not in t[max(0, i - 3):i + len(esc(d))]:
                t = t[:i] + f'<a href="{esc(href)}" rel="noopener" target="_blank">{esc(d)}</a>' + t[i + len(esc(d)):]
    for _ in range(4):   # raw URLs with no docx hyperlink
        plain_spans = [(m.start(), m.end()) for m in re.finditer(r'<a [^>]*>.*?</a>', t)]
        m = next((u for u in URL.finditer(t) if not any(a <= u.start() < b for a, b in plain_spans)), None)
        if not m: break
        g = m.group(0); end = m.end()
        while g and g[-1] in '.,;)': g = g[:-1]; end -= 1
        t = link_title(strip_url(t, m.start(), end), html.unescape(g))
    return re.sub(r'\s+', ' ', t).replace(' .', '.').replace('..', '.').strip()
d = json.load(open(RAW))
# ---- notes: same order as the docx endnotes
R = rels('endnotes.xml.rels')
ens = [b for i, b in re.findall(r'<w:endnote [^>]*w:id="(-?\d+)"[^>]*>(.*?)</w:endnote>', open(f'{X}/word/endnotes.xml').read(), re.S) if int(i) >= 1]
flat = [n for c in d['notes'] for n in c['notes']]
assert len(ens) == len(flat), (len(ens), len(flat))
for body, n in zip(ens, flat):
    links = [(text(h), fix(R.get(rid, ''))) for rid, h in re.findall(r'<w:hyperlink [^>]*r:id="([^"]+)"[^>]*>(.*?)</w:hyperlink>', body, re.S)]
    links = [(a, b) for a, b in links if 'themindofamissionary.com/notes' not in a]
    n['t'] = apply(n['t'], links)
# ---- references: from the docx paragraphs
R = rels('document.xml.rels')
paras = re.findall(r'<w:p[ >].*?</w:p>', open(f'{X}/word/document.xml').read(), re.S)
T = [text(p).strip() for p in paras]
start = [i for i, t in enumerate(T) if t.upper() == 'REFERENCES'][-1]
end = next(i for i in range(start + 1, len(T)) if re.match(r'(THANKS|ACKNOWLEDG|ABOUT THE AUTHOR|ABOUT WITHIN)', T[i].upper()))
heads = {s['title'] for s in d['refs']}
refs = []; cur = None
for p, t in zip(paras[start + 1:end], T[start + 1:end]):
    if not t: continue
    if t in heads: cur = {'title': t, 'items': []}; refs.append(cur); continue
    if cur is None: continue
    sg = segs(p, R)
    h = ''; links = []
    for tx, it, href in sg:
        if href: links.append((tx, href)); h += esc(tx)
        else: h += f'<em>{esc(tx)}</em>' if it else esc(tx)
    h = re.sub(r'</em>(\s*)<em>', r'\1', h)
    cur['items'].append(apply(h, links))
d['refs'] = refs
def tidy(t):
    t = re.sub(r'<a href="\s[^>]*?</a>', '', t)                      # malformed partial-URL links
    if 'web.archive.org' in t:                                        # drop leftover raw-URL-as-text links
        t = re.sub(r',?\s*<a href="[^"]*"[^>]*>(?:https?://|www\.)[^<]*</a>', '', t)
    t = re.sub(r'<a href="([^"]+)"([^>]*)>([^<]*?)([,.]+)</a>', r'<a href="\1"\2>\3</a>\4', t)  # punctuation outside links
    t = re.sub(r'<a [^>]*>\s*</a>', '', t)
    t = re.sub(r'<a href="https://en\.wikipedia\.org/wiki/Oxford[^>]*>([^<]*)</a>', r'\1', t).replace('(Oxford  University', '(Oxford University')
    m = re.match(r'(“)(Official: More Than 1M Child Prostitutes in India), <em>(<a [^>]*>)CNN</a></em>', t)
    if m: t = m.group(1) + m.group(3) + m.group(2) + '</a>,” <em>CNN</em>' + t[m.end():]
    return re.sub(r'\s+([,.])', r'\1', t).replace(',.', '.')
for n in flat: n['t'] = tidy(n['t'])
for s_ in refs: s_['items'] = [tidy(i) for i in s_['items']]
json.dump(d, open(OUT, 'w'), ensure_ascii=False, indent=0)
alln = [n['t'] for n in flat] + [i for s in refs for i in s['items']]
print('notes', len(flat), 'refs', [(s['title'], len(s['items'])) for s in refs])
print('with links', sum('<a ' in t for t in alln), 'archive links', sum(t.count('web.archive.org') for t in alln), 'raw urls left', sum(1 for t in alln if URL.search(re.sub(r'<a [^>]*>', '', t))), '"View source" fallbacks', sum('View source' in t for t in alln))
