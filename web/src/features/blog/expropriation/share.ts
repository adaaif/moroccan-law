import { fileName } from '@/shared/services/fileName';

/** The declarations of public utility as a picture to share, 1080 × 1350: the title, a bar a year since 1956 (water in
 *  blue at the foot, the rest in grey), the legend, the source. Drawn on the phone and handed to its share sheet (or
 *  saved where there is none). */
export type YearsPicture = {
  dir: 'rtl' | 'ltr'; over: string; title: string; years: { year: number; all: number; water: number }[]; water: string; rest: string; source: string; site: string;
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

export async function shareYears(from: Element, p: YearsPicture): Promise<boolean> {
  await document.fonts?.ready;
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = cv.getContext('2d')!;
  const css = getComputedStyle(from);
  const v = (name: string, f: string) => css.getPropertyValue(name).trim() || f;
  const paper = v('--color-paper', '#F4F2EE'), ink = v('--color-ink', '#1E1B2C'), soft = v('--color-ink-soft', '#5D586E'),
    rest = v('--kc-rest', '#b9b6c6'), water = v('--kc-4', '#2f86c8'), stamp = v('--color-stamp', '#5B3A9E');
  const rtl = p.dir === 'rtl';
  const ui = (w: number, s: number) => `${w} ${s}px "Readex Pro", system-ui, sans-serif`;
  ctx.fillStyle = paper; ctx.fillRect(0, 0, W, H);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  const x0 = rtl ? W - PAD : PAD;
  ctx.fillStyle = soft; ctx.font = ui(500, 28); ctx.fillText(p.over, x0, PAD + 18);
  ctx.fillStyle = ink; ctx.fillRect(PAD, PAD + 36, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 43, W - 2 * PAD, 3);
  ctx.font = rtl ? '700 58px "Markazi Text", serif' : '600 46px "Source Serif 4", Georgia, serif';
  let y = PAD + 124;
  for (const l of wrap(ctx, p.title, W - 2 * PAD).slice(0, 3)) { ctx.fillText(l, x0, y); y += rtl ? 64 : 56; }
  // The legend.
  y += 24;
  ctx.font = ui(500, 28);
  let lx = x0;
  for (const [color, words] of [[water, p.water], [rest, p.rest]] as const) {
    const w = ctx.measureText(words).width;
    ctx.fillStyle = color; ctx.fillRect(rtl ? lx - 26 : lx, y - 22, 26, 26);
    ctx.fillStyle = ink; ctx.fillText(words, rtl ? lx - 38 : lx + 38, y);
    lx += (rtl ? -1 : 1) * (38 + w + 44);
  }
  // The bars, left to right.
  const top0 = y + 40, base = H - PAD - 170;
  const max = Math.max(...p.years.map((d) => d.all));
  const step = (W - 2 * PAD) / p.years.length;
  const h = (n: number) => (n / max) * (base - top0);
  p.years.forEach((d, i) => {
    const x = PAD + i * step;
    ctx.fillStyle = rest; ctx.fillRect(x + 1, base - h(d.all), step - 2, h(d.all) - h(d.water));
    ctx.fillStyle = water; ctx.fillRect(x + 1, base - h(d.water), step - 2, h(d.water));
  });
  ctx.direction = 'ltr'; ctx.fillStyle = soft; ctx.font = ui(400, 26);
  for (const yr of [p.years[0].year, 1980, 2000, 2020]) {
    const i = p.years.findIndex((d) => d.year === yr);
    ctx.textAlign = i === 0 ? 'left' : 'center'; ctx.fillText(String(yr), PAD + i * step + step / 2, base + 36);
  }
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  ctx.fillStyle = soft; ctx.font = ui(400, 24);
  let sy = H - PAD - 96;
  for (const l of wrap(ctx, p.source, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, sy); sy += 32; }
  ctx.fillStyle = stamp; ctx.font = ui(700, 30); ctx.fillText(p.site, x0, H - PAD + 4);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName('expropriation.png'), { type: 'image/png' });
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
