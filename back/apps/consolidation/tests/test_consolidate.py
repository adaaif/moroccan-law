"""`consolidate`: every text at the address its kind and number give, then the links pipeline over the whole corpus,
which replaces its own changes, mentions and open doubts, and prunes the waiting texts nothing changes any more."""
import datetime
import json
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from apps.budget.models import FinanceLaw
from apps.consolidation.models import Change, Doubt
from apps.consolidation.tests.test_links import text
from apps.corpus.models import Alias, Mention, Text, Version
from config.confirm import database_name

pytestmark = pytest.mark.django_db
DAY = datetime.date(2026, 8, 10)


def stale(by):
    return Change(text_uri='/akn/ma/act/loi/9-88', number='3', verb='repealed', source='reading', by_kind='law',
                  by_number='9-89', by_uri=by, state='read')


def test_consolidate_runs_on_the_database_named_only(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    with pytest.raises(CommandError, match='give --yes-on'):
        call_command('consolidate', '--yes-on', 'another', stdout=StringIO())
    assert not (tmp_path / 'reports').exists()


def test_consolidate_addresses_every_text_reads_the_whole_corpus_and_prunes_what_nothing_changes(settings, tmp_path):
    settings.CORPUS_DIR = tmp_path
    (tmp_path / 'reports' / 'runs').mkdir(parents=True)
    (tmp_path / 'reports' / 'runs' / 'queue_2019_2026.txt').write_text('7533 2026-08-10 u\n')
    amender = text('/akn/ma/act/loi/13-26', 'law', '13-26', 'قانون رقم 13.26 بتغيير القانون رقم 2.00', DAY,
                   [('المادة الأولى', 'تغير وتتمم، على النحو التالي، أحكام المادة 8 من القانون رقم 2.00 :\n'
                                     '«المادة 8. - لا تشمل الحماية الجديدة ما يلي.»')])
    # Two texts read from the BO claim one address: neither is moved.
    text('/akn/ma/act/loi/64-23', 'law', '64-23', 'قانون رقم 64.23', DAY, [('المادة 1', 'نص.')])
    clash = text('/akn/ma/act/texte/bo7533-2', 'law', '64-23', 'قانون رقم 64.23', DAY, [('المادة 1', 'نص.')])
    # A law and the dahir that promulgated it, cut as a text of its own and waiting: one text, the dahir an alias.
    lease = text('/akn/ma/act/loi/67-12', 'law', '67-12', 'قانون رقم 67.12', DAY, [('المادة 1', 'نص.')])
    Text.objects.filter(pk=lease.pk).update(promulgating_dahir='1.13.111')
    Text.objects.create(akn_uri='/akn/ma/act/dahir/1-13-111', type='dahir', number='1-13-111', title_ar='ظهير')
    own = text('/akn/ma/act/dahir/1-58-250', 'dahir', '1-58-250', 'ظهير شريف رقم 1.58.250', DAY, [('الفصل 1', 'نص.')])
    Text.objects.filter(pk=own.pk).update(promulgating_dahir='1.58.250')
    # A waiting law that is an organic law the site holds: merged into it.
    organic = text('/akn/ma/act/loi-organique/130-13', 'organic_law', '130-13', 'قانون تنظيمي رقم 130.13', DAY,
                   [('المادة 1', 'نص.')])
    Text.objects.create(akn_uri='/akn/ma/act/loi/130-13', type='law', number='130-13', title_ar='القانون رقم 130.13')
    # Waiting texts: one nothing changes any more, one a finance law's figures hold, one with no neighbour the site holds.
    Text.objects.create(akn_uri='/akn/ma/act/loi/99-99', type='law', number='99-99', title_ar='القانون رقم 99.99')
    kept = Text.objects.create(akn_uri='/akn/ma/act/loi/70-19', type='law', number='70-19', title_ar='قانون المالية')
    FinanceLaw.objects.create(year=2020, kind='initial', number='70.19', title='قانون المالية', text=kept)
    # What an earlier run left: its readings, mentions and open doubts go; a person's resolved doubt stays.
    Change.objects.bulk_create([stale(amender.akn_uri), stale('/akn/ma/act/loi/9-89')])
    Mention.objects.create(from_uri='/akn/ma/act/loi/9-89', words='القانون رقم 9.88', kind='cites', state='resolved',
                           to_uri='/akn/ma/act/loi/9-88')
    Doubt.objects.create(by_uri='/akn/ma/act/loi/9-89', reason='unclear')
    resolved = Doubt.objects.create(by_uri='/akn/ma/act/loi/9-89', reason='unplaced', status='resolved')
    out = StringIO()
    call_command('consolidate', '--yes-on', database_name(), stdout=out)

    clash.refresh_from_db()
    assert clash.akn_uri == '/akn/ma/act/texte/bo7533-2'
    assert not Text.objects.filter(akn_uri__in=['/akn/ma/act/dahir/1-13-111', '/akn/ma/act/loi/130-13',
                                                 '/akn/ma/act/loi/99-99']).exists()
    assert set(Alias.objects.values_list('alias', 'uri', 'reason')) == {
        ('/akn/ma/act/dahir/1-13-111', lease.akn_uri, 'dahir'),
        ('/akn/ma/act/loi/130-13', organic.akn_uri, 'merged')}
    assert Text.objects.filter(akn_uri__in=['/akn/ma/act/loi/70-19', '/akn/ma/act/loi/2-00']).count() == 2
    assert not Version.objects.filter(text__akn_uri='/akn/ma/act/loi/2-00').exists()
    assert list(Change.objects.values_list('text_uri', 'number', 'by_uri')) == [
        ('/akn/ma/act/loi/2-00', '8', amender.akn_uri)]
    assert not Mention.objects.filter(from_uri='/akn/ma/act/loi/9-89').exists()
    assert list(Doubt.objects.values_list('pk', flat=True)) == [resolved.pk]
    report = json.loads((tmp_path / 'reports' / 'consolidation.json').read_text())
    assert {k: report[k] for k in ('address_clash', 'address_dahirs', 'address_merged', 'changes', 'waiting_texts',
                                   'waiting_pruned', 'coverage_issues')} == {
        'address_clash': 1, 'address_dahirs': 1, 'address_merged': 1, 'changes': 1, 'waiting_texts': 1,
        'waiting_pruned': 1, 'coverage_issues': 1}
    said = out.getvalue().splitlines()
    assert said[0] == 'read 6 texts: 1 changes, 2 mentions'
    assert f"{'waiting_pruned':>22}  1" in said and f"{'coverage_issues':>22}  1" in said
