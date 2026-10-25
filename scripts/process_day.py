#!/usr/bin/env python3
"""adsb.lol günlük arşivinden THY filosunun (77W/789/77F) meydanlardaki yer hareketlerini çıkarır.
Kullanım: process_day.py <tar dosyası> <tarih YYYY-MM-DD> <çıktı.json> <fleet.json> <airports.csv>
İki geçiş: (1) yalnız Türk tescil bloğundaki (4B8000–4BFFFF) iz dosyaları açılır, filo uçakları ayrılır;
(2) filonun bu gün yerde görüldüğü meydanlarda tüm trafiğin yer izleri zemin (taksi yolu ağı) için sayılır."""
import sys, tarfile, zlib, json, math, csv, time
try:
    import orjson; loads = orjson.loads
except Exception:
    loads = json.loads
TAR, DAY, OUT, FLEET, APT = sys.argv[1:6]
fleet = json.load(open(FLEET))
CELL = 8          # m
GAP = 1200        # s; yer oturumlarını ayıran boşluk
R_AD = 6000       # m; meydan yarıçapı
# meydanlar: tarifeli seferi olan büyük/orta meydanlar
APTS = []
for r in csv.DictReader(open(APT, encoding='utf-8')):
    if r['type'] in ('large_airport', 'medium_airport') and r['scheduled_service'] == 'yes' and r['ident'] and len(r['ident']) == 4:
        APTS.append((r['ident'], float(r['latitude_deg']), float(r['longitude_deg'])))
def nearest(la, lo):
    best = None
    for ic, a, b in APTS:
        if abs(a - la) > 0.2 or abs(b - lo) > 0.3: continue
        d = math.hypot((b - lo) * math.cos(math.radians(la)) * 111320, (a - la) * 110540)
        if best is None or d < best[0]: best = (d, ic, a, b)
    return best if best and best[0] < R_AD else None
def proj(ref):
    la0, lo0 = ref; kx = math.cos(math.radians(la0)) * 111320; ky = 110540
    return lambda la, lo: ((lo - lo0) * kx, (la - la0) * ky)
def cells_of(P, pts, step, maxdt, maxd):
    out = set(); xy = [P(p[1], p[2]) for p in pts]
    for i in range(len(xy) - 1):
        a, b = xy[i], xy[i + 1]; d = math.hypot(b[0] - a[0], b[1] - a[1])
        if pts[i + 1][0] - pts[i][0] > maxdt or d > maxd: continue
        n = max(1, int(d / step))
        for k in range(n + 1):
            t = k / n; out.add((int((a[0] + (b[0] - a[0]) * t) // CELL), int((a[1] + (b[1] - a[1]) * t) // CELL)))
    return out
def members(tf):
    for m in tf:
        if m.isfile() and '/traces/' in '/' + m.name: yield m
def load(tf, m):
    b = tf.extractfile(m).read()
    if b[:2] == b'\x1f\x8b': b = zlib.decompress(b, 47)
    return loads(b)
t0 = time.time()
# ---- 1. geçiş: filo
flights = []; ads = {}
with tarfile.open(TAR, 'r:') as tf:
    for m in members(tf):
        hx = m.name.rsplit('trace_full_', 1)[-1].split('.')[0].lower()
        if not ('4b8000' <= hx <= '4bffff'): continue
        d = load(tf, m)
        reg = d.get('r');
        if reg not in fleet: continue
        ts = d.get('timestamp', 0); tr = d.get('trace') or []
        pts = []; cs = None
        for p in tr:
            det = p[8] if len(p) > 8 else None
            if isinstance(det, dict) and det.get('flight'): cs = det['flight'].strip()
            pts.append([ts + p[0], p[1], p[2], p[3], p[4] or 0, cs])
        # yer oturumları
        g = [i for i, p in enumerate(pts) if p[3] == 'ground']
        sess = []; cur = []
        for i in g:
            if cur and pts[i][0] - pts[cur[-1]][0] > GAP: sess.append(cur); cur = []
            cur.append(i)
        if cur: sess.append(cur)
        for S in sess:
            if len(S) < 5: continue
            G = [pts[i] for i in S]
            mid = G[len(G) // 2]; na = nearest(mid[1], mid[2])
            if not na: continue
            ic = na[1]; ref = ads.setdefault(ic, (round(na[2], 5), round(na[3], 5)))
            before = [p for p in pts[max(0, S[0] - 40):S[0]] if p[3] != 'ground' and G[0][0] - p[0] < 300]
            after = [p for p in pts[S[-1] + 1:S[-1] + 40] if p[3] != 'ground' and p[0] - G[-1][0] < 300]
            kind = 'arr' if before and not after else 'dep' if after and not before else 'x'
            if kind == 'x': continue
            css = [p[5] for p in G if p[5]] + [p[5] for p in (before if kind == 'arr' else after) if p[5]]
            call = max(set(css), key=css.count) if css else None
            mv = [p for p in G if p[4] >= 3]
            P = proj(ref)
            c = cells_of(P, mv, 2, 60, 800)
            # pist tahmini için: inişte ilk, kalkışta son 12 yer noktası (yerel metre)
            ends = (G[:12] if kind == 'arr' else G[-12:])
            flights.append({'ad': ic, 'kind': kind, 'cs': call, 'reg': reg, 'type': fleet[reg], 't0': int(G[0][0]), 't1': int(G[-1][0]),
                            'cells': sorted(c), 'end': [[round(v) for v in P(p[1], p[2])] for p in ends]})
print('pass1', len(flights), 'flights at', len(ads), 'airports', round(time.time() - t0), 's', file=sys.stderr)
# ---- 2. geçiş: zemin (yalnız bu meydanlar)
bg = {ic: {} for ic in ads}
boxes = [(ic, ref, proj(ref)) for ic, ref in ads.items()]
with tarfile.open(TAR, 'r:') as tf:
    for m in members(tf):
        d = load(tf, m); ts = d.get('timestamp', 0); tr = d.get('trace') or []
        gr = [p for p in tr if p[3] == 'ground' and p[1] is not None]
        if len(gr) < 5: continue
        for ic, ref, P in boxes:
            if abs(gr[0][1] - ref[0]) > 0.15 and abs(gr[-1][1] - ref[0]) > 0.15: continue
            sel = [[ts + p[0], p[1], p[2]] for p in gr if abs(p[1] - ref[0]) < 0.06 and abs(p[2] - ref[1]) < 0.08 and (p[4] or 0) >= 3]
            if len(sel) < 3: continue
            B = bg[ic]
            for c in cells_of(P, sel, 4, 40, 500): B[c] = B.get(c, 0) + 1
out = {'day': DAY, 'cell': CELL, 'ads': {ic: {'ref': ref, 'bg': [[c[0], c[1], v] for c, v in bg[ic].items()]} for ic, ref in ads.items()}, 'flights': flights}
json.dump(out, open(OUT, 'w'), separators=(',', ':'))
print('done', round(time.time() - t0), 's', file=sys.stderr)
