import { pageImageUrl } from '@/features/corpus/corpus.api';
import type { DrCrop } from '../blog.api';
import { fileName } from '@/shared/services/fileName';

/** The sentence of six constitutions as a picture to share, 1080 × 1350: the years waited, large, and the six printed
 *  articles cut from their pages, two by two in the page's direction, each under its year. Drawn on the phone and handed
 *  to its share sheet (or saved where there is none). */
export type SentencePicture = {
  dir: 'rtl' | 'ltr'; over: string; title: string; slips: { year: number; viewer: string; crop: DrCrop }[];
  count: number; countWords: string; source: string; site: string;
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

async function load(viewer: string): Promise<HTMLImageElement> {
  const [, doc, index] = viewer.match(/\/pages\/(\d+)\/(\d+)/) ?? [];
  const img = new Image();
  img.src = `${pageImageUrl(doc, index)}?w=1600`;
  await img.decode();
  return img;
}

export async function shareSentence(from: Element, p: SentencePicture): Promise<boolean> {
  await document.fonts?.ready;
  const images = await Promise.all(p.slips.map((s) => load(s.viewer)));
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = cv.getContext('2d')!;
  const css = getComputedStyle(from);
  const v = (n: string, f: string) => css.getPropertyValue(n).trim() || f;
  const paper = v('--color-paper', '#F4F2EE'), ink = v('--color-ink', '#1E1B2C'), soft = v('--color-ink-soft', '#5D586E'), stamp = v('--color-stamp', '#5B3A9E');
  const rtl = p.dir === 'rtl';
  const ui = (w: number, s: number) => `${w} ${s}px "Readex Pro", system-ui, sans-serif`;
  ctx.fillStyle = paper; ctx.fillRect(0, 0, W, H);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  const x0 = rtl ? W - PAD : PAD;
  ctx.fillStyle = soft; ctx.font = ui(500, 28); ctx.fillText(p.over, x0, PAD + 18);
  ctx.fillStyle = ink; ctx.fillRect(PAD, PAD + 36, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 43, W - 2 * PAD, 3);
  ctx.font = rtl ? '700 60px "Markazi Text", serif' : '600 46px "Source Serif 4", Georgia, serif';
  let y = PAD + 120;
  for (const l of wrap(ctx, p.title, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, y); y += rtl ? 66 : 56; }
  // The years waited, large.
  ctx.direction = 'ltr'; ctx.textAlign = rtl ? 'right' : 'left';
  ctx.fillStyle = stamp; ctx.font = ui(200, 170);
  const n = String(p.count);
  ctx.fillText(n, x0, y + 150);
  const nw = ctx.measureText(n).width;
  ctx.direction = p.dir; ctx.fillStyle = ink; ctx.font = ui(500, 40);
  ctx.fillText(p.countWords, x0 + (rtl ? -1 : 1) * (nw + 24), y + 150);
  y += 200;
  // The six articles, two by two, in the page's direction.
  const colW = (W - 2 * PAD - 36) / 2;
  let rowTop = y;
  for (let i = 0; i < p.slips.length; i += 2) {
    let rowH = 0;
    for (let k = 0; k < 2 && i + k < p.slips.length; k++) {
      const s = p.slips[i + k], img = images[i + k];
      const sx = s.crop.left * img.naturalWidth, sy = s.crop.top * img.naturalHeight;
      const sw = (s.crop.right - s.crop.left) * img.naturalWidth, sh = (s.crop.bottom - s.crop.top) * img.naturalHeight;
      const dh = (sh / sw) * colW;
      const left = rtl ? W - PAD - (k + 1) * colW - k * 36 : PAD + k * (colW + 36);
      ctx.direction = 'ltr'; ctx.textAlign = rtl ? 'right' : 'left';
      ctx.fillStyle = ink; ctx.font = ui(300, 34);
      ctx.fillText(String(s.year), rtl ? left + colW : left, rowTop + 30);
      ctx.fillStyle = '#ffffff'; ctx.fillRect(left - 8, rowTop + 44, colW + 16, dh + 16);
      ctx.drawImage(img, sx, sy, sw, sh, left, rowTop + 52, colW, dh);
      rowH = Math.max(rowH, dh + 70);
    }
    rowTop += rowH + 10;
  }
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  ctx.fillStyle = soft; ctx.font = ui(400, 24);
  let sy2 = Math.max(rowTop + 20, H - PAD - 110);
  for (const l of wrap(ctx, p.source, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, sy2); sy2 += 32; }
  ctx.fillStyle = stamp; ctx.font = ui(700, 30); ctx.fillText(p.site, x0, H - PAD + 4);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName('strike-1962-2025.png'), { type: 'image/png' });
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
