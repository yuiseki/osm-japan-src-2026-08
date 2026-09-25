#!/usr/bin/env bash
# Load the frozen extract into PostGIS with osm2pgsql, in Docker.
#
# The schema is osm2pgsql's own classic pgsql output, not one of our design:
#   planet_osm_point / planet_osm_line / planet_osm_polygon / planet_osm_roads
#
# --hstore is required. The style promotes 106 tags to columns, but the
# question set also asks about opening_hours, start_date and building:levels,
# which it does not promote. Those live in the hstore `tags` column.
#
# No projection flag, so osm2pgsql's default EPSG:3857 applies.
set -euo pipefail
cd "$(dirname "$0")/../docker"

PBF=${PBF:-/work/data/japan-260831.osm.pbf}

# Two flags the Tokyo recipe does not need. Neither touches the schema.
#
# --flat-nodes keeps the node locations in a file instead of in RAM. Japan has
# 318 million of them and the in-memory cache for that is tens of gigabytes;
# the file is about 2.5 GB and the machine stays usable.
#
# --cache 8000 caps the rest. Without a cap osm2pgsql sizes itself to the
# machine, and this one has no swap: it does not get OOM-killed, it stops
# answering.
docker compose up -d db
docker compose run --rm loader \
  osm2pgsql \
    --create \
    --database osm \
    --style /opt/osm2pgsql/default.style \
    --hstore \
    --cache "${CACHE:-8000}" \
    --flat-nodes /work/tmp/flat.nodes \
    "$PBF"
