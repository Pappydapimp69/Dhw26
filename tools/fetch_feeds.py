"""Pull Halloween events from the UNT and TWU calendars (Localist) and Denton Public Library
(BiblioCommons) into events-feeds.js.

  python3 tools/fetch_feeds.py > events-feeds.js

Keeps events open to the public whose title matches a Halloween keyword (or whose description
names Halloween / costumes / Día de los Muertos outright). Repeats of one event are collapsed into
one entry with per-date times. Times converted to America/Chicago.
"""
import html, json, re, sys, urllib.parse, urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")
START, END = "2026-10-01", "2026-11-01"
TITLE_KW = re.compile(r"hallowe|spook|costume|haunt|ghost|pumpkin|monster|zombie|witch|muertos|day of the dead|\bboo\b|trick.or.treat|horror|creep|skelet|vampire|fright|scary|jack.o|potion|cauldron|\bbats?\b|frankenstein|dracula|mummy|goblin|ghoul|eerie|creature|spirits", re.I)
DESC_KW = re.compile(r"halloween|costume|d[ií]a de (los )?muertos|day of the dead|trick.or.treat", re.I)
SKIP = re.compile(r"national .{0,30} day\b|course evaluation|last day to", re.I)
PUBLIC = {"General Public", "Community", "Parents & Families", "Families", "Visitors", "Public"}
TAG_RULES = [("family", r"kid|child|famil|all ages|story ?time|toddler|teen"), ("free", r"\bfree\b"), ("show", r"recital|concert|theatre|theater|perform|dance|fashion show"),
             ("music", r"recital|concert|band|orchestra|choir"), ("art", r"craft|paint|art\b|exhibit|make and take|felt|draw"), ("library", r"library"), ("movie", r"film|movie|screening")]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dhw26-denton-halloween-guide/1.0"})
    return json.load(urllib.request.urlopen(req, timeout=40))


def hm(t):
    s = t.strftime("%-I:%M%p").lower().replace(":00", "")
    return {"12am": "midnight", "12pm": "noon"}.get(s, s)


def span(a, b, all_day=False):
    if all_day:
        return "All day"
    return f"{hm(a)}–{hm(b)}" if b and b > a else hm(a)


def tags_for(text, free):
    t = [k for k, pat in TAG_RULES if re.search(pat, text, re.I)]
    if free and "free" not in t:
        t.append("free")
    return sorted(set(t))


def localist(base, src):
    out, page = [], 1
    while True:
        d = get(f"{base}/api/2/events?start={START}&end={END}&pp=100&page={page}")
        for x in d["events"]:
            e = x["event"]
            aud = {a["name"] for a in e.get("filters", {}).get("event_audience", [])}
            if aud and not aud & PUBLIC:
                continue
            desc = e.get("description_text") or ""
            if SKIP.search(e["title"]) or not (TITLE_KW.search(e["title"]) or DESC_KW.search(desc)):
                continue
            for inst in e.get("event_instances", []):
                i = inst["event_instance"]
                a = datetime.fromisoformat(i["start"]).astimezone(CT)
                b = datetime.fromisoformat(i["end"]).astimezone(CT) if i.get("end") else None
                if not (START <= a.date().isoformat() <= END):
                    continue
                out.append(dict(key=f"{src}-{e['id']}", title=e["title"].strip(), day=a.date().isoformat(), time=span(a, b, i.get("all_day")),
                                venue=(e.get("location_name") or "").strip() or src.upper(), address=(e.get("address") or "").strip(),
                                cost=e.get("ticket_cost") or ("Free" if e.get("free") else ""), free=bool(e.get("free")),
                                desc=re.sub(r"\s+", " ", desc).strip()[:600], link=e.get("localist_url") or e.get("url"),
                                tickets=e.get("ticket_url") or None, img=None, src=src))
        if not d["page"].get("next_page"):
            break
        page += 1
    return out


BRANCHES = {}


def library():
    out, seen = [], set()
    for q in ["halloween", "spooky", "costume", "pumpkin", "monster", "ghost", "witch", "muertos", "haunted", "boo", "bats", "trick or treat"]:
        page = 1
        while True:
            d = get("https://gateway.bibliocommons.com/v2/libraries/denton/events?" + urllib.parse.urlencode({"q": q, "limit": 50, "page": page, "startDate": START, "endDate": END}))
            ents = d.get("entities", {})
            for lid, loc in ents.get("locations", {}).items():
                a = loc.get("address") or {}
                BRANCHES[lid] = (loc.get("name", ""), " ".join(filter(None, [a.get("number"), a.get("street")])) or "")
            for eid in d["events"]["items"]:
                if eid in seen:
                    continue
                seen.add(eid)
                ev = ents["events"][eid]; df = ev["definition"]
                if df.get("isCancelled") or not (TITLE_KW.search(df["title"]) or DESC_KW.search(df.get("description") or "")):
                    continue
                a = datetime.fromisoformat(ev["indexStart"].replace("Z", "+00:00")).astimezone(CT)
                b = datetime.fromisoformat(ev["indexEnd"].replace("Z", "+00:00")).astimezone(CT)
                if not (START <= a.date().isoformat() <= END):
                    continue
                multi = (b - a).days >= 1
                name, street = BRANCHES.get(df.get("branchLocationId"), ("Denton Public Library", ""))
                desc = html.unescape(re.sub(r"<[^>]+>", " ", df.get("description") or ""))
                out.append(dict(key="lib-" + (ev.get("seriesId") or eid), title=df["title"].strip(), day=a.date().isoformat(),
                                end=b.date().isoformat() if multi else None, time="During library hours" if multi else span(a, b),
                                venue=name or "Denton Public Library", address=street, cost="Free", free=True,
                                desc=re.sub(r"\s+", " ", desc).strip()[:600], link=f"https://denton.bibliocommons.com/v2/events/{eid}",
                                tickets=None, img=None, src="library"))
            pg = d["events"]["pagination"]
            if pg["page"] >= pg["pages"]:
                break
            page += 1
    return out


def collapse(rows):
    groups = {}
    for r in rows:
        groups.setdefault((r["src"], re.sub(r"[^a-z0-9]", "", r["title"].lower()), r["venue"]), []).append(r)
    out = []
    for g in groups.values():
        g.sort(key=lambda r: r["day"]); r0 = g[0]
        dates = sorted({r["day"] for r in g})
        per = {}
        for r in g:
            per.setdefault(r["day"], []).append(r["time"])
        per = {k: " & ".join(dict.fromkeys(v)) for k, v in per.items()}
        e = dict(id="fd-" + re.sub(r"[^a-z0-9]+", "-", r0["key"].lower()), title=r0["title"], start=dates[0], venue=r0["venue"], address=r0["address"],
                 cost=r0["cost"] or "", tags=tags_for(r0["title"] + " " + r0["desc"] + " " + r0["venue"], r0["free"]),
                 desc=r0["desc"], link=r0["link"], source=r0["link"], verified=True, feed=r0["src"])
        if r0["tickets"]:
            e["tickets"] = r0["tickets"]
        if r0.get("end"):
            e["end"] = r0["end"]; e["time"] = r0["time"]
        elif len(dates) > 1:
            e["end"] = dates[-1]; e["dates"] = dates
            vals = set(per.values())
            e["time"] = vals.pop() if len(vals) == 1 else "Times vary by date"
            if len(set(per.values())) > 1:
                e["times"] = per
        else:
            e["time"] = per[dates[0]]
        out.append(e)
    return sorted(out, key=lambda e: (e["start"], e["title"]))


def previous(name):
    """Events from the last good run for one feed, so a network blip never drops them."""
    import pathlib
    f = pathlib.Path(__file__).resolve().parent.parent / "events-feeds.js"
    if not f.exists():
        return []
    txt = f.read_text()
    return [e for e in json.loads(txt[txt.index("= ") + 2: txt.rindex(";")]) if e.get("feed") == name]


def main():
    rows, kept = [], []
    for name, fn in [("unt", lambda: localist("https://calendar.unt.edu", "unt")), ("twu", lambda: localist("https://events.twu.edu", "twu")), ("library", library)]:
        try:
            got = fn(); rows += got
            print(f"{name}: {len(got)} instances", file=sys.stderr)
        except Exception as ex:  # one feed failing must not take the others down
            old = previous(name)
            kept += old
            print(f"{name}: FAILED {ex}; kept {len(old)} events from the last good run", file=sys.stderr)
    events = sorted(collapse(rows) + kept, key=lambda e: (e["start"], e["title"]))
    print(f"feeds: {len(events)} events", file=sys.stderr)
    sys.stdout.write("// Generated by tools/fetch_feeds.py (UNT, TWU, Denton Public Library). Do not hand-edit.\n")
    sys.stdout.write("window.DHW_FEED_EVENTS = " + json.dumps(events, ensure_ascii=False, indent=0) + ";\n")


if __name__ == "__main__":
    main()
