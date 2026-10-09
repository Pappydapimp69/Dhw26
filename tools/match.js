// Prints curated events.js entries that overlap DB entries (same date, similar title).
global.window = {}; require("../events.js"); require("../events-db.js");
const C = window.DHW_EVENTS, D = window.DHW_DB_EVENTS;
const toks = s => new Set(s.toLowerCase().replace(/[^a-z0-9 ]/g, " ").split(/\s+/).filter(w => w.length > 2 && !["the", "and", "denton", "halloween", "dentons"].includes(w)));
const sim = (a, b) => { const A = toks(a), B = toks(b); const i = [...A].filter(x => B.has(x)).length; return i / Math.max(1, Math.min(A.size, B.size)); };
const end = e => e.end || e.start;
for (const c of C) {
  const m = D.filter(d => d.start <= end(c) && end(d) >= c.start && sim(c.title, d.title) >= 0.5);
  if (m.length) console.log(c.id.padEnd(16), "<=>", m.map(d => `${d.id} [${d.start}${d.end ? "→" + d.end : ""}] ${d.title}`).join(" || "));
}
