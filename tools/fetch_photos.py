"""Download each event's first photo from a fresh details dump and save a small WebP.

  python3 tools/fetch_photos.py raw/details.json

Airtable photo links expire within a day, so run this right after fetch_details.js.
Writes img/<attachment id>.webp (480px wide max) and data/photos.json {record id: file}.
Existing files are reused, so repeat runs only download new photos.
"""
import io, json, pathlib, sys, urllib.request
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageOps

root = pathlib.Path(__file__).resolve().parent.parent
IMG = root / "img"; IMG.mkdir(exist_ok=True)
MAP = root / "data" / "photos.json"


def pick(att):
    thumbs = {t["size"]: t["url"] for t in att.get("thumbnails", [])}
    return thumbs.get("large") or att["url"]


def get(job):
    rid, att = job
    out = IMG / f"{att['id']}.webp"
    if out.exists():
        return rid, out.name, False
    try:
        req = urllib.request.Request(pick(att), headers={"User-Agent": "Mozilla/5.0"})
        raw = urllib.request.urlopen(req, timeout=30).read()
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(raw))).convert("RGB")
        im.thumbnail((480, 480 * 3))
        if im.height > 600:  # keep posters from towering
            top = (im.height - 600) // 3
            im = im.crop((0, top, im.width, top + 600))
        im.save(out, "WEBP", quality=58, method=6)
        return rid, out.name, True
    except Exception as e:
        print("skip", rid, e, file=sys.stderr)
        return rid, None, False


def main(det_path):
    jobs = []
    for x in json.load(open(det_path)):
        atts = [a for a in (x["fields"].get("Event Photo") or []) if str(a.get("type", "")).startswith("image/")]
        if atts:
            jobs.append((x["id"], atts[0]))
    mapping = json.loads(MAP.read_text()) if MAP.exists() else {}
    new = 0
    with ThreadPoolExecutor(8) as pool:
        for rid, name, fresh in pool.map(get, jobs):
            if name:
                mapping[rid] = name; new += fresh
    MAP.write_text(json.dumps(mapping, indent=0, sort_keys=True))
    size = sum(p.stat().st_size for p in IMG.glob("*.webp"))
    print(f"{len(jobs)} records with photos; {new} downloaded; {len(set(mapping.values()))} files, {size/1e6:.1f} MB", file=sys.stderr)


if __name__ == "__main__":
    main(*sys.argv[1:])
