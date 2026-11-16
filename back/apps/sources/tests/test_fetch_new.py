from datetime import date

from apps.sources.management.commands.fetch_new_issues import key_of, missing


def row(number: str, day: str) -> dict:
    ms = int((date.fromisoformat(day) - date(1970, 1, 1)).days * 86_400_000)
    return {'BoNum': number, 'BoDate': f'/Date({ms})/', 'BoUrl': f'https://www.sgg.gov.ma/BO/AR/3111/{day[:4]}/BO_{number}_Ar.pdf'}


def test_the_list_s_numbers_read_as_the_issues_keys():
    assert key_of({'BoNum': '7555-bis'}) == '7555-bis'
    assert key_of({'BoNum': ' 7552 '}) == '7552'
    assert key_of({'BoNum': 'bis-6168'}) == '6168-bis'     # four of 2013 are listed the other way round


def test_the_new_issues_are_those_not_held_since_2019_oldest_first():
    rows = [row('7556', '2026-10-29'), row('7555-bis', '2026-10-27'), row('7555', '2026-10-26'),
            row('6739', '2018-12-31'), row('bis-6168', '2013-07-11'), row('x', '2026-10-30')]
    new = missing(rows, held={'7555'})
    assert [r['BoNum'] for r in new] == ['7555-bis', '7556']   # 2018 and 2013 are the archive's; «x» is no issue
