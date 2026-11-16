"""`repair_tables`: the pages of every finance-law table that fails its checks are read again with a prompt for tables, in
one batch (the model's answers come from a stand-in for the API), and each new reading is kept only where it makes its
table add up. Nothing is sent without --write."""
from io import StringIO

import pytest
from django.core.management import call_command

from apps.budget.management.commands.repair_tables import ASK
from apps.budget.models import FinanceLaw
from apps.budget.services.load import load_finance_law
from apps.budget.tests import world
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.tests import claude
from apps.parliament.tests.pdfs import write_pdf
from apps.sources.models import OcrRun, Page
from apps.sources.services.ocr import SpendingNotAllowed
from apps.sources.services.quality import fingerprint

pytestmark = pytest.mark.django_db


def run(*args, out=None) -> str:
    out = out or StringIO()
    call_command('repair_tables', *args, stdout=out)
    return out.getvalue()


@pytest.fixture
def law(tmp_path, settings, monkeypatch):
    """The 2026 law loaded, its issue's file on disk (blank pages: the stand-in reads no image); the readings the
    model gives back, by printed page, are set by each test in `law.answers`."""
    answers = {}
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: answers[cid])
    text = world.law_2026()
    write_pdf(tmp_path / text.first_published_in.document.path, [[] for _ in world.PAGES])
    pages = {p.printed_number: p for p in Page.objects.filter(document__issue=text.first_published_in)}
    law = load_finance_law(text, year=2026, kind='law', number='50.25')
    law.answers, law.sent, law.pages = answers, sent, pages
    return law


def misread(page: Page, old: str, new: str) -> str:
    page.text = page.text.replace(old, new)
    page.save()
    return page.text


def reload(law: FinanceLaw) -> FinanceLaw:
    return load_finance_law(law.text, year=law.year, kind=law.kind, number=law.number)


def test_nothing_is_sent_without_write_and_a_table_on_no_page_has_nothing_to_repair(law):
    # Every check of 2026 passes; 2019's fail but its BO issue is not in the corpus, so none of its tables is on a page;
    # a law kept without its text is not looked at.
    old = Text.objects.create(akn_uri='/akn/ma/act/loi/80-18', type='law', title_ar='قانون المالية رقم 80.18')
    Version.objects.create(text=old, language='ar', valid_from='2019-01-01', consolidation=Consolidation.AS_PUBLISHED)
    load_finance_law(old, year=2019, kind='law', number='80.18')
    FinanceLaw.objects.create(year=2018, kind='law', number='68.17', title='قانون المالية رقم 68.17',
                              checks=[{'name': 'table B', 'ok': False, 'tables': ['B']}])
    assert run() == 'nothing to repair\n'
    before = misread(law.pages[100], '879 088 000', '879 038 000')
    reload(law)
    assert run('--year', '2019') == 'nothing to repair\n'
    out = StringIO()
    with pytest.raises(SpendingNotAllowed):
        run(out=out)
    assert out.getvalue() == "2026 law: tables ['B'], 2 pages\n"
    assert law.sent.requests() == [] and not OcrRun.objects.exists()
    assert Page.objects.get(pk=law.pages[100].pk).text == before


def test_a_new_reading_is_kept_only_on_the_page_where_it_makes_its_table_add_up(law):
    old_100 = misread(law.pages[100], '879 088 000', '879 038 000')     # table B
    old_102 = misread(law.pages[102], '1 738 331 000', '1 738 331 900')   # table E
    Page.objects.filter(pk=law.pages[100].pk).update(text_source='layer')     # read from its layer until now
    reload(law)
    # The new readings: page 100's right, its amount in visual order as the model may write it; page 101 not answered
    # (the API could not); page 102's wrong another way.
    raw_100 = old_100.replace('879 038 000', '000 088 879')
    law.answers.update({f'p{law.pages[100].pk}': raw_100, f'p{law.pages[101].pk}': None,
                        f'p{law.pages[102].pk}': old_102.replace('1 738 331 900', '1 738 331 090')})
    said = run('--write').splitlines()
    assert said[0] == "2026 law: tables ['B', 'E'], 3 pages"
    assert said[-2:] == ["2026 law: fixed ['B'], still failing ['E']",
                         "  after page by page: shown ['B', 'C', 'D', 'F', 'G', 'balance', 'posts']"]
    requests = law.sent.requests()
    assert [r['custom_id'] for r in requests] == [f'p{law.pages[n].pk}' for n in (100, 101, 102)]
    assert {(r['params']['model'], r['params']['messages'][0]['content'][1]['text']) for r in requests} == {
        ('claude-haiku-5-5', ASK)}
    run_100 = OcrRun.objects.get()
    assert (run_100.page_id, run_100.engine, run_100.variant, run_100.text) == (
        law.pages[100].pk, 'claude-haiku-5-5', 'table-1596', raw_100)
    pages = {p.printed_number: p for p in Page.objects.filter(pk__in=[p.pk for p in law.pages.values()])}
    assert pages[100].text == old_100.replace('879 038 000', '879 088 000') and pages[100].text_source == 'ocr'
    assert (pages[101].text, pages[102].text) == (law.pages[101].text, old_102)
    # Each page's measure is of its reading as left.
    assert all(pages[n].quality['of'] == fingerprint(pages[n]) for n in (100, 101, 102))
    assert pages[99].quality is None
    assert FinanceLaw.objects.get(year=2026).tables_checked() == {'balance', 'posts', 'B', 'C', 'D', 'F', 'G'}


def test_readings_that_fix_every_failing_table_are_all_kept(law):
    old_100 = misread(law.pages[100], '879 088 000', '879 038 000')
    reload(law)
    law.answers.update({f'p{law.pages[100].pk}': old_100.replace('879 038 000', '879 088 000'),
                        f'p{law.pages[101].pk}': law.pages[101].text})
    assert run('--write').splitlines()[-1] == "2026 law: fixed ['B'], still failing []"
    assert sorted(OcrRun.objects.values_list('page__printed_number', flat=True)) == [100, 101]
    assert FinanceLaw.objects.get(year=2026).tables_checked() == {'balance', 'posts', 'B', 'C', 'D', 'E', 'F', 'G'}


def test_the_balance_and_the_posts_are_read_again_on_their_articles_page_and_the_next(law):
    version = law.text.versions.get(valid_from='2026-07-01')
    posts = Article.objects.get(version=version, number='20')
    posts.body = posts.body.replace('**36.000**', '**36.100**')
    posts.save()
    # The balance's article with no printed page: no page to read for it.
    Article.objects.filter(version=version, number='37').update(
        printed_page=None, body=Article.objects.get(version=version, number='37').body.replace('18.180.175.000',
                                                                                              '18.180.175.001'))
    reload(law)
    law.answers.update({f'p{law.pages[n].pk}': law.pages[n].text for n in (100, 101)})
    said = run('--write').splitlines()
    assert said[0] == "2026 law: tables ['balance', 'posts'], 2 pages"
    assert [r['custom_id'] for r in law.sent.requests()] == [f'p{law.pages[n].pk}' for n in (100, 101)]
    # The articles are not cut again from the pages: no new reading helps, none is kept.
    assert said[-2:] == ["2026 law: fixed [], still failing ['balance', 'posts']",
                         "  after page by page: shown ['B', 'C', 'D', 'E', 'F', 'G']"]
    assert not OcrRun.objects.exists()
