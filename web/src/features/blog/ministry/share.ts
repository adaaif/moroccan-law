/** The education ministry's names as a picture to share, 1080 × 1350: the title, the longest name large, then every name
 *  as printed with its bar on one line of years (left to right), coloured by strand, the source. Drawn on the phone and
 *  handed to its share sheet (or saved where there is none). */
import type { Strand } from './strands';
import { fileName } from '@/shared/services/fileName';

export type NamesPicture = {
  dir: 'rtl' | 'ltr'; over: string; title: string; longest: string; note: string;
  names: { name: string; from: number; to: number; strand: Strand }[];
  from: number; to: number; legend: Record<Strand, string>; source: string; site: string;
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

export async function shareNames(from: Element, p: NamesPicture): Promise<boolean> {
  await document.fonts?.ready;
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = cv.getContext('2d')!;
  const css = getComputedStyle(from);
  const v = (name: string, f: string) => css.getPropertyValue(name).trim() || f;
  const paper = v('--color-paper', '#F4F2EE'), ink = v('--color-ink', '#1E1B2C'), soft = v('--color-ink-soft', '#5D586E'),
    rule = v('--color-rule', '#E4E0DA'), stamp = v('--color-stamp', '#5B3A9E');
  const colour: Record<Strand, string> = { school: stamp, higher: v('--kc-2', '#93540a'), both: ink };
  const rtl = p.dir === 'rtl';
  const ui = (w: number, s: number) => `${w} ${s}px "Readex Pro", system-ui, sans-serif`;
  const law = (w: number, s: number) => `${w} ${s}px "Markazi Text", serif`;
  ctx.fillStyle = paper; ctx.fillRect(0, 0, W, H);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  const x0 = rtl ? W - PAD : PAD;
  ctx.fillStyle = soft; ctx.font = ui(500, 28); ctx.fillText(p.over, x0, PAD + 18);
  ctx.fillStyle = ink; ctx.fillRect(PAD, PAD + 36, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 43, W - 2 * PAD, 3);
  ctx.font = rtl ? law(700, 52) : '600 40px "Source Serif 4", Georgia, serif';
  let y = PAD + 116;
  for (const l of wrap(ctx, p.title, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, y); y += rtl ? 58 : 50; }
  // The longest name, as a letterhead prints it, centred.
  ctx.direction = 'rtl'; ctx.textAlign = 'center'; ctx.fillStyle = ink; ctx.font = law(700, 58);
  y += 34;
  for (const l of wrap(ctx, `«${p.longest}»`, W - 2 * PAD - 40).slice(0, 3)) { ctx.fillText(l, W / 2, y); y += 64; }
  ctx.direction = p.dir; ctx.fillStyle = soft; ctx.font = ui(400, 24); ctx.fillText(p.note, W / 2, y - 14);
  y += 34;
  // The legend, in reading order.
  ctx.direction = p.dir; ctx.font = ui(400, 22);
  let lx = rtl ? W - PAD : PAD;
  for (const k of ['school', 'higher', 'both'] as const) {
    ctx.fillStyle = colour[k]; ctx.fillRect(rtl ? lx - 20 : lx, y - 16, 20, 20);
    ctx.fillStyle = soft; ctx.textAlign = rtl ? 'right' : 'left';
    ctx.fillText(p.legend[k], rtl ? lx - 30 : lx + 30, y);
    const w = ctx.measureText(p.legend[k]).width + 30 + 34;
    lx += rtl ? -w : w;
  }
  y += 34;
  // Every name: its words on the reading side, its bar on a track of years left to right.
  const nameW = 430, gap = 24;
  const tx0 = rtl ? PAD : PAD + nameW + gap, tx1 = rtl ? W - PAD - nameW - gap : W - PAD;
  const xs = (yr: number) => tx0 + ((yr - p.from) / (p.to + 1 - p.from)) * (tx1 - tx0);
  const rowH = Math.min(30, (H - PAD - 190 - y) / p.names.length);
  p.names.forEach((nm, i) => {
    const ry = y + i * rowH;
    ctx.fillStyle = rule; ctx.fillRect(tx0, ry + rowH / 2 - 5, tx1 - tx0, 10);
    ctx.fillStyle = colour[nm.strand];
    ctx.fillRect(xs(nm.from), ry + rowH / 2 - 5, Math.max(6, xs(nm.to + 1) - xs(nm.from)), 10);
    ctx.direction = 'rtl'; ctx.textAlign = 'right'; ctx.fillStyle = ink;
    let size = 21;
    do { ctx.font = law(nm.name === p.longest ? 700 : 500, size); size -= 1; } while (ctx.measureText(nm.name).width > nameW && size > 13);
    ctx.fillText(nm.name, rtl ? W - PAD : PAD + nameW, ry + rowH / 2 + 7);
  });
  y += p.names.length * rowH + 30;
  ctx.direction = 'ltr'; ctx.textAlign = 'center'; ctx.fillStyle = soft; ctx.font = ui(400, 22);
  for (const yr of [1960, 1980, 2000, 2020]) ctx.fillText(String(yr), xs(yr), y);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  ctx.fillStyle = soft; ctx.font = ui(400, 24);
  let sy = H - PAD - 96;
  for (const l of wrap(ctx, p.source, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, sy); sy += 32; }
  ctx.fillStyle = stamp; ctx.font = ui(700, 30); ctx.fillText(p.site, x0, H - PAD + 4);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName('ministry.png'), { type: 'image/png' });
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
