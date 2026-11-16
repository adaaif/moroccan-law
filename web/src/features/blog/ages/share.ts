import { lifeX } from './life';
import { fileName } from '@/shared/services/fileName';

/** The reader's age as a picture to share, 1080 × 1350: their age large, the line of a life with their mark, what the
 *  law says holds for them and what comes at the next age. Drawn on the phone and handed to its share sheet (or saved
 *  where there is none). The age never leaves the phone otherwise. */
export type AgePicture = {
  dir: 'rtl' | 'ltr'; over: string; title: string; lines: string[]; next: { head: string; lines: string[] } | null;
  source: string; site: string; age: number;
};

const W = 1080, H = 1350, PAD = 72;

/** Words in at most `most` lines, the last ending «…» when some are left out. */
function lines(ctx: CanvasRenderingContext2D, words: string, max: number, most: number): string[] {
  const all = wrap(ctx, words, max);
  if (all.length <= most) return all;
  const kept = all.slice(0, most);
  let last = kept[most - 1];
  while (last && ctx.measureText(`${last} …`).width > max) last = last.split(' ').slice(0, -1).join(' ');
  kept[most - 1] = `${last} …`;
  return kept;
}

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

export async function shareAge(from: Element, p: AgePicture): Promise<boolean> {
  await document.fonts?.ready;
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = cv.getContext('2d')!;
  const css = getComputedStyle(from);
  const v = (n: string, f: string) => css.getPropertyValue(n).trim() || f;
  const paper = v('--color-paper', '#F4F2EE'), ink = v('--color-ink', '#1E1B2C'), soft = v('--color-ink-soft', '#5D586E'), stamp = v('--color-stamp', '#5B3A9E');
  const rule = v('--color-rule', '#E4E0DA');
  const rtl = p.dir === 'rtl';
  const ui = (w: number, s: number) => `${w} ${s}px "Readex Pro", system-ui, sans-serif`;
  ctx.fillStyle = paper; ctx.fillRect(0, 0, W, H);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  const x0 = rtl ? W - PAD : PAD, side = rtl ? -1 : 1;
  ctx.fillStyle = soft; ctx.font = ui(500, 30); ctx.fillText(p.over, x0, PAD + 20);
  ctx.fillStyle = ink; ctx.fillRect(PAD, PAD + 40, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 47, W - 2 * PAD, 3);
  // The age, large, in the lightest weight; the title beside it.
  ctx.font = ui(200, 190); ctx.fillStyle = ink;
  const ageW = ctx.measureText(String(p.age)).width;
  ctx.direction = 'ltr'; ctx.textAlign = rtl ? 'right' : 'left';
  ctx.fillText(String(p.age), x0, PAD + 250);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  ctx.font = rtl ? '700 54px "Markazi Text", serif' : '600 44px "Source Serif 4", Georgia, serif';
  let ty = PAD + 140;
  for (const line of wrap(ctx, p.title, W - 2 * PAD - ageW - 40).slice(0, 3)) { ctx.fillText(line, x0 + side * (ageW + 40), ty); ty += rtl ? 62 : 54; }
  // The line of a life, left to right, with the reader's years in ink and their mark.
  const L = PAD + 10, R = W - PAD - 10, ly = PAD + 320;
  const x = (a: number) => L + lifeX(a) * (R - L);
  ctx.strokeStyle = rule; ctx.lineWidth = 4; ctx.beginPath(); ctx.moveTo(L, ly); ctx.lineTo(R, ly); ctx.stroke();
  ctx.strokeStyle = ink; ctx.lineWidth = 8; ctx.lineCap = 'round'; ctx.beginPath(); ctx.moveTo(L, ly); ctx.lineTo(x(p.age), ly); ctx.stroke();
  ctx.fillStyle = ink; ctx.beginPath(); ctx.arc(x(p.age), ly, 14, 0, Math.PI * 2); ctx.fill();
  ctx.direction = 'ltr'; ctx.textAlign = 'center'; ctx.fillStyle = soft; ctx.font = ui(400, 24);
  for (const a of [0, 12, 18, 25, 60, 65]) ctx.fillText(String(a), x(a), ly + 44);
  // What holds, then what comes.
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  let y = ly + 110;
  const max = W - 2 * PAD - 40, bottom = H - PAD - 120;
  const bullet = (color: string) => { ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x0 + side * 10, y - 11, 7, 0, Math.PI * 2); ctx.fill(); };
  ctx.font = ui(400, 30);
  let shown = 0;
  for (const words of p.lines) {
    const ls = lines(ctx, words, max, 2);
    if (y + ls.length * 42 > bottom - (p.next ? 190 : 0)) break;
    bullet(stamp); ctx.fillStyle = ink;
    for (const l of ls) { ctx.fillText(l, x0 + side * 34, y); y += 42; }
    y += 12; shown++;
  }
  if (shown < p.lines.length) { ctx.fillStyle = soft; ctx.fillText(`+${p.lines.length - shown}`, x0 + side * 34, y); y += 48; }
  if (p.next) {
    y += 10;
    ctx.fillStyle = stamp; ctx.font = ui(700, 32); ctx.fillText(p.next.head, x0, y); y += 50;
    ctx.font = ui(400, 28);
    for (const words of p.next.lines) {
      const ls = lines(ctx, words, max, 2);
      if (y + ls.length * 40 > bottom + 40) break;
      ctx.strokeStyle = stamp; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(x0 + side * 10, y - 10, 7, 0, Math.PI * 2); ctx.stroke();
      ctx.fillStyle = soft;
      for (const l of ls) { ctx.fillText(l, x0 + side * 34, y); y += 40; }
      y += 6;
    }
  }
  ctx.fillStyle = soft; ctx.font = ui(400, 24); ctx.fillText(p.source, x0, H - PAD - 60);
  ctx.fillStyle = stamp; ctx.font = ui(700, 32); ctx.fillText(p.site, x0, H - PAD + 6);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName(`age-${p.age}.png`), { type: 'image/png' });
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
