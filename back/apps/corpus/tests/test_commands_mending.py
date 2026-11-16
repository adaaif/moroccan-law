"""The commands that put the corpus right, run as an operator runs them: each says what it would change, changes nothing
without --write, and with it writes the rows (and the issue's texts.json where a reload must keep the change)."""
import json
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.corpus.models import Alias, Article, Consolidation, Text, Version
from apps.corpus.tests.test_articles_mended import PAGE, kif_dahir
from apps.corpus.tests.test_records_mended import bo, text
from apps.search.models import SearchEntry
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db


def run(*args, **opts) -> str:
    out = StringIO()
    call_command(*args, stdout=out, **opts)
    return out.getvalue()


def test_mend_records_names_what_it_would_change_and_writes_it_with_the_search_rows():
    issue = bo(1613, date(1943, 9, 24))
    late = text(issue, 1, 'ظهير شريف', ['يعمل به'], signed=date(1943, 11, 8),
                closing='وحرر بالرباط في 9 شعبان عام 1362 الموافق 11 غشت سنة 1943')
    unsigned = text(issue, 2, 'قرار وزيري', ['يعمل به'], signed=date(1943, 12, 1))
    empty = text(issue, 3, 'ظهير شريف ينطبق بموجبه في الامور الجنائية ضابط فريد')
    full = text(issue, 4, 'ظهير شريف ينطبق بموجبه في الأمور الجنائية ضابط فريد', ['تطبق المسطرة الجنائية'] * 6)
    said = run('mend_records')
    assert '1 texts dated after their issue take the day their closing signs; 1 name none' in said
    assert f'  {late.akn_uri}: 1943-11-08 → 1943-08-11' in said and f'  left: {unsigned.akn_uri}' in said
    assert f'1 texts cut twice in one issue\n  {empty.akn_uri} → {full.akn_uri}' in said
    assert Text.objects.get(pk=late.pk).signed_on == date(1943, 11, 8) and Text.objects.filter(pk=empty.pk).exists()

    said = run('mend_records', '--write')
    assert '1 texts cut twice in one issue — folded' in said
    assert Text.objects.get(pk=late.pk).signed_on == date(1943, 8, 11)
    folded = Alias.objects.get(alias=empty.akn_uri)
    assert not Text.objects.filter(pk=empty.pk).exists() and (folded.uri, folded.reason) == (full.akn_uri, 'twin')
    # The kept text is indexed again; the folded one's rows are gone from search.
    full_path = full.akn_uri.replace('/akn/ma/act', '/ma')
    assert SearchEntry.objects.filter(text_path=full_path).exists()
    assert not SearchEntry.objects.filter(text_path=empty.akn_uri.replace('/akn/ma/act', '/ma')).exists()


def test_mend_articles_says_what_can_be_mended_then_mends_it():
    v = kif_dahir(PAGE, [('الفصل الثانى', 'يباشر دفع هذا التعويض مكتب التبغ بمجرد تسلمه تلك المنتوجات')])
    Article.objects.filter(version=v).update(number='')
    said = run('mend_articles')
    assert '1 articles whose label carries a number their row lacked\n' in said
    assert 'missing: 1 of 1 can be mended' in said and 'late: 0 of 0 can be mended' in said
    assert v.articles.count() == 1 and v.articles.get().number == ''

    said = run('mend_articles', '--write')
    assert '1 articles whose label carries a number their row lacked — given' in said and 'missing: 1 of 1 mended' in said
    assert list(v.articles.order_by('order').values_list('eid', 'number')) == [('art_1', '1'), ('art_2', '2')]
    assert SearchEntry.objects.filter(path='/ma/dahir/1-60-138/art_1').exists()


def test_mend_articles_lists_a_text_whose_article_one_its_pages_do_not_show():
    v = kif_dahir('أصدرنا أمرنا الشريف بما يأتي :', [('الفصل الثانى', 'يباشر دفع هذا التعويض')])
    said = run('mend_articles')
    assert 'missing: 0 of 1 can be mended' in said and f'  left: missing: {v.text.akn_uri}' in said
    said = run('mend_articles', '--write')
    assert 'missing: 0 of 1 mended' in said and v.articles.count() == 1


def _glued_issue(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7480, date=date(2026, 2, 23))
    t = Text.objects.create(akn_uri='/akn/ma/act/loi/58-25', type='law', number='58-25', title_ar='قانون رقم 58.25',
                            first_published_in=issue)
    v = Version.objects.create(text=t, language='ar', valid_from=issue.date, consolidation=Consolidation.AS_PUBLISHED)
    body = 'إذا كان تنفيذ السند متوقفا على القيام بعمل.\nالمادة 467\nيبلغ المفوض القضائي السند.'
    Article.objects.create(version=v, order=1, label='المادة 466', number='466', eid='art_466', body=body,
                           heading_path=['الكتاب الخامس'], printed_page=1290)
    Article.objects.create(version=v, order=2, label='المادة 468', number='468', eid='art_468', body='نص.')
    # Neither of these is cut: a heading line with no number of its own, and one that is not the next article's.
    Article.objects.create(version=v, order=3, label='ملحق', number='', eid='annex', body='جدول\nالمادة 2\nسطر')
    Article.objects.create(version=v, order=4, label='المادة 469', number='469', eid='art_469',
                           body='كما ورد في\nالمادة 12\nمن هذا القانون.')
    work = tmp_path / 'reports' / 'issues' / '7480'
    work.mkdir(parents=True)
    (work / 'texts.json').write_text(json.dumps([{'articles': [
        {'label': 'المادة 466', 'body': body}, {'label': 'المادة 468', 'body': 'نص.'}]}], ensure_ascii=False))
    return v, work / 'texts.json'


def test_split_glued_cuts_two_articles_read_as_one_in_the_rows_and_in_texts_json(tmp_path, settings):
    v, saved = _glued_issue(tmp_path, settings)
    said = run('split_glued')
    assert said == '  /akn/ma/act/loi/58-25 المادة 466: «المادة 467» cut out (26 letters)\n1 articles\n'
    assert v.articles.count() == 4

    assert run('split_glued', '--write').endswith('1 articles\n')
    assert list(v.articles.order_by('order').values_list('eid', 'body'))[:3] == [
        ('art_466', 'إذا كان تنفيذ السند متوقفا على القيام بعمل.'), ('art_467', 'يبلغ المفوض القضائي السند.'),
        ('art_468', 'نص.')]
    cut = v.articles.get(eid='art_467')
    assert (cut.label, cut.number, cut.order, cut.heading_path, cut.printed_page) == (
        'المادة 467', '467', 2, ['الكتاب الخامس'], 1290)
    assert list(v.articles.order_by('order').values_list('order', flat=True)) == [1, 2, 3, 4, 5]
    assert [(a['label'], a['body']) for a in json.loads(saved.read_text())[0]['articles']] == [
        ('المادة 466', 'إذا كان تنفيذ السند متوقفا على القيام بعمل.'), ('المادة 467', 'يبلغ المفوض القضائي السند.'),
        ('المادة 468', 'نص.')]


def test_restore_titles_without_write_counts_and_changes_nothing(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=7250, date=date(2023, 11, 23))
    t = Text.objects.create(akn_uri='/akn/ma/act/decret/2-23-350', type='decree', number='2-23-350',
                            number_as_printed='2.23.350', title_ar='بتحديد أشكال إعانة الدولة', first_published_in=issue)
    assert "'unheaded': 1, 'restored': 0, 'no_heading_found': 1" in run('restore_titles')
    assert Text.objects.get(pk=t.pk).title_ar == 'بتحديد أشكال إعانة الدولة'


def test_fold_dahir_numbers_says_what_it_folded():
    Text.objects.create(akn_uri='/akn/ma/act/loi/1-72-184', type='law', number='1-72-184', title_ar='قانون رقم 1.72.184')
    assert run('fold_dahir_numbers') == "  /akn/ma/act/dahir/1-72-184\n{'folded': 0, 'moved': 1}\n"
    assert Text.objects.get().akn_uri == '/akn/ma/act/dahir/1-72-184'


def _decision(number, issue=None, published=True):
    t = Text.objects.create(akn_uri=f'/akn/ma/act/decision/2010/{number.replace(".", "-")}', type='decision',
                            number=number.replace('.', '-'), number_as_printed=number,
                            title_ar=f'قرار لوزير التجهيز والنقل رقم {number} بشأن السياقة')
    if published:
        Version.objects.create(text=t, language='ar', valid_from=date(2010, 9, 30), source_document=issue,
                               consolidation=Consolidation.AS_PUBLISHED)
    return t


def _order(number, issue=None, published=True):
    t = Text.objects.create(akn_uri=f'/akn/ma/act/arrete/{number.replace(".", "-")}', type='order',
                            number=number.replace('.', '-'), title_ar='')
    Version.objects.create(text=t, language='ar', valid_from=date(2010, 9, 30), source_document=issue,
                           consolidation=Consolidation.AS_PUBLISHED if published else Consolidation.ADALA)
    return t


def test_retype_orders_merges_a_waiting_row_folds_a_twin_and_leaves_another_issues_copy():
    from apps.corpus.tests.test_records_mended import bo as bulletin
    one, two = bulletin(5878, date(2010, 9, 30)).document, bulletin(5879, date(2010, 10, 4)).document
    waiting = _order('2701.10', published=False)                    # Adala's copy only: merged into the decision
    moved = _decision('2701.10', one)
    twin = _decision('2702.10', one)
    held = _order('2702.10', one)                                  # the same order from the same issue: the twin goes
    other = _decision('2703.10', two)
    _order('2703.10', one)                                         # from another issue: a person decides
    Text.objects.create(akn_uri='/akn/ma/act/decision/2010/7', type='decision', number='7',
                        title_ar='قرار للهيئة العليا للاتصال السمعي البصري')
    said = run('retype_orders')
    assert said.endswith("{'moved': 0, 'merged': 1, 'twins': 1, 'left': 1}\n")
    assert f'  left: {other.akn_uri} and /akn/ma/act/arrete/2703-10 come from different issues' in said
    assert Text.objects.filter(type='decision').count() == 4                 # a dry run moves nothing

    run('retype_orders', '--write')
    moved.refresh_from_db()
    assert (moved.akn_uri, moved.type) == ('/akn/ma/act/arrete/2701-10', 'order')
    assert not Text.objects.filter(pk=waiting.pk).exists()
    assert Alias.objects.get(alias='/akn/ma/act/decision/2010/2701-10').reason == Alias.Reason.MOVED
    assert moved.versions.filter(consolidation=Consolidation.ADALA).exists()        # the waiting row's version came over
    assert not Text.objects.filter(pk=twin.pk).exists() and Text.objects.filter(pk=held.pk).exists()
    twin_alias = Alias.objects.get(alias='/akn/ma/act/decision/2010/2702-10')
    assert (twin_alias.uri, twin_alias.reason) == (held.akn_uri, Alias.Reason.MERGED)
    assert Text.objects.get(pk=other.pk).type == 'decision'


def test_hijri_months_votes_each_months_first_day_and_writes_the_file(tmp_path, monkeypatch):
    from apps.corpus.services import hijri
    kept = tmp_path / 'hijri_months.json'
    kept.write_text(json.dumps({'1331-9': '1913-08-06', '1300-1': '1800-01-01'}))
    monkeypatch.setattr(hijri, 'FILE', kept)
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=40, date=date(1913, 8, 15), hijri_date='12 رمضان 1331')
    Text.objects.create(akn_uri='/akn/ma/act/dahir/1913/doc', type='dahir', title_ar='ظهير', first_published_in=issue,
                        signed_on=date(1913, 8, 12), signed_on_hijri='9 رمضان 1331')
    also = tmp_path / 'pairs.tsv'
    also.write_text('7556\t1913-08-13\t10 رمضان 1331\n')
    said = run('hijri_months', also=str(also))
    assert '  1300-1: 1800-01-01 is not that month' in said
    assert '3 dated pairs read; 1 months fixed (1331–1331), 0 unsettled, 0 pairs set aside as misprints; ' \
           '0 new, 1 moved beside the file (1 months)' in said
    assert '  1331-9: 1913-08-06 → 1913-08-04' in said
    assert json.loads(kept.read_text()) == {'1331-9': '1913-08-06', '1300-1': '1800-01-01'}

    assert run('hijri_months', '--write').endswith('written: 1 months\n')
    assert json.loads(kept.read_text()) == {'1331-9': '1913-08-04'}


def test_hijri_months_with_no_file_yet_counts_every_month_new(tmp_path, monkeypatch):
    from apps.corpus.services import hijri
    monkeypatch.setattr(hijri, 'FILE', tmp_path / 'data' / 'hijri_months.json')
    Text.objects.create(akn_uri='/akn/ma/act/dahir/1913/doc', type='dahir', title_ar='ظهير',
                        signed_on=date(1913, 8, 12), signed_on_hijri='9 رمضان 1331')
    assert '1 dated pairs read; 0 months fixed, 1 unsettled' in run('hijri_months', '--write')
    assert json.loads((tmp_path / 'data' / 'hijri_months.json').read_text()) == {}


def test_apply_situations_publishes_the_named_drafts_and_refuses_an_unknown_one(tmp_path, monkeypatch):
    from apps.corpus.management.commands import apply_situations
    drafts, approved = tmp_path / 'drafts.json', tmp_path / 'approved.json'
    monkeypatch.setattr(apply_situations, 'DRAFTS', drafts)
    monkeypatch.setattr(apply_situations, 'APPROVED', approved)
    drafts.write_text(json.dumps({'situations': [
        {'slug': 'birth', 'intro': {'ar': 'م', 'fr': 'b'}, 'articles': [], 'draft': True},
        {'slug': 'fired', 'intro': {'ar': 'ط', 'fr': 'f'}, 'articles': []}]}))
    approved.write_text(json.dumps({'situations': [{'slug': 'accident', 'intro': {'ar': 'ح', 'fr': 'a'}, 'articles': []}]}))
    with pytest.raises(CommandError, match='no draft for marriage'):
        call_command('apply_situations', 'birth', 'marriage')
    assert run('apply_situations', 'birth') == '2 situations approved\n'
    published = json.loads(approved.read_text())['situations']
    assert [s['slug'] for s in published] == ['accident', 'birth'] and 'draft' not in published[1]


def test_texts_alike_are_two_when_their_numbers_titles_or_words_say_so():
    issue = bo(1120, date(1934, 4, 13))
    text(bo(1121, date(1934, 4, 20)), 1, 'ظهير شريف في تنظيم مصلحة المياه والغابات', ['نص'])  # alone in its issue
    # Two numbers: two texts, whatever their titles.
    text(issue, 1, 'قرار وزيري في تعيين كاتب نساخ رسميا', ['يعين'], number='12')
    text(issue, 2, 'قرار وزيري في تعيين كاتب نساخ رسميا', ['يعين'], number='13')
    # Titles alike on one page but for a word that is not a spelling: two texts.
    text(issue, 3, 'قرار وزيري بتأسيس اللجنة الجهوية بمدينة مكناس', ['تؤسس لجنة'], page=4)
    text(issue, 4, 'قرار وزيري بتأسيس اللجنة الجهوية بمدينة الرباط', ['تؤسس لجنة'], page=4)
    # One title over the same words but another figure: two texts.
    words = ('يحدد ثمن الخبز في المدن والقرى حسب الوزن والجودة المعتمدة لدى المصالح المختصة طبقا للقوانين الجاري بها '
             'العمل في جميع الجهات والأقاليم')
    text(issue, 5, 'قرار وزيري في تحديد ثمن الخبز بالمدن', [f'{words} 12 فرنكا'])
    text(issue, 6, 'قرار وزيري في تحديد ثمن الخبز بالمدن', [f'{words} 15 فرنكا', 'ينشر'])
    # Too short a title to tell, even over the same words.
    text(issue, 7, 'ظهير شريف', ['يعمل به'])
    text(issue, 8, 'ظهير شريف', ['يعمل به'])
    assert run('mend_records').endswith('0 texts cut twice in one issue\n')
