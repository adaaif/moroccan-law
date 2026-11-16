import threading
from io import StringIO
from types import SimpleNamespace as NS

import pytest
from django.core.management import call_command

from apps.search.tests.model import Session, Tokenizer


@pytest.fixture(autouse=True)
def own_corpus_dir(settings, tmp_path):
    """A search test writes under its own folder, never the real data's: an index rebuilt for a test counted its 19
    words into CORPUS_DIR/derived/search_terms.json (24 Oct 2026), which spelling and the next partial rebuild read."""
    from apps.search.services import index, lemmas, spelling

    def forget():
        # A test may have put a plain function in place of a cached one (monkeypatch).
        for cached in (index.term_counts, lemmas.table, spelling.french_words, spelling.word):
            getattr(cached, 'cache_clear', lambda: None)()

    settings.CORPUS_DIR = tmp_path
    forget()
    yield
    forget()


@pytest.fixture
def model(monkeypatch, settings, tmp_path):
    """The meaning model's third-party pieces replaced by the stand-ins of model.py, its folder the test's own."""
    import onnxruntime
    import tokenizers
    settings.SEARCH_MODEL_DIR = str(tmp_path / 'bge-m3')
    monkeypatch.setattr(onnxruntime, 'InferenceSession', Session)
    monkeypatch.setattr(tokenizers, 'Tokenizer', Tokenizer)
    monkeypatch.setattr(Session, 'output', 'sentence_embedding')
    Tokenizer.files.clear()
    Tokenizer.read.clear()
    Session.made.clear()
    return settings.SEARCH_MODEL_DIR


@pytest.fixture
def served(model, settings, monkeypatch):
    """`serve_models --port 0 --threads 2` in a thread, on the port the system gives; SEARCH_MODEL_URL leads to it. The
    server is stopped before the test's database is emptied."""
    from apps.search.management.commands import serve_models

    made, ready = [], threading.Event()

    class Server(serve_models.ThreadingHTTPServer):
        def __init__(self, *args, **kw):
            super().__init__(*args, **kw)
            made.append(self)
            ready.set()

        def serve_forever(self, poll_interval=0.5):
            super().serve_forever(0.01)      # stopped at once when the test ends, not half a second later

    monkeypatch.setattr(serve_models, 'ThreadingHTTPServer', Server)
    out = StringIO()
    thread = threading.Thread(target=call_command, args=('serve_models', '--port', '0', '--threads', '2'),
                              kwargs={'stdout': out}, daemon=True)
    thread.start()
    assert ready.wait(30)
    settings.SEARCH_MODEL_URL = f'http://127.0.0.1:{made[0].server_address[1]}'
    yield NS(url=settings.SEARCH_MODEL_URL, out=out)
    made[0].shutdown()
    made[0].server_close()
    thread.join(30)
