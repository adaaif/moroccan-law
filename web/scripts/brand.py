"""The site's logo as vector files (4 Nov 2026, chosen from a ChatGPT sketch, redrawn): the horseshoe arch of
the site's doors (src/features/topics/Arch.tsx, the 120 × 132 grid: jambs at 16 and 104, the circle's centre at (60, 58),
radius 48) drawn as a band of violet ink, a small step at each foot like a bab's base, «ق» in Markazi Text standing in
the doorway. The sketch's onion top (the Mashriq's domes) gave way to the Moroccan arch, which closes again at its foot.

Writes public/brand/: mark.svg (the arch and «ق»), wordmark-ar.svg (the mark and «قانون»: Arabic reads from the
right, the mark first), stamp.svg (the mark in the stamp's square), icon.svg (paper on violet, the app's).
The letters are outlines (any viewer draws them alike). Once, from web/, with fontTools and uharfbuzz:
    python3 -m venv /tmp/brand && /tmp/brand/bin/pip install fonttools uharfbuzz && /tmp/brand/bin/python scripts/brand.py
icons.py draws the PNG icons from the same geometry with Pillow alone."""
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

ROOT = Path(__file__).resolve().parents[1]
FONT = ROOT.parent / 'back' / 'apps' / 'corpus' / 'fonts' / 'MarkaziText.ttf'
OUT = ROOT / 'public' / 'brand'
VIOLET, PAPER = '#5b3a9e', '#f4f2ee'
WORD = 84                      # «قانون»'s height beside the arch (140 tall), its baseline on the «ق»'s

# The arch on the grid: the band's width, the foot, the step at each foot (out, up).
BAND, FOOT, STEP_OUT, STEP_UP = 13, 140, 4, 14


def band_path(foot: float = FOOT) -> str:
    """The arch as one band: its outside over the top, then its doorway back (both horseshoes: each circle goes on below
    its centre before its jambs drop, so the arch closes again at its foot)."""
    r_out, r_in = 48, 48 - BAND
    y_out = 58 + (r_out ** 2 - 44 ** 2) ** 0.5            # where the jambs at 16 and 104 meet the outer circle
    dx_in = 44 - BAND
    y_in = 58 + (r_in ** 2 - dx_in ** 2) ** 0.5
    lo, hi = 16 - STEP_OUT, 104 + STEP_OUT
    return (f'M{lo} {foot}V{foot - STEP_UP}H16V{y_out:.2f}A{r_out} {r_out} 0 1 1 104 {y_out:.2f}V{foot - STEP_UP}H{hi}'
            f'V{foot}H{104 - BAND}V{y_in:.2f}A{r_in} {r_in} 0 1 0 {16 + BAND} {y_in:.2f}V{foot}Z')


def _font(weight: int):
    tt = TTFont(FONT)
    instantiateVariableFont(tt, {'wght': weight}, inplace=True)
    blob = hb.Blob.from_file_path(str(FONT))
    face = hb.Face(blob)
    font = hb.Font(face)
    font.set_variations({'wght': weight})
    return tt, font


def word(text: str, weight: int = 700) -> tuple[str, tuple[float, float, float, float], int]:
    """`text` shaped (right to left, joined) as one path in font units, y down; its box (x0, y0, x1, y1); units per em."""
    tt, font = _font(weight)
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {})
    glyphs = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    pen = SVGPathPen(glyphs)
    x = 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        name = order[info.codepoint]
        glyphs[name].draw(TransformPen(pen, (1, 0, 0, -1, x + pos.x_offset, -pos.y_offset)))
        x += pos.x_advance
    from fontTools.pens.boundsPen import BoundsPen
    bounds = BoundsPen(glyphs)
    x = 0
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        glyphs[order[info.codepoint]].draw(TransformPen(bounds, (1, 0, 0, -1, x + pos.x_offset, -pos.y_offset)))
        x += pos.x_advance
    return pen.getCommands(), bounds.bounds, tt['head'].unitsPerEm


def placed(text: str, *, width: float | None = None, height: float | None = None, cx: float | None = None,
           right: float | None = None, bottom: float | None = None, baseline: float | None = None) -> tuple[str, float, float]:
    """The word's path scaled to `width` or `height` (its box) and moved: centred on `cx` or ending at `right`; its box's
    bottom at `bottom` or its baseline at `baseline`. Gives the transform-wrapped path, its left and its scale."""
    d, (x0, y0, x1, y1), _ = word(text)
    k = width / (x1 - x0) if width else height / (y1 - y0)
    tx = (cx - (x0 + x1) / 2 * k) if cx is not None else (right - x1 * k)
    ty = (bottom - y1 * k) if bottom is not None else baseline
    return f'<path transform="translate({tx:.2f} {ty:.2f}) scale({k:.5f})" d="{d}"/>', tx + x0 * k, k


def mark(ink: str, ground: str | None = None) -> tuple[str, str]:
    """The arch and «ق» on the grid (x 12–108, y 10–140): its SVG and the letter's baseline."""
    q, _, k = placed('ق', width=40, cx=60, bottom=FOOT - 13)
    fill = f' fill="{ink}"'
    return f'<g{fill}><path d="{band_path()}"/>{q}</g>', ''


def svg(view: str, body: str, title: str) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}" role="img" aria-label="{title}">'
            f'<title>{title}</title>{body}</svg>\n')


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    m, _ = mark(VIOLET)
    (OUT / 'mark.svg').write_text(svg('8 6 104 138', m, 'قانون'))

    # The word to the mark's left, its letters' baseline on the «ق»'s, as tall as the arch's shoulders allow.
    _, (qx0, qy0, qx1, qy1), _ = word('ق')
    qk = 40 / (qx1 - qx0)
    q_baseline = (FOOT - 13) - qy1 * qk                      # the «ق»'s baseline on the grid
    w, left, _ = placed('قانون', height=WORD, right=-8, baseline=q_baseline)
    _, (wx0, wy0, wx1, wy1), _ = word('قانون')
    wk = WORD / (wy1 - wy0)
    top = min(6, q_baseline + wy0 * wk - 4)
    bottom = max(144, q_baseline + wy1 * wk + 4)
    (OUT / 'wordmark-ar.svg').write_text(svg(f'{left - 6:.1f} {top:.1f} {114 - left:.1f} {bottom - top:.1f}',
                                           f'<g fill="{VIOLET}">{w}</g>{m}', 'قانون'))

    # The stamp: the mark in a square drawn as the Bulletin's stamps are, a rounded frame of the same ink.
    frame = f'<rect x="-8" y="-6" width="136" height="164" rx="12" fill="none" stroke="{VIOLET}" stroke-width="5"/>'
    (OUT / 'stamp.svg').write_text(svg('-14 -12 148 176', frame + m, 'قانون'))

    # The app's icon: the paper's colour on violet, the arch standing in the middle 70 %.
    pm, _ = mark(PAPER)
    icon = (f'<rect x="-28" y="-30" width="176" height="176" rx="40" fill="{VIOLET}"/>'
            f'<g transform="translate(60 58) scale(0.86) translate(-60 -75)">{pm}</g>')
    (OUT / 'icon.svg').write_text(svg('-28 -30 176 176', icon, 'قانون'))
    print('brand written to', OUT)


if __name__ == '__main__':
    main()
