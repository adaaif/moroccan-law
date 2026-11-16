"""The two posts that read each text's latest Arabic version (a `DISTINCT ON`, PostgreSQL's): «على كل قانون يصوّت عليه
البرلمان» and «15 يوما: الأجل المفضل». They run where the corpus is counted, on PostgreSQL (TEST_DATABASE_URL)."""
from datetime import date

import pytest
from django.db import connection

from apps.blog.services import posts  # noqa: F401  first, as the site loads them
from apps.blog.services import deadlines, parliament
from apps.corpus.models import Consolidation, Status, TextType
from apps.sources.models import Edition

from .rows import article, issue, page, text, version

pytestmark = [pytest.mark.django_db,
              pytest.mark.skipif(connection.vendor != 'postgresql', reason="the latest version is PostgreSQL's DISTINCT ON (TEST_DATABASE_URL)")]


def test_the_laws_are_counted_by_the_hand_that_made_them_and_the_law_in_force_by_its_words():
    """The forms: every text of the Arabic edition in the span, by kind. The hands: a text of the law's rank by the first
    title pattern that matches (tatweel and final yā folded), a decree-law with none still a decree-law. The ratio: decrees
    less the royal decrees «بمثابة قانون», and orders, over the voted laws. The reading: the words of each text not
    repealed in its latest Arabic version, a model's translation and a French version never its latest."""
    y63, y64, y65 = issue(2620, date(1963, 1, 4)), issue(2680, date(1964, 3, 6)), issue(2745, date(1965, 6, 9))
    page(y65, 0, 1080)
    titles = [(y63, TextType.LAW, 'قـانون رقم 1.63 يتعلق بالصحافة'), (y63, TextType.DAHIR, 'ظهير شريف رقم 1.63.2 بتنفيذ القانون رقم 3.63'),
              (y64, TextType.DECREE, 'مرسوم ملكى رقم 267.64 بمثابة قانون'), (y64, TextType.DECREE_LAW, 'مرسوم ملكي رقم 1.64 بمثابة قانون يتعلق'),
              (y65, TextType.DAHIR, 'ظهير شريف بمثابة القانون التنظيمي'), (y65, TextType.DECREE_LAW, 'مرسوم يتعلق بالموظفين'),
              (y65, TextType.DECREE, 'مرسوم بتحديد الأجور'), (y65, TextType.DECREE, 'مرسوم آخر'), (y65, TextType.DECREE, 'مرسوم ثالث'),
              (y65, TextType.DECREE, 'مرسوم رابع'), (y65, TextType.DECREE, 'مرسوم خامس'), (y65, TextType.DECREE, 'مرسوم سادس'),
              (y65, TextType.ORDER, 'قرار لوزير'), (y65, TextType.ORDER, 'قرار آخر'),
              (y65, TextType.ORDER, 'قرار ثالث'), (y65, TextType.CIRCULAR, 'قانون داخلي')]
    made = [text(f'/akn/ma/act/{kind}/{k}', kind, at, title=title) for k, (at, kind, title) in enumerate(titles)]
    # Outside the forms: before and after the span, the French edition.
    text('/akn/ma/act/loi/x-1962', TextType.LAW, issue(2600, date(1962, 6, 1)), title='قانون')
    text('/akn/ma/act/loi/x-1966', TextType.LAW, issue(2800, date(1966, 6, 1)), title='قانون')
    text('/akn/ma/act/loi/x-fr', TextType.LAW, issue(2680, date(1964, 3, 6), edition=Edition.TRANSLATION_FR), title='قانون')
    law, dahir = made[0], made[1]
    version(law, 'كلمة واحدة')
    version(law, 'نص محين من خمس كلمات', consolidation=Consolidation.SGG, valid_from=date(2000, 1, 1))
    version(law, 'ترجمة آلية بكلمات كثيرة جدا هنا', consolidation=Consolidation.TRANSLATION, valid_from=date(2020, 1, 1))
    version(law, 'Une version française plus récente', language='fr', valid_from=date(2021, 1, 1))
    dahir.status = Status.PARTLY_REPEALED
    dahir.save()
    version(dahir, 'ثلاث كلمات هنا')
    made[6].status = Status.REPEALED
    made[6].save()
    version(made[6], 'كلمات كثيرة لا تقرأ')
    version(made[12], 'قرار')
    version(made[15], 'دورية لا تقرأ')
    # The same day twice: the version entered last is the latest.
    organic = text('/akn/ma/act/loi-organique/1-11', TextType.ORGANIC_LAW)
    version(organic, 'أ ب', consolidation=Consolidation.ADALA, valid_from=date(2011, 1, 1))
    version(organic, 'أ ب ج', consolidation=Consolidation.SGG, valid_from=date(2011, 1, 1))
    hands = [{'key': 'rdl', 're': '^مرسوم ملكي.{0,140}بمثابة قانون'}, {'key': 'dfl', 're': '^ظهير شريف.{0,140}بمثابة (ال)?قانون'},
             {'key': 'voted', 're': '^(قانون|القانون)|^(ظهير شريف.{0,140})?بتنفيذ (ال)?قانون'},
             {'key': 'dlaw', 're': '^مرسوم (رقم [0-9.\\- ]+ )?(صادر .{0,90})?بقانون'}]
    meta = {'span': [1963, 1965], 'hands': hands, 'ranks': ['law', 'organic_law', 'decree_law', 'dahir', 'decree'],
            'constitutions': [{'year': 1962, 'issue': 2616, 'bis': True, 'page': 2999, 'akn': '/akn/ma/act/dahir/constitution-1962'}],
            'exception': {'decree': {'issue': 2745, 'page': 1080, 'akn': '/akn/ma/act/decret/136-65'}},
            'reading': {'layers': [{'key': 'laws', 'types': ['law', 'organic_law']}, {'key': 'decrees', 'types': ['dahir', 'decree', 'decree_law']},
                                   {'key': 'orders', 'types': ['order']}]}}
    assert parliament.count(meta) == {
        'forms': {'all': 16, 'law': 1, 'dahir': 2, 'decree': 7, 'decree_law': 2, 'order': 3, 'circular': 1,
                  'hand-voted': 2, 'hand-rdl': 2, 'hand-rdl-decree': 1, 'hand-dfl': 1, 'hand-dlaw': 1},
        # (7 decrees − 1 royal decree «بمثابة قانون») / 2 laws voted, 3 orders / 2, 16 texts / 2.
        'ratio': {'decrees': 3, 'orders': 2, 'share': 8},
        'years': [{'year': 1963, 'rdl': 0, 'dfl': 0, 'voted': 2, 'dlaw': 0}, {'year': 1964, 'rdl': 2, 'dfl': 0, 'voted': 0, 'dlaw': 0},
                  {'year': 1965, 'rdl': 0, 'dfl': 1, 'voted': 0, 'dlaw': 1}],
        'reading': [{'key': 'laws', 'words': 5 + 3, 'texts': 2}, {'key': 'decrees', 'words': 3, 'texts': 1},
                    {'key': 'orders', 'words': 1, 'texts': 1}],
        'texts': {'c-1962': {'path': None},
                  'decree': {'issue': '2745', 'edition': 'general_ar', 'published': '1965-06-09', 'page': 1080,
                             'viewer': f'/pages/{y65.document_id}/0', 'path': None}},
    }


def test_a_deadline_counts_where_it_is_written_five_times_at_least_with_its_example_from_the_first_law_the_meta_names():
    """Each number of days, months… after a limit word, in the latest Arabic version of a text of law not repealed; a
    deadline written fewer than five times is left out of the list (not of the total); its example is the first of the
    meta's laws in their order, then its articles' order, with the words around it."""
    first, second = '/akn/ma/act/loi/70-03', '/akn/ma/act/loi/65-99'
    pre, post = ' '.join(['كلمة'] * 20), ' '.join(['أخرى'] * 20)
    family = text(first, TextType.LAW)
    version(family, 'داخل أجل 15 يوما')                                       # as published, replaced since
    latest = version(family, consolidation=Consolidation.SGG, valid_from=date(2016, 1, 1))
    article(latest, 3, 'art_3', 'خلال 15 يوما الموالية')
    article(latest, 2, 'art_2', f'{pre} داخل أجل 15 يوما {post}')
    labour = text(second, TextType.LAW)
    version(labour, 'يجب الطعن داخل أجل خمسة عشر يوما من تاريخ التبليغ')
    version(labour, 'Dans un délai de 15 jours', consolidation=Consolidation.TRANSLATION, valid_from=date(2020, 1, 1))
    # Two months written four times: under the five. A misread «0» is no deadline; 23 days in words is one, once. 5 hours,
    # five times here and once in a partly repealed law (it stands), with no example (no law the meta names).
    version(text('/akn/ma/act/decret/2-04-1', TextType.DECREE), 'داخل 15 يوما ثم داخل 15 يوما',
            'خلال شهرين، خلال شهرين، خلال شهرين، خلال شهرين', 'داخل أجل 0 يوما وخلال ثلاث وعشرين يوما',
            ' ثم '.join(['داخل 5 ساعات'] * 5))
    version(text('/akn/ma/act/loi/3-58', TextType.LAW, status=Status.PARTLY_REPEALED), 'داخل 5 ساعات')
    # Every unit, each said in days to four decimals: 3 weeks seven times, 6 months eight, 5 years nine.
    version(text('/akn/ma/act/decret/2-04-2', TextType.DECREE), ' ثم '.join(['خلال 3 أسابيع'] * 7),
            ' ثم '.join(['داخل 6 أشهر'] * 8), ' ثم '.join(['خلال 5 سنوات'] * 9))
    # Not read: a repealed law (beside it, the same deadline), an order, a French version.
    version(text('/akn/ma/act/loi/1-58', TextType.LAW, status=Status.REPEALED), 'داخل 15 يوما', 'داخل 5 ساعات')
    version(text('/akn/ma/act/arrete/1-04', TextType.ORDER), 'داخل 15 يوما')
    version(text('/akn/ma/act/loi/2-58', TextType.LAW), 'داخل 15 يوما', language='fr')
    meta = {'limit_words': 'أجل|اجل|خلال|داخل', 'rules': ['law', 'decree'], 'examples': [first, second]}
    words = ' '.join(['كلمة'] * 14) + ' داخل أجل 15 يوما ' + ' '.join(['أخرى'] * 10)
    assert deadlines.count(meta) == {
        'deadlines': [{'unit': 'y', 'n': 5, 'count': 9, 'days': 1826.25}, {'unit': 'm', 'n': 6, 'count': 8, 'days': 182.625},
                      {'unit': 'w', 'n': 3, 'count': 7, 'days': 21}, {'unit': 'h', 'n': 5, 'count': 6, 'days': 0.2083},
                      {'unit': 'd', 'n': 15, 'count': 5, 'days': 15,
                       'example': {'path': '/ma/loi/70-03/art_2', 'akn': first, 'eid': 'art_2', 'words': f'… {words} …'}}],
        'total': 40,
    }
