"""T3 of the work plan: a table row cut over the next article as its subject goes back to the end of its own."""
import json
from datetime import date

import pytest

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.quality.services import tables

pytestmark = pytest.mark.django_db


def test_a_row_cut_over_the_next_article_goes_back_in_the_corpus_and_in_texts_json(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    text = Text.objects.create(akn_uri='/akn/ma/act/decret/2-25-265', type='decree', number='2-25-265', title_ar='مرسوم')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2025, 4, 28), consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=2, label='المادة الثانية', number='2', eid='art_2',
                           body='| 900 | من 2473 يوما إلى 2856 يوما |')
    Article.objects.create(version=v, order=3, label='المادة الثالثة', number='3', eid='art_3',
                           heading_path=['| 1000 | 2857 يوما فما فوق |'], body='ينسخ المرسوم.')
    # A heading that is no table row stays where it is.
    Article.objects.create(version=v, order=4, label='المادة الرابعة', number='4', eid='art_4',
                           heading_path=['الباب الثاني: أحكام ختامية'], body='يعمل به.')
    work = tmp_path / 'reports' / 'issues' / '7399'
    work.mkdir(parents=True)
    (work / 'texts.json').write_text(json.dumps([{'articles': [
        {'label': 'المادة الثانية', 'heading_path': [], 'body': '| 900 | من 2473 يوما إلى 2856 يوما |'},
        {'label': 'المادة الثالثة', 'heading_path': ['| 1000 | 2857 يوما فما فوق |'], 'body': 'ينسخ المرسوم.'}]}],
        ensure_ascii=False))
    # An issue read again since: its rows were given back before, the copy kept then stays as it was.
    again = tmp_path / 'reports' / 'issues' / '7400'
    again.mkdir()
    (again / 'texts.json').write_text(json.dumps([{'articles': [
        {'label': 'المادة 1', 'heading_path': [], 'body': '| 1 | 2 |'},
        {'label': 'المادة 2', 'heading_path': ['| 3 | 4 |'], 'body': 'نص.'}]}, {'articles': None}], ensure_ascii=False))
    (again / 'texts.before-rows.json').write_text('[]')
    # One with nothing to give back is not written again.
    still = tmp_path / 'reports' / 'issues' / '7401'
    still.mkdir()
    (still / 'texts.json').write_text(json.dumps([{'articles': [
        {'label': 'المادة 1', 'heading_path': ['الباب الأول'], 'body': 'نص'},
        {'label': 'المادة 2', 'heading_path': ['الباب الثاني'], 'body': 'نص'}]}], ensure_ascii=False))
    told = []
    assert tables.give_back(log=told.append) == {'rows': 1, 'files': 2}
    assert told == ["1 table rows given back to the article above; 2 issues' texts.json kept in step"]
    second, third, fourth = Article.objects.filter(version=v).order_by('order')
    assert second.body.endswith('| 1000 | 2857 يوما فما فوق |') and third.heading_path == []
    assert fourth.heading_path == ['الباب الثاني: أحكام ختامية'] and fourth.body == 'يعمل به.' and third.body == 'ينسخ المرسوم.'
    saved = json.loads((work / 'texts.json').read_text())[0]['articles']
    assert saved[0]['body'].endswith('2857 يوما فما فوق |') and saved[1]['heading_path'] == []
    assert json.loads((work / 'texts.before-rows.json').read_text())[0]['articles'][1]['heading_path'] == [
        '| 1000 | 2857 يوما فما فوق |']
    assert (again / 'texts.before-rows.json').read_text() == '[]'
    assert json.loads((again / 'texts.json').read_text())[0]['articles'][0]['body'] == '| 1 | 2 |\n| 3 | 4 |'
    assert not (still / 'texts.before-rows.json').exists()
