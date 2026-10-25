#!/usr/bin/env python3
"""Son N günün günlük dosyalarını meydan bazında birleştirir, site verisini yazar.
Kullanım: aggregate.py <gün klasörü> <site klasörü> <runways.csv> [N=10]"""
import sys, os, glob, json, math, csv, time
DAYS, SITE, RWY = sys.argv[1:4]; N = int(sys.argv[4]) if len(sys.argv) > 4 else 10
files = sorted(glob.glob(os.path.join(DAYS, '*.json')))[-N:]
BGC = 16
ads = {}
for fn in files:
    d = json.load(open(fn)); day = d['day']
    for ic, A in d['ads'].items():
        a = ads.setdefault(ic, {'ref': A['ref'], 'bg': {}, 'fl': {}, 'days': set()})
        a['days'].add(day)
        k = BGC // d['cell']
        for x, y, c in A['bg']:
            key = (x // k, y // k); a['bg'][key] = a['bg'].get(key, 0) + c
    for f in d['flights']:
        a = ads.get(f['ad'])
        if not a or not f.get('cs'): continue
        a['fl'].setdefault(f['cs'], []).append(dict(f, day=day))
# pistler (OurAirports): yerel metre
rw = {}
for r in csv.reader(open(RWY, encoding='utf-8')):
    if r[2] in ads and r[9] and r[15] and r[6] != '1':
        rw.setdefault(r[2], []).append(r)
def proj(ref):
    la0, lo0 = ref; kx = math.cos(math.radians(la0)) * 111320; ky = 110540
    return lambda la, lo: ((lo - lo0) * kx, (la - la0) * ky)
def rwy_of(R, q):
    if len(q) < 2: return ''
    a, b = q[0], q[-1]; vx, vy = b[0] - a[0], b[1] - a[1]; m = q[len(q) // 2]; best = None
    for r in R:
        ax, ay = r['a']; bx, by = r['b']; dx, dy = bx - ax, by - ay; L = math.hypot(dx, dy) or 1
        t = max(0, min(1, ((m[0] - ax) * dx + (m[1] - ay) * dy) / L / L)); dd = math.hypot(ax + dx * t - m[0], ay + dy * t - m[1])
        if best is None or dd < best[0]: best = (dd, r, (vx * dx + vy * dy) > 0)
    if not best or best[0] > 120: return ''
    return best[1]['le'] if best[2] else best[1]['he']
os.makedirs(os.path.join(SITE, 'ad'), exist_ok=True)
index = {'updated': time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime()), 'days': [json.load(open(f))['day'] for f in files], 'ads': {}}
for ic, a in ads.items():
    P = proj(a['ref'])
    R = []
    for r in rw.get(ic, []):
        try:
            p1 = P(float(r[9]), float(r[10])); p2 = P(float(r[15]), float(r[16]))
            R.append({'le': r[8], 'he': r[14], 'a': [round(p1[0]), round(p1[1])], 'b': [round(p2[0]), round(p2[1])], 'w': round(int(r[4] or 150) * 0.3048)})
        except ValueError: pass
    mx = max(a['bg'].values() or [1])
    bg = [[x, y, max(1, min(9, round(9 * math.log(c + 1) / math.log(mx + 1))))] for (x, y), c in a['bg'].items()]
    xs = sorted(c[0] * BGC for c in bg) or [0]; ys = sorted(c[1] * BGC for c in bg) or [0]
    q = lambda L, p: L[min(len(L) - 1, int(len(L) * p))]
    bb = [q(xs, .005) - 200, q(xs, .995) + 200, q(ys, .005) - 200, q(ys, .995) + 200]
    fl = {}
    for cs, L in a['fl'].items():
        fl[cs] = [{'day': f['day'], 'kind': f['kind'], 'reg': f['reg'], 'type': f['type'], 't0': f['t0'], 't1': f['t1'], 'rwy': rwy_of(R, f['end']), 'cells': f['cells']} for f in sorted(L, key=lambda f: f['t0'])]
    out = {'ad': ic, 'ref': a['ref'], 'cell': 8, 'bgcell': BGC, 'days': sorted(a['days']), 'rw': R, 'bb': bb, 'bg': bg, 'fl': fl}
    json.dump(out, open(os.path.join(SITE, 'ad', ic + '.json'), 'w'), separators=(',', ':'))
    index['ads'][ic] = {cs: {'dep': sum(f['kind'] == 'dep' for f in L), 'arr': sum(f['kind'] == 'arr' for f in L)} for cs, L in fl.items()}
json.dump(index, open(os.path.join(SITE, 'index.json'), 'w'), separators=(',', ':'))
print('airports', len(ads), 'days', len(files))
