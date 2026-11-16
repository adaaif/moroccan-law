import { noteUse } from '../use';
import { fileName } from '@/shared/services/fileName';

/** «صورة للمشاركة» for a tool's answer (F10 of the road tools review): drawn on the phone in a canvas, never sent to
 *  the server, then handed to the phone's share sheet (or kept, where there is none). 1080 × 1350, the post's shape. */
export type Picture = {
  dir: 'rtl' | 'ltr';
  /** The topic's colour, as a CSS colour. */
  colour: string;
  over: string;
  value: string;
  lines: string[];
  /** The articles, in one line at the foot. */
  source: string;
  /** «قانون · 3adala.com»: where it was worked out. */
  site: string;
};

const W = 1080, H = 1350, PAD = 96;

function wrap(ctx: CanvasRenderingContext2D, text: string, width: number): string[] {
  const out: string[] = [];
  let line = '';
  for (const word of text.split(/\s+/)) {
    const next = line ? `${line} ${word}` : word;
    if (ctx.measureText(next).width > width && line) { out.push(line); line = word; } else line = next;
  }
  if (line) out.push(line);
  return out;
}

export async function drawPicture(p: Picture): Promise<Blob> {
  await document.fonts?.ready;
  const canvas = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = canvas.getContext('2d')!;
  const css = getComputedStyle(document.documentElement);
  const token = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  const paper = token('--color-paper', '#F4F2EE'), ink = token('--color-ink', '#1E1B2C'), soft = token('--color-ink-soft', '#5D586E');
  ctx.fillStyle = paper;
  ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = p.colour;
  ctx.fillRect(0, 0, W, 18);
  ctx.direction = p.dir;
  ctx.textAlign = p.dir === 'rtl' ? 'right' : 'left';
  const x = p.dir === 'rtl' ? W - PAD : PAD;
  let y = PAD + 40;
  ctx.fillStyle = soft;
  ctx.font = '500 44px "Readex Pro", system-ui, sans-serif';
  for (const l of wrap(ctx, p.over, W - 2 * PAD)) { ctx.fillText(l, x, y); y += 62; }
  y += 70;
  ctx.fillStyle = p.colour;
  ctx.font = '700 128px "Readex Pro", system-ui, sans-serif';
  for (const l of wrap(ctx, p.value, W - 2 * PAD)) { ctx.fillText(l, x, y); y += 140; }
  y += 30;
  ctx.fillStyle = ink;
  ctx.font = '400 42px "Readex Pro", system-ui, sans-serif';
  for (const text of p.lines) {
    for (const l of wrap(ctx, text, W - 2 * PAD)) { if (y > H - 260) break; ctx.fillText(l, x, y); y += 60; }
    y += 18;
  }
  ctx.fillStyle = soft;
  ctx.font = '400 34px "Readex Pro", system-ui, sans-serif';
  let fy = H - PAD - 60;
  for (const l of wrap(ctx, p.source, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x, fy); fy += 46; }
  // The mark before the address (U15 of the Moroccan-design review): the doors' arch, as on every card the site draws.
  const k = 52 / 154, side = p.dir === 'rtl' ? -1 : 1;
  ctx.save();
  ctx.translate(p.dir === 'rtl' ? x - 88 * k : x, H - PAD + 34 - 52);
  ctx.scale(k, k);
  ctx.translate(-16, -10);
  ctx.fillStyle = token('--color-stamp', '#5B3A9E');
  ctx.fill(new Path2D('M16 164V77.2A48 48 0 1 1 104 77.2V164Z'));
  ctx.restore();
  ctx.fillStyle = p.colour;
  ctx.font = '700 40px "Readex Pro", system-ui, sans-serif';
  ctx.fillText(p.site, x + side * (88 * k + 16), H - PAD + 30);
  return new Promise((done, fail) => canvas.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
}

/** Hands the picture to the phone's share sheet; where there is none, saves it. False when the reader cancelled. */
export async function sharePicture(p: Picture, name: string): Promise<boolean> {
  noteUse('picture');
  const blob = await drawPicture(p);
  const file = new File([blob], fileName(`${name}.png`), { type: 'image/png' });
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
