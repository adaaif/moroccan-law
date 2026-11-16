"""An issue's texts into the corpus (`issue_structure.load_texts`): a promulgating dahir filed as its law, the address
a text takes when another issue already holds it, a row waiting under a neighbouring kind filled, a text folded into
a fuller cut never loaded again, and only the positions asked for loaded."""
import datetime

import pytest

from apps.corpus.models import Alias, Consolidation, Text, Version
from apps.corpus.services.issue_structure import load_texts
from apps.corpus.tests.test_works import _texts
from apps.sources.models import Edition, Issue

pytestmark = pytest.mark.django_db


def bo(number, day=datetime.date(2022, 6, 20)):
    return Issue.objects.create(edition=Edition.GENERAL_AR, number=number, date=day)


def read_in(issue, uri, kind='law', number='66-19'):
    t = Text.objects.create(akn_uri=uri, type=kind, number=number, title_ar='قانون', first_published_in=issue)
    Version.objects.create(text=t, language='ar', valid_from=issue.date, consolidation=Consolidation.AS_PUBLISHED)
    return t


def test_a_dahir_described_by_the_model_is_filed_as_the_law_it_promulgates_and_a_waiting_dahir_row_merged():
    waiting = Text.objects.create(akn_uri='/akn/ma/act/dahir/1-22-30', type='dahir', number='1-22-30', title_ar='ظهير')
    texts = _texts()
    texts[0]['data'].update(type='dahir', number_as_printed='1.22.30', promulgating_dahir='',
                            title='ظهير شريف رقم 1.22.30 صادر في 1 يونيو 2022 بتنفيذ القانون رقم 66.19')
    texts[0]['front'] = 'ظهير شريف رقم 1.22.30 صادر في 1 يونيو 2022 بتنفيذ القانون رقم 66.19'
    assert load_texts(bo(7101), texts)['texts'] == 1
    law = Text.objects.get(akn_uri='/akn/ma/act/loi/66-19')
    assert (law.type, law.number_as_printed, law.promulgating_dahir) == ('law', '66.19', '1.22.30')
    assert not Text.objects.filter(pk=waiting.pk).exists()
    assert Alias.objects.get(alias='/akn/ma/act/dahir/1-22-30').uri == law.akn_uri


def test_an_address_another_issue_holds_is_left_to_it_and_this_text_takes_its_years_or_its_issues():
    read_in(bo(7000, datetime.date(2021, 6, 1)), '/akn/ma/act/loi/66-19')
    read_in(bo(7001, datetime.date(2021, 7, 1)), '/akn/ma/act/loi/2022/66-19')
    load_texts(bo(7101), _texts())
    assert Text.objects.filter(akn_uri='/akn/ma/act/loi/2022/66-19-bo7101', first_published_in__number=7101).exists()
    assert Text.objects.get(akn_uri='/akn/ma/act/loi/66-19').first_published_in.number == 7000


def test_a_row_waiting_under_a_neighbouring_kind_is_filled():
    # An organic law cited as a law before its issue was read: the waiting row becomes the organic law.
    waiting = Text.objects.create(akn_uri='/akn/ma/act/loi/65-13', type='law', number='65-13', title_ar='القانون رقم 65.13')
    texts = _texts('65.13', 'قانون تنظيمي رقم 65.13 يتعلق بتنظيم وتسيير أشغال الحكومة')
    texts[0]['data']['type'] = texts[0]['toc']['type'] = 'organic_law'
    load_texts(bo(6348), texts)
    waiting.refresh_from_db()
    assert (waiting.akn_uri, waiting.type, waiting.versions.count()) == ('/akn/ma/act/loi-organique/65-13', 'organic_law', 1)
    assert Alias.objects.get(alias='/akn/ma/act/loi/65-13').uri == waiting.akn_uri


def test_a_waiting_neighbour_merges_into_a_text_already_at_the_address():
    held = Text.objects.create(akn_uri='/akn/ma/act/loi-organique/65-13', type='organic_law', number='65-13', title_ar='')
    twin = Text.objects.create(akn_uri='/akn/ma/act/loi/65-13', type='law', number='65-13', title_ar='القانون رقم 65.13')
    texts = _texts('65.13', 'قانون تنظيمي رقم 65.13 يتعلق بتنظيم وتسيير أشغال الحكومة')
    texts[0]['data']['type'] = texts[0]['toc']['type'] = 'organic_law'
    load_texts(bo(6348), texts)
    assert not Text.objects.filter(pk=twin.pk).exists() and Text.objects.get(pk=held.pk).versions.count() == 1


def test_a_text_folded_into_a_fuller_cut_is_never_loaded_again_and_only_the_asked_positions_load():
    issue = bo(7101)
    Alias.objects.create(alias='/akn/ma/act/loi/66-19', uri='/akn/ma/act/loi/2022/66-19', reason=Alias.Reason.COPY)
    counts = load_texts(issue, _texts())
    assert (counts['texts'], counts['folded']) == (0, 1) and not Text.objects.filter(akn_uri='/akn/ma/act/loi/66-19').exists()
    texts = _texts('43.20', 'قانون رقم 43.20 يتعلق بخدمات الثقة') + _texts('95.17', 'قانون رقم 95.17 يتعلق بالتحكيم')
    texts.append({**texts[0], 'data': None, 'stop': 'not_found'})        # a text the pages did not show: skipped
    counts = load_texts(issue, texts, only={1, 2})
    assert (counts['texts'], counts['skipped']) == (1, 1)
    assert list(Text.objects.values_list('akn_uri', flat=True)) == ['/akn/ma/act/loi/95-17']
