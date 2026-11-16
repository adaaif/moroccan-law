"""The admin's own actions ask for the right to change what they act on: a staff account that may only look at a list
never runs «Apply» on it (Django offers an action to anyone who may view the list unless it names a permission)."""
from datetime import date

import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.discussion.tests.conftest import make_user
from apps.quality.models import Correction

pytestmark = pytest.mark.django_db


def test_every_action_of_the_admin_asks_for_the_right_to_change():
    for model, model_admin in admin.site._registry.items():
        for name in model_admin.actions or ():
            if name == 'delete_selected':
                continue                                  # Django's own, which asks for the right to delete
            action = getattr(model_admin, name) if isinstance(name, str) else name
            assert 'change' in getattr(action, 'allowed_permissions', ()), f'{model.__name__}: {name}'


@pytest.fixture
def waiting():
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/70-03', type='law', number='70-03', title_ar='مدونة الأسرة')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2016, 1, 1), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=1, label='المادة 171', number='171', eid='art_171', body='ثم ألم الأم.')
    return Correction.objects.create(path='/ma/loi/70-03/art_171', wrong='ألم', right='لأم', source='proofread')


def staff_who_may(*codenames):
    user = make_user('looker', staff=True)
    user.user_permissions.add(*Permission.objects.filter(codename__in=codenames))
    return user


def test_a_staff_account_that_may_only_look_cannot_apply_a_correction(client, waiting):
    client.force_login(staff_who_may('view_correction'))
    page = client.get('/admin/quality/correction/')
    assert page.status_code == 200 and 'apply_them' not in page.content.decode()
    client.post('/admin/quality/correction/', {'action': 'apply_them', '_selected_action': [waiting.pk]})
    waiting.refresh_from_db()
    assert waiting.status == Correction.Status.SUGGESTED
    assert Article.objects.get(eid='art_171').body == 'ثم ألم الأم.'


def test_a_staff_account_given_the_right_to_change_applies_it(client, waiting):
    client.force_login(staff_who_may('view_correction', 'change_correction'))
    assert 'apply_them' in client.get('/admin/quality/correction/').content.decode()
    client.post('/admin/quality/correction/', {'action': 'apply_them', '_selected_action': [waiting.pk]})
    waiting.refresh_from_db()
    assert waiting.status == Correction.Status.APPLIED and Article.objects.get(eid='art_171').body == 'ثم لأم الأم.'


def act(client, model, action, rows):
    """An action run from a list, and the messages the list then shows."""
    r = client.post(f'/admin/quality/{model}/', {'action': action, '_selected_action': rows}, follow=True)
    assert r.status_code == 200
    return [m.message for m in r.context['messages']]


def test_a_reports_status_set_in_its_form_dates_its_resolution(admin_client):
    from apps.quality.models import Report
    report = Report.objects.create(path='/ma/loi/70-03/art_171', kind='reading', quote='ألم')
    address = f'/admin/quality/report/{report.pk}/change/'
    assert admin_client.post(address, {'status': 'fixed', 'note': 'صحح'}).status_code == 302
    report.refresh_from_db()
    assert (report.status, report.note) == ('fixed', 'صحح') and report.resolved_at is not None
    resolved = report.resolved_at
    admin_client.post(address, {'status': 'fixed', 'note': 'صحح في الصفحة'})          # the note alone: the day stays
    report.refresh_from_db()
    assert report.resolved_at == resolved
    admin_client.post(address, {'status': 'open', 'note': ''})                         # opened again
    report.refresh_from_db()
    assert (report.status, report.resolved_at) == ('open', None)


def test_reports_are_marked_fixed_or_set_aside_from_the_list(admin_client):
    from apps.quality.models import Report
    fixed, aside, left = (Report.objects.create(path=f'/ma/loi/70-03/art_{n}', kind='reading', quote='x') for n in (1, 2, 3))
    act(admin_client, 'report', 'mark_fixed', [fixed.pk])
    act(admin_client, 'report', 'set_aside', [aside.pk])
    got = {r.pk: (r.status, r.resolved_at is not None) for r in Report.objects.all()}
    assert got == {fixed.pk: ('fixed', True), aside.pk: ('dismissed', True), left.pk: ('open', False)}


def test_corrections_are_set_aside_and_one_no_longer_in_its_text_is_said(admin_client, waiting):
    gone = Correction.objects.create(path='/ma/loi/70-03/art_171', wrong='لإلثبات', right='للإثبات', source='proofread')
    assert act(admin_client, 'correction', 'apply_them', [waiting.pk, gone.pk]) == [f'Not found in the text any more: {gone}']
    assert Correction.objects.get(pk=waiting.pk).status == 'applied' and Correction.objects.get(pk=gone.pk).status == 'suggested'
    assert act(admin_client, 'correction', 'set_them_aside', [gone.pk]) == []
    gone.refresh_from_db()
    assert (gone.status, gone.decided_by.username) == ('rejected', 'admin') and gone.decided_at is not None


@pytest.fixture
def flagged():
    from datetime import UTC, datetime

    from apps.quality.models import Suspect
    from apps.sources.models import Document, Issue, Page
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='h30', path='30.pdf', mime='application/pdf',
                                  bytes=1, language='ar', fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    Issue.objects.create(edition='general_ar', number=30, date=date(1913, 11, 28), document=doc)
    page = Page.objects.create(document=doc, index=7, printed_number=228, kind='scan', text='بساسط الحدام ٢٫٥٠ التجار')
    unnumbered = Page.objects.create(document=doc, index=8, kind='scan', text='شعباeffective')
    sample = Document.objects.create(source='adala', kind='consolidated_text', sha256='a1', path='a.pdf',
                                     mime='application/pdf', bytes=1, language='ar', fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    loose = Page.objects.create(document=sample, index=2, kind='scan', text='الحيزة')
    return {
        'confirm': Suspect.objects.create(page=page, word='الحدام', suggestion='الخدام', context='بساسط الحدام ٢٫٥٠',
                                          signal='rare'),
        'glued': Suspect.objects.create(page=unnumbered, word='شعباeffective', signal='glued'),
        'loose': Suspect.objects.create(page=loose, word='الحيزة', suggestion='الخبزة', signal='rare'),
        'done': Suspect.objects.create(page=page, word='التجار', suggestion='النجار', signal='rare', status='rejected')}


def test_each_suspect_names_its_page_on_the_site(admin_client, flagged, settings):
    site = settings.SITE_URL.rstrip('/')
    page = admin_client.get('/admin/quality/suspect/').content.decode()
    assert f'<a href="{site}/bo/general_ar/30" target="_blank" rel="noopener">BO 30 p. 228</a>' in page
    assert f'<a href="{site}/bo/general_ar/30" target="_blank" rel="noopener">BO 30 p. 9</a>' in page     # no folio read
    loose = flagged['loose'].page
    assert f'<a href="{site}/pages/{loose.document_id}/2" target="_blank" rel="noopener">p. 3</a>' in page


def test_suspects_are_confirmed_or_set_aside_from_the_list(admin_client, flagged):
    from apps.quality.models import Suspect
    every = [flagged[k].pk for k in ('confirm', 'glued', 'done')]
    # Only open suspects with a suggestion: the glued word has none, the other was set aside before.
    assert act(admin_client, 'suspect', 'confirm', every) == ['1 confirmed, 0 articles put right']
    status = dict(Suspect.objects.values_list('pk', 'status'))
    assert status == {flagged['confirm'].pk: 'confirmed', flagged['glued'].pk: 'open', flagged['loose'].pk: 'open',
                      flagged['done'].pk: 'rejected'}
    assert flagged['confirm'].page.__class__.objects.get(pk=flagged['confirm'].page_id).text == 'بساسط الخدام ٢٫٥٠ التجار'
    assert act(admin_client, 'suspect', 'set_aside', every) == ['1 set aside']
    glued = Suspect.objects.get(pk=flagged['glued'].pk)
    assert (glued.status, glued.decided_by.username) == ('rejected', 'admin') and glued.decided_at is not None


def test_the_reviewers_list_shows_each_placed_words_line_and_what_people_said(admin_client, settings,
                                                                                django_assert_max_num_queries):
    from apps.quality.models import Answer
    from apps.quality.tests.words_helpers import page_with, placed, suspect
    settings.WORD_ANSWERS = 3
    page = page_with()
    agreed = placed(page, 'خيط', 'حيط', asked=3)
    kept = placed(page, 'جدار', 'حدار', asked=3)
    split = placed(page, 'سور', 'سود', asked=3)
    asking = placed(page, 'باب', 'ناب', asked=1)
    unplaced = suspect(page, 'دار', 'ذار', 'دار', place={})
    for s, said in ((agreed, 'suggestion suggestion suggestion'), (kept, 'word word word'),
                    (split, 'word suggestion unclear'), (asking, 'neither')):
        Answer.objects.bulk_create(Answer(suspect=s, says=x) for x in said.split())

    def listed(query=''):
        page = admin_client.get(f'/admin/quality/suspect/{query}').content.decode()
        return {s.word for s in (agreed, kept, split, asking, unplaced) if f'>{s.word}<' in page}, page

    words, page = listed()
    assert words == {'خيط', 'جدار', 'سور', 'باب', 'دار'}
    assert f'src="/api/quality/words/{agreed.pk}/strip/"' in page and f'/api/quality/words/{unplaced.pk}/strip/' not in page
    assert 'suggestion 3' in page and 'word 3' in page and 'suggestion 1, word 1, unclear 1' in page
    assert listed('?said=suggestion')[0] == {'خيط'} and listed('?said=word')[0] == {'جدار'}
    assert listed('?said=disagree')[0] == {'سور'} and listed('?said=asking')[0] == {'باب'}
    one = admin_client.get(f'/admin/quality/suspect/{split.pk}/change/').content.decode()
    assert f'/api/quality/words/{split.pk}/strip/' in one and 'suggestion 1, word 1, unclear 1' in one
    # The answers are counted in the list's own query: more words, no more questions.
    with django_assert_max_num_queries(12) as before:
        admin_client.get('/admin/quality/suspect/')
    for i in range(8):
        Answer.objects.create(suspect=placed(page_with(2000 + i), f'كلمة{i}', f'كلمه{i}', asked=1), says='word')
    with django_assert_max_num_queries(len(before.captured_queries)):
        admin_client.get('/admin/quality/suspect/')
