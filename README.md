# osm-japan-src-2026-08

Dataset: https://huggingface.co/datasets/yuiseki/osm-japan-src-2026-08

A frozen cut of OpenStreetMap covering the whole of Japan, taken from the
planet file of 2026-08-31, and the code that rebuilds every database it was
measured in. This repository holds the code; the data is on the Hub.

A question about a place has an answer only against a stated snapshot. An
answer computed today against the live API is not reproducible tomorrow, so
here the snapshot is one file with a checksum and every tool that reads it is
pinned in a Dockerfile.

The same snapshot as
[osm-tokyo23-src-2026-08](https://github.com/yuiseki/osm-tokyo23-src-2026-08),
the same schema, the same scripts numbered the same way. That one is 23 wards
and this one is 47 prefectures, so a query written against one reads against
the other.

## Where things are

```
scripts/01_extract_bbox.sh          planet -> a generous bbox around Japan
scripts/02_build_japan_boundary.py  the bbox -> the country outline
scripts/03_extract_japan_pbf.sh     the bbox + the outline -> the extract
scripts/04_verify.py                the checks, including the ring check
scripts/05_load_postgis.sh          the extract -> PostGIS
scripts/06_start_overpass.sh        the extract -> Overpass
scripts/07_export_parquet.py        PostGIS -> Parquet
src/publish.py                      pushes the data and its card to the Hub

docker/Dockerfile.osm2pgsql         osm2pgsql 1.11.0+ds-1
docker/Dockerfile.overpass          wiktorn/overpass-api v0.7.62.11
docker/Dockerfile.duckdb            duckdb 1.5.5, sha256 verified
docker/default.style                decides which tags become columns
docker/compose.yml

data/README.md                      the dataset card. Uploaded as-is
data/LICENSE                        the ODbL notice and the chain of derivation
data/provenance.yaml                every version in the chain, and what was left out
data/japan-260831.osm.pbf           generated, 2.8GB
data/parquet/                       generated
```

## Running it

Fetch the planet file first, then point the first script at it:

```sh
PLANET=/path/to/planet-260831.osm.pbf ./scripts/01_extract_bbox.sh
```

```sh
./scripts/01_extract_bbox.sh          # the only pass over the planet
./scripts/02_build_japan_boundary.py
./scripts/03_extract_japan_pbf.sh
./scripts/04_verify.py
./scripts/05_load_postgis.sh
./scripts/06_start_overpass.sh        # optional, and the slowest step here
./scripts/07_export_parquet.py
python3 src/publish.py                # dry run; --push to upload
```

The planet read is the cost of step 1. Step 5 is the cost of everything after
it: 318 million nodes is not 9 million.

## What the size changes

Two flags that the Tokyo recipe does not need, neither of which touches the
schema.

`--flat-nodes` keeps node locations in a file rather than in RAM. Japan has
318 million of them; the in-memory cache for that is tens of gigabytes and the
file is about 2.5 GB.

`--cache 8000` caps the rest. Without a cap osm2pgsql sizes itself to the
machine, and a machine with no swap does not get OOM-killed, it stops
answering.

## No schema of our own

The tables are osm2pgsql's classic pgsql output, because that is the layout
models have read for fifteen years of web maps. A friendlier schema of our own
design would measure whether a model can read a novel schema rather than
whether it knows OSM and SQL.

`--hstore` is not optional. The style promotes 106 tags to columns, but
`opening_hours`, `start_date`, `building:levels` and `operator:en` are not
among them.

The prefecture polygons are already in `planet_osm_polygon`, tagged
`boundary=administrative` and `admin_level=4`; municipalities are
`admin_level=7`. No separate table is needed, and none was added.

## Which Japan

The administrative relation at `admin_level=2` carrying `ISO3166-1=JP`, and
nothing else. Natural Earth is not consulted: its 10m coastline runs inland of
the reclaimed land around Tokyo Bay and drops about a quarter of the special
wards' area, and the same class of error on a country outline removes ports
and reclaimed land everywhere.

The outline is derived from this same snapshot. That is not fussiness. The
Tokyo cut of this planet file once used a boundary a year older and lost
`way/1553541361`, created on 2026-08-30. One boundary way of Setagaya went
missing, its ring stopped closing, Overpass silently stopped generating an
area for that ward, and `area["name"="世田谷区"]` began returning zero with no
error. Nothing in the file sizes or the node counts showed it.

`scripts/04_verify.py` counts relation members for exactly that reason. On
this extract all 47 prefectures have a place node and all 1,918 of their
boundary ways are present.

Japan's outline in OpenStreetMap follows the coast and the maritime borders,
so the cut is a superset of the land. The bounding box of the result reaches
past the outline anyway, because `complete_ways` keeps a way whole when even
one of its nodes is inside: the Ogasawara ferry route is one way that runs a
thousand kilometres out to sea.

## Traps worth knowing

The geometry is EPSG:3857. At Japan's latitudes a Web Mercator metre is
between about 1.16 and 1.45 real metres depending on how far north you are, so
distances come out long and areas long squared, and by a different factor in
Okinawa than in Hokkaido. Write `ST_Transform(way, 4326)::geography`.

The load uses osm2pgsql's defaults, without `-G`, so a multipolygon relation
is several rows sharing one negated `osm_id`. Aggregate before measuring.

`wiktorn/overpass-api` has four of its own, all handled in
`docker/compose.yml` and `scripts/06_start_overpass.sh`: it exits after the
import unless `OVERPASS_STOP_AFTER_INIT=false`, its `/api/status` always
returns 502 while `/api/interpreter` answers fine, its database directory is
created `drwx------` so fcgiwrap cannot reach the dispatcher socket until it
is chmodded, and by default the dispatcher refuses a query identical to one it
just served. For a country-sized extract the Overpass import is long enough
that it is worth treating as optional.

## Source

Cut from the planet file of 2026-08-31:

    https://planet.openstreetmap.org/pbf/planet-260831.osm.pbf
    94,612,383,571 bytes, md5 c67437924cf55de40e8708c7192f354d

OpenStreetMap keeps its dated planet files for about ten years, so that URL is
the one link that makes the whole chain checkable.

## License

The code here is MIT. The data it produces is a Derivative Database of
OpenStreetMap and is ODbL:

    (c) OpenStreetMap contributors, available under the Open Database License.
    https://www.openstreetmap.org/copyright

See `data/LICENSE` for the full notice and the chain of derivation.
