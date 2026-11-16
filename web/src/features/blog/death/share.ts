import { fileName } from '@/shared/services/fileName';

/** The penal code as a picture to share, 1080 × 1350: the title, two sentences, every article a square left to right (the
 *  thirty that punish with death filled in ink, those that rule on it in outline), the legend, the source. Drawn on the
 *  phone and handed to its share sheet (or saved where there is none). */
export type CodePicture = {
  dir: 'rtl' | 'ltr'; over: string; title: string; cells: ('death' | 'rule' | null)[]; lines: string[];
  legend: [string, string]; source: string; site: string;
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

export async function shareCode(from: Element, p: CodePicture): Promise<boolean> {
  await document.fonts?.ready;
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = cv.getContext('2d')!;
  const css = getComputedStyle(from);
  const v = (name: string, f: string) => css.getPropertyValue(name).trim() || f;
  const paper = v('--color-paper', '#F4F2EE'), ink = v('--color-ink', '#1E1B2C'), soft = v('--color-ink-soft', '#5D586E'),
    rule = v('--color-rule', '#E4E0DA'), stamp = v('--color-stamp', '#5B3A9E');
  const rtl = p.dir === 'rtl';
  const ui = (w: number, s: number) => `${w} ${s}px "Readex Pro", system-ui, sans-serif`;
  const law = (s: number) => (rtl ? `700 ${s}px "Markazi Text", serif` : `600 ${Math.round(s * 0.8)}px "Source Serif 4", Georgia, serif`);
  ctx.fillStyle = paper; ctx.fillRect(0, 0, W, H);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  const x0 = rtl ? W - PAD : PAD;
  ctx.fillStyle = soft; ctx.font = ui(500, 28); ctx.fillText(p.over, x0, PAD + 18);
  ctx.fillStyle = ink; ctx.fillRect(PAD, PAD + 36, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 43, W - 2 * PAD, 3);
  let y = PAD + 116;
  ctx.font = law(54);
  for (const l of wrap(ctx, p.title, W - 2 * PAD).slice(0, 3)) { ctx.fillText(l, x0, y); y += rtl ? 60 : 52; }
  y += 8;
  ctx.font = law(40); ctx.fillStyle = soft;
  ctx.fillText(p.lines[0], x0, y); y += 50;
  ctx.fillStyle = ink; ctx.fillText(p.lines[1], x0, y); y += 40;
  // Every article, left to right, 32 a row.
  const cols = 32, gap = 4, size = (W - 2 * PAD - (cols - 1) * gap) / cols;
  p.cells.forEach((k, i) => {
    const cx = PAD + (i % cols) * (size + gap), cy = y + Math.floor(i / cols) * (size + gap);
    if (k === 'death') { ctx.fillStyle = ink; ctx.fillRect(cx, cy, size, size); }
    else if (k === 'rule') { ctx.strokeStyle = ink; ctx.lineWidth = 2.5; ctx.strokeRect(cx + 1.25, cy + 1.25, size - 2.5, size - 2.5); }
    else { ctx.fillStyle = rule; ctx.fillRect(cx, cy, size, size); }
  });
  y += Math.ceil(p.cells.length / cols) * (size + gap) + 44;
  // The legend, in the page's direction.
  ctx.font = ui(500, 24); ctx.direction = p.dir;
  let lx = x0;
  for (const [i, words] of p.legend.entries()) {
    const box = 22, w = ctx.measureText(words).width;
    const bx = rtl ? lx - box : lx;
    if (i === 0) { ctx.fillStyle = ink; ctx.fillRect(bx, y - 19, box, box); } else { ctx.strokeStyle = ink; ctx.lineWidth = 2.5; ctx.strokeRect(bx + 1.25, y - 17.75, box - 2.5, box - 2.5); }
    ctx.fillStyle = ink; ctx.fillText(words, rtl ? bx - 10 : bx + box + 10, y);
    lx += (rtl ? -1 : 1) * (box + 10 + w + 36);
  }
  ctx.fillStyle = soft; ctx.font = ui(400, 22);
  let sy = Math.max(y + 54, H - PAD - 96);
  for (const l of wrap(ctx, p.source, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, sy); sy += 30; }
  ctx.fillStyle = stamp; ctx.font = ui(700, 30); ctx.fillText(p.site, x0, H - PAD + 4);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName('death-penalty.png'), { type: 'image/png' });
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
