import { type Price, type Segment, yearOf } from './price';
import { FIRST_GUESS } from './Draw';
import { fileName } from '@/shared/services/fileName';

/** The picture to share: the reader's line against the orders', 1080 × 1350, drawn on the phone and handed to its share
 *  sheet (or saved where there is none). Never sent to the server. */
export type GuessPicture = { dir: 'rtl' | 'ltr'; over: string; title: string; sub: string; legend: [string, string]; source: string; site: string };

const W = 1080, H = 1350, PAD = 72;

export async function shareGuess(steps: Price[], segs: Segment[], guess: (number | null)[], from: Element, p: GuessPicture): Promise<boolean> {
  await document.fonts?.ready;
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = cv.getContext('2d')!;
  const css = getComputedStyle(from);
  const v = (n: string, f: string) => css.getPropertyValue(n).trim() || f;
  const paper = v('--color-paper', '#F4F2EE'), ink = v('--color-ink', '#1E1B2C'), soft = v('--color-ink-soft', '#5D586E'), stamp = v('--color-stamp', '#5B3A9E');
  const rule = v('--color-rule', '#E4E0DA');
  ctx.fillStyle = paper; ctx.fillRect(0, 0, W, H);
  ctx.direction = p.dir; ctx.textAlign = p.dir === 'rtl' ? 'right' : 'left';
  const x0 = p.dir === 'rtl' ? W - PAD : PAD;
  ctx.fillStyle = soft; ctx.font = '500 30px "Readex Pro", system-ui, sans-serif'; ctx.fillText(p.over, x0, PAD + 20);
  ctx.fillStyle = ink; ctx.fillRect(PAD, PAD + 40, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 47, W - 2 * PAD, 3);
  ctx.font = p.dir === 'rtl' ? '700 74px "Markazi Text", serif' : '600 60px "Source Serif 4", Georgia, serif';
  ctx.fillText(p.title, x0, PAD + 140);
  ctx.fillStyle = soft; ctx.font = '400 32px "Readex Pro", system-ui, sans-serif'; ctx.fillText(p.sub, x0, PAD + 198);
  // The chart, left to right on every page: 1955 to 2027, 0 to 35 dirhams.
  const L = PAD + 54, R = W - PAD, T = PAD + 260, B = H - PAD - 230;
  const x = (yr: number) => L + ((yr - 1955.4) / (2027.2 - 1955.4)) * (R - L);
  const y = (dh: number) => B - (dh / 35) * (B - T);
  ctx.direction = 'ltr'; ctx.textAlign = 'right'; ctx.font = '400 24px "Readex Pro", system-ui, sans-serif';
  for (const d of [0, 10, 20, 30]) {
    ctx.strokeStyle = d ? rule : ink; ctx.lineWidth = d ? 1 : 2;
    ctx.beginPath(); ctx.moveTo(L, y(d)); ctx.lineTo(R, y(d)); ctx.stroke();
    ctx.fillStyle = soft; ctx.fillText(String(d), L - 10, y(d) + 8);
  }
  ctx.textAlign = 'center';
  for (const yr of [1960, 1980, 2000, 2020]) ctx.fillText(String(yr), x(yr), B + 36);
  ctx.strokeStyle = stamp; ctx.lineWidth = 6; ctx.lineJoin = 'round';
  ctx.beginPath();
  let open = false;
  const breaks: [number, number, number, number][] = [];
  segs.forEach((s, i) => {
    if (s.dh === null) { open = false; return; }
    if (!open) { ctx.moveTo(x(yearOf(s.from)), y(s.dh)); open = true; } else ctx.lineTo(x(yearOf(s.from)), y(s.dh));
    if (s.gap) {
      // No order printed after this one for years: its price stands alone, a dashed line to the next.
      const next = segs.slice(i + 1).find((n) => n.dh !== null);
      if (next) breaks.push([x(yearOf(s.from)), y(s.dh), x(yearOf(next.from)), y(next.dh!)]);
      open = false;
      return;
    }
    ctx.lineTo(x(yearOf(s.to)), y(s.dh));
  });
  ctx.stroke();
  ctx.strokeStyle = soft; ctx.lineWidth = 3; ctx.setLineDash([4, 9]);
  for (const [a, b, c, d] of breaks) { ctx.beginPath(); ctx.moveTo(a, b); ctx.lineTo(c, d); ctx.stroke(); }
  ctx.setLineDash([]);
  ctx.fillStyle = stamp;
  for (const st of steps) { const s = segs.find((g) => g.from === st.date); if (s?.dh) { ctx.beginPath(); ctx.arc(x(yearOf(st.date)), y(s.dh), 6, 0, Math.PI * 2); ctx.fill(); } }
  if (guess.some((g) => g !== null)) {
    ctx.strokeStyle = ink; ctx.lineWidth = 5; ctx.setLineDash([16, 12]);
    ctx.beginPath();
    let prev = -1;
    guess.forEach((g, i) => { if (g === null) return; const yr = FIRST_GUESS + i; if (yr === prev + 1) ctx.lineTo(x(yr + 0.5), y(g)); else ctx.moveTo(x(yr + 0.5), y(g)); prev = yr; });
    ctx.stroke(); ctx.setLineDash([]);
  }
  // Legend, source, address.
  ctx.direction = p.dir; ctx.textAlign = p.dir === 'rtl' ? 'right' : 'left';
  const side = p.dir === 'rtl' ? -1 : 1;
  let lx = x0;
  const ly = B + 110;
  ctx.font = '500 30px "Readex Pro", system-ui, sans-serif';
  p.legend.forEach((words, i) => {
    if (i === 1 && !guess.some((g) => g !== null)) return;
    ctx.strokeStyle = i ? ink : stamp; ctx.lineWidth = 6; ctx.setLineDash(i ? [12, 8] : []);
    ctx.beginPath(); ctx.moveTo(lx, ly - 10); ctx.lineTo(lx + side * 44, ly - 10); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = ink; ctx.fillText(words, lx + side * 58, ly);
    lx += side * (ctx.measureText(words).width + 120);
  });
  ctx.fillStyle = soft; ctx.font = '400 24px "Readex Pro", system-ui, sans-serif'; ctx.fillText(p.source, x0, ly + 56);
  ctx.fillStyle = stamp; ctx.font = '700 32px "Readex Pro", system-ui, sans-serif'; ctx.fillText(p.site, x0, H - PAD + 6);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName('marquise.png'), { type: 'image/png' });
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
