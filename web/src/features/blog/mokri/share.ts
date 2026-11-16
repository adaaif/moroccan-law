import { fileName } from '@/shared/services/fileName';

/** The Grand Vizier's years as a picture to share, 1080 × 1350: the title, his name large, a bar a year of the texts that
 *  carry it, the violet band of the name under them and the Residents General in turn under it, the source. Drawn on the
 *  phone and handed to its share sheet (or saved where there is none). */
export type RelayPicture = {
  dir: 'rtl' | 'ltr'; over: string; title: string; years: { year: number; n: number }[]; runs: { name: string; a: number; b: number }[];
  nameLabel: string; source: string; site: string;
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

export async function shareRelay(from: Element, p: RelayPicture): Promise<boolean> {
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
  ctx.font = rtl ? '700 54px "Markazi Text", serif' : '600 42px "Source Serif 4", Georgia, serif';
  let y = PAD + 120;
  for (const l of wrap(ctx, p.title, W - 2 * PAD).slice(0, 3)) { ctx.fillText(l, x0, y); y += rtl ? 60 : 52; }
  ctx.direction = 'rtl'; ctx.textAlign = 'center'; ctx.fillStyle = ink; ctx.font = '700 150px "Markazi Text", serif';
  ctx.fillText('محمد المقري', W / 2, y + 150);
  y += 210;
  // The bars, left to right.
  const step = (W - 2 * PAD) / p.years.length, barsH = 330, base = y + barsH;
  const max = Math.max(...p.years.map((d) => d.n));
  p.years.forEach((d, i) => { const h = (d.n / max) * barsH; ctx.fillStyle = ink; ctx.fillRect(PAD + i * step + 1, base - h, step - 2, h); });
  const at = (yr: number) => p.years.findIndex((d) => d.year === yr);
  const first = p.years.find((d) => d.n > 0)!.year, last = [...p.years].reverse().find((d) => d.n > 0)!.year;
  ctx.fillStyle = stamp; ctx.fillRect(PAD + at(first) * step, base + 12, (at(last) - at(first) + 1) * step, 40);
  ctx.direction = p.dir; ctx.textAlign = 'left'; ctx.fillStyle = '#fff'; ctx.font = ui(700, 26);
  ctx.direction = 'rtl'; ctx.textAlign = 'right'; ctx.fillText(p.nameLabel, PAD + (at(last) + 1) * step - 12, base + 42);
  p.runs.forEach((r, k) => {
    const xa = PAD + at(r.a) * step, xb = PAD + (at(r.b) + 1) * step;
    ctx.fillStyle = k % 2 ? soft : rule; ctx.fillRect(xa, base + 62, xb - xa, 16);
    ctx.fillStyle = ink; ctx.font = ui(500, 22); ctx.direction = p.dir; ctx.textAlign = 'center';
    ctx.fillText(r.name, (xa + xb) / 2, base + 104 + (k % 2) * 28);
  });
  ctx.direction = 'ltr'; ctx.fillStyle = soft; ctx.font = ui(400, 24);
  for (const yr of [p.years[0].year, 1925, 1935, 1945, 1955]) { ctx.textAlign = yr === p.years[0].year ? 'left' : 'center'; ctx.fillText(String(yr), PAD + at(yr) * step + step / 2, base + 168); }
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  ctx.fillStyle = soft; ctx.font = ui(400, 24);
  let sy = H - PAD - 96;
  for (const l of wrap(ctx, p.source, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, sy); sy += 32; }
  ctx.fillStyle = stamp; ctx.font = ui(700, 30); ctx.fillText(p.site, x0, H - PAD + 4);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName('mokri.png'), { type: 'image/png' });
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
