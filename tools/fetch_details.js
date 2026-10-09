const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const ids = JSON.parse(fs.readFileSync(process.argv[2])).map(x => x.id);
  const b = await chromium.launch(); const p = await b.newPage();
  let base = null, hdr = null;
  p.on('request', r => { const u = r.url(); if (!base && u.includes('/records/rec') && r.method() === 'POST') { base = u.replace(/rec[A-Za-z0-9]+$/, ''); hdr = r.headers(); } });
  await p.goto('https://era19963.softr.app/event-submissions-details?recordId=' + ids[0], { waitUntil: 'networkidle', timeout: 60000 });
  const out = await p.evaluate(async ({ ids, base, hdr }) => {
    delete hdr['content-length']; const res = [];
    const body = JSON.stringify({ options: { timeZone: 'UTC', userLocale: 'en-US' }, pageContext: null, filterCriteria: {} });
    for (let i = 0; i < ids.length; i += 15) {
      const chunk = ids.slice(i, i + 15);
      const got = await Promise.all(chunk.map(id => fetch(base + id, { method: 'POST', headers: hdr, body, credentials: 'include' }).then(r => r.ok ? r.json() : { id, error: r.status }).catch(e => ({ id, error: String(e) }))));
      res.push(...got);
    }
    return res;
  }, { ids, base, hdr });
  fs.writeFileSync(process.argv[3], JSON.stringify(out));
  console.log('got', out.length, 'errors', out.filter(x => x.error).length);
  await b.close();
})();
