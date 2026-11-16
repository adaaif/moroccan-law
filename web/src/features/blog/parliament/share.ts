import { fileName } from '@/shared/services/fileName';

/** One law and the sheets that follow it, as a picture to share, 1080 × 1350: the title, three rows of sheets (the law in
 *  violet with its seal, the decrees in ink, the ministers' orders lighter), each with its words, the source. Drawn on the
 *  phone and handed to its share sheet (or saved where there is none). */
export type SheetsPicture = {
  dir: 'rtl' | 'ltr'; over: string; title: string; rows: { n: number; label: string }[]; source: string; site: string;
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

function sheet(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, stroke: string, fill: string, lw: number) {
  const f = w * 0.28;
  ctx.beginPath();
  ctx.moveTo(x, y); ctx.lineTo(x + w - f, y); ctx.lineTo(x + w, y + f); ctx.lineTo(x + w, y + h); ctx.lineTo(x, y + h); ctx.closePath();
  ctx.fillStyle = fill; ctx.fill(); ctx.strokeStyle = stroke; ctx.lineWidth = lw; ctx.stroke();
  ctx.beginPath(); ctx.moveTo(x + w - f, y); ctx.lineTo(x + w - f, y + f); ctx.lineTo(x + w, y + f); ctx.stroke();
  for (let k = 0; k < 3; k++) { ctx.beginPath(); ctx.moveTo(x + w * 0.18, y + h * (0.42 + k * 0.17)); ctx.lineTo(x + w * (k === 2 ? 0.6 : 0.82), y + h * (0.42 + k * 0.17)); ctx.stroke(); }
}

export async function shareSheets(from: Element, p: SheetsPicture): Promise<boolean> {
  await document.fonts?.ready;
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = cv.getContext('2d')!;
  const css = getComputedStyle(from);
  const v = (name: string, f: string) => css.getPropertyValue(name).trim() || f;
  const paper = v('--color-paper', '#F4F2EE'), sheetC = v('--color-sheet', '#FFFFFF'), ink = v('--color-ink', '#1E1B2C'),
    soft = v('--color-ink-soft', '#5D586E'), stamp = v('--color-stamp', '#5B3A9E');
  const rtl = p.dir === 'rtl';
  const ui = (w: number, s: number) => `${w} ${s}px "Readex Pro", system-ui, sans-serif`;
  ctx.fillStyle = paper; ctx.fillRect(0, 0, W, H);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  const x0 = rtl ? W - PAD : PAD;
  ctx.fillStyle = soft; ctx.font = ui(500, 28); ctx.fillText(p.over, x0, PAD + 18);
  ctx.fillStyle = ink; ctx.fillRect(PAD, PAD + 36, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 43, W - 2 * PAD, 3);
  ctx.font = rtl ? '700 58px "Markazi Text", serif' : '600 46px "Source Serif 4", Georgia, serif';
  let y = PAD + 122;
  for (const l of wrap(ctx, p.title, W - 2 * PAD).slice(0, 3)) { ctx.fillText(l, x0, y); y += rtl ? 64 : 56; }
  y += 18;
  const sizes = [{ w: 110, h: 146, gap: 0, stroke: stamp, fill: sheetC, lw: 4 }, { w: 44, h: 58, gap: 12, stroke: ink, fill: sheetC, lw: 2.5 }, { w: 30, h: 40, gap: 9, stroke: soft, fill: sheetC, lw: 2 }];
  p.rows.forEach((r, i) => {
    const s = sizes[i];
    ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
    ctx.fillStyle = i === 0 ? stamp : ink; ctx.font = ui(700, 34);
    ctx.fillText(r.label, x0, y + 30);
    y += 52;
    const per = Math.floor((W - 2 * PAD + s.gap) / (s.w + s.gap));
    for (let k = 0; k < r.n; k++) {
      const col = k % per, line = Math.floor(k / per);
      sheet(ctx, PAD + col * (s.w + s.gap), y + line * (s.h + s.gap), s.w, s.h, s.stroke, s.fill, s.lw);
      if (i === 0) { ctx.beginPath(); ctx.arc(PAD + s.w * 0.7, y + s.h * 0.78, 16, 0, Math.PI * 2); ctx.fillStyle = stamp; ctx.fill(); }
    }
    y += Math.ceil(r.n / per) * (s.h + s.gap) + 40;
  });
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  ctx.fillStyle = soft; ctx.font = ui(400, 24);
  let sy = Math.max(y + 10, H - PAD - 110);
  for (const l of wrap(ctx, p.source, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, sy); sy += 32; }
  ctx.fillStyle = stamp; ctx.font = ui(700, 30); ctx.fillText(p.site, x0, H - PAD + 4);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName('parliament.png'), { type: 'image/png' });
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
