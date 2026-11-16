"""The site's app icons: the logo, the wordmark «قانون المغرب» (9 Nov 2026: drawn with Gemini, its spelling mended,
traced; public/brand/wordmark.svg), in the paper's colour on the site's violet. The arch and «ق» before it (4 Nov 2026) are
in git's history. Run once from web/: python3 scripts/icons.py (Pillow). Writes public/icons/, public/favicon.ico and
public/apple-touch-icon.png. A maskable icon keeps the wordmark inside the middle 80 % (the safe zone, a circle); the
browser's small icons give it more of the square. The share pictures draw the same file with Pillow too
(back/apps/corpus/services/wordmark.py)."""
import math
import re
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

VIOLET, PAPER = (91, 58, 158, 255), (244, 242, 238, 255)
WEB = Path(__file__).resolve().parent.parent
OUT = WEB / 'public' / 'icons'
SVG = WEB / 'public' / 'brand' / 'wordmark.svg'


def outlines() -> tuple[list[list[tuple[float, float]]], tuple[float, ...]]:
    """The wordmark's path (M, L, C, Z, as the trace writes it) as polygons, and its viewBox."""
    svg = SVG.read_text()
    box = tuple(float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split())
    tokens = re.findall(r'[MLCZ]|-?\d+(?:\.\d+)?', re.search(r' d="([^"]+)"', svg).group(1))
    polygons, current, at, i = [], [], (0.0, 0.0), 0
    while i < len(tokens):
        op = tokens[i]
        i += 1
        if op in 'ML':
            at = (float(tokens[i]), float(tokens[i + 1]))
            i += 2
            if op == 'M' and current:
                polygons.append(current)
                current = []
            current.append(at)
        elif op == 'C':
            x1, y1, x2, y2, x, y = (float(t) for t in tokens[i:i + 6])
            i += 6
            x0, y0 = at
            for n in range(1, 13):
                s, u = n / 12, 1 - n / 12
                current.append((u ** 3 * x0 + 3 * u * u * s * x1 + 3 * u * s * s * x2 + s ** 3 * x,
                                u ** 3 * y0 + 3 * u * u * s * y1 + 3 * u * s * s * y2 + s ** 3 * y))
            at = (x, y)
        elif op == 'Z' and current:
            polygons.append(current)
            current = []
    return polygons, box


def mark(height: float) -> Image.Image:
    """The wordmark `height` pixels tall as a mask, filled even-odd (each outline flips what it covers)."""
    polygons, (vx, vy, vw, vh) = outlines()
    k = height / vh
    size = (math.ceil(vw * k), math.ceil(vh * k))
    out = Image.new('L', size, 0)
    for polygon in polygons:
        layer = Image.new('L', size, 0)
        ImageDraw.Draw(layer).polygon([((x - vx) * k, (y - vy) * k) for x, y in polygon], fill=255)
        out = ImageChops.difference(out, layer)
    return out


def icon(size: int, *, maskable: bool = False, rounded: bool = True, share: float = 0.68) -> Image.Image:
    scale = 4  # drawn large, then reduced: smooth edges
    s = size * scale
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    if maskable or not rounded:
        d.rectangle((0, 0, s, s), fill=VIOLET)
    else:
        d.rounded_rectangle((0, 0, s - 1, s - 1), radius=round(s * 40 / 176), fill=VIOLET)
    # A maskable icon's safe zone is a circle 80 % across: the wordmark, about as wide as it is tall, fits at 54 %.
    m = mark(s * (0.54 if maskable else share))
    img.paste(PAPER, ((s - m.width) // 2, (s - m.height) // 2), m)
    return img.resize((size, size), Image.LANCZOS)


OUT.mkdir(parents=True, exist_ok=True)
icon(192).save(OUT / 'icon-192.png')
icon(512).save(OUT / 'icon-512.png')
icon(512, maskable=True).save(OUT / 'icon-maskable-512.png')
icon(180, rounded=False).save(OUT / 'apple-touch-icon.png')
icon(180, rounded=False).save(OUT.parent / 'apple-touch-icon.png')
# The browser's small icons: the wordmark takes more of the square, its letters being all there is to see.
icon(48, share=0.8).save(OUT / 'favicon-48.png')
icon(256, share=0.8).save(OUT.parent / 'favicon.ico', sizes=[(16, 16), (32, 32), (48, 48)])
print('icons written to', OUT)
