import os

import dj_database_url

from .base import *  # noqa: F403

DEBUG = False
ALLOWED_HOSTS = ['localhost', '127.0.0.1', 'testserver']

# SQLite in memory unless TEST_DATABASE_URL names a Postgres server (with ParadeDB): the search tests need it
# and skip without it.
DATABASES = {
    'default': dj_database_url.parse(os.environ['TEST_DATABASE_URL']) if os.environ.get('TEST_DATABASE_URL') else {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

# The throttles' counts in the process; no answer kept between requests (a test changes the data under them).
CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
    'answers': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'},
}

# Fast hashing: the suite creates many accounts.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']

# Throttles count per test run; keep them out of unrelated tests.
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_THROTTLE_RATES': {'auth': '1000/min', 'refresh': '1000/min', 'reports': '1000/min', 'timings': '1000/min',
                               'contribute': '1000/min', 'useful': '1000/min', 'uploads': '1000/min',
                               'codes': '1000/min', 'register': '1000/min', 'password': '1000/min', 'reset': '1000/min', 'oauth': '1000/min', 'oauth_register': '1000/min', 'oauth_metadata': '1000/min', 'oauth_authorize': '1000/min', 'flags': '1000/min', 'checks': '1000/min', 'measure': '1000/min'},
}
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['account'] = '1000/min'
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['open_ticket'] = '1000/min'
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['access_keys'] = '1000/min'
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['access_desk'] = '1000/min'
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['access_request'] = '1000/min'
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['words'] = '1000/min'
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']['words_read'] = '1000/min'

PUBLIC_API_RATES = {'anonymous': '10000/min'}
# The letters an inbox gets a day count in the process's cache across tests, as the throttles do: the tests that
# measure it set their own.
ACCOUNT_MAIL_PER_ADDRESS = 1000

# The suite sets its own budget and models: a developer's cap in .env (OCR_BUDGET_USD, LLM_MODELS_ALLOWED) stays out of it.
OCR_BUDGET_USD = 10.0
LLM_MODELS_ALLOWED = ''
# No key from the environment either: a test that needs one sets a fake one, so nothing in the suite can reach the
# paid API, not even to look up the batches a dead process left open (sources.services.ocr.reconcile).
ANTHROPIC_API_KEY = ''

# The discussion is open in tests; each test that stores a voice or a picture gets its own folder (conftest.py).
DISCUSSION_OPEN = True
SHOW_DEMO_PEOPLE = True
REGISTRATION_OPEN = True
DISCUSSION_CHECK = 'pass'      # a test that checks sets 'model' and answers for the model
DISCUSSION_MEDIA = True        # the voices' and pictures' tests; the launch has them off
EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
# The fetchers refuse to run without a name of their own (apps/sources/services/fetch.py); no test reaches a real site.
FETCH_USER_AGENT = 'law-tests/1 (+https://example.test/about)'
NOTICE_LETTER_PACE_S = 0
# No test calls the model server: meaning's own tests turn it on with their own nearest articles.
SEARCH_MEANING = False
SEARCH_THESAURUS = False

DEMO_IDS_KEPT = 0
