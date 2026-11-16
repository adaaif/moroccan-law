"""Putting right what Adala's ligatures turned round (R7 of the for-everyone review): the proofreader proposes, measured
against the BO as the OCR read it; only a person applies; an applied correction survives a reload."""
from datetime import date

import pytest
from django.contrib.auth.models import Permission
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services.refusals import Refused
from apps.consolidation.services import sgg
from apps.consolidation.services.versions import save_version
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.discussion.tests.conftest import make_user, signed_in
from apps.quality.models import Correction
from apps.quality.services import corrections, proofread
from apps.sources.models import Document

pytestmark = pytest.mark.django_db
ADALA = 'تخول الحضانة للأم، ثم للأب، ثم ألم الأم. ويرجع للقواعد العامة لإلثبات، داخل أجل ثالثة أشهر.'


@pytest.fixture
def family():
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/70-03', type='law', number='70-03', title_ar='مدونة الأسرة')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2016, 1, 1), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='المادة 171', number='171', eid='art_171', body=ADALA)
    # What the BO prints, as the OCR read it.
    bo = Text.objects.create(akn_uri='/akn/ma/act/loi/1-26', type='law', number='1-26', title_ar='قانون')
    pv = Version.objects.create(text=bo, language='ar', valid_from=date(2026, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    for i, body in enumerate(['النفقة لأم الأم ولأم الأب', 'تطبق القواعد العامة للإثبات والإثبات للإثبات',
                              'داخل أجل ثلاثة أشهر', 'في أجل ثلاثة أشهر', 'بعد ثلاثة أشهر', 'لأم الأم', 'ألف درهم', 'النفقة لأم الأب، وللقاضي للإثبات',
                              'المرتبة الثالثة', 'الثالثة', 'ثالثة']):
        Article.objects.create(version=pv, order=i + 1, label=f'المادة {i + 1}', number=str(i + 1), eid=f'art_{i + 1}', body=body)
    return text


def test_the_proofreader_proposes_what_the_bo_prints_and_applies_nothing(family):
    assert proofread.suggest() == 3
    found = {(c.wrong, c.right, c.source) for c in Correction.objects.all()}
    assert found == {('ألم', 'لأم', 'proofread'), ('لإلثبات', 'للإثبات', 'proofread'), ('ثالثة', 'ثلاثة', 'context')}
    assert Article.objects.get(eid='art_171').body == ADALA
    assert proofread.suggest() == 0  # proposed once


def test_only_staff_given_the_right_applies_and_a_reload_keeps_it(family, api):
    proofread.suggest()
    c = Correction.objects.get(wrong='ألم')
    assert api.post(f'/api/quality/corrections/{c.pk}/apply/').status_code == 401
    staff = make_user('staff', staff=True)
    # Staff alone may not change the law's words: the right to change corrections is given on purpose.
    assert signed_in(api, staff).post(f'/api/quality/corrections/{c.pk}/apply/').status_code == 403
    assert api.get('/api/quality/corrections/').json()['can_decide'] is False
    staff.user_permissions.add(Permission.objects.get(codename='change_correction'))
    staff = User.objects.get(pk=staff.pk)                                   # its rights read afresh
    out = signed_in(api, staff).post(f'/api/quality/corrections/{c.pk}/apply/').json()
    assert out['counts'] == {'applied': 1, 'waiting': 2, 'reports_open': 0, 'reports_fixed': 0} and out['can_decide']
    assert 'ثم لأم الأم' in Article.objects.get(eid='art_171').body
    corrections.reject(staff, Correction.objects.get(wrong='ثالثة').pk)
    # Adala's file read again: the person's correction is applied again, the one set aside is not.
    doc = Document.objects.create(source='adala', kind='consolidated_text', sha256='a' * 64, path='x.pdf', mime='application/pdf',
                                  bytes=1, language='ar', page_count=1, fetched_at=timezone.now())
    save_version(family, Consolidation.ADALA, doc, date(2016, 1, 1),
                 [sgg.SggArticle(label='المادة 171', number='171', heading_path=[], lines=[ADALA])])
    body = Article.objects.get(eid='art_171', version__consolidation=Consolidation.ADALA).body
    assert 'ثم لأم الأم' in body and 'لإلثبات' in body and 'ثالثة أشهر' in body
    with pytest.raises(Refused):
        corrections.apply(staff, 999)


def test_anyone_reads_what_was_put_right(family, api):
    proofread.suggest()
    corrections.apply(make_user('staff', staff=True), Correction.objects.get(wrong='لإلثبات').pk)
    got = api.get('/api/quality/corrections/').json()
    assert [(r['wrong'], r['right'], r['article']) for r in got['applied']] == [('لإلثبات', 'للإثبات', 'المادة 171')]
    assert got['waiting'] == [] and got['can_decide'] is False


def test_the_right_words_go_in_as_written_backslashes_and_all():
    whole = Correction(wrong='ويعادل المبلغ ويضاف', right='ويعادل المبلغ $\\frac{K}{2}$ ويضاف')
    assert corrections.put_right('قبل ويعادل المبلغ ويضاف بعد', whole) == 'قبل ويعادل المبلغ $\\frac{K}{2}$ ويضاف بعد'
    foreign = Correction(wrong='دirhم', right='درهم \\1')
    assert corrections.put_right('عشرة دirhم فقط', foreign) == 'عشرة درهم \\1 فقط'


def test_an_empty_page_takes_its_reading_and_a_page_with_words_is_never_touched():
    c = Correction(wrong='', right='الجريدة الرسمية\n\nالفصل 1\nنص الصفحة')
    assert corrections.put_right('', c) == c.right
    assert corrections.put_right(' \n', c) == c.right
    assert corrections.put_right(c.right, c) == c.right
    assert corrections.put_right('نص قرئ من جديد', c) == 'نص قرئ من جديد'


def test_words_cut_apart_are_found_whatever_their_spaces():
    c = Correction(wrong='لا تممت عين', right='المتمتعين')
    assert corrections.put_right('والفتاة لا  تممت عين بقواهما', c) == 'والفتاة المتمتعين بقواهما'


def test_a_page_read_again_is_listed_by_what_changed_in_it(api):
    """RD22 of the readers review: the newest hundred corrections were whole pages, 1 MB and 560,000 px on a phone."""
    from apps.quality.models import Correction
    from apps.quality.services.corrections import _what_changed
    page = ' '.join(f'كلمة{n}' for n in range(400))
    read_again = page.replace('كلمة200', 'الملة').replace('كلمة300', 'الحنيف')
    Correction.objects.create(path='/bo/general_ar/5964-bis#p12', wrong=page, right=read_again, source='page', status='applied',
                              decided_at=timezone.now())
    row = api.get('/api/quality/corrections/').json()['applied'][0]
    assert row['places'] == 2 and len(row['wrong']) < 120 and 'كلمة200' in row['wrong'] and 'الملة' in row['right']
    assert 'كلمة300' in row['wrong'] and 'الحنيف' in row['right'] and 'كلمة10 ' not in row['wrong']
    # A word put right stays as it is.
    assert _what_changed('ثالثة أشهر', 'ثلاثة أشهر') == ('ثالثة أشهر', 'ثلاثة أشهر', 1)


def test_the_reports_of_the_sites_making_are_not_counted_as_readers(api, settings):
    from datetime import timedelta

    from apps.quality.models import Report
    old = Report.objects.create(path='/ma/loi/9-26/art_2', kind='reading')
    Report.objects.filter(pk=old.pk).update(created_at=settings.DEMO_UNTIL - timedelta(days=1))
    Report.objects.create(path='/ma/loi/65-99/art_53', kind='reading')
    settings.SHOW_DEMO_PEOPLE = False                                     # as the public site is set
    assert api.get('/api/quality/corrections/').json()['counts']['reports_open'] == 1
    settings.SHOW_DEMO_PEOPLE = True
    assert api.get('/api/quality/corrections/').json()['counts']['reports_open'] == 2


def put_right_in(n, start=0):
    """`n` texts, each with an article, a correction applied to it and one that waits."""
    for k in range(start, start + n):
        text = Text.objects.create(akn_uri=f'/akn/ma/act/loi/{k}-26', type='law', number=f'{k}-26', title_ar=f'قانون {k}')
        v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 1, 1), consolidation=Consolidation.ADALA)
        Article.objects.create(version=v, order=1, label='المادة 1', number='1', eid='art_1', body='ثم ألم الأم.')
        Correction.objects.create(path=f'/ma/loi/{k}-26/art_1', wrong='ثلاثة', right='ثالثة', source='page',
                                  status='applied', decided_at=timezone.now())
        Correction.objects.create(path=f'/ma/loi/{k}-26/art_1', wrong='ألم', right='لأم', source='proofread')


def test_the_list_asks_the_same_few_questions_however_many_corrections(api):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from apps.corpus.services import generation
    staff = make_user('staff', staff=True)
    staff.is_superuser = True
    staff.save()

    def asked(viewer):
        generation.bump('corpus')                       # the readers' list built anew
        api.force_authenticate(viewer)
        with CaptureQueriesContext(connection) as queries:
            got = api.get('/api/quality/corrections/').json()
        return len(queries), got

    put_right_in(3)
    few = {'reader': asked(None), 'staff': asked(staff)}
    put_right_in(6, start=3)
    many = {'reader': asked(None), 'staff': asked(staff)}
    assert {k: n for k, (n, _) in few.items()} == {k: n for k, (n, _) in many.items()}
    reader, staffs = many['reader'][1], many['staff'][1]
    assert (len(reader['applied']), reader['waiting'], len(staffs['applied']), len(staffs['waiting'])) == (9, [], 9, 9)
    assert staffs['waiting'][0]['text'] == 'قانون 0' and staffs['waiting'][0]['article'] == 'المادة 1'


def test_a_correction_is_set_aside_by_the_api_and_its_refusals_say_why(family, api):
    proofread.suggest()
    staff = make_user('staff', staff=True)
    staff.user_permissions.add(Permission.objects.get(codename='change_correction'))
    staff = User.objects.get(pk=staff.pk)
    signed_in(api, staff)
    c = Correction.objects.get(wrong='ثالثة')
    out = api.post(f'/api/quality/corrections/{c.pk}/reject/')
    assert out.status_code == 200 and out.json()['counts'] == {'applied': 0, 'waiting': 2, 'reports_open': 0, 'reports_fixed': 0}
    c.refresh_from_db()
    assert (c.status, c.decided_by) == ('rejected', staff) and c.decided_at is not None
    assert 'ثالثة أشهر' in Article.objects.get(eid='art_171').body              # set aside: the words stay
    r = api.post(f'/api/quality/corrections/{c.pk}/approve/')
    assert (r.status_code, r.json()) == (404, {'errors': [{'field': 'verb', 'code': 'invalid'}]})
    for verb in ('apply', 'reject'):
        r = api.post(f'/api/quality/corrections/999/{verb}/')
        assert (r.status_code, r.json()) == (404, {'errors': [{'field': 'correction', 'code': 'not_found'}]})
    # Words no longer in the article are not applied, and the correction keeps waiting.
    Article.objects.filter(eid='art_171').update(body='تخول الحضانة للأم.')
    waiting = Correction.objects.get(wrong='ألم')
    r = api.post(f'/api/quality/corrections/{waiting.pk}/apply/')
    assert (r.status_code, r.json()) == (404, {'errors': [{'field': 'correction', 'code': 'not_found'}]})
    assert Correction.objects.get(pk=waiting.pk).status == 'suggested'


def test_a_correction_applied_before_is_applied_again_without_a_refusal(family):
    proofread.suggest()
    staff = make_user('staff', staff=True)
    c = Correction.objects.get(wrong='ألم')
    corrections.apply(staff, c.pk)
    # Applied, then its words already right everywhere: applying it again changes nothing and refuses nothing.
    again = corrections.apply(staff, c.pk)
    assert again.status == 'applied' and Article.objects.get(eid='art_171').body.count('لأم الأم') == 1


def test_a_word_is_put_right_only_where_its_neighbours_are_the_recorded_ones():
    c = Correction(wrong='ثالثة', right='ثلاثة', before='أجل', after='أشهر')
    assert corrections.put_right('المرتبة ثالثة، داخل أجل ثالثة أشهر، الثالثة ثالثة', c) == \
        'المرتبة ثالثة، داخل أجل ثلاثة أشهر، الثالثة ثالثة'


def test_a_long_correction_shows_its_first_three_places_and_counts_them_all(api):
    page = [f'كلمة{n}' for n in range(80)]
    again = list(page)
    for n in (10, 30, 50, 70):
        again[n] = 'تغيرت'
    Correction.objects.create(path='/bo/general_ar/30#p7', wrong=' '.join(page), right=' '.join(again), source='page',
                              status='applied', decided_at=timezone.now())
    row = api.get('/api/quality/corrections/').json()['applied'][0]
    assert row['places'] == 4 and 'كلمة50' in row['wrong'] and 'كلمة70' not in row['wrong']
    assert row['right'].count('تغيرت') == 3
