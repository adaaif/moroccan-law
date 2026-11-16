"""The assistants' shares: a platform's an hour, a ChatGPT user's inside it, half a platform's hour said and kept."""
import logging
from datetime import datetime
from unittest import mock

import pytest
from django.core.cache import cache
from django.utils import timezone

from apps.mcp.models import Alert
from apps.mcp.services import quotas
from apps.mcp.services.quotas import Caller, Limit

pytestmark = pytest.mark.django_db
CLAUDE = Caller('platform', 'claude', 'claude')


@pytest.fixture(autouse=True)
def _fresh():
    cache.clear()


def at(hour, minute=0):
    moment = datetime(2026, 11, 12, hour, minute, tzinfo=timezone.get_current_timezone())
    return mock.patch('apps.mcp.services.quotas.timezone.localtime', return_value=moment)


def test_a_platforms_share_is_an_hours_so_one_user_holds_the_others_an_hour_at_most(settings):
    settings.MCP_PLATFORM_LIMITS = {'minute': 1000, 'hour': 3, 'articles': 100}
    with at(10, 5):
        for _ in range(3):
            quotas.charge(CLAUDE)
        with pytest.raises(Limit) as past:
            quotas.charge(CLAUDE)
    assert 'Everyone on this assistant reached its 3 calls this hour' in str(past.value)
    assert past.value.retry == 55 * 60 and '55 min (on the hour' in str(past.value)
    with at(11, 0):
        quotas.charge(CLAUDE)                      # the next hour: everyone again, not the next day


def test_half_a_platforms_hour_is_said_once_in_the_log_and_kept_as_a_row(settings, caplog):
    settings.MCP_PLATFORM_LIMITS = {'minute': 1000, 'hour': 4, 'articles': 10}
    settings.MCP_QUOTAS = {'minute': 1000, 'day': 4, 'articles': 10}
    caplog.set_level(logging.WARNING, logger='apps.mcp.services.quotas')
    with at(10):
        for _ in range(4):
            quotas.charge(CLAUDE)
            quotas.charge(Caller('account', '7', 'accounts', 1))          # one person's own share: no alert
        quotas.served(CLAUDE, 'read_articles', 6)
    assert list(Alert.objects.order_by('pk').values_list('origin', 'share', 'period', 'limit')) == [
        ('claude', 'calls', 'hour', 4), ('claude', 'articles', 'hour', 10)]
    assert sum('has used half its' in r.getMessage() for r in caplog.records) == 2


def test_a_chatgpt_users_key_is_a_digest_of_its_subject():
    key = quotas.subject_key('v1/anon-subject-42')
    assert len(key) == 24 and 'anon' not in key and key == quotas.subject_key('v1/anon-subject-42')
    assert quotas.subject_key(None) == quotas.subject_key(['x']) == quotas.subject_key('x' * 201) == ''
