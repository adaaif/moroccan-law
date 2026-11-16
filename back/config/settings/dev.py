import os
from pathlib import Path

import dj_database_url
from decouple import config
from dotenv import load_dotenv

from .base import *  # noqa: F403

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent.parent / '.env')

DEBUG = True
ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0']  # noqa: S104 — a host name a browser may use, not an address to bind

# SQLite unless DATABASE_URL says otherwise (search needs Postgres later). No persistent connections: runserver
# answers each request on a new thread, and each thread's kept connection stayed open, so five dev servers filled
# Postgres' 100 slots («too many clients») on 20 Oct 2026.
DATABASES = {
    'default': dj_database_url.parse(
        os.environ.get('DATABASE_URL', f'sqlite:///{BASE_DIR / "db.sqlite3"}'),  # noqa: F405
        conn_max_age=0,
    )
}
# Redis when REDIS_URL names one (a local container: redis://127.0.0.1:6379/0), keyed by this database's name.
if os.environ.get('REDIS_URL'):
    CACHES = redis_caches(os.environ['REDIS_URL'], Path(str(DATABASES['default']['NAME'])).stem,  # noqa: F405
                          os.environ.get('COUNTERS_REDIS_URL', ''))

if DATABASES['default']['ENGINE'].endswith('sqlite3'):
    # Several issues are processed at once. A transaction takes the write lock when it begins (two that both
    # read, then write, would deadlock and fail at once), waits up to a minute for it, and WAL lets reads go on
    # while one process writes.
    DATABASES['default']['OPTIONS'] = {
        'timeout': 60, 'transaction_mode': 'IMMEDIATE',
        'init_command': 'PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;'}

# The Vite dev server (web/, port 5190) proxies /api, so CORS only matters
# when the page is opened on another origin.
CORS_ALLOWED_ORIGINS = ['http://localhost:5190', 'http://127.0.0.1:5190']

# The discussion is open on a dev machine, and its letters (the email codes, the answers) are printed by runserver
# unless EMAIL_BACKEND says otherwise (the e2e scripts write them to files).
# The four switches here read as the other settings do (1 or 0, True or False), with their development defaults.
DISCUSSION_OPEN = config('DISCUSSION_OPEN', default=True, cast=bool)
# Sign-up is open on a dev machine (e2e:accounts makes accounts); REGISTRATION_OPEN=0 shows it closed.
REGISTRATION_OPEN = config('REGISTRATION_OPEN', default=True, cast=bool)
# The check asks the model only when a key is in the environment.
DISCUSSION_CHECK = os.environ.get('DISCUSSION_CHECK', 'model' if os.environ.get('ANTHROPIC_API_KEY') else 'pass')
DISCUSSION_MEDIA = config('DISCUSSION_MEDIA', default=False, cast=bool)
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.console.EmailBackend')
EMAIL_FILE_PATH = os.environ.get('EMAIL_FILE_PATH', '')

# A request that repeats one query shape says so in runserver's log (S20 of the performance audit).
MIDDLEWARE = [*MIDDLEWARE, 'config.querylog.RepeatedQueries']  # noqa: F405
LOGGING = {'version': 1, 'disable_existing_loggers': False,
           'handlers': {'console': {'class': 'logging.StreamHandler'}},
           'loggers': {'querylog': {'handlers': ['console'], 'level': 'WARNING'}}}

SHOW_DEMO_PEOPLE = config('SHOW_DEMO_PEOPLE', default=True, cast=bool)   # the seeded discussions, while developing
SHOW_DRAFTS = True     # drafts shown while developing, as before SHOW_DRAFTS existed

# The browsable API and OPTIONS' description of a view, for a developer's browser only (production answers JSON).
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # noqa: F405
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer', 'rest_framework.renderers.BrowsableAPIRenderer'],
    'DEFAULT_METADATA_CLASS': 'rest_framework.metadata.SimpleMetadata',
}
