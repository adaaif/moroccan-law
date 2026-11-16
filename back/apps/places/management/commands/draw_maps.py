"""The two maps the places' pages draw (PL7, PL13 of the places review): the world in Equal Earth and Morocco
alone, from Natural Earth 5.1 in its Morocco edition (public domain; it draws the Kingdom whole), simplified and
projected once into SVG paths: web/public/geo/world.json and morocco.json. The web projects a place's latitude and
longitude with the same constants, written beside the paths. $0, no network; run when the source changes."""
import json
import math
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
M = math.sqrt(3) / 2


def equal_earth(lon, lat):
    lam, phi = math.radians(lon), math.radians(lat)
    t = math.asin(M * math.sin(phi))
    t2, t6 = t * t, t ** 6
    return (lam * math.cos(t) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2))),
            t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2)))


def simplify(points, eps):
    """Douglas–Peucker."""
    if len(points) < 3:
        return points
    (x1, y1), (x2, y2) = points[0], points[-1]
    dx, dy = x2 - x1, y2 - y1
    norm = math.hypot(dx, dy)
    far, at = 0.0, 0
    for k in range(1, len(points) - 1):
        x0, y0 = points[k]
        d = abs(dy * x0 - dx * y0 + x2 * y1 - y2 * x1) / norm if norm else math.hypot(x0 - x1, y0 - y1)
        if d > far:
            far, at = d, k
    if far > eps:
        return simplify(points[:at + 1], eps)[:-1] + simplify(points[at:], eps)
    return [points[0], points[-1]]


def outline(geometry, project, eps, smallest) -> str:
    polygons = geometry['coordinates'] if geometry['type'] == 'MultiPolygon' else [geometry['coordinates']]
    out = []
    for polygon in polygons:
        pts = [project(lon, lat) for lon, lat in polygon[0] if lat > -58]
        if len(pts) < 4:
            continue
        area = abs(sum(pts[i][0] * pts[i - 1][1] - pts[i - 1][0] * pts[i][1] for i in range(len(pts)))) / 2
        if area < smallest:
            continue
        s = simplify(pts, eps)
        if len(s) >= 3:
            out.append('M' + 'L'.join(f'{x:.1f},{y:.1f}' for x, y in s) + 'Z')
    return ''.join(out)


class Command(BaseCommand):
    help = 'Draw web/public/geo/world.json and morocco.json from Natural Earth\'s Morocco edition ($0).'

    def add_arguments(self, parser):
        parser.add_argument('--out', default=str(Path(settings.BASE_DIR).parent / 'web' / 'public' / 'geo'))

    def handle(self, *args, out, **opts):
        src = Path(settings.CORPUS_DIR) / 'sources' / 'places' / 'naturalearth_ne_10m_admin_0_countries_mar.geojson'
        features = json.loads(src.read_text())['features']
        width = 1000
        scale = width / (2 * equal_earth(180, 0)[0])
        top, bottom = equal_earth(0, 84)[1], equal_earth(0, -58)[1]
        world = lambda lon, lat: ((equal_earth(lon, lat)[0]) * scale + width / 2, (top - equal_earth(lon, lat)[1]) * scale)
        countries = {}
        for f in features:
            a3 = f['properties']['ADM0_A3']
            if a3 == 'ATA':
                continue
            d = outline(f['geometry'], world, 0.55, 0.8)
            if d:
                countries[a3] = d
        folder = Path(out)
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'world.json').write_text(json.dumps({
            'w': width, 'h': round((top - bottom) * scale), 'projection': 'equal-earth', 'scale': scale, 'top': top,
            'source': 'Natural Earth 5.1, Morocco edition (public domain)', 'countries': countries}, separators=(',', ':')))
        # Morocco: a local plate carrée at 28° north, its neighbours' edges faint.
        k = math.cos(math.radians(28))
        lon0, lon1, lat0, lat1 = -17.6, -0.6, 20.4, 36.2
        mw = 400
        ms = mw / ((lon1 - lon0) * k)
        local = lambda lon, lat: ((lon - lon0) * k * ms, (lat1 - lat) * ms)
        shapes = {}
        for f in features:
            a3 = f['properties']['ADM0_A3']
            if a3 in ('MAR', 'DZA', 'MRT', 'ESP', 'PRT'):
                shapes[a3] = outline(f['geometry'], local, 0.3, 0.3 if a3 == 'MAR' else 4)
        (folder / 'morocco.json').write_text(json.dumps({
            'w': mw, 'h': round((lat1 - lat0) * ms), 'projection': 'plate-carree', 'lon0': lon0, 'lat1': lat1, 'k': k, 'scale': ms,
            'source': 'Natural Earth 5.1, Morocco edition (public domain)', 'shapes': shapes}, separators=(',', ':')))
        self.stdout.write(f'world: {len(countries)} countries, {(folder / "world.json").stat().st_size} bytes; '
                          f'morocco: {(folder / "morocco.json").stat().st_size} bytes')
