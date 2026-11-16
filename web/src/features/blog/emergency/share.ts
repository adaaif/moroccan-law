/** The health emergency as a picture to share, 1080 × 1350: the title, its days and decrees large, then the wall calendar
 *  of four years (a row a year, the months left to right, each decree's term a band), the legend, the source. Drawn on
 *  the phone and handed to its share sheet (or saved where there is none). */
import { pieces, type Term } from './calendar';
import { fileName } from '@/shared/services/fileName';

export type CalendarPicture = {
  dir: 'rtl' | 'ltr'; over: string; title: string;
  facts: { n: string; label: string }[];
  terms: (Term & { kind: 'declared' | 'extended' | 'changed' })[];
  months: string[]; legend: { declared: string; extended: string; changed: string }; so: string;
  source: string; site: string;
};

const W = 1080, H = 1350, PAD = 64;

function wrap(ctx: CanvasRenderingContext2D, words: string, max: number): string[] {
  const lines: string[] = [];
  let line = '';
  for (const w of words.split(' ')) {
    const next = line ? `${line} ${w}` : w;
    if (line && ctx.measureText(next).width > max) { lines.push(line); line = w; } else line = next;
  }
  if (line) lines.push(line);
  return lines;
}

function hatch(ctx: CanvasRenderingContext2D, colour: string, paper: string): CanvasPattern {
  const tile = Object.assign(document.createElement('canvas'), { width: 12, height: 12 });
  const c = tile.getContext('2d')!;
  c.fillStyle = paper; c.fillRect(0, 0, 12, 12);
  c.globalAlpha = 0.35; c.fillStyle = colour; c.fillRect(0, 0, 12, 12); c.globalAlpha = 1;
  c.strokeStyle = colour; c.lineWidth = 4;
  c.beginPath(); c.moveTo(-3, 15); c.lineTo(15, -3); c.moveTo(-3, 3); c.lineTo(3, -3); c.moveTo(9, 15); c.lineTo(15, 9); c.stroke();
  return ctx.createPattern(tile, 'repeat')!;
}

export async function shareCalendar(from: Element, p: CalendarPicture): Promise<boolean> {
  await document.fonts?.ready;
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = cv.getContext('2d')!;
  const css = getComputedStyle(from);
  const v = (name: string, f: string) => css.getPropertyValue(name).trim() || f;
  const paper = v('--color-paper', '#F4F2EE'), ink = v('--color-ink', '#1E1B2C'), soft = v('--color-ink-soft', '#5D586E'),
    rule = v('--color-rule', '#E4E0DA'), stamp = v('--color-stamp', '#5B3A9E');
  const rtl = p.dir === 'rtl';
  const ui = (w: number, s: number) => `${w} ${s}px "Readex Pro", system-ui, sans-serif`;
  ctx.fillStyle = paper; ctx.fillRect(0, 0, W, H);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  const x0 = rtl ? W - PAD : PAD;
  ctx.fillStyle = soft; ctx.font = ui(500, 28); ctx.fillText(p.over, x0, PAD + 18);
  ctx.fillStyle = ink; ctx.fillRect(PAD, PAD + 36, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 43, W - 2 * PAD, 3);
  ctx.font = rtl ? '700 56px "Markazi Text", serif' : '600 44px "Source Serif 4", Georgia, serif';
  let y = PAD + 122;
  for (const l of wrap(ctx, p.title, W - 2 * PAD).slice(0, 3)) { ctx.fillText(l, x0, y); y += rtl ? 62 : 54; }
  // The facts, side by side in reading order, each over a violet rule.
  y += 40;
  const colW = (W - 2 * PAD) / p.facts.length;
  p.facts.forEach((f, i) => {
    const cx = rtl ? W - PAD - i * colW : PAD + i * colW;
    const inner = cx + (rtl ? -18 : 18);
    ctx.fillStyle = stamp; ctx.fillRect(rtl ? cx - 5 : cx, y - 6, 5, 196);
    ctx.fillStyle = ink; ctx.font = ui(200, 104); ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
    ctx.fillText(f.n, inner, y + 86);
    ctx.fillStyle = soft; ctx.font = ui(400, 24);
    let ly = y + 124;
    for (const l of wrap(ctx, f.label, colW - 40).slice(0, 3)) { ctx.fillText(l, inner, ly); ly += 30; }
  });
  y += 262;
  // The calendar, left to right on every page.
  const yearW = 92, cx0 = PAD + yearW, cx1 = W - PAD, rowH = 84, band = 54;
  ctx.direction = 'ltr'; ctx.textAlign = 'center'; ctx.fillStyle = soft; ctx.font = ui(400, 20);
  p.months.forEach((m, i) => ctx.fillText(m, cx0 + ((i + 0.5) / 12) * (cx1 - cx0), y));
  y += 18;
  const hatched = hatch(ctx, stamp, paper);
  [2020, 2021, 2022, 2023].forEach((yr, r) => {
    const ry = y + r * rowH;
    ctx.direction = 'ltr'; ctx.textAlign = 'left'; ctx.fillStyle = ink; ctx.font = ui(500, 28); ctx.fillText(String(yr), PAD, ry + band / 2 + 10);
    ctx.fillStyle = rule; ctx.fillRect(cx0, ry, cx1 - cx0, band);
    ctx.save(); ctx.beginPath(); ctx.rect(cx0, ry, cx1 - cx0, band); ctx.clip();
    p.terms.forEach((t, k) => pieces(t).filter(([py]) => py === yr).forEach(([, a, b]) => {
      ctx.globalAlpha = t.kind === 'extended' && k % 2 ? 0.55 : 1;
      ctx.fillStyle = t.kind === 'declared' ? ink : t.kind === 'changed' ? hatched : stamp;
      const xa = cx0 + a * (cx1 - cx0), xb = cx0 + b * (cx1 - cx0);
      ctx.fillRect(xa + 1, ry + 4, Math.max(4, xb - xa - 2), band - 8);
      ctx.globalAlpha = 1;
    }));
    ctx.restore();
    for (let m = 1; m < 12; m += 1) { ctx.fillStyle = paper; ctx.fillRect(cx0 + (m / 12) * (cx1 - cx0) - 0.5, ry, 1, 4); }
  });
  y += 4 * rowH + 20;
  // The legend, in reading order.
  ctx.direction = p.dir; ctx.font = ui(400, 24);
  let lx = rtl ? W - PAD : PAD;
  for (const [fill, words] of [[ink, p.legend.declared], [stamp, p.legend.extended], [hatched, p.legend.changed]] as const) {
    ctx.fillStyle = fill; ctx.fillRect(rtl ? lx - 22 : lx, y - 18, 22, 22);
    ctx.fillStyle = soft; ctx.textAlign = rtl ? 'right' : 'left';
    const tx = rtl ? lx - 32 : lx + 32;
    ctx.fillText(words, tx, y);
    const w = ctx.measureText(words).width + 32 + 36;
    lx += rtl ? -w : w;
  }
  // What the calendar says, in a sentence.
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  ctx.fillStyle = ink; ctx.font = ui(400, 28);
  let wy = y + 66;
  for (const l of wrap(ctx, p.so, W - 2 * PAD).slice(0, 4)) { ctx.fillText(l, x0, wy); wy += 42; }
  ctx.fillStyle = soft; ctx.font = ui(400, 24);
  let sy = H - PAD - 96;
  for (const l of wrap(ctx, p.source, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, sy); sy += 32; }
  ctx.fillStyle = stamp; ctx.font = ui(700, 30); ctx.fillText(p.site, x0, H - PAD + 4);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName('emergency.png'), { type: 'image/png' });
  try {
    if (navigator.canShare?.({ files: [file] })) { await navigator.share({ files: [file] }); return true; }
  } catch (err) {
    if ((err as DOMException).name === 'AbortError') return false;
  }
  const url = URL.createObjectURL(blob);
  Object.assign(document.createElement('a'), { href: url, download: file.name }).click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
  return true;
}
