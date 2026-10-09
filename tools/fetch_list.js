const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  let req = null;
  p.on('request', r => { if (!req && r.url().includes('/v1/datasource/') && r.method() === 'POST') req = { url: r.url(), body: r.postData(), headers: r.headers() }; });
  await p.goto(process.argv[2], { waitUntil: 'domcontentloaded', timeout: 60000 });
  for (let i = 0; i < 20 && !req; i++) { await p.mouse.wheel(0, 4000); await p.waitForTimeout(1000); }
  console.log('BODY', req.body.slice(0, 600));
  const all = await p.evaluate(async (req) => {
    const out = []; const body = JSON.parse(req.body);
    for (let off = 0; off < 700; off += 50) {
      const bb = JSON.parse(JSON.stringify(body));
      bb.pagingOption = { offset: off, count: 50 };
      const h = { ...req.headers }; delete h['content-length'];
      const r = await fetch(req.url, { method: 'POST', headers: h, body: JSON.stringify(bb), credentials: 'include' });
      const j = await r.json(); out.push(...j.items); if (!j.items.length || out.length >= j.total) break;
    }
    return out;
  }, req);
  fs.writeFileSync(process.argv[3], JSON.stringify(all));
  console.log('ITEMS', all.length, new Set(all.map(x => x.id)).size);
  await b.close();
})();
