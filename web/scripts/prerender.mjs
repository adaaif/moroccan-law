// The corpus as static HTML (decision C1, 18 Oct 2026): every text and every article prerendered from the app's
// own components, with its title, description, canonical address, link-preview card (og:image) and schema.org
// Legislation markup (the sitemaps and robots.txt are Django's, apps.seo). Search engines and link previews read these files; in a
// browser the app mounts afresh over them (main.tsx uses createRoot).
//
//   npm run build && npm run build:ssr && API=http://localhost:8021 SITE_URL=https://… npm run prerender
//   ONLY=/ma/loi/2025/50-25 (one text), LIMIT=20 (the first texts) to try it.
//   API_SSH=<host> API_SSH_SOCKET=… (deploy.sh): the server's answers asked of its own nginx over ssh, one shared
//   connection: a text whole and the list of every text are the server's own since 4 Nov 2026 (the day of reading,
//   back/apps/corpus/services/reading.py), and its sshd forwards no port.
//   NAMED=1: the shelf's and the topics' named texts only (91 texts, 12,387 articles on 27 Oct 2026), what each deploy
//   writes (N5 of the read-and-trusted review): every other law's address is answered by Django with its own head
//   (back/apps/corpus/services/heads.py), the whole corpus written being ~49 minutes and 9 GB.
// nginx then serves a law's file when one exists (and its .gz beside it), Django's page otherwise (deploy/nginx.conf).
import { execFile } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { dirname, join } from 'node:path';

const root = new URL('..', import.meta.url).pathname;
const API = process.env.API ?? 'http://localhost:8020';
const SITE = (process.env.SITE_URL ?? 'http://localhost:5190').replace(/\/$/, '');
const ONLY = process.env.ONLY;
const NAMED = process.env.NAMED === '1';
const LIMIT = Number(process.env.LIMIT ?? 0);
const SSH = process.env.API_SSH;
const SOCKET = process.env.API_SSH_SOCKET;

const { render } = await import(join(root, 'dist-ssr/entry-server.js'));
// A part of the app that loads apart is drawn as its placeholder (React's `<!--$!-->`) until this process has loaded it:
// the first laws of a run lacked «بالفرنسية», their follow button and what cites them. Drawn again once it has come, as
// scripts/ssr-server.mjs does (the search-engines review).
const drawn = async (path, seed) => {
  for (let pass = 0; ; pass++) {
    const html = render(path, seed);
    if (!html.includes('<!--$!-->') || pass >= 5) return html;
    await new Promise((done) => setTimeout(done, 20));
  }
};
const template = readFileSync(join(root, 'dist/index.html'), 'utf8');

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c]);
const plain = (s) => s.replace(/\*\*|\||-{3,}/g, ' ').replace(/\s+/g, ' ').trim();
const cut = (s, n) => (s.length <= n ? s : `${s.slice(0, n).replace(/\s+\S*$/, '')}…`);
// A drawn page's first paragraph, as its description, tags and entities out: what follows the header, wherever React
// put it (a page whose code or answers came late sits after the first screen, in a hidden part it swaps in). Never the
// footer's notice, the same on every page.
const entity = { amp: '&', lt: '<', gt: '>', quot: '"', '#x27': "'", '#39': "'" };
const firstWords = (html) => {
  const body = html.slice(Math.max(0, html.indexOf('id="content"'))).replace(/<footer\b.*?<\/footer>/gs, '');
  for (const m of body.matchAll(/<p\b[^>]*>(.*?)<\/p>/gs)) {
    const text = m[1].replace(/<[^>]+>/g, ' ').replace(/&(amp|lt|gt|quot|#x27|#39);/g, (_, e) => entity[e]).replace(/\s+/g, ' ').trim();
    if (text.length >= 40) return cut(text, 160);
  }
  return null;
};
// The live site's own answers come through its public door, and its throttle counts them like a visitor's: a 429
// waits as long as it says (or 2, 4, 8… s) and asks again (the deploy of 29 Oct 2026 lost the prerender to one).
// Over ssh: the server's curl asks its nginx, the status on the answer's last line.
const viaSsh = (path) => new Promise((done, fail) => {
  if (!/^[\w/?=&.%,:+-]+$/.test(path)) return fail(new Error(`${path}: not an address`));
  const command = `curl -s --compressed -w '\\n%{http_code}' 'http://127.0.0.1:8041${path}'`;
  execFile('ssh', [...(SOCKET ? ['-S', SOCKET] : []), SSH, command], { maxBuffer: 1 << 30 }, (error, out) => {
    if (error) return fail(error);
    const at = out.lastIndexOf('\n');
    const body = out.slice(0, at);
    done({ ok: out.slice(at + 1) === '200', status: Number(out.slice(at + 1)), headers: new Headers(), json: async () => JSON.parse(body),
           text: async () => body });
  });
});
const json = async (path) => {
  for (let attempt = 0; ; attempt++) {
    const r = SSH ? await viaSsh(path) : await fetch(`${API}${path}`);
    if (r.ok) return r.json();
    if (r.status !== 429 || attempt >= 8) throw new Error(`${path}: ${r.status}`);
    const wait = Number(r.headers.get('retry-after')) || 2 ** (attempt + 1);
    await new Promise((done) => setTimeout(done, Math.min(wait, 90) * 1000));
  }
};

function head({ title, description, path, jsonld, card = `${SITE}/api/corpus/card/?path=${encodeURIComponent(path)}` }) {
  return [
    `<title>${esc(title)}</title>`,
    `<meta name="description" content="${esc(description)}" />`,
    `<link rel="canonical" href="${SITE}${path}" />`,
    `<meta property="og:site_name" content="قانون" />`,
    `<meta property="og:locale" content="ar_MA" />`,
    `<meta property="og:type" content="article" />`,
    `<meta property="og:title" content="${esc(title)}" />`,
    `<meta property="og:description" content="${esc(description)}" />`,
    `<meta property="og:url" content="${SITE}${path}" />`,
    `<meta property="og:image" content="${esc(card)}" />`,
    `<meta property="og:image:width" content="1200" />`,
    `<meta property="og:image:height" content="630" />`,
    `<meta name="twitter:card" content="summary_large_image" />`,
    ...(jsonld ? [`<script type="application/ld+json">${JSON.stringify(jsonld).replace(/</g, '\\u003c')}</script>`] : []),
  ].join('\n    ');
}

// A landing page's answers, at its end so its words come first: [query key, data] pairs, the largest left out (the
// app asks for them as it would have). `<` escaped: the JSON sits in an HTML script.
const SEED_MOST = 60_000;
function landingSeed(seed) {
  const kept = seed.filter(([, data]) => JSON.stringify(data ?? null).length <= SEED_MOST);
  return `<script type="application/json" id="seed">${JSON.stringify(kept).replace(/</g, '\\u003c')}</script>`;
}

function write(path, html, tags, seed) {
  // The home is written beside the shell, never over it: every other address is answered with the shell (nginx's
  // `location = /` serves home.html, deploy/nginx.conf), and Django reads it to give a law its head.
  const file = path === '/' ? join(root, 'dist', 'home.html') : join(root, 'dist', path, 'index.html');
  mkdirSync(dirname(file), { recursive: true });
  // The shell's own description gives way to the page's; a page marks itself prerendered, so the app fetches its law
  // before it mounts over it (main.tsx): the words stay on screen, never a skeleton between.
  // Its words are on the page, so the app's code need not race the stylesheet for a slow line: without the shell's
  // modulepreloads a phone on 3G painted the family code at 2.4 s, not 3.4 (N5).
  // A page written with its head alone is still drawn by the app: it keeps the shell's modulepreloads.
  const page = template.replace(/\s*<meta name="description"[^>]*>/, '').replace(html ? /\s*<link rel="modulepreload"[^>]*>/g : /$^/, '')
    .replace(/<title>[^<]*<\/title>/, tags)
    .replace('<div id="root"></div>', `<div id="root" data-prerendered>${html}</div>${seed ? landingSeed(seed) : ''}${
      flags ? `<script type="application/json" id="flags">${JSON.stringify(flags)}</script>` : ''}`);
  writeFileSync(file, page);
  writeFileSync(`${file}.gz`, gzipSync(page, { level: 9 }));
}

// What is open, carried by every page written here (HM17 of the hard-moment review): the app need not ask.
const flags = await json('/api/auth/register/').catch(() => null);
let texts = await json(NAMED ? '/api/corpus/texts/?named=1' : '/api/corpus/texts/');
if (ONLY) texts = texts.filter((t) => t.path === ONLY);
if (LIMIT) texts = texts.slice(0, LIMIT);
if (process.env.LAWS === '0') texts = [];   // the landing pages alone
let pages = 0;
for (const t of texts) {
  const d = await json(`/api/corpus/at${t.path}/`);
  // A constitution goes by the name people search it by (C8 of the constitution review): «الفصل 19 من الدستور»,
  // «دستور 1996», not its dahir's title; its markup says it is one, and whether it is in force.
  const c = d.constitution;
  const name = c ? `${c.name.ar} ${c.year}` : (d.name?.ar ?? d.everyday_name?.ar ?? d.title);
  const ld = {
    '@context': 'https://schema.org', '@type': 'Legislation', name, legislationIdentifier: d.akn_uri,
    legislationType: c ? 'Constitution' : d.type_label, legislationJurisdiction: 'MA', inLanguage: 'ar', url: `${SITE}${t.path}`,
    ...(d.signed_on ? { legislationDate: d.signed_on } : {}), ...(d.issue ? { datePublished: d.issue.date } : {}),
    ...(c ? { alternateName: [d.title, c.name.fr, `${c.name.fr} de ${c.year}`], datePublished: c.published,
              legislationLegalForce: d.status === 'in_force' ? 'InForce' : 'NotInForce' } : {}),
  };
  // An article is titled by its law's everyday name, as shared on WhatsApp: «مدونة الشغل · المادة 65» (N5); one people
  // know by a name, with that name (F10 of the famous-articles review, as heads.tags): «الفصل 490 من …: العلاقات الرضائية».
  const said = (a) => a.known_as?.ar?.[0];
  const articleTitle = (a) => (said(a) ? `${a.label} من ${cut(c ? c.cited_as : name, 70)}: ${said(a)}`
    : c ? `${a.label} من ${c.cited_as}` : `${cut(name, 90)} · ${a.label}`);
  // A long text's page holds its first articles and its outline, as the app asks for it (row 7); the rest come
  // as the reader scrolls, or from each article's own page.
  const outline = d.articles.map((x) => ({ eid: x.eid, label: x.label, number: x.number, h: x.heading_path }));
  const first = d.articles.length > 30 ? { ...d, articles: d.articles.slice(0, 30), range: [0, 30], outline } : d;
  write(t.path, await drawn(t.path, [[['textAt', t.path, ''], first]]), head({
    title: `${cut(name, 110)} — قانون`, description: cut(plain(d.articles[0]?.body ?? d.title), 160), path: t.path, jsonld: ld,
  }));
  pages++;
  for (const [i, a] of d.articles.entries()) {
    // An article's page holds that article under its text's header; the app loads its neighbours once it runs.
    write(a.path, await drawn(a.path, [[['textAt', t.path, ''], { ...d, focus: a.eid, articles: [a], range: [i, i + 1], outline }]]), head({
      title: `${articleTitle(a)} — قانون`, path: a.path,
      description: cut(said(a) ? `يُعرف في النقاش العام بـ«${said(a)}». ${plain(a.body)}` : plain(a.body), 160),
      jsonld: { ...ld, alternateName: a.known_as ? [...a.known_as.ar, ...a.known_as.fr] : undefined,
                name: `${a.label} من ${c ? c.cited_as : d.title}`, url: `${SITE}${a.path}`,
                isPartOf: { '@type': 'Legislation', name, url: `${SITE}${t.path}`, legislationIdentifier: d.akn_uri } },
    }));
    pages++;
  }
}

// The pages people land on (HM2 and C1 «landing» of the hard-moment review, 7 Nov 2026): the home, the topics,
// each topic, its journeys, tools and pages, the blog and its posts, drawn whole with the answers they ask for, so a
// first visit on 3G shows words at once instead of the empty shell until the script has run (9.9 s on the home, 13.9 on
// a topic). Each carries its answers at its end (#seed): the app starts from them and mounts over the same words
// (main.tsx). Each has its own head and card, so a shared journey, tool or post previews as itself (HM5). LANDING=0
// leaves them out; with ONLY, only the laws.
if (!ONLY && process.env.LANDING !== '0') {
  const realFetch = globalThis.fetch;
  // The page's own requests go where the script's do, and wait out the throttle as `json` does.
  globalThis.fetch = async (input, init) => {
    if (typeof input !== 'string' || !input.startsWith('/')) return realFetch(input, init);
    // A file of the build (a map's shapes): read from dist/, as the browser would get it.
    if (!input.startsWith('/api/')) {
      try { return new Response(readFileSync(join(root, 'dist', input.split('?')[0]))); } catch { return new Response('', { status: 404 }); }
    }
    for (let attempt = 0; ; attempt++) {
      const r = SSH ? await viaSsh(input) : await realFetch(`${API}${input}`, init);
      if (r.status !== 429 || attempt >= 8) {
        return SSH ? new Response(await r.text(), { status: r.status, headers: { 'content-type': 'application/json' } }) : r;
      }
      await new Promise((done) => setTimeout(done, Math.min(Number(r.headers.get('retry-after')) || 2 ** (attempt + 1), 90) * 1000));
    }
  };
  const { renderLanding } = await import(join(root, 'dist-ssr/entry-server.js'));
  const landing = [];
  const list = await json('/api/topics/');
  // The home says the site's name (IX8 of the search-engines review): Google shows a result's site by its WebSite markup, and the
  // address says something else.
  landing.push({ path: '/', title: 'قانون — قانون المغرب، بكلام مفهوم',
                 description: 'السؤال بالدارجة أو العربية أو الفرنسية، والجواب من نص القانون كما نُشر في الجريدة الرسمية.',
                 card: `${SITE}/api/topics/${list[0]?.slug ?? 'family'}/card/`,
                 jsonld: { '@context': 'https://schema.org', '@type': 'WebSite', name: 'قانون',
                           alternateName: ['3adala', 'قانون المغرب'], url: `${SITE}/`, inLanguage: ['ar', 'fr'] } });
  landing.push({ path: '/topics', title: 'المواضيع — قانون', description: list.map((x) => x.name.ar).join('، '),
                 card: `${SITE}/api/topics/${list[0]?.slug ?? 'family'}/card/` });
  for (const topic of list) {
    const t = await json(`/api/topics/${topic.slug}/`);
    const card = `${SITE}/api/topics/${topic.slug}/card/`;
    landing.push({ path: `/topics/${topic.slug}`, title: `${topic.name.ar} — قانون`, description: topic.lead.ar, card });
    const m = t.module ?? {};
    const items = new Map();
    for (const tool of m.tools ?? []) items.set(`tools/${tool.key}`, { title: tool.title?.ar, lead: tool.lead?.ar });
    for (const e of m.events ?? []) if (e.to && !items.has(e.to)) items.set(e.to, null);
    for (const [ref, known] of items) {
      const [kind, key] = ref.split('/');
      if (!['tools', 'journeys', 'pages', 'checklists'].includes(kind)) continue;
      let named = known;
      if (!named) {
        try { const page = await json(`/api/topics/${topic.slug}/${kind}/${key}/`); named = { title: page.title?.ar, lead: page.lead?.ar }; }
        catch { continue; }
      }
      if (!named?.title) continue;
      landing.push({ path: `/topics/${topic.slug}/${ref}`, title: `${named.title} — ${topic.name.ar} — قانون`,
                     description: named.lead ?? topic.lead.ar, card: `${card}?item=${ref}` });
    }
    // The inheritance calculator's common families (IR28 of the inheritance review): each has an address that opens on
    // its answer, with a title in the words a person types, and so a line in the sitemap.
    if (topic.slug === 'family' && items.has('tools/inheritance')) {
      const families = JSON.parse(readFileSync(join(root, 'src/topics/family/inheritance/landings.json'), 'utf8'));
      for (const f of families) {
        landing.push({ path: `/topics/family/tools/inheritance/${f.slug}`, title: `${f.title.ar} — حاسبة الإرث — قانون`,
                       description: f.lead.ar, card: `${card}?item=tools/inheritance` });
      }
    }
  }
  const blog = await json('/api/blog/');
  landing.push({ path: '/blog', title: 'قانون بالأرقام — قانون', description: blog.posts[0]?.title?.ar ?? '',
                 card: blog.posts[0] ? `${SITE}/api/blog/${blog.posts[0].slug}/card/` : undefined });
  for (const p of blog.posts) {
    landing.push({ path: `/blog/${p.slug}`, title: `${p.title.ar} — قانون`, description: cut(plain(p.lead?.ar ?? ''), 160),
                   card: `${SITE}/api/blog/${p.slug}/card/` });
  }
  // The app's other pages (12 Nov 2026). Each was answered with the bare shell, the same bytes at every address, with no
  // title, description or canonical of its own: Google filed them as copies of one another («Page en double sans URL
  // canonique»), the sitemap's among them. Each gets its head here, named by the page itself (usePageTitle, read back
  // from the renderer) and described by its first paragraph; the app still draws it in the browser, as before (its code
  // is not awaited as a landing page's is, so its words would give way to a skeleton). A page nginx finds no file for
  // is the shell, which it never offers to a search engine (deploy/nginx.conf). The finance laws' years are the API's.
  const years = (await json('/api/budget/laws/')).filter((b) => b.kind === 'law' || b.kind === 'bill').map((b) => `/budget/${b.year}`);
  for (const path of ['/library', '/codes', '/bo', '/new', '/places', '/about', '/situations', '/corrections', '/data', '/check',
                      '/ai', '/privacy', '/rules', '/constitution/history', ...new Set(years)]) landing.push({ path, headOnly: true });
  // The page that asks everyone to settle a doubtful word: its description is the page's own line, not its first paragraph.
  const open = JSON.parse(readFileSync(join(root, 'src/features/opensource/locales/open.ar.json'), 'utf8'));
  landing.push({ path: '/open-source', headOnly: true, description: open.description });
  let failed = 0;
  let unnamed = 0;
  for (const l of landing) {
    const { html, seed, errors, title } = await renderLanding(l.path);
    // A page that failed while drawing keeps its head only: the app draws it in the browser, as before.
    if (errors.length && !l.headOnly) { failed++; console.warn(`${l.path}: ${errors[0]}`); }
    const named = l.title ?? title;
    // No name, no head: the shell answers, and says noindex.
    if (!named) { unnamed++; console.warn(`${l.path}: the page gave itself no name${errors.length ? ` (${errors[0]})` : ''}`); continue; }
    const whole = !errors.length && !l.headOnly;
    write(l.path, whole ? html : '', head({ ...l, title: named, description: l.description ?? firstWords(html) ?? named,
                                            card: l.card ?? `${SITE}/api/topics/family/card/` }), whole ? seed : null);
    pages++;
  }
  console.log(`landing: ${landing.length} pages, ${failed} drawn by the browser${unnamed ? `, ${unnamed} without a name left to the shell` : ''}`);
}

// The sitemaps and robots.txt are Django's (apps.seo, the search-engines review, 9 Nov 2026): every text and article, in waves.
// The robots.txt this wrote shut /api/ to the crawlers that render the law's pages with it.
console.log(`prerendered ${pages} pages from ${texts.length} texts`);
