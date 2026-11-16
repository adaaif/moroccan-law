// The blog's posters (HM41 of the hard-moment review): each post's own picture, its first figure as a phone draws
// it, kept as a still miniature in public/blog/posters/<slug>.webp for /blog's index. Run it with the dev servers up
// (BASE_URL, default http://localhost:5190) after a post's picture changes: `npm run blog:posters`; SLUGS="a b" for a
// few. The figure's top, 4:5 like the share frames, at 240 × 300 (twice the index's 120 × 150), in the light theme.
import { chromium } from 'playwright';
import { mkdirSync, writeFileSync } from 'node:fs';
import path from 'node:path';

const base = process.env.BASE_URL ?? 'http://localhost:5190';
const OUT = path.resolve(import.meta.dirname, '../public/blog/posters');
const W = 240, H = 300;
mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true,
                                           locale: 'ar-MA', timezoneId: 'Africa/Casablanca', colorScheme: 'light', serviceWorkers: 'block' });
const page = await context.newPage();
const slugs = process.env.SLUGS?.split(/\s+/).filter(Boolean)
  ?? (await (await fetch(`${base}/api/blog/`)).json()).posts.map((p) => p.slug);
let made = 0;
for (const slug of slugs) {
  await page.goto(`${base}/blog/${slug}`, { waitUntil: 'networkidle', timeout: 90000 }).catch(() => {});
  await page.waitForTimeout(2500);
  // Nothing fixed over the figure: the bottom bar, a folded answer.
  await page.addStyleTag({ content: '#root>div>nav,.fixed{display:none!important}' });
  // The post's first figure; a post without one, its first drawing wide enough to read.
  const handle = await page.evaluateHandle(() => document.querySelector('main figure')
    ?? [...document.querySelectorAll('main svg')].find((s) => s.getBoundingClientRect().width > 200)?.parentElement ?? null);
  const el = handle.asElement();
  if (!el) { console.log(`${slug}: no figure, no poster`); continue; }
  await el.scrollIntoViewIfNeeded();
  await page.waitForTimeout(900);
  const png = await el.screenshot({ animations: 'disabled' });
  // The top of it, 4:5, scaled down and kept as WebP by the browser itself.
  const webp = await page.evaluate(async ({ data, W, H }) => {
    const img = new Image();
    img.src = `data:image/png;base64,${data}`;
    await img.decode();
    const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
    const ctx = cv.getContext('2d');
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--color-sheet').trim() || '#fff';
    ctx.fillRect(0, 0, W, H);
    const h = Math.min(img.height, (img.width * H) / W);
    ctx.drawImage(img, 0, 0, img.width, h, 0, 0, W, (h * W) / img.width);
    return cv.toDataURL('image/webp', 0.8).split(',')[1];
  }, { data: png.toString('base64'), W, H });
  writeFileSync(path.join(OUT, `${slug}.webp`), Buffer.from(webp, 'base64'));
  made++;
  console.log(`${slug}: ${Math.round(Buffer.from(webp, 'base64').length / 1024)} KB`);
}
await browser.close();
console.log(`${made} posters in ${path.relative(process.cwd(), OUT)}`);
