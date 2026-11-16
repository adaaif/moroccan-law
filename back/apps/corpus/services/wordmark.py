"""The logo, the wordmark «قانون المغرب», drawn with Pillow (9 Nov 2026; drawn with Gemini, its spelling mended,
traced): the share pictures carry it (cards.py `mark`). `data/wordmark.svg` is the same file as the site's
web/public/brand/wordmark.svg (a test keeps them one): its path (M, L, C, Z, as the trace writes it) flattened to polygons
and filled even-odd, drawn four times as large, then reduced."""
import math
import re
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

SVG = Path(__file__).resolve().parent.parent / 'data' / 'wordmark.svg'
_TOKENS = re.compile(r'[MLCZ]|-?\d+(?:\.\d+)?')


@lru_cache(maxsize=1)
def shape() -> tuple[list[list[tuple[float, float]]], tuple[float, float, float, float]]:
    """The wordmark's outlines as polygons, and its viewBox (x, y, width, height)."""
    svg = SVG.read_text()
    box = tuple(float(v) for v in re.search(r'viewBox="([^"]+)"', svg).group(1).split())
    tokens = _TOKENS.findall(re.search(r' d="([^"]+)"', svg).group(1))
    polygons: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    at, i = (0.0, 0.0), 0
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
            for n in range(1, 9):
                s, u = n / 8, 1 - n / 8
                current.append((u ** 3 * x0 + 3 * u * u * s * x1 + 3 * u * s * s * x2 + s ** 3 * x,
                                u ** 3 * y0 + 3 * u * u * s * y1 + 3 * u * s * s * y2 + s ** 3 * y))
            at = (x, y)
        elif op == 'Z' and current:
            polygons.append(current)
            current = []
    if current:
        polygons.append(current)
    return polygons, box


def mask(height: float, scale: int = 4) -> Image.Image:
    """The wordmark `height` pixels tall as a mask (mode L): ink 255, ground 0, its edges smooth."""
    polygons, (vx, vy, vw, vh) = shape()
    k = height * scale / vh
    size = (math.ceil(vw * k), math.ceil(vh * k))
    out = Image.new('L', size, 0)
    for polygon in polygons:     # even-odd: each outline flips what it covers, so a letter's hole stays open
        layer = Image.new('L', size, 0)
        ImageDraw.Draw(layer).polygon([((x - vx) * k, (y - vy) * k) for x, y in polygon], fill=255)
        out = ImageChops.difference(out, layer)
    return out.resize((max(1, round(size[0] / scale)), max(1, round(size[1] / scale))), Image.LANCZOS)
