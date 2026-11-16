// The accessibility checker on the pages the phone-test review tested (UX15, 29 Oct 2026), at 360 px since the readers
// review (9 Nov 2026): axe-core's WCAG 2 A and
// AA rules on a phone, in Arabic; a serious or critical finding fails, so a new page cannot bring one back. Needs both dev
// servers: BASE_URL (default http://localhost:5190). axe comes pinned from cdnjs, as in the test that found them.
import { chromium } from 'playwright';
const CHANNEL = process.env.CHANNEL;

const base = process.env.BASE_URL ?? 'http://localhost:5190';
const AXE = 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js';
const PAGES = ['/', '/search?q=' + encodeURIComponent('كراء'), '/topics', '/topics/family', '/topics/road', '/topics/work',
  '/topics/tax', '/topics/health', '/ma/loi/70-03', '/ma/loi/65-00/art_129', '/ma/loi/58-25/art_200', '/codes', '/library',
  '/bo', '/budget/2026', '/budget/2027', '/words', '/new', '/about', '/situations', '/check', '/data', '/saved',
  '/ma/dahir/1-84-177', '/nope-nothing-here',
  // The conversation, drawn again on 30 Oct 2026: the hub, a topic's room, the questions waiting.
  '/talk', '/talk/housing', '/questions',
  // What the site keeps and until when, drawn as a ruler (31 Oct 2026), and the rules beside it.
  '/privacy', '/rules',
  // «قانون بالأرقام», the blog, and its first post: seventy years of the Bulletin as one picture (31 Oct 2026).
  '/blog', '/blog/seventy-years', '/blog/six-constitutions', '/blog/words-in-the-law', '/blog/who-writes', '/blog/december', '/blog/minimum-wage', '/blog/holidays', '/blog/signed-to-published', '/blog/errata', '/blog/agreements', '/blog/countries', '/blog/cities',
  '/places', '/places/france', '/places/casablanca',
  // What the readers review walked and the list left out (RD23, 9 Nov 2026): a journey, tools, the bill, the corrections.
  '/topics/work/journeys/dismissed', '/topics/work/tools/end', '/topics/road/tools/fine', '/topics/family/tools/inheritance',
  '/topics/housing/tools/rent', '/topics/tax', '/corrections', '/me', '/login', '/ai', '/blog/whatsapp', '/ma/dahir/1-11-91/art_41'];

const browser = await chromium.launch(CHANNEL ? { channel: CHANNEL } : {});
const found = [];
try {
  // 360 px: the width of the cheap Androids most Moroccans hold (the earlier reviews tested at 390 and 412, and /new's
  // fourth issue ran past the screen there).
  const phone = await browser.newContext({ viewport: { width: 360, height: 740 }, isMobile: true, hasTouch: true, locale: 'ar-MA' });
  const page = await phone.newPage();
  for (const path of PAGES) {
    await page.goto(base + path, { waitUntil: 'networkidle', timeout: 60000 });
    await page.waitForTimeout(600);
    await page.addScriptTag({ url: AXE });
    const violations = await page.evaluate(async () => (await window.axe.run(document, {
      runOnly: ['wcag2a', 'wcag2aa'], resultTypes: ['violations'],
    })).violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
      .map((v) => ({ id: v.id, n: v.nodes.length, where: v.nodes.slice(0, 2).map((x) => x.html.slice(0, 120)) })));
    for (const v of violations) found.push({ path, ...v });
    console.log(`${violations.length ? 'FAIL' : 'ok  '} ${path}${violations.length ? ' ' + violations.map((v) => `${v.id} ×${v.n}`).join(', ') : ''}`);
  }
} finally {
  await browser.close();
}
if (found.length) {
  for (const f of found) console.error(`${f.path} ${f.id}: ${f.where.join(' | ')}`);
  process.exit(1);
}
console.log(`no serious finding on ${PAGES.length} pages`);
