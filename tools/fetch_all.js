// Fetch every record (all approval states, past and future) from the event app's detail-page
// datasource, which, unlike the list page, has no "not ended yet" filter.
//   NODE_PATH=$(npm root -g) node tools/fetch_all.js raw/all.json
// Exits non-zero if fewer unique records come back than the source reports.
const { chromium } = require('playwright');
const fs = require('fs');
(async () => {
  const b = await chromium.launch(); const p = await b.newPage();
  let base = null, hdr = null;
  p.on('request', r => { const u = r.url(); if (!base && u.includes('/records/rec') && r.method() === 'POST') { base = u.replace(/rec[A-Za-z0-9]+$/, ''); hdr = r.headers(); } });
  await p.goto('https://era19963.softr.app/event-submissions-details?recordId=recnZz87ZvIt2Mxz2', { waitUntil: 'networkidle', timeout: 60000 });
  if (!base) { console.error('could not find the datasource request'); process.exit(1); }
  const out = await p.evaluate(async ({ base, hdr }) => {
    delete hdr['content-length']; const all = []; let total = 0;
    for (let off = 0; off < 5000; off += 50) {
      const r = await fetch(base, { method: 'POST', headers: hdr, credentials: 'include', body: JSON.stringify({ options: { timeZone: 'UTC', userLocale: 'en-US' }, pageContext: null, filterCriteria: {}, pagingOption: { offset: off, count: 50 }, sortingOption: [{ sortingField: 'Event Start Date', sortType: 'ASC' }] }) });
      const j = await r.json(); total = j.total; all.push(...j.items); if (!j.items.length || all.length >= total) break;
    }
    return { all, total };
  }, { base, hdr });
  const uniq = new Set(out.all.map(x => x.id)).size;
  console.log('records', out.all.length, 'unique', uniq, 'reported total', out.total);
  await b.close();
  if (uniq !== out.total) { console.error(`FETCH INCOMPLETE: got ${uniq} of ${out.total}`); process.exit(1); }
  fs.writeFileSync(process.argv[2], JSON.stringify(out.all));
})();
