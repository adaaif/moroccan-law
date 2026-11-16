"""A text's links as its page shows them (`services/links.py`): the text that repealed it named, each text that
changed it once with its articles and verbs, what it cites (its other kinds of mention aside), and each article with
the texts that cite it and apply it, once each."""
from datetime import date

import pytest

from apps.consolidation.models import Change
from apps.corpus.models import Article, Consolidation, Mention, Text, Version

pytestmark = pytest.mark.django_db
ME = '/akn/ma/act/loi/65-99'


def law(uri, title, *numbers):
    t = Text.objects.create(akn_uri=uri, type='law', number=uri.rsplit('/', 1)[1], title_ar=title, signed_on=date(2003, 9, 11))
    v = Version.objects.create(text=t, language='ar', valid_from=date(2004, 6, 8), consolidation=Consolidation.AS_PUBLISHED)
    for k, n in enumerate(numbers, 1):
        Article.objects.create(version=v, order=k, label=f'المادة {n}', number=n, eid=f'art_{n}', body=f'نص {n}.')
    return t


def change(by, number, verb, on=date(2020, 1, 1)):
    return Change.objects.create(text_uri=ME, number=number, verb=verb, source=Change.Source.READING, by_kind='law',
                                 by_number=by.rsplit('/', 1)[1], by_uri=by, state=Change.State.READ, published_on=on,
                                 effective_on=on)


def mention(src, to, kind, number='', eid='art_1'):
    Mention.objects.create(from_uri=src, from_eid=eid, words='المادة', kind=kind, to_uri=to, to_number=number,
                           state='resolved')


def test_a_texts_page_names_what_repealed_it_what_changed_it_and_who_cites_and_applies_its_articles(api):
    law(ME, 'القانون رقم 65.99 المتعلق بمدونة الشغل', '5', '6')
    law('/akn/ma/act/loi/12-20', 'القانون رقم 12.20 بتغيير مدونة الشغل', '1')
    law('/akn/ma/act/loi/30-25', 'القانون رقم 30.25 بنسخ مدونة الشغل', '1')
    law('/akn/ma/act/loi/18-12', 'القانون رقم 18.12 المتعلق بالتعويض عن حوادث الشغل')
    change('/akn/ma/act/loi/12-20', '5', 'modified')
    change('/akn/ma/act/loi/12-20', '6', 'modified')
    change('/akn/ma/act/loi/12-20', '', 'completed')
    change('/akn/ma/act/loi/30-25', '', 'repealed', date(2025, 1, 1))
    decree = law('/akn/ma/act/decret/2-04-469', 'مرسوم رقم 2.04.469 بتطبيق مدونة الشغل').akn_uri
    mention(decree, ME, Mention.Kind.CITES, '5', 'art_2')
    mention(decree, ME, Mention.Kind.CITES, '5', 'art_2')          # cited twice from one article: listed once
    mention(decree, ME, Mention.Kind.APPLIES, '6', 'art_1')
    mention(decree, ME, Mention.Kind.APPLIES, '6', 'art_3')
    mention(ME, '/akn/ma/act/loi/18-12', Mention.Kind.CITES)
    mention(ME, '/akn/ma/act/loi/18-12', Mention.Kind.REDIRECTS)   # not a citation of it

    r = api.get('/api/corpus/at/ma/loi/65-99/?window=10').json()
    standing = r['standing']
    assert standing['status'] == 'repealed' and standing['repealed']['by']['path'] == '/ma/loi/30-25'
    [by] = [row for row in r['amended_by'] if row['by']['path'] == '/ma/loi/12-20']
    assert (sorted(by['articles']), sorted(by['verbs']), by['whole']) == (['5', '6'], ['completed', 'modified'], True)
    assert [(c['to']['path'], c['count']) for c in r['cites']] == [('/ma/loi/18-12', 1)]
    assert [(row['from']['path'], row['articles']) for row in r['applied_by']] == [('/ma/decret/2-04-469', ['6'])]
    art5, art6 = r['articles']
    assert [(x['from']['path'], x['eid']) for x in art5['cited_by']] == [('/ma/decret/2-04-469', 'art_2')]
    assert [x['eid'] for x in art6['applied_by']] == ['art_1', 'art_3'] and art6['cited_by'] == []
