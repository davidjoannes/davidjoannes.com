# Parses the Notes and References of The Mind of a Missionary (2nd ed.) from pdftohtml -xml output into JSON.
import re, json, sys, html
x = open(sys.argv[1], errors='ignore').read()
pages = re.findall(r'<page number="(\d+)"[^>]*height="(\d+)"[^>]*>(.*?)</page>', x, re.S)
def toks(body):
    out = []
    for top, left, w, h, font, t in re.findall(r'<text top="(\d+)" left="(\d+)" width="(\d+)" height="(\d+)" font="(\d+)">(.*?)</text>', body, re.S):
        out.append((int(top), int(left), int(w), int(font), t))
    return out
def clean(t):
    # ligature glyphs: "!" (italic Th), &#34; (roman Th), lone "f" in a ligature font (ff)
    inner = re.sub(r'</?[ib]>', '', t)
    if inner.strip() in ('!', '&#34;', '"'): return t.replace('!', 'Th').replace('&#34;', 'Th').replace('"', 'Th')
    return t
notes, refs = [], []
cur_ch, cur_note = None, None
mode = None
ref_intro = []; ref_left = None; cur_ref = None; ref_sec = None
last_top = None; prev_right = 0
def add(buf, t, newline):
    t = html.unescape(t) if False else t
    if not buf: return t
    prev = re.sub(r'<[^>]+>', '', buf)
    last = prev.split(' ')[-1] if prev else ''
    if newline:
        if re.search(r'(https?:|www\.|\.(com|org|net|edu|gov|uk|io)\b)', last) and not re.search(r'[.,;)]$', last): return buf + t.lstrip()
        if prev.endswith('-') and re.search(r'(https?:|www\.)', last): return buf + t.lstrip()
        return buf.rstrip() + ' ' + t.lstrip()
    return buf + t
for num, height, body in pages:
    n = int(num)
    T = toks(body)
    for top, left, w, font, t in T:
        raw = re.sub(r'<[^>]+>', '', t).strip()
        if top < 70: continue                                   # running header
        if raw == 'NOTES': mode = 'notes-intro'; continue
        if raw == 'REFERENCES': mode = 'refs-intro'; continue
        if raw.startswith('THANKS') and mode == 'refs': mode = None; continue
        if mode is None: continue
        if top > int(height) - 75 and re.fullmatch(r'\d{1,3}', raw): continue   # page number
        t = clean(t)
        newline = last_top is not None and abs(top - last_top) > 6
        if mode in ('notes-intro', 'notes'):
            if t.startswith('<b>') and re.match(r'(Introduction|Chapter \d+|Conclusion)', raw):
                raw = {'Chapter 4:': 'Chapter 4: The Internal Monologue', 'Chapter 5: Social In': 'Chapter 5: Social Influence', 'Chapter 7: Physical Di': 'Chapter 7: Physical Difficulties', 'Chapter 12:': 'Chapter 12: The Kingdom of God on the Earth'}.get(raw, raw)
                cur_ch = {'title': raw, 'notes': []}; notes.append(cur_ch); cur_note = None; mode = 'notes'; last_top = top; continue
            if mode == 'notes-intro': last_top = top; continue
            if re.fullmatch(r'\d{1,3}', raw) and left < 100 and w < 20:
                cur_note = {'n': int(raw), 't': ''}; cur_ch['notes'].append(cur_note); last_top = top; continue
            if cur_note is not None: cur_note['t'] = add(cur_note['t'], t, newline and cur_note['t'] != '')
        elif mode in ('refs-intro', 'refs'):
            if t.startswith('<b>') and len(raw) < 60 and raw:
                ref_sec = {'title': raw, 'items': []}; refs.append(ref_sec); cur_ref = None; mode = 'refs'; last_top = top; ref_left = None; continue
            if mode == 'refs-intro': ref_intro.append(raw); last_top = top; continue
            if not raw and not newline: 
                if cur_ref is not None: cur_ref['t'] += ' '
                continue
            if newline and cur_ref is not None:
                prev = re.sub(r'<[^>]+>', '', cur_ref['t']).strip()
                ended = bool(re.search(r'[.”/]$|\.\)$', prev)) and not re.search(r'(https?://|www\.)\S*[/.]$', prev.split(' ')[-1] if prev_right > 500 else '')
                starts = bool(re.match(r'(“|‘|[A-Z][\w’\-]+,? (?:[A-Z][\w’\-.]*,? ?){0,5}[.,“]|[A-Z][A-Za-z’\-]+\. |[A-Z]{2,})', raw)) or t.startswith('<i>')
                if ended and (prev_right < 500 or starts):
                    cur_ref = {'t': ''}; ref_sec['items'].append(cur_ref)
            if cur_ref is None: cur_ref = {'t': ''}; ref_sec['items'].append(cur_ref)
            cur_ref['t'] = add(cur_ref['t'], t, newline and cur_ref['t'] != '')
        last_top = top
        if raw: prev_right = left + w
def fin(s):
    s = re.sub(r'</i>(\s*)<i>', r'\1', s); s = re.sub(r'</b>(\s*)<b>', r'\1', s)
    s = re.sub(r'\s+', ' ', s).strip()
    s = s.replace('<i>', '<em>').replace('</i>', '</em>').replace('<b>', '').replace('</b>', '')
    s = re.sub(r'<em>(\s*)</em>', r'\1', s)
    return s
for c in notes:
    for nt in c['notes']: nt['t'] = fin(nt['t'])
YEAR = re.compile(r'\b(1[5-9]|20)\d\d\b')
for sct in refs:
    its = [fin(i['t']) for i in sct['items'] if fin(i['t'])]
    out = []
    for it in its:
        plain = re.sub(r'<[^>]+>', '', it)
        prev = re.sub(r'<[^>]+>', '', out[-1]) if out else ''
        cont = bool(out) and (re.match(r'[a-z0-9(]', plain) or re.match(r'\S*[_/]\S*$|\S{26,}', plain.split(' ')[0]) or (not YEAR.search(prev) and 'http' not in prev)
                              or (it.startswith('<em>') and re.search(r'[”,]$', prev)))
        if cont:
            glue = '' if re.search(r'(https?://\S*|www\.\S*|doi\.org/)$', prev) else ' '
            out[-1] = out[-1] + glue + it
        else: out.append(it)
    final = []
    for it in out:   # two entries run together after a URL
        parts = re.split(r'(?<=\.) (?=(?:[A-Z][\w’\-]+(?: [A-Z][\w’\-]+){0,2}, [A-Z][\w’.,\- ]{0,60}?\. (?:“|<em>|[A-Z])|[A-Z][\w’&\- ]{2,40}\. “))', it)
        parts2 = []
        for x in parts:   # an entry with no author (starts with a quoted title) that follows a finished entry
            while True:
                m = None
                for mm in re.finditer(r'(?<=\S\.) (?=“[^”]{5,140}\.” )', x):
                    left = re.sub(r'<[^>]+>', '', x[:mm.start()])
                    if 'http' in left or YEAR.search(left): m = mm; break
                if not m: break
                parts2.append(x[:m.start()]); x = x[m.end():]
            parts2.append(x)
        merged = []
        for x in parts2:
            x = x.strip()
            if not x: continue
            pm = merged[-1] if merged else ''
            if merged and not ('<em>' in pm or '“' in pm or YEAR.search(re.sub(r'<[^>]+>', '', pm))): merged[-1] += ' ' + x
            else: merged.append(x)
        final.extend(merged)
    sct['items'] = final
json.dump({'notes': notes, 'refs': refs, 'ref_intro': ' '.join(ref_intro)}, open(sys.argv[2], 'w'), ensure_ascii=False, indent=0)
print([(c['title'], len(c['notes'])) for c in notes]); print([(s['title'], len(s['items'])) for s in refs])
