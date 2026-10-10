"""Build the page from src/page.html + event data.

  python3 tools/bundle.py

Writes:
  index.html          standalone page for the repo (full HTML document; photos load from img/)
  dist/artifact.html  same page without the document skeleton, for publishing as a claude.ai artifact
Also inlines venue pins (data/geo.json) and downtown streets (data/streets.json) for the map.
"""
import json, pathlib, re, subprocess, sys

root = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(root / "tools"))
from geocode import key_of  # noqa: E402

page = (root / "src" / "page.html").read_text()
FILES = ("events.js", "events-db.js", "events-feeds.js")
data = "\n".join((root / f).read_text().replace("</script", "<\\/script") for f in FILES if (root / f).exists())

# venue key + display name per event
js = ("global.window={};require('./events.js');require('./events-db.js');try{require('./events-feeds.js')}catch(e){};"
      "console.log(JSON.stringify([...window.DHW_EVENTS,...window.DHW_DB_EVENTS,...(window.DHW_FEED_EVENTS||[])].map(e=>[e.id,e.venue||'',e.address||''])))")
rows = json.loads(subprocess.check_output(["node", "-e", js], cwd=root))
geo = json.loads((root / "data" / "geo.json").read_text())
by_id, names = {}, {}
for eid, venue, addr in rows:
    k = key_of(addr) or key_of(venue) or key_of(venue + " " + addr)
    if not k:
        continue
    by_id[eid] = k
    label = venue.strip() or re.split(r"\s\d{2,5}\s", " " + addr)[0].strip(" ,:-")
    label = re.sub(r"\s+(located at|is|at)$", "", label, flags=re.I)
    if label and not re.match(r"^\d", label) and len(label) < 60:
        names.setdefault(k, {}).setdefault(label, 0)
        names[k][label] += 1
venues = {}
for k in set(by_id.values()):
    g = geo.get(k)
    ok = g and not str(g[-1]).startswith("off-street") or (g and str(g[-1]).startswith("off-street") and int(re.sub(r"\D", "", g[-1])) < 150)
    nm = max(names.get(k, {}).items(), key=lambda x: x[1])[0] if names.get(k) else k
    venues[k] = {"name": nm, "addr": k, **({"lat": round(g[0], 5), "lon": round(g[1], 5)} if ok else {})}
streets = json.loads((root / "data" / "streets.json").read_text())
shops_p = root / "data" / "shops.json"
shops_js = "window.DHW_SHOPS = " + (shops_p.read_text() if shops_p.exists() else "[]") + ";\n"
geo_js = shops_js + "window.DHW_GEO = " + json.dumps({"byId": by_id, "venues": venues, "streets": streets}, separators=(",", ":")) + ";"

body = page.replace("<!--DATA-->", "<script>\n" + data + "\n" + geo_js + "\n</script>")
(root / "dist").mkdir(exist_ok=True)
(root / "dist" / "artifact.html").write_text(body)
head, rest = body.split("</style>", 1)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
       + head + "</style>\n</head>\n<body>\n" + rest + "\n</body>\n</html>\n")
(root / "index.html").write_text(doc)
print(f"built index.html {len(doc)} bytes; {len(venues)} venues, {sum(1 for v in venues.values() if 'lat' in v)} pinned")
