"""The public answers are compressed: the public views' whoever asks (they read no account, so they hold nothing of the
reader's), the topics', explanations' and discussion's only for a reader with no account (BREACH; S16 of the
performance audit)."""
import pytest

pytestmark = pytest.mark.django_db


def test_public_answers_are_compressed(client):
    r = client.get('/api/corpus/shelf/', HTTP_ACCEPT_ENCODING='gzip')
    assert r.status_code == 200 and r.headers.get('Content-Encoding') == 'gzip'


def test_a_public_views_answer_is_compressed_for_a_signed_in_reader_too(client):
    r = client.get('/api/corpus/shelf/', HTTP_ACCEPT_ENCODING='gzip', HTTP_AUTHORIZATION='Bearer x')
    assert r.headers.get('Content-Encoding') == 'gzip'


def test_answers_that_may_hold_the_readers_own_are_compressed_only_without_an_account(client):
    r = client.get('/api/topics/', HTTP_ACCEPT_ENCODING='gzip')
    assert r.headers.get('Content-Encoding') == 'gzip'
    r = client.get('/api/topics/', HTTP_ACCEPT_ENCODING='gzip', HTTP_AUTHORIZATION='Bearer x')
    assert r.headers.get('Content-Encoding') is None
