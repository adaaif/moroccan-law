"""`seed_demo_explain`, the development's demo explanations: a dev database only, after the demo people exist; each item
written by its demo author through the same gates and guards as anyone's, the checked ones checked by demo-staff, and
running it again replaces what it made."""
import io
from datetime import date

import pytest
from django.core.management import CommandError, call_command

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.discussion.models import Check
from apps.discussion.services import review
from apps.discussion.tests.conftest import make_user
from apps.explain.management.commands.seed_demo_explain import ITEMS
from apps.explain.models import Explanation, Revision
from apps.explain.services import explanations

pytestmark = pytest.mark.django_db

# The texts and articles the items explain or cite, by their address.
TEXTS = {'/akn/ma/act/loi/67-12': ['32', '33', '34', '35', '45'], '/akn/ma/act/loi/70-03': ['49'],
         '/akn/ma/act/decret/2-25-983': [], '/akn/ma/act/loi/41-26': [], '/akn/ma/act/decret/2-26-434': [],
         '/akn/ma/act/decision/2026/3-44-26': [], '/akn/ma/act/loi/32-26': []}
KINDS = {'loi': 'law', 'decret': 'decree', 'decision': 'decision'}


@pytest.fixture
def dev(settings):
    """A dev database: DEBUG on, the markers standing in for the model (the dev check, so the agreement is asked), the
    demo people seed_demo_talk makes, accounts of other people named as they are, and the texts the items rest on."""
    settings.DEBUG, settings.DISCUSSION_CHECK = True, 'markers'
    people = {name: make_user(f'demo-{name}', staff=name == 'staff')
              for name in ('staff', 'salma', 'youssef', 'karim', 'hamid')}
    make_user('staff'), make_user('salma')          # not the demo's: the seed never writes or checks as them
    for uri, numbers in TEXTS.items():
        text = Text.objects.create(akn_uri=uri, type=KINDS[uri.split('/')[4]], number=uri.rsplit('/', 1)[1], title_ar='نص')
        v = Version.objects.create(text=text, language='ar', valid_from=date(2020, 1, 1),
                                   consolidation=Consolidation.AS_PUBLISHED)
        for k, n in enumerate(numbers):
            Article.objects.create(version=v, order=k, label=f'المادة {n}', number=n, eid=f'art_{n}', body=f'نص المادة {n}.')
    return people


def seed() -> str:
    out = io.StringIO()
    call_command('seed_demo_explain', stdout=out)
    return out.getvalue()


def test_the_seed_writes_each_item_through_its_author_and_checks_all_but_one(dev):
    assert seed() == 'seeded 14 explanations (13 checked)\n'
    assert Explanation.objects.count() == len(ITEMS) == 14
    for path, register, who, headline, body, sources, checked in ITEMS:
        e = Explanation.objects.select_related('pending').get(path=path, register=register)
        [r] = e.revisions.all()
        assert (r.author, r.headline, r.body, r.sources, r.held_reasons) == (dev[who], headline, body, sources, []), path
        assert r.note == ('أول صيغة' if register == 'ar' else ''), path
        if checked:
            assert (e.reviewed_by, e.pending, r.checked_by, e.body, e.headline, e.sources) == \
                (dev['staff'], None, dev['staff'], body, headline, sources), path
        else:
            assert (e.reviewed_at, e.pending, r.checked_at) == (None, r, None), path
    # The demo authors gave the agreement to the check, and the check read every state.
    for name in ('salma', 'youssef', 'karim', 'hamid'):
        dev[name].refresh_from_db()
        assert dev[name].check_consent_at is not None, name
    assert Check.objects.filter(model='markers').count() == 14


def test_running_it_again_replaces_what_it_made(dev):
    seed()
    first = set(Explanation.objects.values_list('pk', flat=True))
    Explanation.objects.filter(path='/words/rent').update(body='شيء آخر')
    # An explanation someone wrote at an address the seed does not explain stays.
    other = explanations.save(dev['staff'], '/words/custody', 'ar', 'الحضانة حفظ الولد.', consent=True)
    assert seed() == 'seeded 14 explanations (13 checked)\n'
    assert first.isdisjoint(Explanation.objects.exclude(pk=other.pk).values_list('pk', flat=True))
    assert Explanation.objects.count() == 15 and Revision.objects.count() == 15
    assert Explanation.objects.get(path='/words/rent').body.startswith('الوجيبة الكرائية هي مبلغ الكراء')
    assert Explanation.objects.get(pk=other.pk).body == 'الحضانة حفظ الولد.'


def test_an_item_its_author_checked_as_a_reviewer_of_its_text_is_not_checked_again(dev):
    review.appoint(dev['staff'], dev['salma'], ['/ma/loi/67-12'])
    assert seed() == 'seeded 14 explanations (13 checked)\n'
    by = {(p, r): e.reviewed_by for p, r, e in
          ((e.path, e.register, e) for e in Explanation.objects.select_related('reviewed_by'))}
    assert {k for k, who in by.items() if who == dev['salma']} == {
        ('/ma/loi/67-12', 'ar'), ('/ma/loi/67-12/art_34', 'ar'), ('/ma/loi/67-12/art_34', 'fr'),
        ('/ma/loi/67-12/art_45', 'ar')}
    assert by[('/ma/loi/67-12/art_34', 'darija')] == by[('/words/rent', 'ar')] == dev['staff']


def test_the_seed_refuses_a_database_that_is_not_a_dev_one_or_has_no_demo_people(dev, settings):
    settings.DEBUG = False
    with pytest.raises(CommandError, match='dev database only'):
        seed()
    settings.DEBUG = True
    dev['staff'].delete()
    with pytest.raises(CommandError, match='seed_demo_talk first'):
        seed()
    assert not Explanation.objects.exists()
