#!/usr/bin/env python3
"""Step 2 of 3: derive Japan's outline from the extract itself.

The rule is: the administrative relation at admin_level=2 carrying
ISO3166-1=JP. Nothing else is consulted. In particular Natural Earth is not:
its 10m coastline runs inland of the reclaimed land around Tokyo Bay and drops
about a quarter of the special wards' area, and the same class of error on a
country outline would silently remove the ports and the reclaimed land, which
is where a great deal of what this extract is for sits.

The boundary must also come from the same snapshot as the data. A boundary
drawn earlier once dropped a way created the day before the snapshot and broke
a ward's ring, and every area query for that ward was wrong afterwards.

Japan's outline in OpenStreetMap follows the coast and the maritime borders,
so what comes out here is a superset of the land and is used only to decide
what is in the country.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from shapely.geometry import mapping, shape
from shapely.ops import unary_union

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("WORK", ROOT / "tmp"))
SRC = WORK / "japan-bbox-260831.osm.pbf"
FILTERED = WORK / "admin2.osm.pbf"
OUT = ROOT / "data" / "japan_osm_boundary.geojson"


def country_polygons():
    subprocess.run(
        ["osmium", "tags-filter", "-o", str(FILTERED), "--overwrite",
         str(SRC), "r/admin_level=2"],
        check=True, stdout=subprocess.DEVNULL)
    seq = subprocess.run(
        ["osmium", "export", "-f", "geojsonseq", "--geometry-types=polygon",
         str(FILTERED)],
        check=True, capture_output=True, text=True).stdout

    found, others = [], {}
    for line in seq.replace("\x1e", "").splitlines():
        line = line.strip()
        if not line:
            continue
        f = json.loads(line)
        p = f["properties"]
        if p.get("boundary") != "administrative" or p.get("admin_level") != "2":
            continue
        iso = p.get("ISO3166-1") or p.get("ISO3166-1:alpha2")
        if iso == "JP":
            found.append(shape(f["geometry"]))
        else:
            others[iso or p.get("name", "?")] = others.get(iso, 0) + 1
    return found, others


def main() -> int:
    polys, others = country_polygons()
    if not polys:
        print("no admin_level=2 relation with ISO3166-1=JP in the extract",
              file=sys.stderr)
        print(f"  saw instead: {sorted(others)}", file=sys.stderr)
        return 1

    union = unary_union(polys)
    if not union.is_valid:
        union = union.buffer(0)
        if not union.is_valid:
            print("the union is not a valid geometry", file=sys.stderr)
            return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "type": "Feature",
        "properties": {
            "name": "日本",
            "name_en": "Japan",
            "rule": "admin_level=2 with ISO3166-1=JP",
            "parts": len(polys),
            "source": "OpenStreetMap, derived from planet-260831 itself",
        },
        "geometry": mapping(union),
    }, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT}: {len(polys)} polygons, "
          f"bounds={[round(v, 4) for v in union.bounds]}")
    print(f"  other countries in the box: {sorted(k for k in others if k)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
