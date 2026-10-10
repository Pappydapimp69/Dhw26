# dhw26 — Denton Halloween 2026

One-page guide to the **31 Days of Denton Halloween** (Oct 2026). `index.html` is self-contained — open it anywhere.

The page source is `src/page.html`. After editing it, `events.js` or `events-db.js`, run `python3 tools/bundle.py` — it writes `index.html` (standalone) and `dist/artifact.html` (published at https://claude.ai/artifact/PL6hpEYq7ZzXmWjBSy5t8k).

- `events-db.js` — generated from the official dentonhalloween.com event database (a Softr app backed by Airtable that the site's Events page embeds). 623 records → 247 events after collapsing repeat dates. Don't hand-edit.
- `events.js` — hand-checked entries (attractions, Day of the Dead schedule, prices, notes). `dbIds` on an entry hides the matching DB records so nothing shows twice.
- Events with no official page show "No official page"; DB events always link to their "Official listing".
- `verified: false` marks events with only one secondary source or conflicting info.

## Refresh the database

```sh
tools/refresh.sh      # fetch list + all records, photos, build, geocode, bundle
```

Steps inside: `fetch_list.js` (tags for live events), `fetch_all.js` (every record incl. ended ones), `fetch_photos.py` (480px WebP into img/), `build_db.py` (archive merge into data/records.json, collapse repeats, UTC→Central), `geocode.py` (data/geo.json, each pin checked against its named street in data/streets.json), `bundle.py` (index.html + dist/artifact.html). `raw/match.txt` lists hand-checked entries that may now duplicate DB records — add their ids to `dbIds`.

Needs Playwright + Chromium. Both fetch scripts exit with an error if they get fewer records than the database reports. The DB only returns events that haven't ended yet, so every fetch is merged into `data/records.json` (committed): records that aged out are kept, records that vanished before their end date (cancelled/unapproved) are dropped.

Other sources: cityofdenton.com, Denton Record-Chronicle, dentondayofthedeadfestival.com, Prekindle (Big Top Tent), TWU, Denton Enterprise Airport, dentoncommunityvoice.com.

Conflicts resolved toward the organizer's own listing (e.g. Spooky Spirits Stroll 4–7pm, not the 1–4pm in news roundups). Unresolved: Big Top Tent address — organizer listings say 126 E. Oak St. and some say 301 E. Oak St.
