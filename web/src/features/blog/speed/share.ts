import { angle, DIAL_MAX, polar } from './dial';
import { fileName } from '@/shared/services/fileName';

/** The speeds of the Bulletin as a picture to share, 1080 × 1350: the title, a large dial whose rim carries every era's
 *  speed and year, the needle on the fastest, the source. Drawn on the phone and handed to its share sheet (or saved
 *  where there is none). */
export type DialPicture = {
  dir: 'rtl' | 'ltr'; over: string; title: string; eras: { year: number; kmh: number }[]; unit: string; source: string; site: string;
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

export async function shareDial(from: Element, p: DialPicture): Promise<boolean> {
  await document.fonts?.ready;
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = cv.getContext('2d')!;
  const css = getComputedStyle(from);
  const v = (name: string, f: string) => css.getPropertyValue(name).trim() || f;
  const paper = v('--color-paper', '#F4F2EE'), sheet = v('--color-sheet', '#FFFFFF'), ink = v('--color-ink', '#1E1B2C'),
    soft = v('--color-ink-soft', '#5D586E'), stamp = v('--color-stamp', '#5B3A9E');
  const rtl = p.dir === 'rtl';
  const ui = (w: number, s: number) => `${w} ${s}px "Readex Pro", system-ui, sans-serif`;
  ctx.fillStyle = paper; ctx.fillRect(0, 0, W, H);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  const x0 = rtl ? W - PAD : PAD;
  ctx.fillStyle = soft; ctx.font = ui(500, 28); ctx.fillText(p.over, x0, PAD + 18);
  ctx.fillStyle = ink; ctx.fillRect(PAD, PAD + 36, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 43, W - 2 * PAD, 3);
  ctx.font = rtl ? '700 56px "Markazi Text", serif' : '600 44px "Source Serif 4", Georgia, serif';
  let y = PAD + 120;
  for (const l of wrap(ctx, p.title, W - 2 * PAD).slice(0, 3)) { ctx.fillText(l, x0, y); y += rtl ? 62 : 54; }
  // The dial.
  const cx = W / 2, cy = y + 400, R = 330;
  const top = Math.max(...p.eras.map((e) => e.kmh));
  ctx.fillStyle = sheet; ctx.beginPath(); ctx.arc(cx, cy, R + 40, 0, Math.PI * 2); ctx.fill();
  ctx.strokeStyle = ink; ctx.lineWidth = 6; ctx.beginPath();
  ctx.arc(cx, cy, R, (angle(0) - 90) * Math.PI / 180, (angle(DIAL_MAX) - 90) * Math.PI / 180); ctx.stroke();
  ctx.direction = 'ltr'; ctx.textAlign = 'center';
  for (let k = 0; k <= DIAL_MAX; k += 10) {
    const [x1, y1] = polar(cx, cy, R - 8, angle(k));
    const [x2, y2] = polar(cx, cy, R - (k % 20 ? 30 : 48), angle(k));
    ctx.lineWidth = k % 20 ? 3 : 5; ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
    if (k % 20 === 0 && Math.abs(k - top) > 8) { const [tx, ty] = polar(cx, cy, R - 90, angle(k)); ctx.fillStyle = soft; ctx.font = ui(400, 34); ctx.fillText(String(k), tx, ty + 12); }
  }
  // Each era on the rim: a violet dot, its year outside.
  const byKmh = new Map<number, number[]>();
  for (const e of p.eras) byKmh.set(e.kmh, [...(byKmh.get(e.kmh) ?? []), e.year]);
  for (const [kmh, years] of byKmh) {
    const [dx, dy] = polar(cx, cy, R + 18, angle(kmh));
    ctx.fillStyle = stamp; ctx.beginPath(); ctx.arc(dx, dy, 12, 0, Math.PI * 2); ctx.fill();
    const a = angle(kmh);
    const [lx, ly] = polar(cx, cy, R + 36, a);
    ctx.font = ui(700, 30); ctx.textAlign = Math.abs(a) < 12 ? 'center' : a < 0 ? 'right' : 'left';
    years.forEach((yr, i) => ctx.fillText(String(yr), lx, ly + (Math.abs(a) < 12 ? -6 : 10) + (i - (years.length - 1) / 2) * 34));
    ctx.textAlign = 'center';
  }
  // The needle on the fastest, the hub, the speed.
  const [nx, ny] = polar(cx, cy, R - 60, angle(top));
  ctx.strokeStyle = ink; ctx.lineWidth = 12; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(cx, cy); ctx.lineTo(nx, ny); ctx.stroke();
  ctx.fillStyle = ink; ctx.beginPath(); ctx.arc(cx, cy, 110, 0, Math.PI * 2); ctx.fill();
  ctx.fillStyle = sheet; ctx.font = ui(200, 120); ctx.fillText(String(top), cx, cy + 34);
  ctx.font = ui(500, 32); ctx.fillText(p.unit, cx, cy + 80);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  ctx.fillStyle = soft; ctx.font = ui(400, 24);
  let sy = H - PAD - 96;
  for (const l of wrap(ctx, p.source, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, sy); sy += 32; }
  ctx.fillStyle = stamp; ctx.font = ui(700, 30); ctx.fillText(p.site, x0, H - PAD + 4);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName('speed.png'), { type: 'image/png' });
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
