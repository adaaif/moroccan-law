"""3. apply (`engine.rebuild`): each change put into the articles of the version before it — words swapped, an article
repealed or added — or refused with the reason a person reads; and a text rebuilt through its changes, weighed against
the witnesses (the SGG's notes and later wording, the model's own list), into dated machine versions."""
import datetime
import json

import pytest
from django.utils import timezone

from apps.consolidation.models import Change, Doubt
from apps.consolidation.services import engine, fill
from apps.consolidation.tests.test_links import text
from apps.corpus.models import Article, Version
from apps.sources.models import Document


def rows(*pairs):
    return [{'key': k, 'label': f'المادة {k}', 'eid': f'art_{k}', 'body': body, 'heading_path': [], 'page': 3}
            for k, body in pairs]


def change(verb, number='', wording=(), **detail):
    return Change(text_uri='/akn/ma/act/loi/2-00', number=number, verb=verb, wording=list(wording),
                  by_uri='/akn/ma/act/loi/13-26', detail=detail)


def test_a_swap_of_words_changes_its_article_or_every_article_and_is_refused_where_the_words_are_not():
    arts = rows(('1', 'يعد منتج مسجل صوتي كل شخص.'), ('2', 'يتمتع منتج مسجل صوتي بحق.'))
    engine.apply(arts, change('words', '1', pairs=[['منتج مسجل صوتي', 'منتج تسجيل صوتي']]))
    assert [r['body'] for r in arts] == ['يعد منتج تسجيل صوتي كل شخص.', 'يتمتع منتج مسجل صوتي بحق.']
    engine.apply(arts, change('words', pairs=[['منتج مسجل\nصوتي', 'منتج التسجيل الصوتي'], ['تسجيل صوتي', 'تسجيل سمعي']]))
    assert [r['body'] for r in arts] == ['يعد منتج تسجيل سمعي كل شخص.', 'يتمتع منتج التسجيل الصوتي بحق.']
    with pytest.raises(fill.Unplaced, match=r'^words_not_found$'):
        engine.apply(arts, change('words', '2', pairs=[['المصنف السمعي', 'المصنف']]))


def test_an_article_repealed_reads_as_repealed_and_a_part_or_a_missing_one_is_refused():
    arts = rows(('3', 'نص.'), ('4', 'نص.'))
    engine.apply(arts, change('repealed', '3'))
    assert [r['body'] for r in arts] == ['(نسخت)', 'نص.']
    with pytest.raises(fill.Unplaced, match=r'^part$'):
        engine.apply(arts, change('repealed', '4', part=['الفقرة', [2]]))
    with pytest.raises(fill.Unplaced, match=r'^article_missing$'):
        engine.apply(arts, change('repealed', '9'))
    engine.apply(arts, change('repealed'))                       # the whole text
    assert [r['body'] for r in arts] == ['(نسخت)', '(نسخت)']


def test_an_added_article_goes_after_the_one_it_is_numbered_from_or_last():
    arts = rows(('7', 'نص 7.'), ('7-1', 'نص 7-1.'), ('8', 'نص 8.'))
    engine.apply(arts, change('added', '7-2', ['يحدد', 'بمرسوم.'], label='المادة 7-2'))
    engine.apply(arts, change('added', '12', ['نص المادة الجديدة.']))
    assert [(r['key'], r['label'], r['eid'], r['body'], r['page']) for r in arts[2:4] + arts[-1:]] == [
        ('7-2', 'المادة 7-2', 'art_7-2', 'يحدد بمرسوم.', None), ('8', 'المادة 8', 'art_8', 'نص 8.', 3),
        ('12', '12', 'art_12', 'نص المادة الجديدة.', None)]
    # An «added» article the version holds already is rewritten.
    engine.apply(arts, change('added', '8', ['نص 8 الجديد.']))
    assert arts[3]['body'] == 'نص 8 الجديد.' and len(arts) == 5


@pytest.mark.parametrize('part', [['الفقرة', [4]], ['الفقرة', [1, 3]], ['البند', [2]]])
def test_a_part_the_article_cannot_give_is_refused(part):
    arts = rows(('5', 'الفقرة الأولى.\nالفقرة الثانية.\nالفقرة الثالثة.'))
    with pytest.raises(fill.Unplaced, match=r'^part$'):
        engine.apply(arts, change('modified', '5', ['نص جديد.'], part=part))
    assert arts[0]['body'] == 'الفقرة الأولى.\nالفقرة الثانية.\nالفقرة الثالثة.'


BASE = '/akn/ma/act/loi/2-00'
ADDED = ['تحدد كيفيات تطبيق هذه المادة بمرسوم يتخذ باقتراح من الوزير المكلف.',
         'ويجب أن ينشر المرسوم في أجل ستة أشهر من تاريخ نشر هذا القانون.']
SIX_2026 = 'يحدد السعر بمرسوم يصدر كل سنة في الجريدة الرسمية للمملكة.'
ONE_AUGUST = 'يعد منتج تسجيل صوتي كل شخص طبيعي أو معنوي يتولى التثبيت الأول للأصوات.'
ONE_2026 = 'يعد منتج التسجيل الصوتي كل شخص ذاتي أو اعتباري يتولى التثبيت الأول للأصوات.'


def base_text():
    return text(BASE, 'law', '2-00', 'القانون رقم 2.00 المتعلق بحقوق المؤلف', datetime.date(2000, 5, 18), [
        ('المادة 1', 'يعد منتج مسجل صوتي كل شخص طبيعي أو معنوي.'), ('المادة 2', 'تحمى المصنفات الأدبية.\n'
                                                                    'وتحمى المصنفات الفنية.\nوتحمى المصنفات العلمية.'),
        ('المادة 3', 'تحمى المصنفات المشتقة.'), ('المادة 5', 'تحدد مدة الحماية في خمسين سنة.'),
        ('المادة 6', 'يحدد السعر بمرسوم.'), ('المادة 7', 'نص المادة السابعة.'), ('المادة 8', 'نص المادة الثامنة.')],
        number_issue=4796)


def sgg_version(target, as_of, articles):
    doc = Document.objects.create(source='sgg_consolidated', kind='consolidated_text', sha256='5' * 64, path='2_00.pdf',
                                  mime='application/pdf', language='ar', bytes=1, page_count=1, fetched_at=timezone.now(),
                                  meta={'as_of': as_of})
    v = Version.objects.create(text=target, language='ar', valid_from=datetime.date(2026, 8, 20), consolidation='sgg',
                               source_document=doc)
    Article.objects.bulk_create([Article(version=v, order=k, label=f'المادة {n}', number=n, eid=f'art_{n}', body=body)
                                 for k, (n, body) in enumerate(articles, 1)])


@pytest.mark.django_db
def test_changes_are_weighed_against_their_witnesses_and_applied_day_by_day(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    target = base_text()
    first = text('/akn/ma/act/loi/13-26', 'law', '13-26', 'قانون رقم 13.26 بتغيير وتتميم القانون رقم 2.00',
                 datetime.date(2026, 8, 10), [
                     ('المادة الأولى', 'تحل عبارتا «منتج تسجيل صوتي» و«المصنفات الرقمية»، على التوالي، محل عبارتي '
                                       '«منتج مسجل صوتي» و«المصنفات الأدبية» في المادتين 1 و2 من القانون رقم 2.00.'),
                     ('المادة 2', 'تنسخ أحكام المادة 3 من القانون رقم 2.00.'),
                     ('المادة 3', 'يتمم القانون رقم 2.00 بالمادة 7.1 التالية :\n«المادة 7.1. - ' + ADDED[0] + '\n«' + ADDED[1] + '»'),
                     ('المادة 4', 'تغير أحكام المادة 5 من القانون رقم 2.00 كما يلي :\n«المادة 5. - تحدد مدة الحماية في '
                                  'سبعين سنة تحتسب من وفاة المؤلف.»'),
                     ('المادة 5', 'تغير أحكام المادة 6 من القانون رقم 2.00 كما يلي :\n«المادة 6. - يحدد السعر بقرار '
                                  'للوزير المكلف بالمالية بعد استشارة المجلس.»')])
    second = text('/akn/ma/act/loi/20-26', 'law', '20-26', 'قانون رقم 20.26 بتغيير القانون رقم 2.00',
                  datetime.date(2026, 8, 20), [('المادة الأولى', 'تغير أحكام المادة 1 من القانون رقم 2.00 كما يلي :\n'
                                                                 f'«المادة 1. - {ONE_AUGUST}»'),
                                               ('المادة 2', 'تغير أحكام المادة 6 من القانون رقم 2.00 كما يلي :\n'
                                                            f'«المادة 6. - {SIX_2026}»')], number_issue=7536)
    # The SGG's text of 1 September 2026: it holds the swap (in 20.26's art. 1), the repeal, the added article (one word
    # printed otherwise) and 20.26's art. 6, not 13.26's art. 5; its notes name 13.26 for art. 1.
    sgg_version(target, '2026-09-01', [
        ('1', ONE_AUGUST), ('2', 'تحمى المصنفات الرقمية.\nوتحمى المصنفات الفنية.\n'
                                                                 'وتحمى المصنفات العلمية.'),
        ('3', '(نسخت)'), ('5', 'تحدد مدة الحماية في خمسين سنة.'),
        ('6', SIX_2026), ('7', 'نص المادة السابعة.'), ('7-1', ADDED[0] + '\n' + ADDED[1].replace('ويجب', 'ويتعين')),
        ('8', 'نص المادة الثامنة.')])
    Change.objects.create(text_uri=BASE, number='1', verb='modified', source='sgg', by_kind='law', by_number='013-26')
    # The model's own list of what 13.26 changes (texts.json): art. 3 of 2.00.
    issue = tmp_path / 'reports' / 'issues' / '7533'
    issue.mkdir(parents=True)
    (issue / 'texts.json').write_text(json.dumps([
        {'data': {'number_as_printed': '64.23', 'amends': [{'target_text': 'القانون رقم 2.00', 'target_article': '5'}]}},
        {'data': {'number_as_printed': '13.26', 'amends': [
            {'target_text': 'الجريدة الرسمية عدد 4796', 'target_article': '8'},
            {'target_text': 'القانون رقم 2.00', 'target_article': '3'}, {'target_text': 'القانون', 'target_article': '8'}]}},
    ], ensure_ascii=False))
    third = text('/akn/ma/act/loi/30-26', 'law', '30-26', 'قانون رقم 30.26 بتغيير القانون رقم 2.00',
                 datetime.date(2026, 10, 1), [('المادة الأولى', 'تغير أحكام المادة 1 من القانون رقم 2.00 كما يلي :\n'
                                                                f'«المادة 1. - {ONE_2026}»')], number_issue=7560)
    # Read newest first: the days are applied in their own order whatever the order their texts came in.
    engine.run([third, second, first], log=lambda *_: None)

    def state(by, number):
        c = Change.objects.get(source='reading', by_uri=by.akn_uri, number=number)
        return c.state, c.witnesses, c.placed
    # The title says 13.26 amends 2.00; its note and the SGG's wording bear art. 1's swap out (20.26 rewrote the article
    # after it, so the article as rebuilt that day does not read like the SGG's), the model's list art. 3.
    assert state(first, '1') == ('confirmed', {'title': True, 'sgg': True}, True)
    assert state(second, '1') == ('confirmed', {'title': True, 'sgg': True, 'wording': True}, True)
    # The swap «on each in turn» puts its second pair in art. 2: the SGG's art. 2 holds that pair's new words, and the
    # first pair, which is art. 1's, is not counted against it.
    two = Change.objects.get(source='reading', by_uri=first.akn_uri, number='2')
    assert (two.state, two.witnesses, two.verdict, two.score) == ('confirmed', {'title': True, 'sgg': True, 'wording': True},
                                                                  'agrees', 1.0)
    assert state(first, '3') == ('confirmed', {'title': True, 'model': True, 'sgg': True, 'wording': True}, True)
    # The SGG prints a word otherwise: no witness by its fragments, but the article as rebuilt reads like the SGG's.
    added = Change.objects.get(source='reading', by_uri=first.akn_uri, number='7-1')
    assert (added.state, added.witnesses, added.verdict, added.detail['likeness']) == (
        'confirmed', {'title': True, 'wording': True}, 'partly', 0.958)
    assert state(first, '5') == ('conflict', {'title': True, 'sgg': False}, None)     # the SGG's art. 5 is not it
    # 20.26 changed art. 6 again before the SGG's date: the SGG cannot speak against 13.26's wording of it.
    six = Change.objects.get(source='reading', by_uri=first.akn_uri, number='6')
    assert (six.state, six.witnesses, six.placed, six.detail['likeness']) == ('read', {'title': True}, True, 0.211)
    assert state(second, '6') == ('confirmed', {'title': True, 'sgg': True, 'wording': True}, True)
    assert list(Doubt.objects.values_list('number', 'by_uri', 'reason')) == [('5', first.akn_uri, 'sgg_disagrees')]
    published, august, later, _sgg, october = target.versions.order_by('valid_from', 'consolidation')
    assert (published.valid_to, august.valid_from, august.valid_to, later.valid_from) == (
        datetime.date(2026, 8, 10), datetime.date(2026, 8, 10), datetime.date(2026, 8, 20), datetime.date(2026, 8, 20))
    assert (august.consolidation, later.consolidation) == ('machine', 'machine')
    # 20.26's version is built on 13.26's, whichever was read first.
    assert list(later.articles.order_by('order').values_list('number', 'body')) == [
        ('1', ONE_AUGUST), ('2', 'تحمى المصنفات الرقمية.\nوتحمى المصنفات الفنية.\n'
                                                                 'وتحمى المصنفات العلمية.'),
        ('3', '(نسخت)'), ('5', 'تحدد مدة الحماية في خمسين سنة.'), ('6', SIX_2026), ('7', 'نص المادة السابعة.'),
        ('7-1', '\n'.join(ADDED)), ('8', 'نص المادة الثامنة.')]
    # 30.26 came after the SGG's text: nothing to weigh it against, it is read and applied.
    assert state(third, '1') == ('read', {'title': True}, True)
    assert october.valid_from == datetime.date(2026, 10, 1) and october.articles.get(number='1').body == ONE_2026
    assert october.articles.get(number='6').body == SIX_2026          # built on August's, not on the BO's


@pytest.mark.django_db
def test_an_amending_text_whose_change_cannot_be_placed_is_held_back_whole_and_says_why():
    target = base_text()
    first = text('/akn/ma/act/loi/13-26', 'law', '13-26', 'قانون رقم 13.26 بتغيير القانون رقم 2.00', datetime.date(2026, 8, 10), [
        ('المادة الأولى', 'تحل عبارة «المصنف» محل عبارة «المصنف السمعي» في المادة 1 من القانون رقم 2.00.'),
        ('المادة 2', 'تغير أحكام المادة 9 من القانون رقم 2.00 كما يلي :\n«المادة 9. - نص جديد.»'),
        ('المادة 3', 'تغير أحكام المادة 5 من القانون رقم 2.00 كما يلي :\n«المادة 5. - تحدد الرسوم ............ بقرار.»'),
        ('المادة 4', 'تنسخ أحكام المادة 7 من القانون رقم 2.00.')])
    second = text('/akn/ma/act/loi/20-26', 'law', '20-26', 'قانون رقم 20.26 بتغيير القانون رقم 2.00', datetime.date(2026, 8, 20), [
        ('المادة الأولى', 'تغير أحكام المادة 2 من القانون رقم 2.00 كما يلي :\n«المادة 2. - تحمى المصنفات ............ '
                          'الأدبية والرقمية.»')], number_issue=7536)
    # A person set art. 9 aside already: no doubt is raised for it again.
    Doubt.objects.create(text_uri=BASE, number='9', by_uri=first.akn_uri, reason='unplaced', status='dismissed')
    engine.run([first, second], log=lambda *_: None)
    assert dict(Change.objects.filter(by_uri=first.akn_uri).values_list('number', 'placed')) == {
        '1': False, '9': False, '5': False, '7': False}
    assert sorted(Doubt.objects.filter(status='open').values_list('number', 'by_uri', 'reason', 'detail')) == [
        # 20.26's wording keeps art. 2's first paragraph and drops the two after it with no dots for them.
        ('1', first.akn_uri, 'words_not_found', {'why': 'words_not_found'}),
        ('2', second.akn_uri, 'dropped', {'dropped': 2}),
        ('5', first.akn_uri, 'unplaced', {'why': 'anchor'})]
    # 13.26 is held back whole (art. 7 stays); 20.26 stands on the text as published.
    machine = target.versions.get(consolidation='machine')
    assert machine.valid_from == datetime.date(2026, 8, 20)
    assert dict(machine.articles.values_list('number', 'body'))['2'] == 'تحمى المصنفات الأدبية والرقمية.'
    assert dict(machine.articles.values_list('number', 'body'))['7'] == 'نص المادة السابعة.'
