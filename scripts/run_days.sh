#!/bin/bash
# Eksik günleri (son 10 gün) işler. Kullanım: run_days.sh <gün klasörü> [tek gün YYYY-MM-DD]
set -u
DAYS=$1; ONE=${2:-}
mkdir -p "$DAYS"
curl -sL -o /tmp/airports.csv https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/airports.csv
curl -sL -o /tmp/runways.csv https://raw.githubusercontent.com/davidmegginson/ourairports-data/main/runways.csv
if [ -n "$ONE" ]; then LIST=$ONE; else LIST=$(for i in $(seq 10 -1 1); do date -u -d "$i days ago" +%Y-%m-%d; done); fi
for D in $LIST; do
  [ -s "$DAYS/$D.json" ] && continue
  T=v${D//-/.}-planes-readsb-prod-0
  U=https://github.com/adsblol/globe_history_${D:0:4}/releases/download/$T/$T.tar
  rm -f /tmp/day.tar; n=0
  for s in aa ab ac ad ae af ag; do
    code=$(curl -sIL -o /dev/null -w "%{http_code}" "$U.$s"); [ "$code" = 200 ] || break
    curl -sL --retry 5 --retry-delay 5 "$U.$s" >> /tmp/day.tar && n=$((n+1))
  done
  if [ "$n" = 0 ]; then echo "$D: arşiv yok (henüz yayımlanmamış olabilir)"; continue; fi
  python3 scripts/process_day.py /tmp/day.tar "$D" "$DAYS/$D.json" data/fleet.json /tmp/airports.csv || rm -f "$DAYS/$D.json"
  rm -f /tmp/day.tar
done
# 10 günden eskileri at
ls "$DAYS"/*.json 2>/dev/null | sort | head -n -10 | xargs -r rm -f
