"""`manage.py proofread`: each way of finding what to put right (the turned words, the words cut in two, letters of
another alphabet, table rows over the next article) and a correction a person found reading, recorded once."""
from datetime import date

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.quality.models import Correction
from apps.sources.models import Document, OcrRun, Page

pytestmark = pytest.mark.django_db


def text_with(uri, consolidation, *bodies, document=None):
    text, _ = Text.objects.get_or_create(akn_uri=uri, defaults={'type': 'law', 'title_ar': 'قانون'})
    v = Version.objects.create(text=text, language='ar', valid_from=date(2020, 1, 1), consolidation=consolidation,
                               source_document=document)
    for k, body in enumerate(bodies, 1):
        Article.objects.create(version=v, order=k, label=f'المادة {k}', number=str(k), eid=f'art_{k}', body=body)
    return v


def test_the_proofreader_proposes_the_turned_words(capsys):
    call_command('proofread')
    assert capsys.readouterr().out == '0 corrections proposed\n'          # nothing to read yet
    # «ثالثة» is a word the BO prints, beside the same neighbour as here: left as it is.
    text_with('/akn/ma/act/loi/70-03', Consolidation.ADALA, 'تخول الحضانة للأم، ثم للأب، ثم ألم الأم.', 'في المرتبة ثالثة')
    text_with('/akn/ma/act/loi/1-26', Consolidation.AS_PUBLISHED, 'لأم الأم', 'النفقة لأم الأب', 'لأم',
              'في المرتبة ثالثة', 'ثلاثة أشهر', 'ثلاثة أيام', 'ثلاثة')
    call_command('proofread')
    assert capsys.readouterr().out == '1 corrections proposed\n'
    c = Correction.objects.get()
    assert (c.path, c.wrong, c.right, c.before, c.after, c.status) == (
        '/ma/loi/70-03/art_1', 'ألم', 'لأم', 'ثم', 'الأم', 'suggested')


def test_split_proposes_the_words_a_stray_space_cut(capsys):
    text_with('/akn/ma/act/loi/65-99', Consolidation.ADALA, 'تطبق على الاستغلالات الفلاحية وتو ابعها.')
    text_with('/akn/ma/act/loi/1-26', Consolidation.AS_PUBLISHED, *['وتوابعها'] * 5)
    call_command('proofread', '--split')
    assert capsys.readouterr().out == '1 words cut in two proposed joined\n'
    assert Correction.objects.get().right == 'وتوابعها'


def test_table_rows_go_back_to_the_article_above(capsys, settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    v = text_with('/akn/ma/act/decret/2-25-265', Consolidation.AS_PUBLISHED, '| 900 | 2856 يوما |', 'ينسخ المرسوم.')
    Article.objects.filter(version=v, number='2').update(heading_path=['| 1000 | 2857 يوما فما فوق |'])
    call_command('proofread', '--table-rows')
    assert capsys.readouterr().out == "1 table rows given back to the article above; 0 issues' texts.json kept in step\n"
    assert Article.objects.get(version=v, number='1').body == '| 900 | 2856 يوما |\n| 1000 | 2857 يوما فما فوق |'


def test_foreign_letters_are_put_right_from_the_pages_second_reading(capsys):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='b' * 64, path='x.pdf', mime='application/pdf',
                                  language='ar', bytes=1, fetched_at=timezone.now())
    kept = 'ينشر هذا المرسوم. وحרר بالرباط في 3 مارس 2025.'
    page = Page.objects.create(document=doc, index=0, printed_number=1525, kind='text', text=kept)
    OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='page-1596', text=kept.replace('وحרר', 'وحرر'))
    text_with('/akn/ma/act/decret/2-25-1', Consolidation.AS_PUBLISHED, kept, document=doc)
    text_with('/akn/ma/act/decret/2-25-2', Consolidation.AS_PUBLISHED, 'وحرر بالرباط', 'وحرر بفاس')
    call_command('proofread', '--foreign')
    assert capsys.readouterr().out == "{'flagged': 1, 'applied': 1}; 1 articles changed\n"
    assert Article.objects.get(version__text__akn_uri='/akn/ma/act/decret/2-25-1').body == kept.replace('وحרר', 'وحرر')


def test_a_correction_found_reading_is_recorded_once(capsys):
    call_command('proofread', '--add', '/ma/loi/70-03/art_400', 'لا تممت عين', 'المتمتعين', '--before', 'الفتاة',
                 '--after', 'بقواهما')
    call_command('proofread', '--add', '/ma/loi/70-03/art_400', 'لا تممت عين', 'المتمتعين', '--before', 'الفتاة',
                 '--after', 'بقواهما')
    c = Correction.objects.get()
    assert (c.before, c.after, c.source, c.status) == ('الفتاة', 'بقواهما', 'review', 'suggested')
    assert capsys.readouterr().out.splitlines() == [f'proposed: {c}', f'already proposed: {c}']
