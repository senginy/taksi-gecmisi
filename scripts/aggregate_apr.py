#!/usr/bin/env python3
"""Son N günün yaklaşma dosyalarını meydan bazında birleştirir: site/apr/index.json ve site/apr/<ICAO>.json.
Kullanım: aggregate_apr.py <yaklaşma gün klasörü> <site klasörü> <runways.csv> [N=10]
Her iniş için: iniş pisti (teker koyma noktası + son noktaların yönü), eşiğe kalan iz mesafesi (d),
süzülüşün başladığı nokta (geriye doğru ilk düz uçuş: 0,8 NM'de 120 ft'ten az alçalma) ve
yalnız finalde (pist uzantısında, yanal ≤ 1500 m, eşiğe ≤ 12 NM) ve süzülüşteyken 3°'den sapma
(eşikte 50 ft, 318,4 ft/NM). Yükseklik, eşiği geçtikten sonraki en alçak hava noktasına göre yeniden sıfırlanır.
LTFM yazılmaz (ana üs)."""
import sys, os, glob, json, math, csv, time
DAYS, SITE, RWY = sys.argv[1:4]; N = int(sys.argv[4]) if len(sys.argv) > 4 else 10
SKIP = {'LTFM'}
BGC = 250
files = sorted(glob.glob(os.path.join(DAYS, '*.json')))[-N:]
ads = {}
for fn in files:
    d = json.load(open(fn)); day = d['day']
    for ic, A in d['ads'].items():
        if ic in SKIP: continue
        a = ads.setdefault(ic, {'ref': A['ref'], 'elev': A.get('elev', 0), 'bg': {}, 'fl': {}, 'days': set()})
        a['days'].add(day)
        k = BGC // d['cell']
        for x, y, c in A['bg']:
            key = (x // k, y // k); a['bg'][key] = a['bg'].get(key, 0) + c
    for f in d['arr']:
        a = ads.get(f['ad'])
        if not a or not f.get('cs'): continue
        a['fl'].setdefault(f['cs'], []).append(dict(f, day=day))
rw = {}
for r in csv.reader(open(RWY, encoding='utf-8')):
    if r[2] in ads and r[9] and r[15] and r[7] != '1':
        rw.setdefault(r[2], []).append(r)
def proj(ref):
    la0, lo0 = ref; kx = math.cos(math.radians(la0)) * 111320; ky = 110540
    return lambda la, lo: ((lo - lo0) * kx, (la - la0) * ky)
def fnum(v):
    try: return float(v)
    except ValueError: return 0.0
def landing(R, f):
    td = f['td']; q = f['pts'][-6:]
    vx, vy = td[0] - q[0][0], td[1] - q[0][1]; V = math.hypot(vx, vy) or 1; best = None
    for r in R:
        for name, T, E, dsp in ((r['le'], r['a'], r['b'], r['ld']), (r['he'], r['b'], r['a'], r['hd'])):
            dx, dy = E[0] - T[0], E[1] - T[1]; L = math.hypot(dx, dy) or 1; ux, uy = dx / L, dy / L
            if (vx * ux + vy * uy) / V < 0.94: continue
            Tx, Ty = T[0] + ux * dsp, T[1] + uy * dsp          # eşik (kaydırılmış eşik dahil)
            along = (td[0] - Tx) * ux + (td[1] - Ty) * uy; lat = abs(-(td[0] - Tx) * uy + (td[1] - Ty) * ux)
            if lat > 120 or along < -300 or along > L: continue
            if best is None or lat < best[0]: best = (lat, name, (Tx, Ty), (ux, uy), along)
    return best
os.makedirs(os.path.join(SITE, 'apr'), exist_ok=True)
index = {'updated': time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime()), 'days': [json.load(open(f))['day'] for f in files], 'ads': {}}
for ic, a in ads.items():
    P = proj(a['ref']); R = []
    for r in rw.get(ic, []):
        try:
            p1 = P(float(r[9]), float(r[10])); p2 = P(float(r[15]), float(r[16]))
            R.append({'le': r[8], 'he': r[14], 'a': [round(p1[0]), round(p1[1])], 'b': [round(p2[0]), round(p2[1])], 'w': round(int(r[4] or 150) * 0.3048),
                      'ld': fnum(r[13]) * 0.3048, 'hd': fnum(r[19]) * 0.3048})
        except ValueError: pass
    fl = {}
    for cs, L in a['fl'].items():
        out = []
        for f in sorted(L, key=lambda f: f['t']):
            lb = landing(R, f); pts = f['pts']
            off = lb[4] / 1852 if lb else 0.0
            dd = [p[3] - off for p in pts]
            # yükseklik düzeltmesi: ADS-B "yerde" bayrağı çoğu zaman teker koymadan birkaç saniye sonra gelir; pist üstündeki
            # (eşiği geçmiş) en alçak hava noktası yer seviyesi kabul edilir
            over = [p[2] for p, x in zip(pts, dd) if x <= 0]
            if over:
                hz = max(-100, min(400, min(over)))
                pts = [[p[0], p[1], p[2] - hz] + p[3:] for p in pts]
            # süzülüş başlangıcı: eşikten geriye, 0,8 NM'de 120 ft'ten az alçalınan ilk yer
            g = 0
            for i in range(len(pts) - 1, -1, -1):
                if dd[i] < 0.3: continue                  # pist üstü (flare, teker koyma öncesi) sayılmaz
                j = i
                while j > 0 and dd[j] - dd[i] < 0.8: j -= 1
                if dd[j] - dd[i] < 0.8: break
                if pts[j][2] - pts[i][2] < 120: g = i; break
            P2 = []
            for i, p in enumerate(pts):
                dev = None
                if lb and i >= g:
                    _, _, T, (ux, uy), _ = lb
                    al = -((p[0] - T[0]) * ux + (p[1] - T[1]) * uy); lt = abs(-(p[0] - T[0]) * uy + (p[1] - T[1]) * ux)
                    if 0 < al < 12 * 1852 and lt < 1500: dev = round(p[2] - (50 + 318.4 * al / 1852))
                P2.append([p[0], p[1], p[2], round(dd[i], 2), dev])
            out.append({'day': f['day'], 'reg': f['reg'], 'type': f['type'], 't': f['t'], 'rwy': lb[1] if lb else '', 'ga': 1 if f.get('ga') else 0, 'pts': P2})
        fl[cs] = out
    mx = max(a['bg'].values() or [1])
    bg = [[x, y, max(1, min(9, round(9 * math.log(c + 1) / math.log(mx + 1))))] for (x, y), c in a['bg'].items() if c > 2]
    outj = {'ad': ic, 'ref': a['ref'], 'elev': a['elev'], 'days': sorted(a['days']), 'rw': [{k: v for k, v in r.items() if k not in ('ld', 'hd')} for r in R], 'bgcell': BGC, 'bg': bg, 'fl': fl}
    json.dump(outj, open(os.path.join(SITE, 'apr', ic + '.json'), 'w'), separators=(',', ':'))
    index['ads'][ic] = {cs: len(L) for cs, L in fl.items()}
json.dump(index, open(os.path.join(SITE, 'apr', 'index.json'), 'w'), separators=(',', ':'))
print('apr airports', len(ads), 'days', len(files))
