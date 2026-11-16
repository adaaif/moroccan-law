import { fileName } from '@/shared/services/fileName';

/** The basket as a picture to share, 1080 × 1350: the five lines, the picked staple in violet with its three prices, the
 *  three days and their issues, the days between them. Drawn on the phone and handed to its share sheet (or saved where
 *  there is none). Never sent to the server. */
export type BasketPicture = {
  dir: 'rtl' | 'ltr'; over: string; title: string; sub: string; source: string; site: string;
  columns: [string, string][]; spans: [string, string];
  items: { key: string; name: string; values: number[] }[]; picked: string; money: (v: number) => string;
};

const W = 1080, H = 1350, PAD = 72;

/** Words broken into lines no wider than `max`. */
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

export async function shareBasket(from: Element, p: BasketPicture): Promise<boolean> {
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
  const x0 = rtl ? W - PAD : PAD;
  ctx.fillStyle = soft; ctx.font = ui(500, 30); ctx.fillText(p.over, x0, PAD + 20);
  ctx.fillStyle = ink; ctx.fillRect(PAD, PAD + 40, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 47, W - 2 * PAD, 3);
  ctx.font = rtl ? '700 70px "Markazi Text", serif' : '600 56px "Source Serif 4", Georgia, serif';
  let ty = PAD + 130;
  for (const line of wrap(ctx, p.title, W - 2 * PAD).slice(0, 3)) { ctx.fillText(line, x0, ty); ty += rtl ? 78 : 68; }
  ctx.fillStyle = soft; ctx.font = ui(400, 32);
  ty += 6;
  for (const line of wrap(ctx, p.sub, W - 2 * PAD).slice(0, 2)) { ctx.fillText(line, x0, ty); ty += 46; }

  // The chart, left to right on every page: three columns, each line indexed to 100 on the first.
  const L = PAD + 90, R = W - PAD - 200, T = ty + 170, B = H - PAD - 210;
  const xs = [L, (L + R) / 2, R];
  const lo = 94, hi = 180;
  const y = (i: number) => B - ((i - lo) / (hi - lo)) * (B - T);
  const index = (vals: number[]) => vals.map((x) => (x / vals[0]) * 100);
  ctx.direction = rtl ? 'rtl' : 'ltr';
  ctx.textAlign = 'center';
  p.columns.forEach(([day, issue], i) => {
    ctx.strokeStyle = rule; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(xs[i], T - 36); ctx.lineTo(xs[i], B); ctx.stroke();
    ctx.fillStyle = ink; ctx.font = ui(700, 28); ctx.fillText(day, xs[i], T - 104);
    ctx.fillStyle = stamp; ctx.font = ui(500, 26); ctx.fillText(issue, xs[i], T - 66);
  });
  // The days between the columns.
  p.spans.forEach((s, i) => {
    const a = xs[i] + 10, b = xs[i + 1] - 10, yy = B + 34;
    ctx.strokeStyle = soft; ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(a, yy - 10); ctx.lineTo(a, yy); ctx.lineTo(b, yy); ctx.lineTo(b, yy - 10); ctx.stroke();
    ctx.fillStyle = i ? ink : soft; ctx.font = ui(i ? 700 : 500, 28); ctx.fillText(s, (a + b) / 2, yy + 40);
  });
  // The picked peak's price over it, unless another peak sits just above (then under it, inside the line's angle).
  const peak = (it: { values: number[] }) => y(index(it.values)[1]);
  const pickedItem = p.items.find((it) => it.key === p.picked)!;
  const over = !p.items.some((o) => o !== pickedItem && peak(pickedItem) - peak(o) > 10 && peak(pickedItem) - peak(o) < 80);
  const order = [...p.items].sort((a, b) => Number(a.key === p.picked) - Number(b.key === p.picked));
  for (const it of order) {
    const on = it.key === p.picked, ix = index(it.values);
    ctx.strokeStyle = on ? stamp : soft; ctx.lineWidth = on ? 9 : 3; ctx.lineJoin = 'round'; ctx.lineCap = 'round';
    ctx.globalAlpha = on ? 1 : 0.55;
    ctx.beginPath(); ix.forEach((i, k) => (k ? ctx.lineTo(xs[k], y(i)) : ctx.moveTo(xs[k], y(i)))); ctx.stroke();
    ctx.globalAlpha = 1;
    if (on) {
      ix.forEach((i, k) => {
        ctx.fillStyle = paper; ctx.beginPath(); ctx.arc(xs[k], y(i), 12, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = stamp; ctx.lineWidth = 6; ctx.stroke();
        // Its prices as the orders print them: before the first, over or under the peak, under and before the last
        // (the names stand after it).
        ctx.direction = 'ltr'; ctx.textAlign = k === 1 ? 'center' : 'right'; ctx.fillStyle = ink; ctx.font = ui(700, 34);
        if (k === 0) ctx.fillText(p.money(it.values[k]), xs[k] - 24, y(i) + 12);
        else ctx.fillText(p.money(it.values[k]), k === 2 ? xs[k] - 8 : xs[k], k === 1 && over ? y(i) - 30 : y(i) + 58);
      });
    }
  }
  // The names at the ends, kept apart.
  const ends = p.items.map((it) => ({ it, y: y(index(it.values)[2]) })).sort((a, b) => a.y - b.y);
  let prev = -Infinity;
  for (const e of ends) {
    const yy = Math.max(e.y, prev + 36); prev = yy;
    const on = e.it.key === p.picked, kept = Math.round(index(e.it.values)[2] - 100);
    ctx.direction = 'ltr'; ctx.textAlign = 'left'; ctx.fillStyle = on ? stamp : soft; ctx.font = ui(on ? 700 : 500, 28);
    ctx.fillText(`+${kept}%`, R + 24, yy + 10);
    ctx.direction = p.dir; ctx.textAlign = 'left'; ctx.fillStyle = on ? ink : soft;
    ctx.fillText(e.it.name, R + 108, yy + 10);
  }
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  ctx.fillStyle = soft; ctx.font = ui(400, 24); ctx.fillText(p.source, x0, H - PAD - 60);
  ctx.fillStyle = stamp; ctx.font = ui(700, 32); ctx.fillText(p.site, x0, H - PAD + 6);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName(`${p.picked}-1981.png`), { type: 'image/png' });
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
