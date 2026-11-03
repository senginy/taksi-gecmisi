# ECMWF IFS open data (CC BY 4.0) -> Ellrod TI1 türbülans indeksi, seyir seviyeleri, 0.5° ızgara
import json, os, sys, urllib.request, numpy as np, xarray as xr, gzip, datetime as dt
BASE = 'https://data.ecmwf.int/forecasts'
LEVS = [400, 300, 250, 200, 150, 100]   # hesap için; çıktı seviyeleri 300/250/200/150
OUTL = [300, 250, 200, 150]
def latest_run():
    now = dt.datetime.utcnow()
    for back in range(0, 48, 6):
        t = now - dt.timedelta(hours=back); h = (t.hour // 12) * 12   # 00z/12z: 0..144 h, 3 h adım
        d = t.strftime('%Y%m%d'); url = f'{BASE}/{d}/{h:02d}z/ifs/0p25/oper/{d}{h:02d}0000-48h-oper-fc.index'
        try: urllib.request.urlopen(url, timeout=30).read(100); return d, h
        except Exception: pass
    sys.exit('run yok')
def fetch(d, h, step):
    stem = f'{BASE}/{d}/{h:02d}z/ifs/0p25/oper/{d}{h:02d}0000-{step}h-oper-fc'
    idx = [json.loads(l) for l in urllib.request.urlopen(stem + '.index', timeout=60).read().decode().splitlines()]
    out = {}
    for p in ('u', 'v', 'gh'):
        for L in LEVS:
            e = next(x for x in idx if x.get('levtype') == 'pl' and x['param'] == p and x.get('levelist') == str(L))
            req = urllib.request.Request(stem + '.grib2', headers={'Range': f"bytes={e['_offset']}-{e['_offset'] + e['_length'] - 1}"})
            fn = f'/tmp/f_{p}{L}.grib2'; open(fn, 'wb').write(urllib.request.urlopen(req, timeout=120).read())
            ds = xr.open_dataset(fn, engine='cfgrib', backend_kwargs={'indexpath': ''})
            out[(p, L)] = ds[list(ds.data_vars)[0]].values.astype('float64')
            lat = ds.latitude.values; lon = ds.longitude.values
    return out, lat, lon
def ti1(F, lat, lon):
    R = 6371000.0; dlat = np.deg2rad(abs(lat[1] - lat[0])); dlon = np.deg2rad(abs(lon[1] - lon[0]))
    coslat = np.cos(np.deg2rad(lat))[:, None].clip(0.05)
    res = {}
    for k, L in enumerate(LEVS):
        if L not in OUTL: continue
        u, v = F[('u', L)], F[('v', L)]
        dudx = np.gradient(u, axis=1) / (R * coslat * dlon); dvdx = np.gradient(v, axis=1) / (R * coslat * dlon)
        dudy = -np.gradient(u, axis=0) / (R * dlat); dvdy = -np.gradient(v, axis=0) / (R * dlat)   # lat azalan
        DEF = np.sqrt((dudx - dvdy) ** 2 + (dvdx + dudy) ** 2)
        La, Lb = LEVS[k - 1], LEVS[k + 1]   # alt (yüksek basınç) ve üst seviye
        dz = (F[('gh', Lb)] - F[('gh', La)]).clip(100)
        VWS = np.hypot(F[('u', Lb)] - F[('u', La)], F[('v', Lb)] - F[('v', La)]) / dz
        res[L] = VWS * DEF * 1e7
    return res
d, h = latest_run(); steps = list(range(int(os.environ.get('S0', 0)), int(os.environ.get('S1', 48)) + 1, 3))
meta = {'src': 'ECMWF IFS open data (CC BY 4.0)', 'index': 'Ellrod TI1 x1e7 (VWS*DEF)', 'run': f'{d}{h:02d}', 'steps': steps, 'levels_hpa': OUTL, 'grid': {'lat0': 90, 'lon0': -180, 'd': 0.5, 'nlat': 361, 'nlon': 720}, 'scale': 0.1}
os.makedirs('out', exist_ok=True); buf = bytearray()
for s in steps:
    F, lat, lon = fetch(d, h, s); T = ti1(F, lat, lon)
    for L in OUTL:
        g = T[L][::2, ::2]
        buf += np.clip(np.round(g / 0.1), 0, 255).astype(np.uint8).tobytes()
    print('step', s, {L: round(float(np.percentile(T[L], 99)), 1) for L in OUTL}, flush=True)
open('out/ti.bin.gz', 'wb').write(gzip.compress(bytes(buf), 6)); json.dump(meta, open('out/meta.json', 'w'))
print('bytes', len(buf), os.path.getsize('out/ti.bin.gz'))
