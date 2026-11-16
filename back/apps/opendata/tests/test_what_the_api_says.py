"""What the API tells a client beyond its answer: JSON only, no description of a view, and the stages of an answer
(Server-Timing) only to the machine itself and to staff."""
import pytest
from django.test import Client
from django.urls import include, path
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.discussion.tests.conftest import make_user, signed_in
from config.timing import laps

pytestmark = pytest.mark.django_db


class Timed(APIView):
    """An answer in two stages, for anyone; signed in when a token comes with it."""
    permission_classes = [AllowAny]

    def get(self, request):
        lap = laps()
        lap('words')
        lap('snippets')
        return Response({'ok': True})


urlpatterns = [path('timed/', Timed.as_view()), path('', include('config.urls'))]


def test_asked_for_a_web_page_the_api_answers_json():
    r = Client().get('/api/open/about/', HTTP_ACCEPT='text/html,application/xhtml+xml,*/*;q=0.8')
    assert r.status_code == 200 and r['Content-Type'] == 'application/json'


def test_options_describes_no_view(api):
    r = api.options('/api/quality/corrections/')
    body = r.content.decode()
    assert r.status_code == 405 and 'description' not in body and 'what was put right' not in body


@pytest.mark.urls('apps.opendata.tests.test_what_the_api_says')
def test_the_stages_of_an_answer_go_to_the_machine_itself_and_to_staff_only(api):
    # The machine itself (perf_report, the jobs): no proxy in between.
    assert api.get('/timed/', REMOTE_ADDR='127.0.0.1')['Server-Timing'].startswith('words;dur=')
    # A reader, through the proxy or not: nothing about which stage costs what.
    assert not api.get('/timed/', REMOTE_ADDR='127.0.0.1', HTTP_X_FORWARDED_FOR='41.92.1.2').has_header('Server-Timing')
    assert not api.get('/timed/', REMOTE_ADDR='41.92.1.2').has_header('Server-Timing')
    assert not signed_in(api, make_user('reader')).get('/timed/', REMOTE_ADDR='41.92.1.2').has_header('Server-Timing')
    # Staff, signed in, from anywhere.
    assert signed_in(api, make_user('staff', staff=True)).get('/timed/', REMOTE_ADDR='41.92.1.2').has_header('Server-Timing')
