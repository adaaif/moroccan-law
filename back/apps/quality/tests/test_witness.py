"""A7 of the consumer plan: the BO's reading of a text set beside a second copy (Adala's or the SGG's), article by
article; the articles the law changed between the two copies are set apart."""
import json
from datetime import date

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.consolidation.models import Change
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.parliament.tests.pdfs import write_pdf
from apps.quality.services.witness import changed_between, compare
from apps.sources.models import Issue

pytestmark = pytest.mark.django_db

URI = '/akn/ma/act/loi/31-08'
LETTERS = 'بتثجحخدذرزسشصضطظعغفقكلمن'
# Words of four letters, each its own: an article of a hundred of them is 400 letters.
WORDS = [f'م{a}{b}ل' for a in LETTERS for b in LETTERS]


def article(*words):
    return ' '.join(words)


LONG = WORDS[:100]
# The witness holds one word more, of eight letters: its words agree at 0.995 and its letters at 0.981, so the two copies
# agree by their words although their letters, spaces left out, differ by more than 1.5 %.
LONG_MORE = LONG[:50] + ['مستهلكين'] + LONG[50:]
# A word the layer cut in two: few words agree, every letter does.
SPLIT_BO = article(*WORDS[100:110], 'مب', 'تل', *WORDS[110:118])
SPLIT_W = article(*WORDS[100:110], 'مبتل', *WORDS[110:118])
# Eight words a letter apart in a hundred: 0.92 of the words, 2 % of the letters.
DOTS = WORDS[200:300]
DOTS_W = [w[:-1] + 'ن' if k % 13 == 0 else w for k, w in enumerate(DOTS)]
SIGNED = 'ينشر هذا القانون بالجريدة الرسمية.'
# Fourteen words apart in forty: the runs each side alone holds are listed twelve at most.
MANY = WORDS[400:440]
MANY_W = [w[:-1] + 'ن' if k % 3 == 0 else w for k, w in enumerate(MANY)]

BO = [('1', 'نص المادة الأولى كما هو'), ('2', article(*LONG)), ('3', SPLIT_BO), ('4', article(*DOTS)),
      ('5', article(*WORDS[300:340])), ('6', 'يعاقب بغرامة من ألف درهم'), ('7', 'يحدد بنص تنظيمي أجل الإرجاع'),
      ('8', 'تطبق العقوبة على المورد'), ('9', 'يمنع البيع بالتخفيض'), ('10', 'مادة لا يحملها الشاهد'), ('12', SIGNED),
      ('13', article(*MANY))]
WITNESS = [('1', 'نص المادة الأولى كما هو'), ('2', article(*LONG_MORE)), ('3', SPLIT_W), ('4', article(*DOTS_W)),
           # The columns read in the other order: every word is there, in another place.
           ('5', article(*WORDS[320:340], *WORDS[300:320])), ('6', 'يعاقب بغرامة من ألفي درهم'),
           ('7', 'يحدد بنص تنظيمي أجل الاسترجاع'), ('8', 'تطبق العقوبة على المهني'), ('9', 'يمنع البيع بالتخفيضات'),
           ('11', 'مادة لا يحملها الجريدة'),
           ('12', f'{SIGNED}\nوحرر بالرباط في 14 من ربيع الأول 1432 (18 فبراير 2011).\nالإمضاء: فلان.'),
           ('13', article(*MANY_W))]


def version(text, consolidation, day, articles, pages=''):
    v = Version.objects.create(text=text, language='ar', valid_from=day, consolidation=consolidation, source_pages=pages)
    for k, (n, body) in enumerate(articles, 1):
        Article.objects.create(version=v, order=k, label=f'المادة {n}', number=n, eid=f'art_{n}', body=body)
    return v


def amending(number, day):
    issue = Issue.objects.create(edition='general_ar', number=number, date=day)
    text = Text.objects.create(akn_uri=f'/akn/ma/act/loi/{number}-00', type='law', number=f'{number}-00',
                               first_published_in=issue)
    return text.akn_uri


def change(number, by_uri=''):
    Change.objects.create(text_uri=URI, number=number, verb='modified', source='sgg', by_kind='law', by_number='x',
                          by_uri=by_uri)


@pytest.fixture
def consumer():
    text = Text.objects.create(akn_uri=URI, type='law', number='31-08', title_ar='القانون رقم 31.08')
    # Made first, so neither copy is chosen by the order rows were made in: a later printing and an older Adala copy.
    version(text, Consolidation.AS_PUBLISHED, date(2012, 1, 1), [])
    version(text, Consolidation.ADALA, date(2016, 1, 1), [])
    version(text, Consolidation.AS_PUBLISHED, date(2011, 4, 7), BO, pages='1072-1093')
    version(text, Consolidation.ADALA, date(2020, 1, 1), WITNESS)
    change('6', amending(6000, date(2015, 5, 1)))         # between the two copies
    change('7')                                           # by a text the site does not hold: its day is unknown
    change('8', amending(5932, date(2011, 4, 7)))         # on the BO's own day: already in it
    change('9', amending(6840, date(2020, 1, 1)))         # on the witness's day: in it
    change('4', amending(6950, date(2021, 1, 1)))         # after the witness: in neither
    return text


def test_the_articles_changed_between_the_two_copies_are_those_the_law_changed(consumer):
    held = Text.objects.create(akn_uri='/akn/ma/act/loi/1-00', type='law', number='1-00')        # held, no first issue
    change('10', held.akn_uri)
    assert changed_between(consumer, date(2011, 4, 7), date(2020, 1, 1)) == {'6', '7', '9', '10'}


def test_each_article_is_set_beside_the_witness(consumer):
    r = compare(consumer)
    status = {row['number']: row['status'] for row in r['rows']}
    assert status == {'1': 'agree', '2': 'agree', '3': 'agree', '4': 'differ', '5': 'differ', '6': 'changed',
                      '7': 'changed', '8': 'differ', '9': 'changed', '10': 'only_bo', '12': 'agree', '13': 'differ',
                      '11': 'only_witness'}
    assert (r['articles'], r['compared'], r['agree'], r['share'], r['changed'], r['only_bo'], r['only_witness']) == (
        13, 8, 4, 0.5, 3, 1, 1)
    assert r['base'] == {'consolidation': 'as_published', 'from': '2011-04-07', 'pages': '1072-1093'}
    assert r['witness'] == {'consolidation': 'adala', 'from': '2020-01-01'}
    rows = {row['number']: row for row in r['rows']}
    assert (rows['2']['f1'], rows['2']['cer'], rows['2']['bo_only']) == (0.995, 0.0177, [])
    assert rows['5']['f1'] == 1.0 and rows['5']['cer'] > 0.03                  # every word, in another order
    assert (rows['4']['f1'], rows['4']['cer']) == (0.92, 0.016)
    assert (rows['8']['bo_only'], rows['8']['witness_only']) == (['المورد'], ['المهني'])
    assert (rows['6']['bo_only'], rows['6']['witness_only']) == (['الف'], ['الفي'])
    assert (len(rows['13']['bo_only']), rows['13']['bo_only'][-1], rows['13']['witness_only'][0]) == (
        12, MANY[33], MANY_W[0])
    assert rows['10'] == {'number': '10', 'label': 'المادة 10', 'status': 'only_bo', 'f1': 0.0, 'cer': 0.0,
                          'bo_only': [], 'witness_only': []}
    # A change to the whole text: whatever differs, the law did.
    Change.objects.create(text_uri=URI, number='', verb='modified', source='sgg', by_kind='law', by_number='y',
                          by_uri=amending(6500, date(2016, 9, 1)))
    again = compare(consumer)
    assert (again['compared'], again['share'], again['changed']) == (4, 1.0, 7)


def test_a_text_without_one_of_its_copies_says_which(consumer):
    alone = Text.objects.create(akn_uri='/akn/ma/act/loi/9-26', type='law', number='9-26')
    version(alone, Consolidation.ADALA, date(2020, 1, 1), [('1', 'نص')])
    assert compare(alone) == {'text': '/akn/ma/act/loi/9-26', 'error': 'no as_published version'}
    assert compare(consumer, witness='sgg') == {'text': URI, 'error': 'no sgg version'}


def test_two_copies_that_share_no_article_have_no_share(settings, tmp_path, capsys):
    settings.CORPUS_DIR = tmp_path
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/9-27', type='law', number='9-27')
    version(text, Consolidation.AS_PUBLISHED, date(2019, 1, 1), [('1', 'نص')])
    version(text, Consolidation.ADALA, date(2020, 1, 1), [('2', 'نص')])
    assert (compare(text)['compared'], compare(text)['share']) == (0, None)
    call_command('witness', text.akn_uri, '--min', '0.9')                  # nothing compared: no failure
    assert capsys.readouterr().out == (
        '/akn/ma/act/loi/9-27: 0/0 articles agree (0.0 %), 0 changed since, 1 only in the BO, 1 only in adala\n')


def test_the_command_prints_the_share_keeps_the_report_and_fails_below_its_floor(consumer, settings, tmp_path, capsys):
    settings.CORPUS_DIR = tmp_path
    call_command('witness', URI, '--show', '2')
    out = capsys.readouterr().out.splitlines()
    assert out[0] == (f'{URI}: 4/8 articles agree (50.0 %), 3 changed since, 1 only in the BO, 1 only in adala')
    # The first two differing articles, each with the words each side alone holds.
    # Art. 4 differs in eight places: three of each side's words are shown.
    assert len(out) == 3 and out[1] == (
        f'   المادة 4: F1 0.92, CER 0.016 · as_published alone «{DOTS[0]} | {DOTS[13]} | {DOTS[26]}»'
        f' · adala alone «{DOTS_W[0]} | {DOTS_W[13]} | {DOTS_W[26]}»')
    assert out[2].startswith('   المادة 5: F1 1.0, CER ')
    kept = json.loads((tmp_path / 'reports' / 'witness' / 'akn_ma_act_loi_31-08.as_published-adala.json').read_text())
    assert kept['agree'] == 4 and len(kept['rows']) == 13
    with pytest.raises(CommandError, match=f'below 60%: {URI}'):
        call_command('witness', URI, '--min', '0.6')
    call_command('witness', URI, '--min', '0.5')              # at its floor: no failure


def test_the_command_says_what_it_cannot_compare_and_goes_on(consumer, settings, tmp_path, capsys):
    settings.CORPUS_DIR = tmp_path
    alone = Text.objects.create(akn_uri='/akn/ma/act/loi/9-26', type='law', number='9-26')
    version(alone, Consolidation.ADALA, date(2020, 1, 1), [('1', 'نص')])
    with pytest.raises(CommandError, match=f'below 90%: {URI}$'):
        call_command('witness', alone.akn_uri, URI, '--min', '0.9', '--show', '0')
    out = capsys.readouterr().out.splitlines()
    assert out == ['/akn/ma/act/loi/9-26: no as_published version',
                   f'{URI}: 4/8 articles agree (50.0 %), 3 changed since, 1 only in the BO, 1 only in adala']
    with pytest.raises(CommandError, match='/akn/ma/act/loi/99-99: not in the corpus'):
        call_command('witness', '/akn/ma/act/loi/99-99')


def test_adalas_own_file_witnesses_a_text_whose_bo_version_took_its_place(settings, tmp_path, capsys):
    """Decree 2.12.503 (24 Oct 2026): the BO's version replaced Adala's of the same day, so Adala's PDF is read again."""
    settings.CORPUS_DIR = tmp_path
    text = Text.objects.create(akn_uri='/akn/ma/act/decret/2-12-503', type='decree', number='2-12-503')
    version(text, Consolidation.AS_PUBLISHED, date(2013, 2, 4),
            [('1', 'تطبق أحكام هذا المرسوم على جميع المنتوجات والسلع المعروضة للبيع'),
             ('2', 'يحدد بنص تنظيمي شكل الفاتورة وبياناتها')])
    write_pdf(tmp_path / 'sources' / 'adala' / 'decree.pdf',
              [['صيغة محينة بتاريخ 3 يناير 2020', 'المادة 1',
                'تطبق أحكام هذا المرسوم على جميع المنتوجات والسلع المعروضة للبيع', 'المادة 2',
                'يحدد بنص تنظيمي شكل الفواتير وبياناتها']], rtl=True)
    call_command('witness', text.akn_uri, '--file', 'sources/adala/decree.pdf')
    out = capsys.readouterr().out
    assert out.startswith(f'{text.akn_uri}: 1/2 articles agree (50.0 %), 0 changed since')
    kept = json.loads((tmp_path / 'reports' / 'witness' / 'akn_ma_act_decret_2-12-503.as_published-adala.json').read_text())
    assert kept['witness'] == {'consolidation': 'adala', 'from': '2020-01-03',
                               'file': str(tmp_path / 'sources' / 'adala' / 'decree.pdf')}
    assert [(r['number'], r['bo_only'], r['witness_only']) for r in kept['rows']] == [
        ('1', [], []), ('2', ['الفاتوره'], ['الفواتير'])]
