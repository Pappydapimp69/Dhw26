"""Build the page from src/page.html + event data.

  python3 tools/bundle.py

Writes:
  index.html          standalone page for the repo (full HTML document)
  dist/artifact.html  same page without the document skeleton, for publishing as a claude.ai artifact
"""
import pathlib

root = pathlib.Path(__file__).resolve().parent.parent
page = (root / "src" / "page.html").read_text()
data = "\n".join((root / f).read_text().replace("</script", "<\\/script") for f in ("events.js", "events-db.js"))
body = page.replace("<!--DATA-->", "<script>\n" + data + "\n</script>")
(root / "dist").mkdir(exist_ok=True)
(root / "dist" / "artifact.html").write_text(body)
head, rest = body.split("</style>", 1)
doc = ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
       '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
       + head + "</style>\n</head>\n<body>\n" + rest + "\n</body>\n</html>\n")
(root / "index.html").write_text(doc)
print("built index.html", len(doc), "bytes; dist/artifact.html", len(body), "bytes")
