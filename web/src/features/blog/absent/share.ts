import { share } from './screens';
import { fileName } from '@/shared/services/fileName';

/** The two home screens as a picture to share, 1080 × 1350: the title, the law's four machines with the standing texts
 *  that write them, the Moroccans' ten networks with their share of users and the texts that name them (none), the zero
 *  large, the source. Drawn on the phone and handed to its share sheet (or saved where there is none). */
export type ScreensPicture = {
  dir: 'rtl' | 'ltr'; lang: string; over: string; title: string; law: string; people: string;
  machines: { key: string; name: string; shown: string }[];
  apps: { name: string; pct: string; shown: string }[];
  zero: string; zeroWords: string; source: string; site: string;
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

/** Sets the largest font from `from` down to `to` (by 2 px) at which the words fit `max`; the smallest when none does. */
function fit(ctx: CanvasRenderingContext2D, words: string, max: number, font: (size: number) => string, from: number, to: number) {
  for (let size = from; size >= to; size -= 2) {
    ctx.font = font(size);
    if (ctx.measureText(words).width <= max) return;
  }
}

function round(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.moveTo(x + r, y); ctx.arcTo(x + w, y, x + w, y + h, r); ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r); ctx.arcTo(x, y, x + w, y, r); ctx.closePath();
}

export async function shareScreens(from: Element, p: ScreensPicture): Promise<boolean> {
  await document.fonts?.ready;
  const cv = Object.assign(document.createElement('canvas'), { width: W, height: H });
  const ctx = cv.getContext('2d')!;
  const css = getComputedStyle(from);
  const v = (n: string, f: string) => css.getPropertyValue(n).trim() || f;
  const paper = v('--color-paper', '#F4F2EE'), sheet = v('--color-sheet', '#FFFFFF'), ink = v('--color-ink', '#1E1B2C'),
    soft = v('--color-ink-soft', '#5D586E'), stamp = v('--color-stamp', '#5B3A9E'), onStamp = v('--color-on-stamp', '#FFFFFF');
  const rtl = p.dir === 'rtl';
  const ui = (w: number, s: number) => `${w} ${s}px "Readex Pro", system-ui, sans-serif`;
  ctx.fillStyle = paper; ctx.fillRect(0, 0, W, H);
  ctx.direction = p.dir; ctx.textAlign = rtl ? 'right' : 'left';
  const x0 = rtl ? W - PAD : PAD;
  ctx.fillStyle = soft; ctx.font = ui(500, 28); ctx.fillText(p.over, x0, PAD + 18);
  ctx.fillStyle = ink; ctx.fillRect(PAD, PAD + 36, W - 2 * PAD, 3); ctx.fillRect(PAD, PAD + 43, W - 2 * PAD, 3);
  // The title on one line when a smaller size allows it, else on two.
  const titleFont = (size: number) => (rtl ? `700 ${size}px "Markazi Text", serif` : `600 ${size}px "Source Serif 4", Georgia, serif`);
  fit(ctx, p.title, W - 2 * PAD, titleFont, rtl ? 64 : 50, rtl ? 52 : 40);
  let y = PAD + 126;
  for (const l of wrap(ctx, p.title, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, y); y += rtl ? 70 : 60; }
  y += 6;
  // Two screens in the page's direction: the law's first.
  const gap = 36, sw = (W - 2 * PAD - gap) / 2, sh = 780;
  const lawX = rtl ? W - PAD - sw : PAD, peopleX = rtl ? PAD : PAD + sw + gap;
  const screen = (x: number, title: string, color: string) => {
    ctx.fillStyle = sheet; round(ctx, x, y, sw, sh, 44); ctx.fill();
    ctx.strokeStyle = color; ctx.lineWidth = 4; round(ctx, x, y, sw, sh, 44); ctx.stroke();
    ctx.fillStyle = color; round(ctx, x + sw / 2 - 50, y + 18, 100, 12, 6); ctx.fill();
    ctx.direction = p.dir; ctx.textAlign = 'center'; ctx.fillStyle = color;
    fit(ctx, title, sw - 48, (size) => ui(700, size), 30, 22);
    ctx.fillText(title, x + sw / 2, y + 78);
  };
  screen(lawX, p.law, stamp);
  screen(peopleX, p.people, ink);
  // The law's tiles, two by two, each with its count as a badge.
  const tile = (x: number, ty: number, size: number, label: string, badge: string, inner: () => void, color: string, hollow: boolean) => {
    ctx.fillStyle = paper; round(ctx, x, ty, size, size, size * 0.24); ctx.fill();
    inner();
    ctx.font = ui(700, 26);
    const bw = Math.max(44, ctx.measureText(badge).width + 26);
    const bx = rtl ? x - 10 : x + size - bw + 10;
    round(ctx, bx, ty - 14, bw, 42, 21);
    if (hollow) { ctx.fillStyle = sheet; ctx.fill(); ctx.strokeStyle = color; ctx.lineWidth = 3; ctx.stroke(); } else { ctx.fillStyle = color; ctx.fill(); }
    ctx.fillStyle = hollow ? color : onStamp; ctx.direction = 'ltr'; ctx.textAlign = 'center'; ctx.fillText(badge, bx + bw / 2, ty + 16);
    ctx.direction = p.dir; ctx.fillStyle = ink; ctx.font = ui(500, 24);
    wrap(ctx, label, size + 36).slice(0, 2).forEach((l, k) => ctx.fillText(l, x + size / 2, ty + size + 34 + k * 30));
  };
  const lawSize = 150, lawCols = 2;
  const lawLeft = lawX + (sw - (lawCols * lawSize + 50)) / 2;
  p.machines.forEach((m, i) => {
    const col = rtl ? lawCols - 1 - (i % lawCols) : i % lawCols, row = Math.floor(i / lawCols);
    const tx = lawLeft + col * (lawSize + 50), ty = y + 140 + row * (lawSize + 110);
    tile(tx, ty, lawSize, m.name, m.shown, () => drawPictogram(ctx, m.key, tx + lawSize / 2, ty + lawSize / 2, 70, stamp), stamp, false);
  });
  // The Moroccans' ten tiles, three a row in the page's direction (the last row centred), the share inside, a hollow
  // zero as the badge.
  const appSize = 92, appCols = 3, appGapX = 46, appStep = appSize + 72;
  p.apps.forEach((a, i) => {
    const row = Math.floor(i / appCols), inRow = Math.min(appCols, p.apps.length - row * appCols);
    const k = i % appCols, rowW = inRow * appSize + (inRow - 1) * appGapX;
    const start = peopleX + (sw - rowW) / 2;
    const col = rtl ? inRow - 1 - k : k;
    const tx = start + col * (appSize + appGapX), ty = y + 136 + row * appStep;
    tile(tx, ty, appSize, a.name, a.shown, () => {
      ctx.fillStyle = ink; ctx.font = ui(300, 27); ctx.direction = 'ltr'; ctx.textAlign = 'center';
      ctx.fillText(share(a.pct, p.lang).replace(/[\u2066\u2069]/g, ''), tx + appSize / 2, ty + appSize / 2 + 10);
    }, ink, true);
  });
  y += sh + 78;
  // The zero, large, and its words.
  ctx.direction = 'ltr'; ctx.textAlign = rtl ? 'right' : 'left';
  ctx.fillStyle = ink; ctx.font = ui(200, 120);
  ctx.fillText(p.zero, x0, y + 30);
  const zw = ctx.measureText(p.zero).width;
  ctx.direction = p.dir; ctx.font = ui(500, 36);
  ctx.fillText(p.zeroWords, x0 + (rtl ? -1 : 1) * (zw + 22), y + 18);
  ctx.fillStyle = soft; ctx.font = ui(400, 22);
  let sy = y + 80;
  for (const l of wrap(ctx, p.source, W - 2 * PAD).slice(0, 2)) { ctx.fillText(l, x0, sy); sy += 30; }
  ctx.fillStyle = stamp; ctx.font = ui(700, 30); ctx.fillText(p.site, x0, H - PAD + 4);
  const blob = await new Promise<Blob>((done, fail) => cv.toBlob((b) => (b ? done(b) : fail(new Error('canvas'))), 'image/png'));
  const file = new File([blob], fileName('telegram-whatsapp.png'), { type: 'image/png' });
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

/** The pictograms of Screens.tsx, drawn on the canvas from the same 40 × 40 paths. */
function drawPictogram(ctx: CanvasRenderingContext2D, key: string, cx: number, cy: number, size: number, color: string) {
  const paths: Record<string, string[]> = {
    telegram: ['M8 7h24a2 2 0 0 1 2 2v22a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2z', 'M10 13h12', 'M11 18h18a1 1 0 0 1 1 1v3a1 1 0 0 1-1 1H11a1 1 0 0 1-1-1v-3a1 1 0 0 1 1-1z', 'M10 28h8M22 28h8', 'M28 10l-3 4h3l-3 4'],
    typewriter: ['M13 16V6h14v10', 'M16 10h8M16 13h6', 'M5 18h30l-3 15H8z', 'M11 23h2M15 23h2M19 23h2M23 23h2M27 23h2M13 28h14'],
    fax: ['M14 15V5h15v10', 'M18 9h7M18 12h5', 'M12 15h21a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H12a2 2 0 0 1-2-2V17a2 2 0 0 1 2-2z', 'M5 17v14a2 2 0 0 0 4 0V17a2 2 0 0 0-4 0z', 'M15 21h15M15 25h3M21 25h3M27 25h3M15 29h3M21 29h3M27 29h3'],
    telex: ['M3 14h34v12H3z', 'M3 20h34'],
  };
  ctx.save();
  ctx.translate(cx - size / 2, cy - size / 2);
  ctx.scale(size / 40, size / 40);
  ctx.strokeStyle = color; ctx.fillStyle = color; ctx.lineWidth = 1.8; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  for (const d of paths[key] ?? []) ctx.stroke(new Path2D(d));
  if (key === 'telex') for (const [x, y] of [[8, 18], [13, 22], [18, 18], [18, 22], [23, 18], [28, 22], [33, 18], [33, 22]]) { ctx.beginPath(); ctx.arc(x, y, 1.3, 0, Math.PI * 2); ctx.fill(); }
  ctx.restore();
}
