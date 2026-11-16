"""Morocco's constitutions since 1962 (25 Oct 2026): a constitution and a year mean the one in force that year, its
article when one is named; never article 1996 of today's. Without a database."""
from datetime import date

from apps.corpus.services.works import code_target
from apps.search.services.search.asking import _constitution_of_year


def test_a_constitution_and_a_year_are_the_one_in_force_that_year():
    for q, year, article in [('دستور 1996', 1996, None), ('دستور المملكة المغربية لسنة 1962', 1962, None),
                             ('constitution de 1970', 1970, None), ('Constitution du Maroc 1972', 1972, None),
                             ('دستور 1992 الفصل 19', 1992, '19'), ('الفصل 19 من دستور 1996', 1996, '19')]:
        (citation,), on = _constitution_of_year(q)
        assert on == date(year, 12, 31) and citation['code'] == 'constitution' and citation['article'] == article, q
    assert _constitution_of_year('الفصل 19 من الدستور') is None
    assert _constitution_of_year("constitution d'une société 1996") is None
    assert code_target('constitution', date(1980, 12, 31))[0] == '/akn/ma/act/dahir/1-72-061'     # 1972's, in force in 1980
    assert code_target('constitution', date(1995, 12, 31))[0] == '/akn/ma/act/dahir/1-92-155'
    assert code_target('constitution')[0] == code_target('constitution', date(2026, 1, 1))[0] == '/akn/ma/act/dahir/1-11-91'
    assert code_target('civil_procedure', date(2020, 1, 1))[0] == '/akn/ma/act/dahir/1-74-447'
