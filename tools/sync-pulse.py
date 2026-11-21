#!/usr/bin/env python3
"""Copy the newest Missions Pulse episodes from withinreachglobal.org into assets/pulse.json.
Run by .github/workflows/sync-pulse.yml. The site's pages read that file in the browser."""
import json, os, re, sys, html, urllib.request, email.utils
import xml.etree.ElementTree as ET
FEED = 'https://withinreachglobal.org/missions-pulse/rss.xml'
OUT = sys.argv[1] if len(sys.argv) > 1 else 'assets/pulse.json'
KEEP = 12
req = urllib.request.Request(FEED, headers={'User-Agent': 'Mozilla/5.0 (davidjoannes.com episode sync)'})
raw = urllib.request.urlopen(req, timeout=60).read()
root = ET.fromstring(raw)
new = []
for it in root.iter('item'):
    title = html.unescape((it.findtext('title') or '').strip())
    link = (it.findtext('link') or '').strip().split('?')[0]
    if not title or '/missions-pulse/' not in link: continue
    d = it.findtext('pubDate') or ''
    try: date = email.utils.parsedate_to_datetime(d).strftime('%Y-%m-%d')
    except Exception: date = ''
    body = (it.findtext('description') or '') + (it.findtext('{http://purl.org/rss/1.0/modules/content/}encoded') or '')
    m = re.search(r'<img[^>]+src="([^"]+)"', body)
    img = html.unescape(m.group(1)) if m else ''
    if img.startswith('//'): img = 'https:' + img
    new.append({'title': title, 'link': link, 'date': date, 'image': img})
if not new: sys.exit('No episodes found in the feed; leaving the file as it is.')
old = {}
if os.path.exists(OUT):
    try: old = json.load(open(OUT))
    except Exception: old = {}
seen = {e['link'] for e in new}
eps = new + [e for e in old.get('episodes', []) if e.get('link') not in seen]
eps.sort(key=lambda e: e.get('date', ''), reverse=True)
nums = [int(m.group(1)) for e in eps for m in [re.match(r'#(\d+)', e['title'])] if m]
data = {'count': max(nums + [int(old.get('count') or 0)]), 'episodes': eps[:KEEP]}
if data != {k: old.get(k) for k in ('count', 'episodes')}:
    os.makedirs(os.path.dirname(OUT) or '.', exist_ok=True)
    json.dump(data, open(OUT, 'w'), ensure_ascii=False, indent=1)
    print('updated:', data['count'], 'episodes; newest:', eps[0]['title'])
else:
    print('no change')
