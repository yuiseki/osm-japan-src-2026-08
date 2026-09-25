#!/usr/bin/env bash
# Step 1 of 3: cut a generous box around Japan out of the planet.
#
# This is the only pass over the planet, and it is where the hours go. The box
# reaches into Korea, Sakhalin, the Kurils and Taiwan on purpose: the real
# border is cut afterwards with a polygon derived from this same file, so no
# boundary of another vintage is ever consulted.
set -euo pipefail
cd "$(dirname "$0")/.."

# Override with PLANET=/path/to/planet-260831.osm.pbf
# https://planet.openstreetmap.org/pbf/planet-260831.osm.pbf
PLANET=${PLANET:-planet-260831.osm.pbf}
WORK=${WORK:-tmp}

test -r "$PLANET"
mkdir -p "$WORK"

exec osmium extract \
  --bbox 122.0,20.0,154.5,46.2 \
  --strategy complete_ways \
  --progress \
  --overwrite \
  -o "$WORK/japan-bbox-260831.osm.pbf" \
  "$PLANET"
