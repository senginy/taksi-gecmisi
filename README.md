# Taksi Geçmişi

Uçuş Paketi Asistanı’nın **Taksi** sekmesine veri üretir. Her gün adsb.lol’un açık ADS-B arşivinden bir önceki günü indirir; THY B777-300ER, B787-9 ve B777F filosunun (`data/fleet.json`, DOW/DOI tablolarındaki tesciller) meydanlardaki yer hareketlerini çıkarır, son 10 günü tutar ve GitHub Pages’te yayımlar.

## Kurulum (bir kez)
1. GitHub’da **herkese açık** yeni bir depo aç (ör. `taksi-gecmisi`). Herkese açık depoda Actions dakikaları ücretsizdir.
2. Bu klasördeki her şeyi depoya yükle (`.github/workflows/daily.yml` dahil).
3. Depo → **Settings → Pages → Build and deployment → Source: GitHub Actions**.
4. Depo → **Actions → “Taksi geçmişi (günlük)” → Run workflow** (gün alanı boş). İlk çalıştırma son 10 günü işler, ~45–60 dk sürer. Sonraki günlerde her sabah 08:30 UTC’de kendiliğinden çalışır (~5 dk).
5. Yayın adresi: `https://<kullanıcı-adın>.github.io/<depo-adı>/`. Bu adresi uygulamada Taksi sekmesine bir kez gir.

## Nasıl çalışır
- `scripts/process_day.py`: Günlük arşivden (~4 GB) yalnız Türk tescil bloğundaki (4B8000–4BFFFF) iz dosyalarını açar, filo uçaklarının yer oturumlarını ayırır (iniş / kalkış, callsign, 8 m hücre). Ardından aynı meydanlardaki tüm trafiğin yer izlerinden taksi yolu ağı zeminini sayar.
- `scripts/aggregate.py`: Son 10 günü birleştirir; `index.json` ve meydan başına `ad/<ICAO>.json` yazar, pist tahmini OurAirports eşiklerinden.
- Önceki günlerin ara dosyaları geçmişi büyütmemek için `state` dalında tek commit olarak tutulur.

## Filo değişince
`data/fleet.json`’a tescil ekle/çıkar (`"TC-XXX": "B77W"`).

Kaynaklar: adsb.lol açık ADS-B arşivi (ODbL), OurAirports (public domain). Resmi doküman değildir.
