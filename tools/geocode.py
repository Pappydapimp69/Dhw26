"""Geocode event addresses into data/geo.json {normalized street address: [lat, lon, how]}.

  python3 tools/geocode.py

Reads events.js + events-db.js through node. Nominatim first (1 req/s, cached), Census geocoder
as fallback. Addresses without a street number are skipped (they get no pin).
"""
import json, pathlib, re, subprocess, sys, time, urllib.parse, urllib.request

root = pathlib.Path(__file__).resolve().parent.parent
GEO = root / "data" / "geo.json"
STREET = re.compile(r"(\d{2,5})\s+((?:[NSEW]\.?\s+)?[A-Za-z0-9 .'-]+?\s(?:St|Street|Ave|Avenue|Blvd|Boulevard|Dr|Drive|Rd|Road|Ln|Lane|Pkwy|Parkway|Way|Pl|Place|Hwy|Highway|Ct|Court|Loop|Trl|Trail|Cir|Circle)\b\.?|(?:N\.?|S\.?)?\s*(?:I-?35E?|Interstate 35E?))", re.I)


# landmarks written without a street number -> the address we pin them to
PLACES = [(r"big top", "126 E Oak St"),
          (r"john b\.? denton|courthouse|denton square|on the square|around the square|square by|^downtown denton$|hickory, oak & industrial", "110 W Hickory St"),
          (r"\bw\.? pecan", "100 W Pecan St"), (r"\bunt\b.*lot 3[67]|lot 3[67].*\bunt\b", "1155 Union Cir")]
LOOSE = re.compile(r"(\d{2,5})\s+((?:[NSEW]\.?|North|South|East|West)\s+)?(Ave [A-Z]|[A-Z][a-z]+)(?=\s*,|\s+Denton|\s*$)")
DIRS = {"north": "N", "south": "S", "east": "E", "west": "W"}


def key_of(addr):
    addr = re.sub(r"(Street|St\.?|Avenue|Drive)(?=[A-Z])", r"\1 ", addr or "")
    m = STREET.search(addr)
    if not m:
        l = LOOSE.search(addr)
        if l:
            d = (l.group(2) or "").strip().rstrip(".")
            name = l.group(3)
            suffix = "" if name.startswith("Ave ") else {"University": " Dr", "Teasley": " Ln", "Bonnie Brae": " St"}.get(name, " St")
            return re.sub(r"\s+", " ", f"{l.group(1)} {DIRS.get(d.lower(), d)} {name}{suffix}").strip().title()
        for pat, k in PLACES:
            if re.search(pat, addr, re.I):
                return k
        return None
    k = f"{m.group(1)} {m.group(2)}"
    k = re.sub(r"^(\d+) (North|South|East|West)\b", lambda x: x.group(1) + " " + DIRS[x.group(2).lower()], k, flags=re.I)
    k = re.sub(r"\.", "", k)
    k = re.sub(r"\bStreet\b", "St", k, flags=re.I); k = re.sub(r"\bAvenue\b", "Ave", k, flags=re.I)
    k = re.sub(r"\bDrive\b", "Dr", k, flags=re.I); k = re.sub(r"\bRoad\b", "Rd", k, flags=re.I)
    k = re.sub(r"\bBoulevard\b", "Blvd", k, flags=re.I); k = re.sub(r"\bLane\b", "Ln", k, flags=re.I)
    k = re.sub(r"\b([NSEW])\s", lambda m: m.group(1).upper() + " ", k)
    return re.sub(r"\s+", " ", k).strip().title().replace("Ih", "IH")


# messy keys -> a query that geocodes (street text, or a place name for Nominatim free-text search)
ALIASES = {"126 E Oak Across The St": "126 E Oak St", "00 West Oak St": "100 W Oak St",
           "2100 N I-35E": "q:Murchison Performing Arts Center, Denton, TX"}


def get(url, headers=None):
    req = urllib.request.Request(url, headers={"User-Agent": "dhw26-denton-halloween-guide/1.0", **(headers or {})})
    return json.load(urllib.request.urlopen(req, timeout=30))


def nominatim(k):
    q = urllib.parse.urlencode({"street": k, "city": "Denton", "state": "TX", "country": "USA", "format": "json", "limit": 1, "addressdetails": 1})
    r = get("https://nominatim.openstreetmap.org/search?" + q)
    time.sleep(1.1)
    if r and r[0].get("address", {}).get("house_number"):
        return [float(r[0]["lat"]), float(r[0]["lon"]), "osm"]
    return None


def census(k):
    q = urllib.parse.urlencode({"address": k + ", Denton, TX", "benchmark": "Public_AR_Current", "format": "json"})
    m = get("https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?" + q)["result"]["addressMatches"]
    if m:
        c = m[0]["coordinates"]
        return [c["y"], c["x"], "census"]
    return None


STREETS = root / "data" / "streets.json"  # downtown OSM ways (tools/streets: Overpass dump, simplified)
ABBR = {"st": "street", "ave": "avenue", "dr": "drive", "rd": "road", "blvd": "boulevard", "ln": "lane", "pl": "place",
        "ct": "court", "n": "north", "s": "south", "e": "east", "w": "west", "pkwy": "parkway", "hwy": "highway"}


def street_name(k):
    words = k.lower().split()[1:]
    return " ".join(ABBR.get(w, w) for w in words)


def dist_m(p, a, b):
    import math
    ky, kx = 111320, 111320 * math.cos(math.radians(p[0]))
    px, py = p[1] * kx, p[0] * ky; ax, ay = a[1] * kx, a[0] * ky; bx, by = b[1] * kx, b[0] * ky
    dx, dy = bx - ax, by - ay
    t = 0 if dx == dy == 0 else max(0, min(1, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def off_street(k, pt, ways):
    """Metres from pt to the nearest OSM way carrying this street's name; None if not checkable."""
    name = street_name(k)
    segs = [w["c"] for w in ways if w["n"].lower() == name]
    if not segs:
        return None
    return min(dist_m(pt, c[i], c[i + 1]) for c in segs for i in range(len(c) - 1))


def main():
    js = ("global.window={};require('./events.js');require('./events-db.js');try{require('./events-feeds.js')}catch(e){};"
          "console.log(JSON.stringify([...window.DHW_EVENTS,...window.DHW_DB_EVENTS,...(window.DHW_FEED_EVENTS||[])].map(e=>e.address||'')))")
    addrs = json.loads(subprocess.check_output(["node", "-e", js], cwd=root))
    geo = json.loads(GEO.read_text()) if GEO.exists() else {}
    keys = sorted({k for a in addrs if (k := key_of(a))})
    todo = [k for k in keys if not geo.get(k)]
    print(f"{len(keys)} distinct street addresses, {len(todo)} to geocode", file=sys.stderr)
    for k in todo:
        try:
            a = ALIASES.get(k, k)
            if a.startswith("q:"):
                r = get("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": a[2:], "format": "json", "limit": 1}))
                time.sleep(1.1)
                geo[k] = [float(r[0]["lat"]), float(r[0]["lon"]), "osm"] if r else None
            else:
                geo[k] = nominatim(a) or census(a)
        except Exception as e:
            print("fail", k, e, file=sys.stderr); geo[k] = None
    ways = json.loads(STREETS.read_text()) if STREETS.exists() else []
    fixed = 0
    for k, v in geo.items():
        if not v or len(v) > 3:
            continue
        d = off_street(k, v, ways)
        if d is None or d <= 80:
            v.append("checked" if d is not None else "unchecked")
            continue
        alt = census(k) if v[2] == "osm" else nominatim(k)
        d2 = off_street(k, alt, ways) if alt else None
        if alt and d2 is not None and d2 <= 80:
            geo[k] = alt + ["checked"]; fixed += 1
        else:
            v.append(f"off-street {int(d)}m")
    print(f"street check: {fixed} swapped to the other geocoder; still off: "
          f"{[k for k, v in geo.items() if v and str(v[-1]).startswith('off')]}", file=sys.stderr)
    geo = {k: v for k, v in geo.items() if k in keys}  # drop keys no event uses any more
    GEO.write_text(json.dumps(geo, indent=0, sort_keys=True))
    print(f"ok {sum(1 for v in geo.values() if v)} / {len(geo)}", file=sys.stderr)


if __name__ == "__main__":
    main()
