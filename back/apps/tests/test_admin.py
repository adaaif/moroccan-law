"""The admin, every page of it (12 Nov 2026): each registered list costs the same number of queries for 3 rows as for
30, each row's page stays under its ceiling, every search and every filter answers, the read-only pages refuse to add,
change or delete, the forms that edit change only what a person may set, and no page shows a password's hash, a
token or a digest.

The rows are made by `make`, which fills every field a row needs, and every relation of the listed row itself, with a
new related row for each (a self-relation points at the batch's first row): a column that reads a relation row by row
costs a query more for each row, and the 3-and-30 test fails."""
import itertools
import re
import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.apps import apps
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import Group
from django.db import connection, models
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.models import EmailCode, User
from apps.consolidation.models import Doubt
from apps.corpus.models import Article, Consolidation, Text, Version
from apps.discussion.models import Action, Appeal, Contribution, Reviewer
from apps.opendata.models import ApiKey
from apps.quality.models import Correction, Report as QualityReport, Suspect
from apps.sources.models import Edition, Issue
from config import admin as site_admin

pytestmark = pytest.mark.django_db

REGISTERED = sorted(admin.site._registry, key=lambda m: m._meta.label)
serial = itertools.count(1)

# Fields a made row is given (a value, or a function of the row's serial), where the plain fill breaks a rule.
GIVEN = {
    Appeal: {'ban': None},                                  # an appeal is against a removal or a pause, never both
    Reviewer: {'ended_at': None},                           # a moderator still appointed: an ended one is kept as is
}

# What the forms that edit may change; every other registered admin is read-only.
EDITABLE = {
    User: {'username', 'email', 'email_proven_at', 'display_name', 'preferred_language', 'is_active', 'is_staff',
           'is_superuser', 'groups', 'user_permissions'},
    Group: {'name', 'permissions'},
    Doubt: {'status', 'note'},
    QualityReport: {'status', 'note'},
    Correction: {'right'},
    Suspect: {'suggestion'},
    Reviewer: {'text_paths'},
}
READ_ONLY = [m for m in REGISTERED if m not in EDITABLE]

# A row's page: the most queries it may run (the session, the user, the row, its relations, its small tables).
PAGE_CEILING = 8
PAGE_CEILINGS = {User: 12, Contribution: 14}

# What staff type into the search boxes: a word, the site's addresses, numbers.
TERMS = ['x', '/ma/loi/2013/67-12', 'https://example.org/ma/loi/2013/67-12/art_34', '/akn/ma/act/loi/2013/67-12',
         '67.12 34', '7533', '7533 12', 'BO 7465 bis']


def value(field, k: int, depth: int, rows: list):
    """A value for `field` of the k-th row made."""
    if field.is_relation:
        if field.related_model is field.model:
            return rows[0] if rows else None
        return make(field.related_model, 1, depth + 1)[0]
    if field.choices:
        return next(c for c, _ in field.flatchoices if c != '')
    if isinstance(field, models.EmailField):
        return f'p{k}@example.org'
    if isinstance(field, models.URLField):
        return 'https://example.org/'
    if isinstance(field, models.UUIDField):
        return uuid.uuid4()
    if isinstance(field, (models.CharField, models.TextField)):
        return f'{field.name[:3]}{k}'[:field.max_length or 200]
    if isinstance(field, models.BooleanField):
        return False
    if isinstance(field, models.DecimalField):
        return Decimal('1')
    if isinstance(field, models.FloatField):
        return 1.5
    if isinstance(field, models.DateTimeField):
        return timezone.now()
    if isinstance(field, models.DateField):
        return date(2026, 1, 2)
    if isinstance(field, models.IntegerField):
        return k
    if isinstance(field, models.JSONField):
        return field.get_default()
    raise AssertionError(f'no value for {field}')


def make(model, n: int, depth: int = 0) -> list:
    """`n` rows of `model`. The listed rows (depth 0) get every field, their nullable relations too; a related row gets
    only what it needs."""
    rows = []
    for _ in range(n):
        k = next(serial)
        given = {name: v(k) if callable(v) else v for name, v in GIVEN.get(model, {}).items()}
        for field in model._meta.concrete_fields:
            if field.primary_key or field.name in given or getattr(field, 'auto_now', False) \
                    or getattr(field, 'auto_now_add', False):
                continue
            needed = not field.null and not field.has_default() and not field.has_db_default()
            if needed or (depth == 0 and (field.null or field.is_relation) and not field.has_default()):
                given[field.name] = value(field, k, depth, rows)
        rows.append(model.objects.create(**given))
    if model is Suspect and depth == 0:              # its list names the page's issue
        for s in rows:
            Issue.objects.create(edition=Edition.GENERAL_AR, number=next(serial), date=date(2026, 1, 2),
                                 document=s.page.document)
    return rows


def url(model, view: str, *args) -> str:
    return reverse(f'admin:{model._meta.app_label}_{model._meta.model_name}_{view}', args=args)


def label(model) -> str:
    return model._meta.label


def counted(client, address: str):
    """The page and its queries' shapes (the SQL without its values)."""
    with CaptureQueriesContext(connection) as queries:
        page = client.get(address)
    assert page.status_code == 200, (address, page.status_code)
    return page, [re.sub(r"'[^']*'|\b\d+\b", '?', q['sql']) for q in queries.captured_queries]


@pytest.mark.parametrize('model', REGISTERED, ids=label)
def test_a_list_costs_the_same_for_3_rows_as_for_30(admin_client, model):
    make(model, 3)
    address = url(model, 'changelist')
    admin_client.get(address)                                        # the caches warm
    _, three = counted(admin_client, address)
    make(model, 27)
    page, thirty = counted(admin_client, address)
    assert len(page.context['cl'].result_list) >= 30
    again = sorted({q for q in thirty if thirty.count(q) > three.count(q)})
    assert len(thirty) == len(three), f'{len(three)} queries for 3 rows, {len(thirty)} for 30, repeating: {again}'


@pytest.mark.parametrize('model', REGISTERED, ids=label)
def test_a_rows_page_answers_under_its_ceiling(admin_client, model):
    row = make(model, 2)[1]                     # the second: its relations to its own model are set too
    _, queries = counted(admin_client, url(model, 'change', row.pk))
    ceiling = PAGE_CEILINGS.get(model, PAGE_CEILING)
    assert len(queries) <= ceiling, f'{len(queries)} queries over {ceiling}'


@pytest.mark.parametrize('model', REGISTERED, ids=label)
def test_every_search_and_every_filter_answers(admin_client, model):
    make(model, 3)
    address = url(model, 'changelist')
    page = admin_client.get(address)
    model_admin = admin.site._registry[model]
    if model_admin.search_fields:
        assert model_admin.search_help_text, 'the search box says what it searches'
        for term in TERMS:
            assert admin_client.get(address, {'q': term}).status_code == 200, term
    cl = page.context['cl']
    for spec in cl.filter_specs:
        for choice in spec.choices(cl):
            if not choice.get('selected'):
                assert admin_client.get(address + choice['query_string']).status_code == 200, choice
    if model_admin.show_facets is not admin.ShowFacets.NEVER:
        assert admin_client.get(address, {'_facets': 'True'}).status_code == 200


@pytest.mark.parametrize('model', READ_ONLY, ids=label)
def test_a_read_only_page_refuses_to_add_change_or_delete(admin_client, model):
    row = make(model, 1)[0]
    assert admin_client.get(url(model, 'add')).status_code == 403
    assert admin_client.post(url(model, 'change', row.pk), {}).status_code == 403
    assert admin_client.post(url(model, 'delete', row.pk), {'post': 'yes'}).status_code == 403
    assert admin_client.post(url(model, 'changelist'), {'action': 'delete_selected', '_selected_action': [row.pk],
                                                        'post': 'yes'}).status_code in (200, 302)
    assert model.objects.filter(pk=row.pk).exists()


@pytest.mark.parametrize('model', list(EDITABLE), ids=label)
def test_a_form_changes_only_what_a_person_may_set(admin_client, model):
    row = make(model, 1)[0]
    page = admin_client.get(url(model, 'change', row.pk))
    assert set(page.context['adminform'].form.fields) == EDITABLE[model]


def test_no_page_shows_a_password_a_token_or_a_digest(admin_client):
    person = make(User, 1)[0]
    person.password = make_password('a long secret 2026')
    person.save()
    page = admin_client.get(url(User, 'change', person.pk)).content.decode()
    assert person.password.split('$')[-1] not in page and 'set a new password' in page
    ended = make(BlacklistedToken, 1)[0]
    OutstandingToken.objects.filter(pk=ended.token_id).update(token='eyJhbGciOiJIUzI1NiJ9.a-refresh-token.signature')
    for page in (url(OutstandingToken, 'change', ended.token_id), url(BlacklistedToken, 'change', ended.pk),
                 url(OutstandingToken, 'changelist')):
        assert 'a-refresh-token' not in admin_client.get(page).content.decode()
    from apps.opendata.tests.helpers import accepted
    key, secret = ApiKey.issue(accepted(), 'a newsroom')
    page = admin_client.get(url(ApiKey, 'change', key.pk)).content.decode()
    assert key.key_hash not in page and secret not in page
    code = make(EmailCode, 1)[0]
    EmailCode.objects.filter(pk=code.pk).update(code_digest='c0de' * 16, email_digest='e4a1' * 16)
    page = admin_client.get(url(EmailCode, 'change', code.pk)).content.decode()
    assert 'c0de' * 16 not in page and 'e4a1' * 16 not in page


def test_a_long_texts_page_costs_what_a_short_ones_does(admin_client):
    text = make(Text, 1)[0]
    version = Version.objects.create(text=text, language='ar', valid_from=date(2020, 1, 1),
                                     consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=version, order=1, label='المادة 1', number='1', eid='art_1', body='نص')
    for model, pk in ((Text, text.pk), (Version, version.pk)):
        admin_client.get(url(model, 'change', pk))                  # the caches warm
    _, one = counted(admin_client, url(Text, 'change', text.pk))
    _, one_version = counted(admin_client, url(Version, 'change', version.pk))
    for i in range(30):
        Version.objects.create(text=text, language='fr', valid_from=date(2000, 1, 1) + timedelta(days=i),
                               consolidation=Consolidation.MACHINE)
        Article.objects.create(version=version, order=i + 2, label=f'المادة {i + 2}', number=str(i + 2),
                               eid=f'art_{i + 2}', body='نص')
    page, many = counted(admin_client, url(Text, 'change', text.pk))
    assert len(many) == len(one) and 'every version of this text' in page.content.decode()
    page, many = counted(admin_client, url(Version, 'change', version.pk))
    assert len(many) == len(one_version) and 'every article of this version' in page.content.decode()


def test_the_search_boxes_find_a_text_and_an_article_by_their_addresses(admin_client):
    issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=6208, date=date(2013, 11, 28))
    lease = Text.objects.create(akn_uri='/akn/ma/act/loi/2013/67-12', type='law', number='67-12',
                                number_as_printed='67.12', title_ar='القانون رقم 67.12 المتعلق بالكراء',
                                first_published_in=issue)
    other = Text.objects.create(akn_uri='/akn/ma/act/loi/2012/67-11', type='law', number='67-11', title_ar='قانون آخر')
    for text in (lease, other):
        v = Version.objects.create(text=text, language='ar', valid_from=date(2013, 11, 28),
                                   consolidation=Consolidation.AS_PUBLISHED)
        for n in ('33', '34'):
            Article.objects.create(version=v, order=int(n), label=f'المادة {n}', number=n, eid=f'art_{n}', body='نص')

    def found(model, term):
        return list(admin_client.get(url(model, 'changelist'), {'q': term}).context['cl'].result_list)

    assert found(Text, 'https://3adala.example/ma/loi/2013/67-12/art_34') == [lease]
    assert found(Text, '67.12') == [lease] and found(Text, 'بالكراء') == [lease]
    art_34 = Article.objects.get(version__text=lease, number='34')
    assert found(Article, '/ma/loi/2013/67-12/art_34') == [art_34]
    assert found(Article, '67.12 34') == [art_34]
    assert found(Version, '/ma/loi/2013/67-12') == list(lease.versions.all())
    assert found(Issue, '6208') == [issue]


def test_a_large_unfiltered_list_is_counted_from_the_estimate(admin_client, monkeypatch):
    make(Article, 3)
    monkeypatch.setattr(site_admin, 'estimate', lambda model, using='default': 650_094)
    cl = admin_client.get(url(Article, 'changelist')).context['cl']
    assert cl.result_count == 650_094 and len(cl.result_list) == 3
    filtered = admin_client.get(url(Article, 'changelist'), {'version__language__exact': 'fr'}).context['cl']
    assert filtered.result_count == 0
    monkeypatch.setattr(site_admin, 'estimate', lambda model, using='default': 400)     # a small table: counted
    assert admin_client.get(url(Article, 'changelist')).context['cl'].result_count == 3


def test_the_index_says_what_waits_and_puts_the_law_first(admin_client):
    make(QualityReport, 2)
    page = admin_client.get(reverse('admin:index'))
    assert page.status_code == 200
    labels = [a['app_label'] for a in page.context['app_list']]
    assert labels[:3] == ['corpus', 'sources', 'consolidation'] and labels.index('admin') == len(labels) - 1
    text = page.content.decode()
    assert 'Waiting for a person' in text and "2 readers&#x27; reports" in text
    assert f'{url(QualityReport, "changelist")}?status__exact=open' in text
    QualityReport.objects.update(status='fixed')
    assert 'Nothing waits for a person.' in admin_client.get(reverse('admin:index')).content.decode()
    for label_, _, query, rows in site_admin.WAITING:           # each queue's link keeps what it counted
        model = apps.get_model(label_)
        make(model, 2)
        cl = admin_client.get(f'{url(model, "changelist")}?{query}').context['cl']
        assert cl.result_count == model.objects.filter(rows).count(), label_


def test_the_admins_own_log_is_read_there(admin_client):
    make(LogEntry, 1)
    assert admin_client.get(url(LogEntry, 'changelist')).status_code == 200


def test_appointing_changing_and_ending_a_moderator_write_the_ledger(admin_client):
    person = make(User, 1)[0]
    page = admin_client.post(url(Reviewer, 'add'), {'user': person.pk, 'text_paths': '["/talk/family"]'})
    assert page.status_code == 302
    first = Reviewer.objects.get(user=person)
    assert first.text_paths == ['/talk/family'] and first.appointed_by.username == 'admin'
    admin_client.post(url(Reviewer, 'change', first.pk), {'text_paths': '[]'})
    first.refresh_from_db()
    live = Reviewer.objects.get(user=person, ended_at=None)
    assert first.ended_at and first.text_paths == ['/talk/family'] and live.text_paths == []
    assert admin_client.get(url(Reviewer, 'change', first.pk)).context['adminform'].form.fields == {}
    admin_client.post(url(Reviewer, 'changelist'), {'action': 'end', '_selected_action': [live.pk]})
    assert not Reviewer.objects.filter(user=person, ended_at=None).exists()
    assert list(Action.objects.filter(target=person).order_by('pk').values_list('verb', flat=True)) == [
        'appoint', 'appoint', 'dismiss']


def test_a_decision_typed_in_the_form_is_dated(admin_client):
    doubt = Doubt.objects.create(text_uri='/akn/ma/act/loi/2013/67-12', number='34', reason='unclear')
    admin_client.post(url(Doubt, 'change', doubt.pk), {'status': 'resolved', 'note': 'read on the page'})
    doubt.refresh_from_db()
    assert doubt.status == 'resolved' and doubt.resolved_at and doubt.note == 'read on the page'
    admin_client.post(url(Doubt, 'change', doubt.pk), {'status': 'open', 'note': ''})
    doubt.refresh_from_db()
    assert doubt.resolved_at is None
