"""gunicorn --preload forks its workers from a master that ran a search (config/wsgi.py warms it): the question's vector,
asked in a thread while the words are searched, must still come in a worker (31 Oct 2026: every search waited 60 s for
a 504, the pool made in the master telling each worker it had an idle thread it never had)."""
import os

from apps.search.services.search import query


def test_a_forked_worker_asks_for_the_vector_in_threads_of_its_own():
    assert query._EMBED.submit(int).result(timeout=5) == 0     # the master's pool, used as the warm-up uses it
    pid = os.fork()
    if pid == 0:
        try:
            ok = query._EMBED.submit(int).result(timeout=5) == 0
        except BaseException:  # noqa: BLE001 — the forked child exits with a status whatever went wrong
            ok = False
        os._exit(0 if ok else 1)
    _, status = os.waitpid(pid, 0)
    assert os.waitstatus_to_exitcode(status) == 0


def test_a_vector_that_does_not_come_leaves_the_words_to_answer(monkeypatch):
    from concurrent.futures import Future

    from apps.search.services import meaning
    monkeypatch.setattr(meaning, 'TIMEOUT', 0.1)
    assert query._vector(Future(), 'الطرد') is None             # never resolved: the words answer alone
