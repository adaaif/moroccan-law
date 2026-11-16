import { NO_DAY } from './time';

/** The grid's drawing, shared by the page's canvas and the picture to share (share.ts). */
export type Layout = { width: number; left: number; right: number; top: number; cell: number; rowH: number; gap: number; height: number };

/** `notes`: room at the right for a few words beside their rows (a wide screen only); `tall`: the height the rows may
 *  fill on a desk, so the picture takes the screen. */
export function layout(width: number, rows: number, notes = false, tall = 0): Layout {
  const left = width < 480 ? 38 : 46, top = 26;
  const right = notes && width >= 700 ? 160 : 2;
  const cell = (width - left - right) / 366;
  const fit = width >= 700 && tall ? Math.floor((tall - top - 6) / rows) : 0;
  const rowH = fit ? Math.max(4, Math.min(8, fit)) : width >= 760 ? 5 : width >= 480 ? 4 : 3;
  const gap = rowH >= 4 ? 1 : 0.6;
  return { width, left, right, top, cell, rowH, gap, height: top + rows * rowH + 6 };
}

export function colours(el: Element) {
  const css = getComputedStyle(el);
  const v = (name: string, fallback: string) => css.getPropertyValue(name).trim() || fallback;
  return { gmt: v('--ck-gmt', '#ECE8E0'), ahead: v('--ck-ahead', '#B47206'), stripe: v('--ck-ahead-wash', '#E9CF9E'),
           ink: v('--color-ink', '#1E1B2C'), stamp: v('--color-stamp', '#5B3A9E'), sheet: v('--color-sheet', '#FFFFFF') };
}

/** Paints the rows into a 2D context: the same drawing for the page and for the picture to share. */
export function paint(ctx: CanvasRenderingContext2D, rows: Uint8Array[], l: Layout, col: ReturnType<typeof colours>,
                      focus: [number, number] | null, first: number, keep: number | null = null) {
  const stripes = document.createElement('canvas');
  stripes.width = stripes.height = 6;
  const sc = stripes.getContext('2d')!;
  sc.fillStyle = col.stripe; sc.fillRect(0, 0, 6, 6);
  sc.strokeStyle = col.ahead; sc.lineWidth = 2;
  sc.beginPath(); sc.moveTo(-1, 7); sc.lineTo(7, -1); sc.stroke();
  const unknown = ctx.createPattern(stripes, 'repeat')!;
  const fill = [null, col.gmt, col.ahead, unknown];
  rows.forEach((r, i) => {
    const year = first + i;
    // The year in focus, and the year a reader picked, in full; the others recede.
    ctx.globalAlpha = !focus || (year >= focus[0] && year <= focus[1]) || year === keep ? 1 : 0.2;
    const y = l.top + i * l.rowH;
    let s0 = 0, code = r[0];
    for (let s = 1; s <= 366; s += 1) {
      let c = s < 366 ? r[s] : -1;
      if (c === NO_DAY) c = code;
      if (c === code) continue;
      const f = fill[code];
      if (f) {
        ctx.fillStyle = f;
        ctx.fillRect(l.left + s0 * l.cell, y, (s - s0) * l.cell + 0.35, l.rowH - l.gap);
      }
      s0 = s; code = c as number;
    }
  });
  ctx.globalAlpha = 1;
}
