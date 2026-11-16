"""The drawing service as Django asks it (apps/seo/services/ssr.py; OP14 of the open-source audit): when it gives no
answer in time, says it is busy or is down, no page is sent to it for SSR_REST seconds, and every page goes with its
head alone meanwhile: every worker had waited out the timeout on every page."""
import io
import urllib.error
from unittest import mock

import pytest

from apps.seo.services import ssr
from config.caching import counters

SEED = [(['textAt', '/ma/loi/65-99', ''], b'{"articles": []}')]


@pytest.fixture
def service(settings):
    settings.SSR_URL = 'http://127.0.0.1:8043'
    settings.SSR_REST = 10
    counters.delete(ssr.RESTING)
    with mock.patch('urllib.request.urlopen') as urlopen:
        yield urlopen
    counters.delete(ssr.RESTING)


def drawn(html: str):
    answer = mock.MagicMock()
    answer.__enter__.return_value.read.return_value = html.encode()
    return answer


def test_a_page_is_drawn_while_the_service_answers(service):
    service.return_value = drawn('<main>65</main>')
    assert ssr.draw('/ma/loi/65-99', SEED) == '<main>65</main>'
    assert ssr.draw('/ma/loi/65-99', SEED) == '<main>65</main>' and service.call_count == 2


@pytest.mark.parametrize('failure', [TimeoutError('timed out'), urllib.error.URLError(ConnectionRefusedError()),
                                     urllib.error.HTTPError('http://ssr', 503, 'busy', {}, io.BytesIO())])
def test_no_page_is_sent_for_a_while_after_the_service_was_slow_busy_or_down(service, failure):
    service.side_effect = failure
    assert ssr.draw('/ma/loi/65-99', SEED) == ''
    assert ssr.draw('/ma/loi/66-99', SEED) == '' and service.call_count == 1    # not asked: nobody waits on it
    assert ssr.resting()
    counters.delete(ssr.RESTING)                                                # SSR_REST seconds later
    service.side_effect, service.return_value = None, drawn('<main>66</main>')
    assert ssr.draw('/ma/loi/66-99', SEED) == '<main>66</main>'


def test_a_page_that_failed_to_draw_does_not_stop_the_others(service):
    service.side_effect = urllib.error.HTTPError('http://ssr', 500, 'failed', {}, io.BytesIO())
    assert ssr.draw('/ma/loi/65-99', SEED) == ''
    service.side_effect, service.return_value = None, drawn('<main>66</main>')
    assert ssr.draw('/ma/loi/66-99', SEED) == '<main>66</main>' and not ssr.resting()


def test_without_a_pause_the_service_is_asked_each_time(service, settings):
    settings.SSR_REST = 0
    service.side_effect = TimeoutError('timed out')
    ssr.draw('/ma/loi/65-99', SEED)
    ssr.draw('/ma/loi/65-99', SEED)
    assert service.call_count == 2
