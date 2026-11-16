"""`draw_maps` (PL7, PL13): Natural Earth's Morocco edition, kept under CORPUS_DIR/sources/places, drawn once as SVG paths
into world.json (Equal Earth) and morocco.json (a plate carrée at 28°), with the constants the web projects a place by.
A few shapes in Natural Earth's own GeoJSON (simplified by hand, some made up where said); the two files are written
into the test's folder. A point is placed here as the web places it (web/src/features/places/Maps.tsx)."""
import io
import json
import math
import re

import pytest
from django.core.management import call_command

# The corners the simplification must tell apart, each alone on a straight border (a parallel is a straight line on
# both maps): its height off the line, in pixels, on the world map (0.55 the limit) or on Morocco's (0.3).
W_LOW, W_HIGH = (-15.0, 21.3 + 0.11), (0.0, 19.0 + 0.21)            # 0.40 and 0.76 px on the world map
M_LOW, M_HIGH = (-10.3, 26.0 + 0.0075), (-6.0, 29.0 + 0.017)        # 0.20 and 0.45 px on Morocco's
COAST = [(-9.8, 32.0), (-9.8, 31.5), (-9.8, 31.0), (-9.8, 30.5)]   # on one straight coast, from (-9.8, 32.5) to (-9.8, 29.9)
MOROCCO = [(-8.7, 27.7), (-8.7, 28.7), (-3.6, 30.0), (-1.2, 32.1), (-2.2, 35.1), (-5.9, 35.8), (-6.8, 34.0), (-9.8, 32.5),
           *COAST, (-9.8, 29.9), (-14.5, 26.1), (-17.1, 21.3), W_LOW, (-13.0, 21.3), (-13.0, 23.0), (-12.0, 23.5), (-12.0, 26.0),
           M_LOW, (-8.7, 26.0), (-8.7, 27.7)]
MOGADOR = [(-9.80, 31.53), (-9.76, 31.53), (-9.76, 31.49), (-9.80, 31.49), (-9.80, 31.53)]   # an islet, drawn a little large
ALGERIA = [(0.0, 35.8), (8.6, 36.9), (11.9, 23.5), (4.0, 19.0), W_HIGH, (-4.8, 19.0), (-8.7, 27.7), (-8.7, 29.0), M_HIGH,
           (-3.0, 29.0), (-1.2, 32.1), (0.0, 35.8)]
NORWAY = [(5.0, 58.0), (31.0, 70.0), (25.0, 71.2), (5.0, 62.0), (5.0, 58.0)]
# A made-up shape across the map's southern edge: three corners are left above 58° S, too few for a ring.
ACROSS = [(-88.0, -69.5), (-92.0, -69.5), (-92.0, -57.0), (-90.0, -56.0), (-88.0, -57.0), (-88.0, -69.5)]
MALTA = [(14.2, 35.8), (14.5, 35.8), (14.5, 36.0), (14.2, 36.0), (14.2, 35.8)]                   # 0.5 px² on the world map
SPAIN = [(-9.3, 43.0), (3.3, 42.3), (-1.8, 36.7), (-6.3, 36.5), (-9.3, 43.0)]
GRAN_CANARIA = [(-15.8, 28.0), (-15.4, 28.2), (-15.4, 27.8), (-15.8, 27.8), (-15.8, 28.0)]      # 1.1 px² on the world map
LA_GRACIOSA = [(-13.54, 29.27), (-13.46, 29.27), (-13.46, 29.23), (-13.54, 29.23), (-13.54, 29.27)]   # 2 px² on Morocco's
ANTARCTICA = [(-180.0, -90.0), (180.0, -90.0), (180.0, -63.2), (-57.0, -63.2), (-180.0, -63.2), (-180.0, -90.0)]
PATH = re.compile(r'(M-?\d+\.\d,-?\d+\.\d(?:L-?\d+\.\d,-?\d+\.\d)+Z)+')
A1, A2, A3, A4, M = 1.340264, -0.081106, 0.000893, 0.003796, math.sqrt(3) / 2     # Equal Earth's, as the web has them


def feature(a3, *rings):
    geometry = ({'type': 'Polygon', 'coordinates': [list(rings[0])]} if len(rings) == 1 else
                {'type': 'MultiPolygon', 'coordinates': [[list(r)] for r in rings]})
    return {'type': 'Feature', 'properties': {'ADM0_A3': a3, 'ISO_A3': a3}, 'geometry': geometry}


@pytest.fixture
def drawn(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path / 'corpus'
    kept = tmp_path / 'corpus' / 'sources' / 'places'
    kept.mkdir(parents=True)
    (kept / 'naturalearth_ne_10m_admin_0_countries_mar.geojson').write_text(json.dumps({'type': 'FeatureCollection', 'features': [
        feature('MAR', MOROCCO, MOGADOR), feature('DZA', ALGERIA), feature('NOR', NORWAY, ACROSS), feature('MLT', MALTA),
        feature('ESP', SPAIN, GRAN_CANARIA, LA_GRACIOSA), feature('ATA', ANTARCTICA)]}))
    out = io.StringIO()
    call_command('draw_maps', out=str(tmp_path / 'geo'), stdout=out)
    world, morocco = (json.loads((tmp_path / 'geo' / name).read_text()) for name in ('world.json', 'morocco.json'))
    return world, morocco, out.getvalue(), tmp_path / 'geo'


def on_world(world, lon, lat):
    lam, t = math.radians(lon), math.asin(M * math.sin(math.radians(lat)))
    t2, t6 = t * t, t ** 6
    x, y = lam * math.cos(t) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2))), t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))
    return x * world['scale'] + world['w'] / 2, (world['top'] - y) * world['scale']


def on_morocco(morocco, lon, lat):
    return (lon - morocco['lon0']) * morocco['k'] * morocco['scale'], (morocco['lat1'] - lat) * morocco['scale']


def vertices(d: str) -> list[tuple[float, float]]:
    return [(float(x), float(y)) for x, y in re.findall(r'(-?\d+\.\d),(-?\d+\.\d)', d)]


def has(d: str, point) -> bool:
    return any(abs(x - point[0]) < 0.06 and abs(y - point[1]) < 0.06 for x, y in vertices(d))


def test_the_world_in_equal_earth(drawn):
    world, _, said, folder = drawn
    assert (world['w'], world['h'], world['projection'], world['source']) == (
        1000, 437, 'equal-earth', 'Natural Earth 5.1, Morocco edition (public domain)')
    # The frame: 84° N on its top, 58° S on its foot, the antimeridian on both sides, as the web projects a place.
    assert on_world(world, 0, 84)[1] == pytest.approx(0, abs=1e-9)
    assert on_world(world, 0, -58)[1] == pytest.approx(world['h'], abs=0.5)
    assert (on_world(world, -180, 0)[0], on_world(world, 180, 0)[0]) == (pytest.approx(0), pytest.approx(world['w']))
    # Antarctica is left out; a speck under 0.8 px² (Malta at this width) is not drawn, an island over it is.
    assert sorted(world['countries']) == ['DZA', 'ESP', 'MAR', 'NOR']
    assert world['countries']['ESP'].count('M') == 2 and has(world['countries']['ESP'], on_world(world, -15.8, 28.0))
    assert all(PATH.fullmatch(d) for d in world['countries'].values())
    assert all(0 <= x <= world['w'] and 0 <= y <= world['h'] for d in world['countries'].values() for x, y in vertices(d))
    # The prime meridian is the map's middle: Algeria's ring starts on it.
    assert world['countries']['DZA'].startswith('M500.0,112.1L')
    # Norway's shape across the map's foot keeps three corners: too few to draw. Morocco's islet is too small here.
    assert world['countries']['NOR'].count('M') == 1 and world['countries']['MAR'].count('M') == 1
    # A straight coast is one line: its points on the way go, its ends stay; a corner 0.76 px high stays, one 0.40 px goes.
    mar, dza = world['countries']['MAR'], world['countries']['DZA']
    assert not any(has(mar, on_world(world, *p)) for p in COAST) and has(mar, on_world(world, -9.8, 32.5))
    assert has(dza, on_world(world, *W_HIGH)) and not has(mar, on_world(world, *W_LOW))
    assert not has(mar, on_world(world, *M_LOW)) and not has(dza, on_world(world, *M_HIGH))
    sizes = [(folder / n).stat().st_size for n in ('world.json', 'morocco.json')]
    assert said == f'world: 4 countries, {sizes[0]} bytes; morocco: {sizes[1]} bytes\n'


def test_morocco_and_its_neighbours_in_a_plate_carree(drawn):
    _, morocco, _, _ = drawn
    assert (morocco['w'], morocco['h'], morocco['projection'], morocco['lon0'], morocco['lat1']) == (400, 421, 'plate-carree', -17.6, 36.2)
    assert round(morocco['k'], 6) == 0.882948 and round(morocco['scale'], 3) == 26.649
    # The frame: 17.6° W to 0.6° W, 36.2° N to 20.4° N.
    assert on_morocco(morocco, -0.6, 20.4) == (pytest.approx(morocco['w']), pytest.approx(morocco['h'], abs=0.5))
    # Only the Kingdom and its neighbours; a lon of -8.7 and a lat of 27.7 fall where the web would put them.
    assert sorted(morocco['shapes']) == ['DZA', 'ESP', 'MAR']
    assert morocco['shapes']['MAR'].startswith('M209.4,226.5L')
    # Morocco's islet, 1 px², is drawn; La Graciosa, 2 px², is too small for a neighbour's edge (Spain: mainland, Gran Canaria).
    assert morocco['shapes']['MAR'].count('M') == 2 and has(morocco['shapes']['MAR'], on_morocco(morocco, -9.80, 31.53))
    assert morocco['shapes']['ESP'].count('M') == 2
    # Closer: a corner 0.45 px high stays, one 0.20 px goes; those the world map dropped stay.
    mar, dza = morocco['shapes']['MAR'], morocco['shapes']['DZA']
    assert has(dza, on_morocco(morocco, *M_HIGH)) and not has(mar, on_morocco(morocco, *M_LOW))
    assert has(mar, on_morocco(morocco, *W_LOW)) and has(dza, on_morocco(morocco, *W_HIGH))
    assert not any(has(mar, on_morocco(morocco, *p)) for p in COAST)
