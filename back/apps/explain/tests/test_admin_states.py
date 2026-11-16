"""The admin names each state of an explanation as the reviewers know it: removed, checked, held by the patterns or the
check, waiting; on the explanation's page (newest first) and in the states' list, whose filter keeps one kind."""
import re

import pytest

from apps.discussion.services import review
from apps.discussion.tests.conftest import ARTICLE as PATH, lease, make_user, uploads  # noqa: F401  (fixtures)
from apps.explain.models import Explanation, Revision
from apps.explain.services import explanations

pytestmark = pytest.mark.django_db


@pytest.fixture
def states(lease):
    """One state of each kind, oldest first: checked, held (a phone number), waiting, removed."""
    staff, writer = make_user('staff', staff=True), make_user('nadia')
    review.appoint(staff, make_user('salma'), ['/ma/loi/2013/67-12'])
    explanations.save(writer, PATH, 'ar', 'لا تتجاوز الزيادة 8% للسكن.')
    explanations.check(staff, PATH, 'ar')
    for body in ('للاستشارة اتصلوا على 0600000000', 'صيغة ثالثة.', 'صيغة رابعة.'):
        explanations.save(writer, PATH, 'ar', body)
    explanations.remove(staff, Revision.objects.get(body='صيغة رابعة.').pk, 'on_topic')
    return Explanation.objects.get()


def test_the_explanations_page_names_each_states_kind_newest_first(admin_client, states):
    page = admin_client.get(f'/admin/explain/explanation/{states.pk}/change/').content.decode()
    table = page.split('field-revisions_table', 1)[1].split('</table>', 1)[0]
    assert re.findall(r'<td>(\w+)</td></tr>', table) == ['removed', 'waiting', 'held', 'checked']


@pytest.mark.parametrize('state', ['held', 'checked', 'removed'])
def test_the_states_list_keeps_one_kind_and_names_it(admin_client, states, state):
    page = admin_client.get('/admin/explain/revision/', {'state': state}).content.decode()
    assert re.findall(r'<td class="field-state">(\w+)</td>', page) == [state]
