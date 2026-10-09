"""Turn the official Denton Halloween event database (Softr/Airtable dump) into events-db.js.

Usage:
  node tools/fetch_list.js https://era19963.softr.app/ raw/list.json
  node tools/fetch_details.js raw/list.json raw/details.json
  python3 tools/build_db.py raw/list.json raw/details.json > events-db.js

The live database only returns events that have not ended, so every fetch is merged into
data/records.json. A record that drops out of the feed is kept only if it had already ended
(it aged out); one that vanishes before its end date was cancelled or unapproved and is dropped.
"""
import json, re, sys
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
DETAIL = "https://era19963.softr.app/event-submissions-details?recordId="
TAGMAP = {"Family Friendly": "family", "21+": "21plus", "Show/Performance": "show", "Tour": "tour",
          "Haunted House": "haunted", "Live Music": "music", "Arts": "art", "Art Sale/Market": "market",
          "Seasonal Food and Drinks": "food", "Library": "library", "Festival": "festival",
          "Adapted and Inclusive": "inclusive", "Big Top Tent": "show"}
RECUR_MIN = 4  # same event on this many+ dates -> one recurring entry


def local(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(CT)


def hm(t):
    s = t.strftime("%-I:%M%p").lower().replace(":00", "")
    return {"12am": "midnight", "12pm": "noon"}.get(s, s)


def timestr(a, b):
    if a.hour == 0 and a.minute == 0 and (b <= a or (b - a) >= timedelta(hours=23)):
        return "All day"
    if b <= a:
        return hm(a)
    return f"{hm(a)}–{hm(b)}"


def norm(s):
    return re.sub(r"[^a-z0-9 ]", "", s.lower().replace("’", "'")).strip()


ARCHIVE = __import__("pathlib").Path(__file__).resolve().parent.parent / "data" / "records.json"


def merge_archive(list_path, det_path):
    """Merge a fresh fetch into the archive; returns the record list to build from."""
    tags = {x["id"]: [t["label"] for t in x["fields"].get("Tags", [])] for x in json.load(open(list_path))}
    now = datetime.now(timezone.utc).isoformat()
    fresh = {}
    for x in json.load(open(det_path)):
        f = {k: v for k, v in x["fields"].items() if k != "Event Photo"}
        f["Tags"] = tags.get(x["id"], [])
        fresh[x["id"]] = {"id": x["id"], "fields": f, "seen": now}
    old = json.loads(ARCHIVE.read_text()) if ARCHIVE.exists() else {}
    kept = {rid: r for rid, r in old.items() if rid not in fresh and r["fields"]["Event End Date"] <= now}
    dropped = [r["fields"]["Event Name"] for rid, r in old.items() if rid not in fresh and rid not in kept]
    merged = {**kept, **fresh}
    ARCHIVE.parent.mkdir(exist_ok=True)
    ARCHIVE.write_text(json.dumps(merged, ensure_ascii=False, indent=0, sort_keys=True))
    print(f"archive: {len(fresh)} live + {len(kept)} ended kept; {len(dropped)} dropped (vanished early): {dropped[:5]}", file=sys.stderr)
    return list(merged.values())


def main(list_path, det_path):
    rows = []
    for x in merge_archive(list_path, det_path):
        f = x["fields"]
        if (f.get("Approval Status") or {}).get("label") != "Approved":
            continue
        a, b = local(f["Event Start Date"]), local(f["Event End Date"])
        labels = f.get("Tags", [])
        ticketed = any(t.get("label") == "Yes" for t in (f.get("Ticketed") or [])) or "Ticket Required" in labels
        t = sorted({TAGMAP[l] for l in labels if l in TAGMAP})
        if not ticketed:
            t.append("free")
        rows.append(dict(rid=x["id"], title=f["Event Name"].strip(), a=a, b=b, tags=t,
                         address=re.sub(r"\s*\n\s*", ", ", (f.get("Address") or "").strip()).rstrip(", "),
                         desc=(f.get("Detailed Overview") or "").strip(),
                         link=f.get("Link to learn more, website, or social media") or None,
                         tickets=f.get("If ticketed, please provide link.") or None,
                         ticketed=ticketed))

    groups = {}
    for r in rows:
        groups.setdefault(norm(r["title"]), []).append(r)

    out = []
    for key, g in groups.items():
        g.sort(key=lambda r: r["a"])
        r0 = g[0]
        base = dict(title=r0["title"], venue="", address=r0["address"],
                    cost="Ticketed" if r0["ticketed"] else "No ticket needed",
                    tags=r0["tags"], desc=r0["desc"], link=r0["link"] or r0["tickets"],
                    tickets=r0["tickets"] if r0["tickets"] and r0["tickets"] != r0["link"] else None,
                    source=DETAIL + r0["rid"], verified=True, db=True)
        dates = sorted({r["a"].date().isoformat() for r in g})
        if len(dates) >= RECUR_MIN:
            per = {}
            for r in g:
                per.setdefault(r["a"].date().isoformat(), []).append(timestr(r["a"], r["b"]))
            per = {k: " & ".join(dict.fromkeys(v)) for k, v in per.items()}
            same = len(set(per.values())) == 1
            out.append(dict(base, id="db-" + r0["rid"], start=dates[0], end=dates[-1], dates=dates,
                            time=next(iter(per.values())) if same else "Times vary by date",
                            **({} if same else {"times": per}),
                            tags=sorted(set(base["tags"]) | {"allmonth"})))
        else:
            for r in g:
                d = r["a"].date().isoformat()
                e = dict(base, id="db-" + r["rid"], start=d, time=timestr(r["a"], r["b"]), source=DETAIL + r["rid"])
                if r["b"].date() > r["a"].date() and (r["b"] - r["a"]) >= timedelta(hours=20):
                    e["end"] = r["b"].date().isoformat()
                out.append(e)

    out.sort(key=lambda e: (e["start"], e["title"].lower()))
    sys.stdout.write("// Generated by tools/build_db.py from the official dentonhalloween.com event database.\n"
                     "// Do not hand-edit; re-run the tools instead. Hand-checked entries live in events.js.\n")
    sys.stdout.write("window.DHW_DB_UPDATED = %s;\n" % json.dumps(datetime.now(CT).date().isoformat()))
    sys.stdout.write("window.DHW_DB_EVENTS = " + json.dumps(out, ensure_ascii=False, indent=0) + ";\n")
    print(f"{len(rows)} rows -> {len(out)} events", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:])
