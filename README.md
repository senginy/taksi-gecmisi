# Taksi Geçmişi

Uçuş Paketi Asistanı’nın **Taksi** sekmesine veri üretir. Her gün adsb.lol’un açık ADS-B arşivinden bir önceki günü indirir; THY B777-300ER, B787-9 ve B777F filosunun (`data/fleet.json`, DOW/DOI tablolarındaki tesciller) meydanlardaki yer hareketlerini ve son 6000 ft yaklaşmalarını çıkarır, son 10 günü tutar ve `site` dalında yayımlar.

## Kurulum (bir kez)
1. Herkese açık depo (Actions dakikaları ücretsiz).
2. Depo → **Actions → “Taksi geçmişi (günlük)” → Run workflow** (gün alanı boş). İlk çalıştırma son 10 günü işler, ~45–60 dk sürer. Sonraki günlerde her sabah 08:30 UTC’de kendiliğinden çalışır (~5 dk).
3. Veri `site` dalına yazılır; uygulama `https://raw.githubusercontent.com/senginy/taksi-gecmisi/site/` adresinden okur (Pages gerekmez).

## Nasıl çalışır
- `scripts/process_day.py`: Günlük arşivden (~4 GB) yalnız Türk tescil bloğundaki (4B8000–4BFFFF) iz dosyalarını açar, filo uçaklarının yer oturumlarını ayırır (iniş / kalkış, callsign, 8 m hücre). Ardından aynı meydanlardaki tüm trafiğin yer izlerinden taksi yolu ağı zeminini sayar.
- `scripts/aggregate.py`: Son 10 günü birleştirir; `index.json` ve meydan başına `ad/<ICAO>.json` yazar, pist tahmini OurAirports eşiklerinden.
- `scripts/approach_day.py`: Aynı arşivden filonun inişlerinde son 6000 ft yaklaşma izini (vektörler, base ve final dönüşü dahil) çıkarır (yükseklik uçuş bazında teker koyma anına göre sıfırlanır, QNH ve geoid farkı düşer); aynı meydanlarda tüm trafiğin 6000 ft altı inen izleri zemin için sayılır.
- `scripts/aggregate_apr.py`: Son 10 günün yaklaşmalarını birleştirir; `apr/index.json` ve `apr/<ICAO>.json` yazar: iniş pisti, finale katılış noktası, eşiğe kalan iz mesafesi, süzülüş başladıktan sonra finalde 3°'den (eşikte 50 ft) sapma. LTFM yazılmaz.
- Önceki günlerin ara dosyaları geçmişi büyütmemek için `state` dalında tek commit olarak tutulur.

## Filo değişince
`data/fleet.json`’a tescil ekle/çıkar (`"TC-XXX": "B77W"`).

Kaynaklar: adsb.lol açık ADS-B arşivi (ODbL), OurAirports (public domain). Resmi doküman değildir.
