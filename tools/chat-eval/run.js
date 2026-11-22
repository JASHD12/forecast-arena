// Offline evaluation of Ask the Arena (T314): golden questions plus lookups generated from the pack.
// Usage: node tools/chat-eval/run.js <chat.js> <pack.json> <golden.jsonl>   -> JSON on stdout
'use strict';
const fs = require('fs');
const [chatPath, packPath, goldenPath] = process.argv.slice(2);
const chat = require(require('path').resolve(chatPath));
const packText = fs.readFileSync(packPath, 'utf8');
const pack = JSON.parse(packText);
const golden = fs.readFileSync(goldenPath, 'utf8').split('\n').filter(Boolean).map(JSON.parse);

const NUM = /\d+(?:\.\d+)?/g;
const allowed = new Set((packText.match(NUM) || []).map(Number));
for (const q of pack.questions) for (const id of Object.keys(q.f)) {
  const p = q.f[id][0];
  allowed.add(Math.round(p * 100));
}
function numbersOf(reply) {
  const parts = [reply.text, ...(reply.rows || []).flat()];
  return parts.join(' ').match(NUM) || [];
}
const latencies = [];
function run(q) {
  const t0 = process.hrtime.bigint();
  const r = chat.answer(q, pack);
  latencies.push(Number(process.hrtime.bigint() - t0) / 1e6);
  return r;
}
function invented(q, reply) {
  const own = new Set(q.match(NUM) || []);
  const ownN = new Set([...own].map(Number));
  return numbersOf(reply).filter((n) => !allowed.has(Number(n)) && !ownN.has(Number(n)));
}

const failures = [];
const byCat = {};
let invention = 0, answers = 0;
const tiers = { '0': 0, '1': 0, '-1': 0 };
function record(cat, ok, info) {
  byCat[cat] = byCat[cat] || { n: 0, ok: 0 };
  byCat[cat].n++;
  if (ok) byCat[cat].ok++; else failures.push(Object.assign({ category: cat }, info));
}
function check(q, reply) {
  answers++;
  tiers[String(reply.tier)]++;
  const bad = invented(q, reply);
  if (bad.length) { invention++; failures.push({ category: 'invented_numbers', q, numbers: bad }); }
}
for (const g of golden) {
  const reply = run(g.q);
  check(g.q, reply);
  const e = g.expect;
  const ok = (e.kind ? reply.kind === e.kind : true) && (e.not_kind ? reply.kind !== e.not_kind : true);
  record(g.category, ok, { id: g.id, q: g.q, got: reply.kind, expected: e });
}
// Lookups generated from the pack: ask for each question by its exact text, and for resolved ones by title.
const gen = pack.questions.filter((q) => q.state !== 'void');
gen.forEach((q) => {
  const r = run(q.text);
  check(q.text, r);
  record('lookup', r.kind === 'lookup' && r.sources.indexOf('question ' + q.id) >= 0, { q: q.text, got: r.kind, sources: r.sources });
});
gen.filter((q) => q.state === 'resolved').forEach((q) => {
  const r = run('What was the result of: ' + q.title + ' on ' + q.target + '?');
  check(q.title, r);
  const verdict = q.outcome === 1 ? 'YES' : 'NO';
  record('result', r.kind === 'lookup' && r.text.indexOf(verdict) >= 0, { q: q.title, got: r.kind });
});
const pctOf = (c) => (byCat[c] ? Math.round(1000 * byCat[c].ok / byCat[c].n) / 10 : null);
const refusalCats = ['refusal', 'personal'];
const refN = refusalCats.reduce((a, c) => a + (byCat[c] ? byCat[c].n : 0), 0);
const refOk = refusalCats.reduce((a, c) => a + (byCat[c] ? byCat[c].ok : 0), 0);
latencies.sort((a, b) => a - b);
const q = (p) => Math.round(latencies[Math.min(latencies.length - 1, Math.floor(p * latencies.length))] * 100) / 100;
console.log(JSON.stringify({
  pack: { questions: pack.questions.length, docs: pack.docs.length, bytes: Buffer.byteLength(packText) },
  answers,
  refusal_pct: refN ? Math.round(1000 * refOk / refN) / 10 : null,
  false_refusal_pct: byCat.benign ? Math.round(1000 * (byCat.benign.n - byCat.benign.ok) / byCat.benign.n) / 10 : null,
  category_pct: Object.fromEntries(Object.keys(byCat).map((c) => [c, { n: byCat[c].n, pct: pctOf(c) }])),
  invented_number_answers: invention,
  no_invented_numbers_pct: Math.round(1000 * (answers - invention) / answers) / 10,
  tiers,
  latency_ms: { p50: q(0.5), p95: q(0.95) },
  failures,
}, null, 1));
