#!/usr/bin/env bash
# Step 3 of 3: cut the box down to the country, with the outline from step 2.
#
# complete_ways, so a way that crosses the outline keeps all of its nodes. A
# way carries no coordinates of its own, so anything that dropped nodes first
# could not decide afterwards whether a way is in Japan.
set -euo pipefail
cd "$(dirname "$0")/.."

WORK=${WORK:-tmp}
POLY=data/japan_osm_boundary.geojson
OUT=data/japan-260831.osm.pbf

test -r "$WORK/japan-bbox-260831.osm.pbf"
test -r "$POLY"

osmium extract \
  --polygon "$POLY" \
  --strategy complete_ways \
  --progress \
  --overwrite \
  -o "$OUT" \
  "$WORK/japan-bbox-260831.osm.pbf"

( cd data && md5sum "$(basename "$OUT")" > "$(basename "$OUT").md5" )
osmium fileinfo -e "$OUT"
