import re, json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from places import P, ORG, ADJ
_names = sorted(P, key=len, reverse=True)
_rx = re.compile(r'(?<![\w])(' + '|'.join(re.escape(n) for n in _names) + r')(?![\w])')
_adj = re.compile(r'(?<![\w])(' + '|'.join(re.escape(n) for n in sorted(ADJ, key=len, reverse=True)) + r')(?![\w])')
_org = re.compile('|'.join(re.escape(o) for o in sorted(ORG, key=len, reverse=True)))
OVR = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'overrides.json')))
def geocode(text, key=None):
    if key in OVR:
        n = OVR[key]; lat, lon, rank = P[n]; return {'n': n, 'lat': lat, 'lon': lon, 'r': rank}
    t = _org.sub(lambda m: '#' * len(m.group(0)), text)
    best = None
    for m in _rx.finditer(t):
        n = m.group(1); lat, lon, rank = P[n]
        pre = t[max(0, m.start() - 6):m.start()].lower()
        score = rank * 10 - (25 if pre.endswith('from ') else 0) - m.start() / 1000
        if best is None or score > best[0]: best = (score, n, lat, lon, rank)
    if best: return {'n': best[1], 'lat': best[2], 'lon': best[3], 'r': best[4]}
    m = _adj.search(t)
    if m:
        n = ADJ[m.group(1)]; lat, lon, rank = P[n]
        return {'n': n, 'lat': lat, 'lon': lon, 'r': min(rank, 1)}
    return None
