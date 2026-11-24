#!/usr/bin/env python3
"""adsb.lol günlük arşivinden THY filosunun (77W/789/77F) son 6000 ft yaklaşma izlerini çıkarır (vektörler, base ve final dönüşü dahil).
Kullanım: approach_day.py <tar> <gün YYYY-MM-DD> <çıktı.json> <fleet.json> <airports.csv>
Her iniş için: teker koyma anından geriye, yer üstü yükseklik 6000 ft'i geçene kadar olan hava noktaları.
Yükseklik: uçağın kendi irtifası (GNSS varsa o, yoksa barometrik) eksi teker koyma anındaki irtifa
(son hava noktalarından teker koyma anına doğrusal uzatma). Böylece QNH ve geoid farkı uçuş bazında düşer.
Kalan mesafe (dtg): o noktadan teker koyma noktasına uçulan iz boyunca NM.
Yer izi olmayan inişlerde (ng=1) son alçak hava noktası teker koyma yerine geçer; yükseklik barometrik (QNH düzeltmeli) eksi meydan rakımıdır.
2. geçiş: aynı meydanlarda tüm trafiğin 6000 ft altı inen izleri zemin için sayılır (50 m hücre, barometrik, yaklaşık)."""
import sys, tarfile, zlib, json, math, csv, time
try:
    import orjson; loads = orjson.loads
except Exception:
    loads = json.loads
TAR, DAY, OUT, FLEET, APT = sys.argv[1:6]
fleet = json.load(open(FLEET))
CELL = 50          # m, zemin hücresi
HMAX = 6000        # ft AGL
R_AD = 9000        # m; teker koyma noktası meydana bu mesafede (KDEN gibi geniş meydanlar)
R_BOX = 55000      # m; zemin için meydan çevresi
APTS = []; ELEV = {}
for r in csv.DictReader(open(APT, encoding='utf-8')):
    if r['type'] in ('large_airport', 'medium_airport') and r['scheduled_service'] == 'yes' and r['ident'] and len(r['ident']) == 4:
        APTS.append((r['ident'], float(r['latitude_deg']), float(r['longitude_deg'])))
        try: ELEV[r['ident']] = float(r['elevation_ft'] or 0)
        except ValueError: ELEV[r['ident']] = 0
def nearest(la, lo, rad=R_AD):
    best = None
    for ic, a, b in APTS:
        if abs(a - la) > 0.2 or abs(b - lo) > 0.3: continue
        d = math.hypot((b - lo) * math.cos(math.radians(la)) * 111320, (a - la) * 110540)
        if best is None or d < best[0]: best = (d, ic, a, b)
    return best if best and best[0] < rad else None
def proj(ref):
    la0, lo0 = ref; kx = math.cos(math.radians(la0)) * 111320; ky = 110540
    return lambda la, lo: ((lo - lo0) * kx, (la - la0) * ky)
def members(tf):
    for m in tf:
        if m.isfile() and '/traces/' in '/' + m.name: yield m
def load(tf, m):
    b = tf.extractfile(m).read()
    if b[:2] == b'\x1f\x8b': b = zlib.decompress(b, 47)
    return loads(b)
t0 = time.time()
arr = []; ads = {}
with tarfile.open(TAR, 'r:') as tf:
    for m in members(tf):
        hx = m.name.rsplit('trace_full_', 1)[-1].split('.')[0].lower()
        if not ('4b8000' <= hx <= '4bffff'): continue
        d = load(tf, m); reg = d.get('r')
        if reg not in fleet: continue
        ts = d.get('timestamp', 0); tr = d.get('trace') or []
        pts = []; cs = None
        for p in tr:
            det = p[8] if len(p) > 8 else None
            if isinstance(det, dict) and det.get('flight'): cs = det['flight'].strip()
            geo = p[10] if len(p) > 10 and isinstance(p[10], (int, float)) else None
            qnh = det.get('nav_qnh') if isinstance(det, dict) else None
            pts.append((ts + p[0], p[1], p[2], p[3], geo, p[4] or 0, cs, qnh))
        # iniş adayları: (a) havadan yere ilk geçiş; (b) yer izi yoksa: meydanın 6 km'sinde ~700 ft altına inip
        # iz kesilen ya da 90 s'den uzun boşluk veren, ardından pas geçme tırmanışı olmayan son hava noktası
        cands = []
        for i in range(1, len(pts)):
            if pts[i][3] == 'ground' and pts[i - 1][3] != 'ground': cands.append((i - 1, pts[i], 0))
        for e in range(len(pts)):
            p = pts[e]
            if not isinstance(p[3], (int, float)) or p[1] is None: continue
            nxt = pts[e + 1] if e + 1 < len(pts) else None
            if nxt is not None and (nxt[3] == 'ground' or nxt[0] - p[0] <= 90): continue
            na = nearest(p[1], p[2])
            if not na or p[3] - ELEV.get(na[1], 0) > 700: continue
            if any(isinstance(q[3], (int, float)) and q[3] - ELEV.get(na[1], 0) > 1500 for q in pts[e + 1:e + 40] if q[0] - p[0] < 180): continue
            cands.append((e, p, 1))
        for i0, td, ng in cands:
            na = nearest(td[1], td[2])
            if not na: continue
            ic = na[1]
            seg = []
            for j in range(i0, max(-1, i0 - 900), -1):
                p = pts[j]
                if p[3] == 'ground' or not isinstance(p[3], (int, float)) or p[1] is None: break
                if seg and seg[-1][0] - p[0] > 90: break
                if td[0] - p[0] > 2700: break
                seg.append(p)
            if len(seg) < 8: continue
            seg.reverse()
            if not ng and td[0] - seg[-1][0] > 60:     # yerde bayrağı var ama son hava noktasıyla arasında uzun boşluk (alçakta kapsama yok)
                ng = 1; td = seg[-1]
            useg = sum(1 for p in seg if p[4] is not None) > 0.8 * len(seg)
            alt = lambda p: (p[4] if useg and p[4] is not None else p[3])
            if ng:
                # yer izi yok: barometrik irtifa, uçağın QNH'si varsa ona göre düzeltilir, meydan rakımı çıkarılır (kaba)
                q = next((p[7] for p in reversed(seg) if p[7]), None)
                alt = (lambda p, q=q: p[3] + (q - 1013.25) * 27.3) if q else (lambda p: p[3])
                a_td = ELEV.get(ic, 0)
            else:
                a_td = None
            # teker koyma irtifası: son 40 s'lik noktalara doğru, teker koyma anına uzatma
            if a_td is None:
                tail = [p for p in seg if td[0] - p[0] <= 40 and alt(p) is not None][-8:]
                if len(tail) < 3: continue
                mt = sum(p[0] for p in tail) / len(tail); ma = sum(alt(p) for p in tail) / len(tail)
                den = sum((p[0] - mt) ** 2 for p in tail) or 1
                k = sum((p[0] - mt) * (alt(p) - ma) for p in tail) / den
                if not (-30 < k < 2): continue           # ft/s; makul alçalma
                a_td = ma + k * (td[0] - mt)
            ref = ads.setdefault(ic, (round(na[2], 5), round(na[3], 5))); P = proj(ref)
            xy = [P(p[1], p[2]) for p in seg] + [P(td[1], td[2])]
            dtg = [0.0] * len(seg); acc = 0.0
            for j in range(len(seg) - 1, -1, -1):
                acc += math.hypot(xy[j + 1][0] - xy[j][0], xy[j + 1][1] - xy[j][1]); dtg[j] = acc / 1852
            out = []; ga = False; hmin = 1e9
            for j, p in enumerate(seg):
                h = alt(p) - a_td
                if h > HMAX + 300: out = []; hmin = 1e9; continue
                if h < hmin: hmin = h
                if hmin < 1500 and h - hmin > 500: ga = True
                out.append([round(xy[j][0]), round(xy[j][1]), round(h), round(dtg[j], 2), round(p[5]), round(td[0] - p[0])])
            out = [q for q in out if q[2] <= HMAX]
            th = []                                   # ~150 m'de bir nokta, son 1 NM tam
            for q in out:
                if not th or q[3] < 1 or math.hypot(q[0] - th[-1][0], q[1] - th[-1][1]) >= 150: th.append(q)
            out = th
            if len(out) < 6: continue
            call = seg[-1][6] or cs
            if any(a['reg'] == reg and abs(a['t'] - td[0]) < 900 for a in arr): continue   # aynı iniş iki aday
            arr.append({'ad': ic, 'cs': call, 'reg': reg, 'type': fleet[reg], 't': int(td[0]), 'src': 'g' if useg else 'b', 'ga': ga, 'ng': ng,
                        'td': [round(v) for v in P(td[1], td[2])], 'pts': out})
print('pass1', len(arr), 'arrivals at', len(ads), 'airports', round(time.time() - t0), 's', file=sys.stderr)
# ---- 2. geçiş: zemin (tüm trafik, inen, ~3000 ft AGL altı, barometrik yaklaşık)
bg = {ic: {} for ic in ads}
boxes = [(ic, ref, proj(ref), ELEV.get(ic, 0)) for ic, ref in ads.items()]
with tarfile.open(TAR, 'r:') as tf:
    for m in members(tf):
        d = load(tf, m); ts = d.get('timestamp', 0); tr = d.get('trace') or []
        low = [p for p in tr if isinstance(p[3], (int, float)) and p[3] < 9000 and p[1] is not None and (p[7] or 0) < -200]
        if len(low) < 5: continue
        for ic, ref, P, el in boxes:
            if abs(low[0][1] - ref[0]) > 0.7 and abs(low[-1][1] - ref[0]) > 0.7: continue
            B = bg[ic]; seen = set()
            for p in low:
                if p[3] - el > HMAX or abs(p[1] - ref[0]) > 0.55 or abs(p[2] - ref[1]) > 0.8: continue
                x, y = P(p[1], p[2])
                if math.hypot(x, y) > R_BOX: continue
                c = (int(x // CELL), int(y // CELL))
                if c not in seen: seen.add(c); B[c] = B.get(c, 0) + 1
out = {'day': DAY, 'cell': CELL, 'ads': {ic: {'ref': ref, 'elev': ELEV.get(ic, 0), 'bg': [[c[0], c[1], v] for c, v in bg[ic].items()]} for ic, ref in ads.items()}, 'arr': arr}
json.dump(out, open(OUT, 'w'), separators=(',', ':'))
print('done', round(time.time() - t0), 's', file=sys.stderr)
