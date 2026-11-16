"""The constitution's pages (the constitution review, 25 Oct 2026): /constitution/1996/19 is article 19 of the one in
force in 1996, the citation people write, the short history with each one's facts."""
from datetime import date

import pytest

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.services.citing import citation_ar
from apps.corpus.services.constitutions import by_uri

URIS = {c['year']: c['uri'] for c in by_uri().values()}


def make(year: int, number: str, status: str = 'repealed') -> Text:
    t = Text.objects.create(akn_uri=URIS[year], type='dahir', number=number, number_as_printed=number,
                            title_ar=f'دستور {year}', status=status)
    Version.objects.create(text=t, language='ar', valid_from=date(year, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    return t


@pytest.mark.django_db
def test_a_year_and_an_article_lead_to_the_constitution_in_force_that_year(client):
    make(1996, '1.96.157')
    make(2011, '1.11.91', 'in_force')
    get = lambda q: client.get(f'/api/corpus/constitution/{q}')
    assert get('?year=1996&article=19').json() == {'path': '/ma/dahir/1-96-157/art_19'}
    assert get('?year=1999').json() == {'path': '/ma/dahir/1-96-157'}
    assert get('').json() == {'path': '/ma/dahir/1-11-91'}
    assert get('?year=2011&article=180').json() == {'path': '/ma/dahir/1-11-91/art_180'}
    r = get('?year=1950')
    assert r.status_code == 404 and r.json() == {'errors': [{'field': 'year', 'code': 'not_found'}]}
    assert get('?year=1980').status_code == 404                 # 1972's, not loaded here


@pytest.mark.django_db
def test_a_constitution_is_cited_as_people_cite_it(client):
    t = make(2011, '1.11.91', 'in_force')
    old = make(1996, '1.96.157')
    a = Article.objects.create(version=t.versions.get(), eid='art_19', label='الفصل 19', number='19', order=19, body='…')
    assert citation_ar(t, a) == 'الفصل 19 من الدستور، الجريدة الرسمية عدد 5964 مكرر بتاريخ 30 يوليوز 2011'
    assert citation_ar(t).startswith('دستور المملكة المغربية، الجريدة الرسمية عدد 5964 مكرر')
    assert citation_ar(old).startswith('دستور 1996، الجريدة الرسمية عدد')
    chapters = client.get('/api/corpus/constitution/history/').json()['chapters']
    assert [(c['year'], c['current'], c['path']) for c in chapters] == [(1996, False, '/ma/dahir/1-96-157'),
                                                                          (2011, True, '/ma/dahir/1-11-91')]
    assert chapters[1]['referendum'] == '2011-07-01' and chapters[1]['story']['ar']


@pytest.mark.django_db
def test_an_article_is_followed_through_the_constitutions_the_machine_is_sure_of(client, monkeypatch):
    from apps.corpus.services import constitutions

    old, new = make(1996, '1.96.157'), make(2011, '1.11.91', 'in_force')
    for t, eid, body in [(old, 'art_23', 'شخص الملك مقدس لا تنتهك حرمته.'), (old, 'art_8', 'الرجل والمرأة متساويان.'),
                         (new, 'art_46', 'شخص الملك لا تنتهك حرمته، وللملك واجب التوقير والاحترام.'),
                         (new, 'art_20', 'الحق في الحياة هو أول الحقوق لكل إنسان.'),
                         (new, 'art_19', 'يتمتع الرجل والمرأة، على قدم المساواة، بالحقوق.')]:
        Article.objects.create(version=t.versions.get(), eid=eid, label=f'الفصل {eid[4:]}', number=eid[4:],
                               order=int(eid[4:]), body=body)
    monkeypatch.setattr(constitutions, '_lineage', lambda: {'checked': '', 'pairs': {'2011': {'from': 1996, 'links': {
        'art_46': ['art_23', 'changed', 0.71, 0.5], 'art_20': ['', 'none', 0.5, 0.1],
        'art_19': ['art_8', 'unsure', 0.72, 0.1]}}}})
    got = client.get('/api/corpus/constitution/lineage/?path=/ma/dahir/1-96-157/art_23').json()
    assert [(r['year'], r['label'], r['here'], r['state']) for r in got['rows']] == [
        (1996, 'الفصل 23', True, ''), (2011, 'الفصل 46', False, 'changed')]
    assert ['-', 'مقدس'] in got['rows'][1]['diff'] and got['before'] is None and got['checked'] == ''
    assert client.get('/api/corpus/constitution/lineage/?path=/ma/dahir/1-11-91/art_20').json()['before'] == {
        'year': 1996, 'state': 'none'}
    unsure = client.get('/api/corpus/constitution/lineage/?path=/ma/dahir/1-11-91/art_19').json()
    assert len(unsure['rows']) == 1 and unsure['before'] == {'year': 1996, 'state': 'unsure'}
    assert len(client.get('/api/corpus/constitution/lineage/?path=/ma/dahir/1-96-157/art_8').json()['rows']) == 1
    assert client.get('/api/corpus/constitution/lineage/?path=/ma/loi/52-05/art_1').status_code == 404


@pytest.mark.django_db
def test_the_constitutions_pages_cost_the_same_whatever_they_hold(client, django_assert_max_num_queries):
    for year, number in [(1962, '—'), (1970, '1.70.177'), (1972, '1.72.061'), (1992, '1.92.155'), (1996, '1.96.157')]:
        make(year, number)
    make(2011, '1.11.91', 'in_force')
    with django_assert_max_num_queries(2):
        client.get('/api/corpus/constitution/history/')
    with django_assert_max_num_queries(2):
        client.get('/api/corpus/constitution/lineage/?path=/ma/dahir/1-11-91/art_19')


@pytest.mark.django_db
def test_a_revision_puts_its_paragraph_in_and_a_replaced_constitution_keeps_its_last_words():
    # C10: 1980's art. 21 (BO 3523 bis), then 1992's whole-text repeal: the text reads as revised, never «(نسخت)».
    from apps.consolidation.models import Change, Verb
    from apps.consolidation.services import engine

    t = make(1972, '1.72.061')
    t.type = 'constitution'
    t.save()
    Article.objects.create(version=t.versions.get(), order=1, label='الفصل 21', number='21', eid='art_21',
                           body='يعتبر الملك غير بالغ سن الرشد قبل نهاية السنة الثامنة عشرة من عمره.\nقواعد سير مجلس الوصاية تحدد بقانون تنظيمي.')
    common = dict(text_uri=t.akn_uri, source=Change.Source.READING, by_kind='dahir', state=Change.State.READ)
    Change.objects.create(**common, number='21', verb=Verb.MODIFIED, by_number='1-80-271', by_uri='/akn/ma/act/dahir/1-80-271',
                          published_on=date(1980, 5, 9), effective_on=date(1980, 6, 3), detail={'part': ['الفقرة', [1]]},
                          wording=['يعتبر الملك غير بالغ سن الرشد قبل نهاية السنة السادسة عشرة من عمره.'])
    Change.objects.create(**common, number='', verb=Verb.REPEALED, by_number='1-92-155', by_uri=URIS[1992],
                          published_on=date(1992, 10, 14), effective_on=date(1992, 10, 14))
    _changes, doubts, stats = engine.apply_to(t, set())
    assert stats['versions'] == 1 and not doubts
    latest = t.latest_version()
    assert (latest.valid_from, latest.consolidation) == (date(1980, 6, 3), Consolidation.MACHINE)
    assert latest.articles.get().body == ('يعتبر الملك غير بالغ سن الرشد قبل نهاية السنة السادسة عشرة من عمره.\n'
                                          'قواعد سير مجلس الوصاية تحدد بقانون تنظيمي.')
    assert engine.standing(t, date(2026, 10, 25))['status'] == 'repealed'


@pytest.mark.django_db
def test_a_constitutions_own_word_constitution_is_itself_though_signed_before_its_bo():
    from apps.corpus.services.annotate import marks

    t = make(1972, '1.72.061')
    t.signed_on = date(1972, 3, 10)          # its BO, 15 March 1972, is when 1970's stopped being the constitution
    t.save()
    make(1970, '1.70.177')
    a = Article.objects.create(version=t.versions.get(), order=1, label='الفصل 100', number='100', eid='art_100',
                               body='تصير مراجعة الدستور نهائية بعد إقرارها بالاستفتاء.')
    hrefs = [m.get('href') for m in marks(t, [a], [])['art_100'] if m['kind'] == 'link']
    assert hrefs == ['/ma/dahir/1-72-061']
