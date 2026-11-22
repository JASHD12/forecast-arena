// Ask the Arena: a small chat over the site's own published data (T312).
// One self-hosted file, no dependencies, no storage, no network beyond the site's own
// chat/pack.json. It never makes a new prediction: it looks up locked forecasts, searches the
// project documents (BM25) and refuses what is out of scope. Source of
// src/arena/site/static/chat.js: edit this file and run `make site-ts`.
// The pure functions are exported for the Node tests (module.exports) and used by the page.
declare const module: { exports: unknown } | undefined;

(function (): void {
  'use strict';

  interface QRow {
    id: string; domain: string; template: string; entity: string; title: string; text: string;
    target: string; batch: string; lock: string; threshold: number | null; unit: string;
    state: 'open' | 'resolved' | 'void'; outcome: 0 | 1 | null;
    f: Record<string, [number, number | null]>;
  }
  interface BoardRowData { f: string; n: number; brier: number; verdict: string }
  interface BoardData {
    kind: string; domain: string; questions: number; days: number; label: string | null;
    rows: BoardRowData[];
  }
  interface DocChunk { id: string; path: string; heading: string; text: string }
  interface Pack {
    version: number; built: string; status: string; disclaimer: string;
    forecasters: Record<string, string>; domains: Record<string, string>;
    questions: QRow[]; boards: BoardData[]; docs: DocChunk[];
  }
  interface Reply {
    tier: number;            // 0 lookup, 1 documents, -1 declined or refused
    kind: string;            // lookup | board | docs | status | refusal | decline
    text: string;
    why: string;
    head?: string[];
    rows?: string[][];
    sources: string[];
  }

  const MIN_COVERAGE = 0.5;
  const DECISIVE = 0.15;
  const MIN_N = 20;
  const STOP = new Set((
    'a an and are as at be by do does for from how in is it of on or that the this to was what ' +
    'when where which who why with project will would could can you me my tell give show about please next any some'
  ).split(' '));

  function tokens(text: string): string[] {
    return text.toLowerCase().match(/[a-z0-9]+/g) || [];
  }
  function terms(text: string): string[] {
    return tokens(text).filter((t) => !STOP.has(t) && t.length > 1);
  }

  // Okapi BM25 with the same constants and formula as arena.agent.retrieval.BM25Index.
  class BM25 {
    private tf: Array<Map<string, number>> = [];
    private len: number[] = [];
    private avg = 0;
    private idf = new Map<string, number>();
    constructor(docs: string[], private k1 = 1.5, private b = 0.75) {
      const df = new Map<string, number>();
      for (const d of docs) {
        const m = new Map<string, number>();
        for (const t of tokens(d)) m.set(t, (m.get(t) || 0) + 1);
        this.tf.push(m);
        let n = 0;
        m.forEach((c) => { n += c; });
        this.len.push(n);
        m.forEach((_c, t) => { df.set(t, (df.get(t) || 0) + 1); });
      }
      this.avg = docs.length ? this.len.reduce((a, c) => a + c, 0) / docs.length : 0;
      df.forEach((d, t) => {
        this.idf.set(t, Math.log(1 + (docs.length - d + 0.5) / (d + 0.5)));
      });
    }
    scores(query: string): number[] {
      const out = this.tf.map(() => 0);
      const seen: Record<string, boolean> = {};
      for (const t of tokens(query)) {
        if (seen[t]) continue;
        seen[t] = true;
        const idf = this.idf.get(t);
        if (idf === undefined) continue;
        for (let i = 0; i < this.tf.length; i++) {
          const f = this.tf[i].get(t) || 0;
          const norm = this.k1 * (1 - this.b + this.b * this.len[i] / Math.max(this.avg, 1e-9));
          out[i] += idf * f * (this.k1 + 1) / (f + norm);
        }
      }
      return out;
    }
  }

  function order(scores: number[], k: number): number[] {
    return scores.map((s, i) => [s, i] as [number, number])
      .filter((p) => p[0] > 0).sort((a, b) => b[0] - a[0] || a[1] - b[1]).slice(0, k)
      .map((p) => p[1]);
  }

  // ---- Guard -------------------------------------------------------------------------------
  const STOCK = /\b(stocks?|shares?|share price|equity|equities|aktie[n]?|etf[s]?|nasdaq|nyse|dax|dow jones|s&p|ftse|index fund|mutual fund|hedge fund|ticker)\b/i;
  const COMPANY = /\b(google|alphabet|apple|microsoft|amazon|tesla|nvidia|meta platforms|netflix)\b/i;
  const PRICEY = /\b(price|worth|value|stock|share|forecast|predict|rise|fall|go up|go down|double|crash)\b/i;
  const ADVICE = /\b(should i (?:buy|sell|invest|trade|hold)|shall i (?:buy|sell)|buy|sell|invest|investing|investment|trade|trading|portfolio|financial advice|stock tip|worth buying|go long|go short|kaufen|verkaufen|anlegen)\b/i;
  const PERSONAL = /\b(my (email|phone|address|password|iban|salary)|home address|social security)\b/i;
  const PERSON_NAME = /\b[Ww]ho is [A-Z][a-z]+ [A-Z][a-z]+\b/;

  function norm(t: string): string {
    return tokens(t).join(' ');
  }
  function isPublished(q: string, pack: Pack | null): boolean {
    if (!pack) return false;
    const n = norm(q);
    return pack.questions.some((x) => n.indexOf(norm(x.text)) >= 0);
  }

  function guard(q: string, pack: Pack | null = null): { blocked: boolean; kind: string; text: string } {
    if (isPublished(q, pack)) return { blocked: false, kind: '', text: '' };
    if (STOCK.test(q) || ADVICE.test(q) || (COMPANY.test(q) && PRICEY.test(q))) {
      return {
        blocked: true, kind: 'finance',
        text: 'I cannot help with stocks, funds, trading or what to buy or sell. This is a research ' +
          'project, not advice of any kind, and it forecasts only the topics it publishes: ' +
          'electricity, weather, Wikipedia attention, exchange rates and crypto thresholds.',
      };
    }
    if (PERSONAL.test(q) || PERSON_NAME.test(q)) {
      return {
        blocked: true, kind: 'personal',
        text: 'I do not answer questions about private persons or personal data, and I store nothing you type.',
      };
    }
    return { blocked: false, kind: '', text: '' };
  }

  // ---- Slots -------------------------------------------------------------------------------
  const DOMAIN_WORDS: Record<string, string[]> = {
    power: ['electricity', 'power', 'strom', 'mwh', 'energy', 'evening', 'day-ahead'],
    weather: ['weather', 'temperature', 'rain', 'wind', 'sunshine', 'wetter', 'degrees', 'snow'],
    attention: ['wikipedia', 'article', 'views', 'attention', 'pageviews'],
    markets: ['exchange', 'currency', 'currencies', 'eur', 'usd', 'dollar', 'euro', 'gbp', 'yen', 'chf', 'rate'],
    crypto: ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'coin', 'solana'],
  };
  const MONTHS = ['jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'oct', 'nov', 'dec'];
  const WEEKDAYS = ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday'];

  function iso(d: Date): string {
    return d.toISOString().slice(0, 10);
  }
  function addDays(day: string, n: number): string {
    const d = new Date(day + 'T00:00:00Z');
    d.setUTCDate(d.getUTCDate() + n);
    return iso(d);
  }

  function parseDate(q: string, today: string): string | null {
    const s = q.toLowerCase();
    const m = s.match(/\b(20\d\d)-(\d\d)-(\d\d)\b/);
    if (m) return m[0];
    if (/\btomorrow\b|\bmorgen\b/.test(s)) return addDays(today, 1);
    if (/\byesterday\b|\bgestern\b/.test(s)) return addDays(today, -1);
    if (/\btoday\b|\bheute\b/.test(s)) return today;
    const year = today.slice(0, 4);
    const dm = s.match(/\b(\d{1,2})(?:st|nd|rd|th)?[ .\-]*(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b/);
    const md = s.match(/\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[ .\-]*(\d{1,2})(?:st|nd|rd|th)?\b/);
    const hit = dm ? [dm[2], dm[1]] : md ? [md[1], md[2]] : null;
    if (hit) {
      const mm = String(MONTHS.indexOf(hit[0]) + 1).padStart(2, '0');
      return year + '-' + mm + '-' + hit[1].padStart(2, '0');
    }
    for (let i = 0; i < 7; i++) {
      if (s.indexOf(WEEKDAYS[i]) >= 0) {
        const t = new Date(today + 'T00:00:00Z').getUTCDay();
        return addDays(today, ((i - t + 7) % 7) || 7);
      }
    }
    return null;
  }

  function parseDomain(q: string): string | null {
    const toks = tokens(q);
    let best: string | null = null;
    let bestN = 0;
    for (const d of Object.keys(DOMAIN_WORDS)) {
      let n = 0;
      for (const w of DOMAIN_WORDS[d]) if (toks.indexOf(w) >= 0) n++;
      if (n > bestN) { best = d; bestN = n; }
    }
    return best;
  }

  function parseForecaster(q: string, names: Record<string, string>): string | null {
    const s = q.toLowerCase();
    const alias: Array<[string, string]> = [
      ['base rate', 'base_rate'], ['persistence', 'persistence'], ['same as last time', 'persistence'],
      ['langgraph', 'agent_graph'], ['agent', 'agent'], ['fine-tuned', 'llm_local_ft'],
      ['fine tuned', 'llm_local_ft'], ['open model', 'llm_local'], ['ml model', 'ml'],
      ['gradient', 'ml'], ['ensemble', 'ensemble'],
    ];
    for (const [w, id] of alias) if (s.indexOf(w) >= 0 && names[id] !== undefined) return id;
    return null;
  }

  function numbersIn(q: string): number[] {
    const flat = q.replace(/\b\d{4}-\d\d-\d\d\b/g, ' ').replace(/\d{1,2}:\d\d/g, ' ')
      .replace(/(\d),(\d{3})/g, '$1$2');
    return (flat.match(/\d+(?:\.\d+)?/g) || []).map(Number);
  }

  // ---- Choice of the leading forecaster (a hypothesis from the routing study) ----------------
  function pct(p: number): string {
    return Math.round(p * 100) + '%';
  }

  function choose(q: QRow, pack: Pack): { lead: string | null; why: string } {
    const ids = Object.keys(q.f);
    if (!ids.length) return { lead: null, why: 'No forecaster published a locked forecast for this question.' };
    const ml = q.f['ml'];
    if (ml && Math.abs(ml[0] - 0.5) >= DECISIVE) {
      return { lead: 'ml', why: 'Easy case: the ML forecast is decisive (' + pct(ml[0]) + ', at least 15 points from 50%), so it leads.' };
    }
    const board = pack.boards.find((b) => b.kind === 'all' && b.domain === q.domain);
    if (board) {
      const rows = board.rows.filter((r) => r.n >= MIN_N && q.f[r.f] !== undefined)
        .sort((a, b) => a.brier - b.brier);
      if (rows.length) {
        const r = rows[0];
        return {
          lead: r.f,
          why: 'Hard case: no decisive ML forecast, so the forecaster with the best record on ' +
            (pack.domains[q.domain] || q.domain) + ' leads (' + (pack.forecasters[r.f] || r.f) +
            ', Brier ' + r.brier.toFixed(4) + ' over ' + r.n + ' questions).',
        };
      }
    }
    const base = q.f['base_rate'] !== undefined ? 'base_rate' : ids[0];
    return { lead: base, why: 'Hard case with too little track record on this topic: the base rate leads.' };
  }

  // ---- Tier 0: lookup ----------------------------------------------------------------------
  interface Match { q: QRow; score: number; exact: boolean }

  function matchQuestions(text: string, pack: Pack, today: string): Match[] {
    const qs = pack.questions;
    const bm = new BM25(qs.map((q) => q.title + ' ' + q.text + ' ' + q.entity + ' ' + q.domain));
    const sc = bm.scores(terms(text).join(' '));
    const day = parseDate(text, today);
    const dom = parseDomain(text);
    const isoAll: string[] = text.match(/\b20\d\d-\d\d-\d\d\b/g) || [];
    const nums = numbersIn(text).filter((n) => !(n >= 1900 && n <= 2100) && !(n >= 1 && n <= 31 && day !== null));
    const qnums = numbersIn(text).filter((n) => !(n >= 1 && n <= 31 && day !== null));
    const out: Match[] = [];
    qs.forEach((q, i) => {
      let s = sc[i];
      let slots = 0;
      if (day && (q.target === day || isoAll.indexOf(q.target) >= 0)) { s += 2; slots++; }
      if (dom && q.domain === dom) { s += 1; slots++; }
      if (q.threshold !== null && nums.some((n) => Math.abs(n - (q.threshold as number)) < 1e-9)) { s += 2; slots++; }
      const want = terms(text);
      const have = new Set(terms(q.title + ' ' + q.text + ' ' + q.entity));
      const cov = want.length ? want.filter((t) => have.has(t)).length / want.length : 0;
      const own = numbersIn(q.title + ' ' + q.text);
      if (q.threshold !== null) own.push(q.threshold);
      const numberClash = qnums.some((n) => !own.some((o) => Math.abs(o - n) < 1e-9));
      const exact = !numberClash && cov >= 0.34 && (day !== null ? (q.target === day || isoAll.indexOf(q.target) >= 0) : true) && (dom !== null ? q.domain === dom : true) &&
        (slots >= 2 || cov >= 0.6) && s > 0;
      if (s > 0) out.push({ q, score: s, exact });
    });
    return out.sort((a, b) => b.score - a.score || (a.q.id < b.q.id ? -1 : 1));
  }

  function forecastRows(q: QRow, lead: string | null, pack: Pack): string[][] {
    const ids = Object.keys(q.f).sort((a, b) =>
      (a === lead ? -1 : b === lead ? 1 : (pack.forecasters[a] || a).localeCompare(pack.forecasters[b] || b)));
    return ids.map((id) => {
      const [p, br] = q.f[id];
      return [(pack.forecasters[id] || id) + (id === lead ? ' (leads)' : ''), pct(p), br === null ? 'open' : br.toFixed(4)];
    });
  }

  function lookupReply(m: Match[], pack: Pack, wantResult: boolean): Reply {
    const q = m[0].q;
    const ch = choose(q, pack);
    const state = q.state === 'resolved'
      ? 'It resolved ' + (q.outcome === 1 ? 'YES' : 'NO') + '.'
      : q.state === 'void' ? 'It was voided and does not count.' : 'It is still open (locks ' + q.lock + ').';
    const head = wantResult && q.state !== 'resolved'
      ? 'There is no result yet. ' + state : state;
    return {
      tier: 0, kind: 'lookup',
      text: q.text + ' ' + head + (ch.lead ? ' ' + ch.why : ''),
      why: 'Tier 0, lookup: a published question matched your words and date.',
      head: ['Forecaster', 'Locked forecast of YES', 'Brier'],
      rows: forecastRows(q, ch.lead, pack),
      sources: ['question ' + q.id],
    };
  }

  function nearestReply(m: Match[], pack: Pack): Reply {
    const near = m.slice(0, 2).map((x) => x.q);
    const base = 'There is no locked forecast for that, and I do not make new ones.';
    if (!near.length) {
      return { tier: -1, kind: 'decline', text: base + ' No published question is close to it.', why: 'Declined: nothing matched.', sources: [] };
    }
    const rows: string[][] = [];
    for (const q of near) {
      const ch = choose(q, pack);
      const lead = ch.lead && q.f[ch.lead] ? pack.forecasters[ch.lead] + ' ' + pct(q.f[ch.lead][0]) : 'no forecasts';
      rows.push([q.text, q.target, lead]);
    }
    return {
      tier: -1, kind: 'decline',
      text: base + ' The nearest published questions are below.',
      why: 'Declined: no exact match; showing the nearest published questions.',
      head: ['Question', 'Target day', 'Leading forecast'], rows,
      sources: near.map((q) => 'question ' + q.id),
    };
  }

  // ---- Boards ------------------------------------------------------------------------------
  function boardReply(text: string, pack: Pack): Reply | null {
    const dom = parseDomain(text) || 'overall';
    const b = pack.boards.find((x) => x.kind === 'common' && x.domain === dom && x.rows.length) ||
      pack.boards.find((x) => x.kind === 'all' && x.domain === dom && x.rows.length);
    if (!b) return null;
    const rows = b.rows.slice().sort((x, y) => x.brier - y.brier)
      .map((r) => [pack.forecasters[r.f] || r.f, r.brier.toFixed(4), String(r.n), r.verdict]);
    return {
      tier: 0, kind: 'board',
      text: 'Brier score per forecaster' + (dom === 'overall' ? '' : ' on ' + (pack.domains[dom] || dom)) +
        ' (lower is better; ' + b.questions + ' questions over ' + b.days + ' days). ' + (b.label ? b.label + '. ' : '') +
        pack.status,
      why: 'Tier 0, lookup: the leaderboard of this site.',
      head: ['Forecaster', 'Brier', 'Questions', 'Against the base rate'], rows,
      sources: ['leaderboard.html'],
    };
  }

  // ---- Tier 1: documents -------------------------------------------------------------------
  function sentences(text: string): string[] {
    const flat = text.replace(/[#>*`|]/g, ' ').replace(/\s+/g, ' ');
    return flat.split(/(?<=[.!?])\s+/).map((s) => s.trim()).filter((s) => s.length > 20);
  }

  function docsReply(text: string, pack: Pack): Reply {
    const none: Reply = {
      tier: -1, kind: 'decline', text: 'That is not in the published documents, and I do not guess.',
      why: 'Declined: no document matched your question well enough.', sources: [],
    };
    if (!pack.docs.length) return none;
    const bm = new BM25(pack.docs.map((d) => d.heading + ' ' + d.text));
    const want = terms(text);
    const idx = order(bm.scores(want.join(' ')), 3);
    if (!idx.length || !want.length) return none;
    const cover = (d: DocChunk): number => {
      const have = new Set(terms(d.heading + ' ' + d.text));
      return want.filter((t) => have.has(t)).length / want.length;
    };
    if (Math.max(...idx.map((i) => cover(pack.docs[i]))) < MIN_COVERAGE) return none;
    const scored: Array<[number, string, string]> = [];
    for (const i of idx) {
      const d = pack.docs[i];
      for (const s of sentences(d.text)) {
        const ov = terms(s).filter((t) => want.indexOf(t) >= 0).length;
        if (ov) scored.push([ov, d.id, s]);
      }
    }
    scored.sort((a, b) => b[0] - a[0]);
    const top = scored.slice(0, 3);
    if (!top.length) return none;
    const ids: string[] = [];
    top.forEach((t) => { if (ids.indexOf(t[1]) < 0) ids.push(t[1]); });
    return {
      tier: 1, kind: 'docs',
      text: top.map((t) => t[2] + ' [' + t[1] + ']').join(' '),
      why: 'Tier 1, documents: no published question matched, so these are the best-matching sentences of the project documents (BM25).',
      sources: ids,
    };
  }

  // ---- Orchestrator ------------------------------------------------------------------------
  function answer(text: string, pack: Pack): Reply {
    const q = text.trim();
    const g = guard(q, pack);
    if (g.blocked) {
      return { tier: -1, kind: 'refusal', text: g.text, why: 'Refused by the guard (' + g.kind + ').', sources: [] };
    }
    if (!q) return { tier: -1, kind: 'decline', text: 'Ask a question about the published forecasts or the methods.', why: 'Empty question.', sources: [] };
    const s = q.toLowerCase();
    const today = pack.built;
    if (/\b(official|rehearsal|status|record start)\b/.test(s) && !/\bforecast\b/.test(s)) {
      return { tier: 0, kind: 'status', text: pack.status, why: 'Tier 0, lookup: the status line of this site.', sources: ['status.html'] };
    }
    const boardAsk = /\b(leaderboard|winner|best forecaster|top forecaster|most accurate|ranking|ranked)\b/.test(s) ||
      /\bwho(?: is|'s)? (?:winning|best|ahead|leading)\b/.test(s) ||
      /\bwhich forecaster is (?:best|most accurate|leading)\b/.test(s) ||
      /\bshow\b.*\b(?:brier|scores?)\b/.test(s);
    if (boardAsk) {
      const b = boardReply(q, pack);
      if (b) return b;
    }
    const wantResult = /\b(result|resolved|outcome|turned out|happened|actual|was it|did it)\b/.test(s);
    const m = matchQuestions(q, pack, today);
    const fc = parseForecaster(q, pack.forecasters);
    const methodish = /\b(how|why|explain|method|what is|what are|leak|ledger|lock|calibrat|score|scoring)\b/.test(s);
    const strictMethod = /\b(how|why|explain|method|leak|ledger|calibrat|scoring|computed|defined)\b/.test(s);
    if (m.length && m[0].exact && !(methodish && fc && !parseDate(q, today))) {
      return lookupReply(m, pack, wantResult);
    }
    const forecastish = /\b(forecast|predict|prediction|probability|chance|likely|will|expect|price)\b/.test(s);
    if ((forecastish || wantResult) && !strictMethod && (parseDate(q, today) || parseDomain(q))) return nearestReply(m, pack);
    if (methodish || fc) {
      const d = docsReply(q, pack);
      if (d.tier === 1) return d;
    }
    if (m.length && m[0].exact) return lookupReply(m, pack, wantResult);
    const d = docsReply(q, pack);
    if (d.tier === 1) return d;
    return nearestReply(m, pack);
  }

  const api = { tokens, terms, BM25, guard, parseDate, parseDomain, choose, answer, matchQuestions };

  // ---- Page --------------------------------------------------------------------------------
  function el<K extends keyof HTMLElementTagNameMap>(tag: K, cls?: string, text?: string): HTMLElementTagNameMap[K] {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  function render(log: HTMLElement, reply: Reply): void {
    const box = el('div', 'ask-msg bot');
    box.appendChild(el('p', undefined, reply.text));
    if (reply.head && reply.rows) {
      const wrap = el('div', 'table-scroll');
      wrap.tabIndex = 0;
      wrap.setAttribute('role', 'region');
      wrap.setAttribute('aria-label', 'Answer table');
      const t = el('table');
      const tr = el('tr');
      reply.head.forEach((h) => { const th = el('th', undefined, h); th.scope = 'col'; tr.appendChild(th); });
      t.appendChild(el('thead')).appendChild(tr);
      const tb = el('tbody');
      reply.rows.forEach((r) => {
        const row = el('tr');
        r.forEach((c, i) => { row.appendChild(i === 0 ? Object.assign(el('th', undefined, c), { scope: 'row' }) : el('td', undefined, c)); });
        tb.appendChild(row);
      });
      t.appendChild(tb);
      wrap.appendChild(t);
      box.appendChild(wrap);
    }
    const tier = reply.tier === 0 ? 'Tier 0 (lookup)' : reply.tier === 1 ? 'Tier 1 (documents)' : 'No answer';
    const meta = el('p', 'ask-meta', tier + '. ' + reply.why + (reply.sources.length ? ' Sources: ' + reply.sources.join(', ') + '.' : ''));
    box.appendChild(meta);
    log.appendChild(box);
    log.scrollTop = log.scrollHeight;
  }

  function init(pack: Pack): void {
    const log = document.getElementById('ask-log');
    const form = document.getElementById('ask-form');
    const input = document.getElementById('ask-input') as HTMLInputElement | null;
    const ex = document.getElementById('ask-examples');
    if (!log || !form || !input) return;
    const ask = (text: string): void => {
      const u = el('div', 'ask-msg user', text);
      log.appendChild(u);
      render(log, answer(text, pack));
    };
    form.addEventListener('submit', (e: Event) => {
      e.preventDefault();
      const v = input.value.trim();
      if (v) { ask(v); input.value = ''; }
    });
    const first = pack.questions.filter((q) => q.state === 'open')[0];
    const examples = ['Who is winning the leaderboard?', 'What is the official status?', 'How is the Brier score computed?'];
    if (first) examples.unshift('What was forecast for: ' + first.title + '?');
    if (ex) {
      examples.forEach((t) => {
        const b = el('button', undefined, t);
        b.type = 'button';
        b.addEventListener('click', () => ask(t));
        ex.appendChild(b);
      });
    }
    render(log, {
      tier: -1, kind: 'decline', text: pack.disclaimer, why: 'Ready.', sources: [],
    });
  }

  if (typeof module !== 'undefined' && module && typeof document === 'undefined') {
    module.exports = api;
    return;
  }
  if (typeof document === 'undefined') return;
  const start = (): void => {
    fetch('chat/pack.json').then((r) => r.json()).then((p: Pack) => { init(p); }).catch(() => {
      const log = document.getElementById('ask-log');
      if (log) log.textContent = 'The chat data could not be loaded. The other pages of this site have the same information.';
    });
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start);
  else start();
})();
