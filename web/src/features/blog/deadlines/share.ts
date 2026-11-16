import { fileName } from '@/shared/services/fileName';

/** The law's four favourite deadlines as a picture to share, 1080 × 1350: the title, four leaves of a wall calendar (the
 *  first large, the three after it smaller, each with its number, its unit and the times the law writes it), the source.
 *  Drawn on the phone and handed to its share sheet (or saved where there is none). */
export type LeavesPicture = {
  dir: 'rtl' | 'ltr'; over: string; title: string; leaves: { n: number; unit: string; times: string }[]; source: string; site: string;
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

function leaf(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, c: { sheet: string; ink: string; soft: string; band: string; onBand: string },
  l: { n: number; unit: string; times: string }, scale: number, ui: (w: number, s: number) => string) {
  ctx.fillStyle = c.sheet; ctx.fillRect(x, y, w, h);
  ctx.strokeStyle = c.ink; ctx.lineWidth = 3; ctx.strokeRect(x, y, w, h);
  ctx.fillStyle = c.band; ctx.fillRect(x, y, w, h * 0.16);
  for (const k of [0.3, 0.5, 0.7]) { ctx.fillStyle = c.onBand; ctx.beginPath(); ctx.arc(x + w * k, y + h * 0.08, 7 * scale, 0, Math.PI * 2); ctx.fill(); }
  ctx.direction = 'ltr'; ctx.textAlign = 'center'; ctx.fillStyle = c.ink;
  ctx.font = ui(200, 230 * scale); ctx.fillText(String(l.n), x + w / 2, y + h * 0.6);
  ctx.font = ui(600, 44 * scale); ctx.direction = 'rtl'; ctx.fillText(l.unit, x + w / 2, y + h * 0.76);
  ctx.fillStyle = c.soft; ctx.font = ui(500, 30 * scale); ctx.fillText(l.times, x + w / 2, y + h * 0.9);
}

export async function shareLeaves(from: Element, p: LeavesPicture): Promise<boolean> {
  await document.fonts?.ready;
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = cv.getContext('2d')!;
  const css = getComputedStyle(from);
  const v = (name: string, f: string) => css.getPropertyValue(name).trim() || f;
  const c = { sheet: v('--color-sheet', '#FFFFFF'), ink: v('--color-ink', '#1E1B2C'), soft: v('--color-ink-soft', '#5D586E'), band: v('--color-ink', '#1E1B2C'), onBand: v('--color-paper', '#F4F2EE') };
  const paper = v('--color-paper', '#F4F2EE'), stamp = v('--color-stamp', '#5B3A9E');
  const rtl = p.dir === 'rtl';
  const ui = (w: number, s: number) => `${w} ${s}px "Readex Pro", system-ui, sans-serif`;
  ctx.fillStyle = paper; ctx.fillRect(0, 0, W, H);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  const x0 = rtl ? W - PAD : PAD;
  ctx.fillStyle = c.soft; ctx.font = ui(500, 28); ctx.fillText(p.over, x0, PAD + 18);
  ctx.fillStyle = c.ink; ctx.fillRect(PAD, PAD + 36, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 43, W - 2 * PAD, 3);
  ctx.font = rtl ? '700 60px "Markazi Text", serif' : '600 48px "Source Serif 4", Georgia, serif';
  let y = PAD + 126;
  for (const l of wrap(ctx, p.title, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, y); y += rtl ? 66 : 58; }
  y += 30;
  // The first leaf large, the three after it in a row under it, in the page's direction.
  const bigW = 460, bigH = 480;
  leaf(ctx, (W - bigW) / 2, y, bigW, bigH, c, p.leaves[0], 1, ui);
  y += bigH + 40;
  const gap = 30, sw = (W - 2 * PAD - 2 * gap) / 3, sh = sw * 0.9;
  p.leaves.slice(1, 4).forEach((l, i) => {
    const col = rtl ? 2 - i : i;
    leaf(ctx, PAD + col * (sw + gap), y, sw, sh, c, l, 0.52, ui);
  });
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  ctx.fillStyle = c.soft; ctx.font = ui(400, 24);
  let sy = H - PAD - 96;
  for (const l of wrap(ctx, p.source, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, sy); sy += 32; }
  ctx.fillStyle = stamp; ctx.font = ui(700, 30); ctx.fillText(p.site, x0, H - PAD + 4);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName('deadlines.png'), { type: 'image/png' });
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
