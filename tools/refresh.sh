#!/usr/bin/env bash
# Re-pull the official event database and rebuild the page. Fails (non-zero) on any short fetch.
set -euo pipefail
cd "$(dirname "$0")/.."
export NODE_PATH="${NODE_PATH:-$(npm root -g)}"
mkdir -p raw
node tools/fetch_list.js https://era19963.softr.app/ raw/list.json
node tools/fetch_all.js raw/all.json
python3 tools/fetch_photos.py raw/all.json 2> >(grep -v Warning >&2)
python3 tools/build_db.py raw/list.json raw/all.json > events-db.js.new && mv events-db.js.new events-db.js
python3 tools/fetch_feeds.py > events-feeds.js.new && mv events-feeds.js.new events-feeds.js
python3 tools/geocode.py
python3 tools/bundle.py
node tools/match.js > raw/match.txt || true
echo "refresh ok: $(date -u +%FT%TZ)"
