# dhw26 — Denton Halloween 2026

One-page guide to the **31 Days of Denton Halloween** (Oct 2026). `index.html` is self-contained — open it anywhere.

After editing `events.js` or `events-db.js`, run `python3 tools/bundle.py` to inline the data into `index.html`.

- `events-db.js` — generated from the official dentonhalloween.com event database (a Softr app backed by Airtable that the site's Events page embeds). 623 records → 247 events after collapsing repeat dates. Don't hand-edit.
- `events.js` — hand-checked entries (attractions, Day of the Dead schedule, prices, notes). `dbIds` on an entry hides the matching DB records so nothing shows twice.
- Events with no official page show "No official page"; DB events always link to their "Official listing".
- `verified: false` marks events with only one secondary source or conflicting info.

## Refresh the database

```sh
mkdir -p raw
NODE_PATH=$(npm root -g) node tools/fetch_list.js https://era19963.softr.app/ raw/list.json
NODE_PATH=$(npm root -g) node tools/fetch_details.js raw/list.json raw/details.json
python3 tools/build_db.py raw/list.json raw/details.json > events-db.js
node tools/match.js   # curated entries that may duplicate DB records -> add dbIds
python3 tools/bundle.py
```

Needs Playwright + Chromium. The DB only returns events that haven't ended yet, so past events drop off on refresh.

Other sources: cityofdenton.com, Denton Record-Chronicle, dentondayofthedeadfestival.com, Prekindle (Big Top Tent), TWU, Denton Enterprise Airport, dentoncommunityvoice.com.

Conflicts resolved toward the organizer's own listing (e.g. Spooky Spirits Stroll 4–7pm, not the 1–4pm in news roundups). Unresolved: Big Top Tent address — organizer listings say 126 E. Oak St. and some say 301 E. Oak St.
