"""The rows an address keeps follow the text when its address changes (`works.move`): its French, the Chamber's
memoranda and their files, readers' reports and follows, each only where it is the old text's own and never over what
the new address already holds; a twin merged or a copy folded gives the kept text what it lacks."""
from datetime import date

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from apps.budget.models import FinanceLaw
from apps.corpus.models import Alias, Consolidation, Text, Version
from apps.corpus.services import works
from apps.follows.models import Follow
from apps.parliament.models import Explanation
from apps.quality.models import Report
from apps.sources.models import Document, Source
from apps.translations.models import FrenchText

pytestmark = pytest.mark.django_db
OLD, NEW = '/akn/ma/act/loi/2022/66-19', '/akn/ma/act/loi/66-19'


def french(uri, title):
    return FrenchText.objects.create(text_uri=uri, type='law', number='66-19', title=title, issue_number=7100,
                                     issue_date=date(2022, 6, 16), document_sha='f' * 64, pages='1-2')


def memorandum(uri, body):
    return Explanation.objects.create(text_uri=uri, body=body, source_url='https://example.org/bill.pdf',
                                      document_sha='e' * 64)


def test_a_move_takes_along_what_is_the_old_texts_own_and_never_overwrites_the_new_ones():
    works.move(NEW, NEW, Alias.Reason.MOVED)
    assert not Alias.objects.exists()                                      # a text never leads to itself
    french(OLD, 'Loi n° 66-19 (old)')
    french(NEW, 'Loi n° 66-19')
    memorandum(OLD, 'مذكرة قديمة')
    memorandum(NEW, 'مذكرة تقديمية')
    bill = Document.objects.create(source=Source.PARLIAMENT, kind='bill', sha256='b' * 64, path='bill.pdf',
                                   mime='application/pdf', language='ar', bytes=1, fetched_at=timezone.now(),
                                   meta={'text_uri': OLD, 'stage': 'adopted'})
    for path in ('/ma/loi/2022/66-19', '/ma/loi/2022/66-19/art_3', '/ma/loi/2022/66-190/art_1'):
        Report.objects.create(path=path, kind='typo', quote='كلمة')
    reader = get_user_model().objects.create_user('reader', 'reader@example.org', 'a long phrase 7')
    Follow.objects.create(user=reader, path='/ma/loi/2022/66-19/art_3')
    Follow.objects.create(user=reader, path='/ma/loi/66-19/art_3')          # already followed at the new address
    Follow.objects.create(user=reader, path='/ma/loi/2022/66-190')          # another text, its number longer

    works.move(OLD, NEW, Alias.Reason.MOVED)
    assert FrenchText.objects.get(text_uri=OLD).title == 'Loi n° 66-19 (old)'        # the new one's own French stays
    assert Explanation.objects.get(text_uri=OLD).body == 'مذكرة قديمة'
    bill.refresh_from_db()
    assert bill.meta == {'text_uri': NEW, 'stage': 'adopted'}
    assert sorted(Report.objects.values_list('path', flat=True)) == [
        '/ma/loi/2022/66-190/art_1', '/ma/loi/66-19', '/ma/loi/66-19/art_3']
    assert sorted(Follow.objects.values_list('path', flat=True)) == [
        '/ma/loi/2022/66-19/art_3', '/ma/loi/2022/66-190', '/ma/loi/66-19/art_3']
    assert Alias.objects.get(alias=OLD).uri == NEW


def _version(text, consolidation, day=date(2022, 6, 16)):
    return Version.objects.create(text=text, language='ar', valid_from=day, consolidation=consolidation)


def test_a_twin_merges_only_when_it_holds_no_reading_of_the_bulletin():
    text = Text.objects.create(akn_uri=NEW, type='law', number='66-19', title_ar='')
    _version(text, Consolidation.AS_PUBLISHED)
    _version(text, Consolidation.ADALA, date(2024, 1, 1))
    read = Text.objects.create(akn_uri=OLD, type='law', number='66-19', title_ar='قانون رقم 66.19')
    _version(read, Consolidation.AS_PUBLISHED, date(2022, 6, 20))
    works.merge(read, text)
    works.merge(text, text)
    assert Text.objects.filter(pk=read.pk).exists() and not Alias.objects.exists()

    twin = Text.objects.create(akn_uri='/akn/ma/act/loi/2023/66-19', type='law', number='66-19',
                               title_ar='القانون رقم 66.19 المتعلق بحقوق المؤلف')
    _version(twin, Consolidation.ADALA, date(2024, 1, 1))                  # the same as the text's: dropped
    sgg = _version(twin, Consolidation.SGG, date(2024, 1, 1))             # one it lacks: moved over
    budget = FinanceLaw.objects.create(year=2023, kind='law', number='66.19', title='قانون', text=twin)
    works.merge(twin, text)
    assert FinanceLaw.objects.get(pk=budget.pk).text == text              # its finance law follows it
    text.refresh_from_db()
    assert not Text.objects.filter(pk=twin.pk).exists()
    assert sorted(text.versions.values_list('consolidation', flat=True)) == ['adala', 'as_published', 'sgg']
    assert Version.objects.get(pk=sgg.pk).text == text
    assert text.title_ar == 'القانون رقم 66.19 المتعلق بحقوق المؤلف'       # it had none: the twin's
    assert Alias.objects.get(alias='/akn/ma/act/loi/2023/66-19').reason == Alias.Reason.MERGED


def test_a_copy_folded_gives_the_kept_cut_what_it_lacks_and_drops_its_own_reading():
    kept = Text.objects.create(akn_uri=NEW, type='law', number='66-19', title_ar='قانون رقم 66.19')
    _version(kept, Consolidation.AS_PUBLISHED)
    copy = Text.objects.create(akn_uri=OLD, type='law', number='66-19', title_ar='قانون رقم 66.19')
    _version(copy, Consolidation.AS_PUBLISHED)
    sgg = _version(copy, Consolidation.SGG, date(2024, 1, 1))
    budget = FinanceLaw.objects.create(year=2022, kind='law', number='66.19', title='قانون', text=copy)
    works.fold_copy(kept, kept)
    assert Text.objects.filter(pk=kept.pk).exists()
    works.fold_copy(copy, kept)
    assert FinanceLaw.objects.get(pk=budget.pk).text == kept
    assert list(kept.versions.order_by('valid_from').values_list('consolidation', flat=True)) == ['as_published', 'sgg']
    assert Version.objects.get(pk=sgg.pk).text == kept
    assert Alias.objects.get(alias=OLD).reason == Alias.Reason.COPY


def test_a_dahirs_number_filed_as_a_law_but_read_from_the_bulletin_stays_where_it_is():
    read = Text.objects.create(akn_uri='/akn/ma/act/loi/1-72-184', type='law', number='1-72-184', title_ar='ظهير')
    _version(read, Consolidation.AS_PUBLISHED, date(1972, 7, 27))
    assert works.fold_dahir_numbers(log=lambda *a: None) == {'folded': 0, 'moved': 0}
    assert Text.objects.get(pk=read.pk).akn_uri == '/akn/ma/act/loi/1-72-184'


def test_a_text_cited_by_its_day_is_the_one_of_that_kind_and_day_and_never_a_guess():
    assert works.resolve_dated('dahir', 'not a day') == ('', 'unresolved')
    assert works.resolve_dated(None, '1913-08-12') == ('', 'unresolved')
    doc = Text.objects.create(akn_uri='/akn/ma/act/dahir/1913/doc', type='dahir', signed_on=date(1913, 8, 12),
                              title_ar='ظهير شريف بمثابة قانون الالتزامات والعقود')
    assert works.resolve_dated('dahir', '1913-08-12') == (doc.akn_uri, 'resolved')
    land = Text.objects.create(akn_uri='/akn/ma/act/dahir/1913/land', type='dahir', signed_on=date(1913, 8, 12),
                               title_ar='ظهير شريف يتعلق بالتحفيظ العقاري')
    assert works.resolve_dated('law', '1913-08-12', 'المتعلق بالتحفيظ العقاري') == (land.akn_uri, 'resolved')
    assert works.resolve_dated('dahir', '1913-08-12', 'المتعلق بالمحاكم') == ('', 'ambiguous')


def test_a_citation_names_no_address_without_a_kind_and_number_that_make_one():
    assert works.candidates('law', '') == 'unresolved'
    assert works.candidates('circular', '12-20') == 'unresolved'
    assert works.candidates('order', '12') == 'unresolved'
    assert works.candidates('law', '013-26') == ['/akn/ma/act/loi/13-26', '/akn/ma/act/loi-organique/13-26']
    # Held under two kinds, the kind the citation names wins; when it names the other, neither is sure.
    both = {'/akn/ma/act/loi/13-26', '/akn/ma/act/loi-organique/13-26'}
    assert works.choose(['/akn/ma/act/loi/13-26', '/akn/ma/act/loi-organique/13-26'], both) == ('/akn/ma/act/loi/13-26', 'resolved')
    assert works.choose(['/akn/ma/act/decret/13-26', '/akn/ma/act/loi/13-26', '/akn/ma/act/loi-organique/13-26'],
                        both) == ('', 'ambiguous')
    assert works.choose(['/akn/ma/act/loi/13-26'], set()) == ('/akn/ma/act/loi/13-26', 'resolved')
