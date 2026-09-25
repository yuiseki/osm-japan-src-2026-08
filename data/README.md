---
license: odbl
language:
- ja
- en
task_categories:
- table-question-answering
- question-answering
- text-generation
tags:
- openstreetmap
- japan
- geospatial
- text-to-sql
- text2sql
- overpass
- postgis
- duckdb
- frozen-snapshot
size_categories:
- 10M<n<100M
configs:
- config_name: planet_osm_point
  data_files: parquet/planet_osm_point.parquet
- config_name: planet_osm_line
  data_files: parquet/planet_osm_line.parquet
- config_name: planet_osm_polygon
  data_files: parquet/planet_osm_polygon.parquet
- config_name: planet_osm_roads
  data_files: parquet/planet_osm_roads.parquet
---

# osm-japan-src-2026-08

A frozen cut of OpenStreetMap covering the whole of Japan, taken from the
planet file of 2026-08-31, together with everything needed to rebuild the
databases it was measured in.

The point is the freezing. A question about a place has an answer only against
a stated snapshot, and an answer computed today against the live API is not
reproducible tomorrow. Here the snapshot is one file with a checksum, and the
tools that read it are pinned by version.

This is the country-sized sibling of
[osm-tokyo23-src-2026-08](https://huggingface.co/datasets/yuiseki/osm-tokyo23-src-2026-08):
the same planet file, the same schema, the same scripts numbered the same way.
That one is 23 wards and this one is 47 prefectures, so a query written
against either reads against the other.

No schema of our own. The tables are osm2pgsql's, `planet_osm_point` and its
three siblings, because that is the layout that models have read for fifteen
years of web maps. Inventing a friendlier one would measure whether a model
can read a novel schema rather than whether it knows OSM and SQL.

## What is here

| file | |
|---|---|
| `japan-260831.osm.pbf` | the frozen extract, 2.8 GB. md5 `2f803a54de5bdeb5ecbbb740c9b5100d` |
| `japan_osm_boundary.geojson` | the outline it was cut with |
| `parquet/planet_osm_*.parquet` | the same records in the osm2pgsql schema |
| `provenance.yaml` | every version in the chain, and what was left out |
| `LICENSE` | the ODbL notice and the chain of derivation |

| | nodes | ways | relations |
|---|---|---|---|
| `japan-260831.osm.pbf` | 318,225,406 | 45,679,976 | 241,943 |

| table | rows |
|---|---|
| `planet_osm_point` | 3,720,141 |
| `planet_osm_line` | 12,259,617 |
| `planet_osm_polygon` | 33,281,956 |
| `planet_osm_roads` | 762,255 |

## Three ways to query it, one answer

The pbf is the source. A PostGIS database is built from it and the Parquet is
a second reading of the same records. An Overpass database is buildable from
the same file with the script in the repository, and is not published here
because a country-sized Overpass import is a long job.

```
japan-260831.osm.pbf
  ├─ PostGIS    osm2pgsql pgsql output    -> text-to-SQL
  │    └─ parquet/                        -> this viewer, and DuckDB
  └─ Overpass   osm3s                     -> text-to-Overpass QL
```

Counting cafes in a ward, a city or a prefecture is the same query with a
different `admin_level`: 2 for the country, 4 for a prefecture, 7 for a
municipality and for Tokyo's special wards.

```sql
-- PostGIS
SELECT count(*) FROM planet_osm_point p
JOIN planet_osm_polygon a ON ST_Within(p.way, a.way)
WHERE a.boundary='administrative' AND a.admin_level='4' AND a.name='京都府'
  AND p.amenity='cafe';
```

```sql
-- DuckDB, straight off the Parquet
LOAD spatial;
CREATE VIEW planet_osm_point   AS SELECT * FROM read_parquet('planet_osm_point.parquet');
CREATE VIEW planet_osm_polygon AS SELECT * FROM read_parquet('planet_osm_polygon.parquet');
SELECT count(*) FROM planet_osm_point p
JOIN planet_osm_polygon a
  ON ST_Within(ST_GeomFromWKB(p.way), ST_GeomFromWKB(a.way))
WHERE a.boundary='administrative' AND a.admin_level='4' AND a.name='京都府'
  AND p.amenity='cafe';
```

The administrative polygons are already in `planet_osm_polygon`. There is no
separate prefecture or municipality table and none is needed.

## Reading the Parquet

Two columns could not travel as they were. Everything else keeps the name and
type osm2pgsql gave it.

| column | PostGIS | Parquet |
|---|---|---|
| `way` | `geometry(*, 3857)` | WKB bytes, still EPSG:3857 |
| `tags` | `hstore` | JSON text |

Three things to know if you are porting a PostGIS query to DuckDB.

Wrap the geometry: `ST_GeomFromWKB(way)`.

Tags are JSON, so `->>` rather than `->`, and the parentheses are required.
`->>` binds looser than `=`, and without them DuckDB tries to cast `tags` to a
boolean and fails.

```sql
WHERE (tags->>'operator:en') = 'East Japan Railway'
```

DuckDB's spatial extension has no `geography` type and `ST_Distance_Sphere`
takes only points, so project to metres when you need a true distance.

## The trap in the coordinates, and it is worse here

The geometry is EPSG:3857, which is what osm2pgsql produces unless told
otherwise. A Web Mercator metre is not a metre, and how far it is from one
depends on latitude. Japan spans from 24°N to 45°N, so the error is not one
number:

| | 3857 metre is about |
|---|---|
| Okinawa, 26°N | 1.11 real metres |
| Tokyo, 36°N | 1.24 real metres |
| Wakkanai, 45°N | 1.41 real metres |

An area is wrong by the square of that: 1.2 times too large in Okinawa and
2.0 times too large at the northern tip. A national ranking computed straight
off 3857 is therefore not just wrong but wrong in an order-changing way, which
a single-city extract can hide.

PostGIS at least refuses rather than lying: casting a 3857 geometry to
`geography` raises `Only lon/lat coordinate systems are supported in
geography`. Write `ST_Transform(way, 4326)::geography`.

## Multipolygons occupy several rows

The load used osm2pgsql's defaults, without `-G`, so a multipolygon relation
is stored as several rows sharing one `osm_id`, negated. Aggregate before you
measure.

```sql
SELECT ST_Union(way) FROM planet_osm_polygon WHERE osm_id = -1234567;
```

## Which Japan, and why it matters

The administrative relation at `admin_level=2` carrying `ISO3166-1=JP`, and
nothing else. The outline was derived from the same snapshot as the data.

That is not fussiness. The Tokyo cut of this same planet file once used a
boundary a year older and lost `way/1553541361`, created on 2026-08-30. One
boundary way of Setagaya went missing, its ring no longer closed, Overpass
silently stopped generating an area for that ward, and
`area["name"="世田谷区"]` began returning zero with no error. File size, node
counts and every ward's place node all looked normal.

The check that catches it is in the repository and was run on this extract:
all 47 prefectures have a place node, and all 1,918 of their boundary ways are
present.

Natural Earth was not consulted for the outline. Its 10m coastline runs inland
of the reclaimed land around Tokyo Bay and drops about a quarter of the
special wards' area; the same class of error on a country outline removes
ports and reclaimed land everywhere.

## What the extract includes beyond the coast

The cut used `complete_ways`, so a way with even one node inside Japan is kept
whole. Nothing is chopped at the boundary, which is why the bounding box of
the file reaches from 103°E to 156°E and from 1°N to 51°N: the Ogasawara
ferry route is one way that runs a thousand kilometres out to sea, and it is
kept in full.

## Source

Code, Docker files and the verification scripts:
[yuiseki/osm-japan-src-2026-08](https://github.com/yuiseki/osm-japan-src-2026-08)

Cut from the planet file of 2026-08-31:

    https://planet.openstreetmap.org/pbf/planet-260831.osm.pbf

    94,612,383,571 bytes, md5 c67437924cf55de40e8708c7192f354d

That checksum was verified against the 94 GB file on disk on 2026-09-25, and
re-cutting Japan from the box reproduces `japan-260831.osm.pbf` byte for byte.
OpenStreetMap keeps its dated planet files for about ten years, so that URL
should still fetch the same bytes long after the mirrors of this dataset have
moved. `provenance.yaml` has the rest of the chain.

## License

ODbL-1.0. (The Hub's license identifier for this is `odbl`.)

This dataset is a Derivative Database of
[OpenStreetMap](https://www.openstreetmap.org/):

    (c) OpenStreetMap contributors, available under the Open Database License.
    https://www.openstreetmap.org/copyright

The Parquet files are a reformatting of the same records, not new data, and
carry ODbL unchanged. So does anything built from them, including question and
answer pairs whose answers are computed from them. The full notice is in
`LICENSE` beside this file.
