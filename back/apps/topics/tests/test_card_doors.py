"""A topic's link picture (U15 of the Moroccan-design review) draws its first doors as pills in a row from the right;
a pill that does not fit goes to the next row, and one too wide for any row ends them. An item the card cannot name
is no picture."""
import io

import pytest
from PIL import Image

from apps.topics.services import kit
from apps.topics.services.kit import folders

pytestmark = pytest.mark.django_db

PILL = (0xed, 0xd9, 0xde)       # the family's colour #c2417a at 14 % over the paper #f4f2ee
EDGE = 1200 - 72 - 10           # 10 px inside the right margin: inside a row's first pill, right of its words


def hub(*titles):
    events = '\n'.join(f'  - {{key: d{n}, title: {{ar: {t}, fr: Porte}}, to: journeys/one}}' for n, t in enumerate(titles))
    return f'events:\n{events}\n'


@pytest.fixture
def family(tmp_path, monkeypatch, settings):
    settings.SHOW_DRAFTS = True
    settings.CORPUS_DIR = tmp_path / 'corpus'
    monkeypatch.setattr(folders, 'BASE', tmp_path)
    (tmp_path / 'family').mkdir()
    (tmp_path / 'family' / 'journeys.yaml').write_text('- {key: one, title: {ar: واحد, fr: Un}, steps: []}\n',
                                                       encoding='utf-8')
    return tmp_path / 'family'


def rows_of_pills(api):
    """The rows the card's pills stand in: each a run of lines of the pill's colour down the right edge."""
    r = api.get('/api/topics/family/card/')
    assert r.status_code == 200
    img = Image.open(io.BytesIO(b''.join(r.streaming_content))).convert('RGB')
    ys = [y for y in range(img.height) if img.getpixel((EDGE, y)) == PILL]
    runs = []
    for y in ys:
        if runs and y == runs[-1][1] + 1:
            runs[-1][1] = y
        else:
            runs.append([y, y])
    return runs


@pytest.mark.needs('fribidi')
def test_a_door_that_does_not_fit_goes_to_the_next_row(family, api):
    # 368 and 336 px wide: together they pass the 648 px the words have.
    (family / 'hub.yaml').write_text(hub('غادي نتزوج ونوثق العقد', 'تزاد عندي مولود جديد'), encoding='utf-8')
    kit.load.cache_clear()
    first, second = rows_of_pills(api)
    assert second[0] - first[0] == 74 and second[1] - first[1] == 74


@pytest.mark.needs('fribidi')
def test_a_door_too_wide_for_a_row_ends_the_doors(family, api):
    (family / 'hub.yaml').write_text(hub('مات واحد من العائلة وبغينا نقسمو الورث بيناتنا بالعدل وبلا مشاكل',
                                         'تزاد عندي مولود جديد'), encoding='utf-8')
    kit.load.cache_clear()
    assert rows_of_pills(api) == []


@pytest.mark.needs('fribidi')
def test_a_card_whose_name_and_line_fill_their_lines_keeps_its_doors_to_one_row(family, api, tmp_path, monkeypatch):
    # A name of three lines and a line of two put the first row of doors at 503 px: no second row under it.
    import json
    from apps.topics.services import topics
    long = {**topics.find('family'), 'name': {'ar': 'الأسرة والزواج والطلاق والحضانة والنفقة والإرث والكفالة والحالة المدنية '
                                                     'والنسب والولاية والوصية', 'fr': 'La famille'},
            'lead': {'ar': 'الزواج والطلاق والحضانة والنفقة والإرث والكفالة والحالة المدنية والنسب والولاية والوصية '
                           'والهبة والصدقة', 'fr': 'Le mariage'}}
    (tmp_path / 'topics.json').write_text(json.dumps({'topics': [long]}, ensure_ascii=False), encoding='utf-8')
    monkeypatch.setattr(topics, 'DATA', tmp_path / 'topics.json')
    (family / 'hub.yaml').write_text(hub('غادي نتزوج ونوثق العقد', 'تزاد عندي مولود جديد'), encoding='utf-8')
    kit.load.cache_clear()
    assert [first for first, _ in rows_of_pills(api)] == [511]


def test_an_item_of_no_kind_the_card_knows_is_no_picture(family, api):
    (family / 'hub.yaml').write_text(hub('تزاد عندي مولود جديد'), encoding='utf-8')
    kit.load.cache_clear()
    assert api.get('/api/topics/family/card/', {'item': 'hub/events'}).status_code == 404
