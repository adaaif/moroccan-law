import os
import time
import zoneinfo
from datetime import UTC, datetime, timedelta
from pathlib import Path

import tzdata
from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# The default is for tests and a local runserver only: config.settings.prod
# refuses to start on it.
INSECURE_SECRET_KEY = 'django-insecure-law-local-only-never-in-production-0'  # noqa: S105 — the development default, which the production settings refuse
SECRET_KEY = config('SECRET_KEY', default=INSECURE_SECRET_KEY)

DEBUG = False
ALLOWED_HOSTS = []

# The site's Latin name, the one readers see beside the Arabic «قانون» (15 Nov 2026; the address is 3adala.com): the
# letters' sender's name, the assistants' connector, the files a reader saves (config/saved.py).
SITE_NAME = config('SITE_NAME', default='3adala')

INSTALLED_APPS = [
    'config.admin.AdminConfig',         # Django's admin, with our own admin site (config/admin.py)
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    'rest_framework',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',

    'apps.accounts',
    'apps.sources',
    'apps.corpus',
    'apps.budget',
    'apps.search',
    'apps.quality',
    'apps.consolidation',
    'apps.parliament',
    'apps.translations',
    'apps.gate',
    'apps.opendata',
    'apps.media',
    'apps.discussion',
    'apps.explain',
    'apps.follows',
    'apps.topics',
    'apps.blog',
    'apps.places',
    'apps.oauth',
    'apps.mcp',
    'apps.seo',
    'apps.analytics',
]

MIDDLEWARE = [
    # An address or query holding a NUL answers 400 before any view (config/malformed.py).
    'config.malformed.RefuseUnstorable',
    # While the site is shown to a few: nothing without the password (apps.gate; GATE_PASSWORD empty, no gate).
    'apps.gate.middleware.GateMiddleware',
    'config.compress.PublicGZipMiddleware',
    # An ETag on every answer and a 304 when the reader has it; then whether a public answer may be kept (S17).
    'django.middleware.http.ConditionalGetMiddleware',
    'config.caching.PublicCaching',
    # A browser's own day of reading: its cookie, on the answer that first counted for it (marked private).
    'apps.corpus.middleware.ReaderCookie',
    'django.middleware.security.SecurityMiddleware',
    # No other site holds Django's pages in a frame (the admin, the gate, the heads of /ma/, /bo/, /search, /words).
    # nginx says the same for every answer, the files included (deploy/nginx-headers.conf); /embed/, the one page another
    # site may frame, is the app's and never Django's.
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    # A request with a key (X-Api-Key): refused when the key opens nothing, else counted on its access (apps.opendata).
    'apps.opendata.middleware.Keys',
    'config.timing.ServerTiming',
]

X_FRAME_OPTIONS = 'SAMEORIGIN'      # the site's own pages may frame each other, as nginx's frame-ancestors 'self'

ROOT_URLCONF = 'config.urls'
WSGI_APPLICATION = 'config.wsgi.application'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('POSTGRES_DB', default='law'),
        'USER': config('POSTGRES_USER', default='law'),
        'PASSWORD': config('POSTGRES_PASSWORD', default=''),
        'HOST': config('POSTGRES_HOST', default='localhost'),
        'PORT': config('POSTGRES_PORT', default='5432'),
    }
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# The caches (S13 of the performance audit; until 24 Oct 2026 each process kept its own, so the request limits and the
# hourly figures were per worker): 'default' holds what is worked out once and kept a while, 'answers' the public answers
# kept by what they depend on (apps/corpus/services/generation.py), and 'counters', when COUNTERS_REDIS_URL names a
# store that never evicts, every limit's counts (config/caching.py `counters`; without it they are the default cache's).
# Without Redis, tests and a dev machine with no REDIS_URL, 'default' stays in the process and 'answers' keeps nothing.
CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
    'answers': {'BACKEND': 'django.core.cache.backends.dummy.DummyCache'},
}


# The largest answer the 'answers' cache keeps, in bytes: a law's window is 0.1 to 1 MB, and a few answers of
# megabytes (a decision's table of parcels) would fill it.
ANSWERS_KEPT_MOST = config('ANSWERS_KEPT_MOST', default=2_000_000, cast=int)


def redis_caches(url: str, database: str, counters_url: str = '') -> dict:
    """The caches in Redis, under the database's name: two databases never share an answer or a limit. A second
    without Redis fails a request rather than holding it. The counts go to `counters_url` when it is given."""
    places = [('default', url, 300), ('answers', url, 24 * 3600)] + ([('counters', counters_url, 300)] if counters_url else [])
    return {name: {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': location,
                   'KEY_PREFIX': f'{database}:{name}', 'TIMEOUT': timeout,
                   'OPTIONS': {'socket_connect_timeout': 1, 'socket_timeout': 1}}
            for name, location, timeout in places}

AUTH_USER_MODEL = 'accounts.User'

# Sign in with the username or the email address (apps/accounts/backends.py).
AUTHENTICATION_BACKENDS = ['apps.accounts.backends.UsernameOrEmailBackend']

# The first broken rule is the error `code` the clients translate.
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
     'OPTIONS': {'user_attributes': ('username', 'email', 'display_name')}},
]

LANGUAGE_CODE = 'ar'
LANGUAGES = [
    ('ar', 'العربية'),
    ('fr', 'Français'),
]
TIME_ZONE = 'Africa/Casablanca'
# Morocco's legal time moves by decree: 2.26.530 put it back on Greenwich's time on 20 September 2026, and a machine
# whose own zone files were older went on counting an hour ahead, its day turning at eleven at night. The zones'
# rules are read from the pinned `tzdata` package (requirements/base.txt), the same on every machine and updated with
# the other packages, never from the system's files. Two readers are told so. zoneinfo, which Django's
# `timezone.localtime()` and `localdate()` ask: its search path is emptied, and the package is what is left. And the C
# library, which `date.today()`, `datetime.now()` and the logs' hours ask: it looks for a zone's file under TZDIR, and
# reads it only when the zone's name changes, so the zone is set to UTC and then to TIME_ZONE, here, whatever the
# process started with and however often these settings are read (a test reloads them).
zoneinfo.reset_tzpath(to=[])
zoneinfo.ZoneInfo.clear_cache()
if hasattr(time, 'tzset'):
    os.environ['TZDIR'] = str(Path(tzdata.__file__).parent / 'zoneinfo')
    for zone in ('UTC', TIME_ZONE):
        os.environ['TZ'] = zone
        time.tzset()
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

REST_FRAMEWORK = {
    # JWT only: a session cookie from the Django admin must never CSRF-gate
    # the API's POSTs.
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    # JSON only, and OPTIONS describes nothing: the browsable page and the metadata class showed each view's
    # docstring to anyone who asked. Development turns both back on (dev.py).
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_METADATA_CLASS': None,
    # A JSON body is one object, and no body holds a NUL (config/malformed.py); DRF's own refusals answer in the one
    # error shape, a code and no sentence (apps/accounts/api/errors.py).
    'DEFAULT_PARSER_CLASSES': [
        'config.malformed.JSONParser',
        'config.malformed.FormParser',
        'config.malformed.MultiPartParser',
    ],
    'EXCEPTION_HANDLER': 'apps.accounts.api.errors.exception_handler',
    # DRF's scoped limits, counting an IPv6 address by its /64 (apps/opendata/throttles.py `ident`).
    'DEFAULT_THROTTLE_CLASSES': [
        'apps.opendata.throttles.ScopedRate',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'auth': '20/min',
        # A session's refresh, per account (accounts/api/views.py: RefreshThrottle): a device asks once every half hour.
        'refresh': '30/min',
        # A sign-up mails a code to the address it names: an address makes 20 accounts an hour.
        'register': '20/hour',
        # The doors that ask for the password again (a new password, a new address) and the reset mails.
        'password': '10/hour',
        'reports': '20/hour',
        'timings': '120/hour',
        # The doubtful words of «ساهم» (apps/quality/services/words.py): answers, and the next word asked for.
        'words': '300/hour',
        'words_read': '600/hour',
        # The discussion (apps.discussion): the services hold the finer limits (a newcomer's five a day).
        'contribute': '60/hour',
        'useful': '600/hour',
        'uploads': '40/hour',
        'codes': '10/hour',
        'reset': '20/hour',
        # Every other door that needs an account (one's own page, follows, notices, the reviewers' desk), per account,
        # not per address: a reviewer at work makes two requests an item, the header asks for its dot every two minutes.
        'account': '120/min',
        # The assistants' sign-in (apps.oauth): the token endpoint per address, and registrations (Claude registers
        # again on each fresh connection when it does not use its metadata document). Every Claude user's refresh comes
        # from Anthropic's few addresses, every ChatGPT user's from OpenAI's: a limit per address is a limit on everyone,
        # so it is wide; the MCP server's quotas are per account.
        'oauth': '600/min',
        'oauth_register': '30/hour',
        # The metadata documents, read by the assistants' servers as the token endpoint is: as wide, in a count of their own.
        'oauth_metadata': '600/min',
        # The assistant's link a person's browser opens to connect: one a connection. Sixty a minute leaves the many
        # people behind one mobile address alone and bounds the requests one address can make the server keep.
        'oauth_authorize': '60/min',
        'flags': '30/hour',
        'checks': '600/hour',
        # The measures' door (apps.analytics), by network like every limit: a batch holds 40 events at most, and one
        # Moroccan mobile address carries many readers.
        'measure': '120/min',
        # The signed links to the database's files (POST /api/open/ticket/): one a file, five files a day.
        'open_ticket': '60/hour',
        # An account's keys and their use (/api/access/keys/), per account.
        'access_keys': '30/min',
        # The access desk (/api/access/desk/), per account: a superuser reading lists and answering requests.
        'access_desk': '240/min',
        # Access on request (apps.opendata): sending a request, answering what was asked, ending one's access, per
        # account. A person sends one request and answers a line or two.
        'access_request': '10/hour',
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=90),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    # Every token carries a mark of the account's password: a new or voided password ends the access tokens made under
    # the old one at once, not after their 30 minutes (the refresh view checks the same mark: accounts/api/serializers.py).
    # No extra query: the account is read for every signed-in request anyway.
    'CHECK_REVOKE_TOKEN': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'AUTH_HEADER_TYPES': ('Bearer',),
}

CORS_ALLOWED_ORIGINS = []

# The corpus on disk: fetched files (samples/, later the full archive), page images (renders/),
# reports. Outside git; on a server, its own volume.
CORPUS_DIR = Path(config('CORPUS_DIR', default=str(BASE_DIR.parent / 'data')))
# Pictures drawn because a reader asked (config/drawing.py: a page's image, a link's picture, a card to forward): at
# most DRAWING_AT_ONCE drawn at a time in the whole site, DRAWING_PER_MINUTE new ones a minute from one address (those
# drawn already are served whatever the count), and each folder of them kept under DRAWN_FOLDER_MOST bytes, the least
# lately used removed first.
DRAWING_AT_ONCE = config('DRAWING_AT_ONCE', default=3, cast=int)
DRAWING_PER_MINUTE = config('DRAWING_PER_MINUTE', default=30, cast=int)
DRAWN_FOLDER_MOST = config('DRAWN_FOLDER_MOST', default=2_000_000_000, cast=int)
# The name every fetcher gives the sites it reads (the SGG, Adala, Parliament, the press feeds, the crawler and
# platform lists): the project's own, with the page that says who runs it and how to write to us. Never a browser's.
FETCH_USER_AGENT = config('FETCH_USER_AGENT', default='')

# OCR through Claude. The key comes from the environment only. Every run is priced and the
# total never passes the budget: a batch that could is refused before it is sent.
ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')
OCR_BUDGET_USD = config('OCR_BUDGET_USD', default=10.0, cast=float)
# The models the budget allows, comma-separated (A10 of the consumer plan: one model only): a request naming
# another is refused before it is sent. Empty allows every priced model.
LLM_MODELS_ALLOWED = config('LLM_MODELS_ALLOWED', default='')
# The structuring ledger, under CORPUS_DIR. A `.jsonl` one is appended to, never rewritten: the archive run's
# 160,000 entries would make the JSON list a 40 MB file written again at every batch.
LLM_LEDGER = config('LLM_LEDGER', default='reports/llm_ledger.json')

# Search by meaning (B7 and B25 of the search plan, 24 Oct 2026): a local model, never an API. The model's folder
# (ONNX, its tokenizer, SOURCE.txt with its licence and hash), the model server that embeds a question (one process
# beside Django, `manage.py serve_models`), and whether search uses it: on since 25 Oct 2026, when the test set said it
# helps every register and intent (top 3: 187 → 387 of 1,036; nDCG@10 0.209 → 0.441). Without the server, BM25 alone.
SEARCH_MODEL = config('SEARCH_MODEL', default='bge-m3')
SEARCH_MODEL_DIR = config('SEARCH_MODEL_DIR', default=str(BASE_DIR.parent / 'models' / 'bge-m3-int8'))
SEARCH_MODEL_URL = config('SEARCH_MODEL_URL', default='http://127.0.0.1:8090')
SEARCH_MEANING = config('SEARCH_MEANING', default=True, cast=bool)
# BM25's share when its scores and the meaning's are summed (B8: chosen on the tune split, held on dev: 0.5; the pilot's
# 0.2 was worse with today's search); a negative value fuses by reciprocal rank instead.
SEARCH_FUSION_WEIGHT = config('SEARCH_FUSION_WEIGHT', default=0.5, cast=lambda v: None if float(v) < 0 else float(v))
# N11 of the read-and-trusted review: beside what the words found, a decree, order or decision found by meaning alone
# comes after them ('rules'; 'all' moves every meaning-only text, '' none). Graded tune split: nDCG@10 0.466 → 0.493,
# recall@20 0.443 → 0.480, top 3 1,132 → 1,129; held on dev: 0.505 → 0.526, 0.486 → 0.520, 372 → 371. 'all' lost 30 of
# the top 3. The floor (a cosine a meaning-only article needs) changed nothing at 0.45 or 0.5: left at 0.
SEARCH_MEANING_AFTER = config('SEARCH_MEANING_AFTER', default='rules')  # '', 'rules' or 'all'
SEARCH_MEANING_FLOOR = config('SEARCH_MEANING_FLOOR', default=0.0, cast=float)
# A broken plural meets its singular through the lemma table (B4): off, the test set lost 14 of its top 3 with it.
SEARCH_LEMMAS = config('SEARCH_LEMMAS', default=False, cast=bool)
# B10: the thesaurus's people's words read as everyday words, until the measures say it helps.
SEARCH_THESAURUS = config('SEARCH_THESAURUS', default=False, cast=bool)
# B15: the box that answers first, with the law's sentence: off until its measures have been read.
SEARCH_ANSWER = config('SEARCH_ANSWER', default=False, cast=bool)
# Drafts (topics' items, situations) shown, marked as drafts: in development, and on a server behind the password where
# the few readers are the reviewers (25 Oct 2026). Off where the public reads: F17, nothing before a check.
SHOW_DRAFTS = config('SHOW_DRAFTS', default=False, cast=bool)
# DB-IP's free ASN database (`fetch_geoip`), which names an address's network operator for the day of reading's
# READING_OPERATOR_CEILING (apps/corpus/services/operators.py).
GEOIP_DIR = config('GEOIP_DIR', default=str(CORPUS_DIR / 'geo'))

# The password in front of the whole site (apps.gate, 25 Oct 2026), while it is shown to a few; empty, none.
GATE_PASSWORD = config('GATE_PASSWORD', default='')
# C12 of the constitution review: a question inside a named code searched in that code first, until measured.
SEARCH_INSIDE = config('SEARCH_INSIDE', default=False, cast=bool)

# The public API's limit per address (apps.opendata.throttles). 240 a minute since HM17 of the hard-moment review
# (7 Nov 2026): one mobile IPv4 holds many subscribers, and a cold home asks 11 answers, a law 5, a search 4. A request
# with a key (X-Api-Key) is counted on its access's own limits instead (ACCESS_SIZES, apps/opendata/services/usage.py).
PUBLIC_API_RATES = {'anonymous': '240/min'}
# The database's editions (apps.opendata): one folder an edition, written on the first day of each month
# (deploy/law-edition.timer), the newest three kept.
# The address «عن «قانون»» gives readers to write to (P18 of the polish review, 19 Oct 2026); empty hides the line.
CONTACT_EMAIL = config('CONTACT_EMAIL', default='')
# The public repository of the site's code, given on «عن «قانون»» and «ساهم»; empty until the code is published.
SOURCE_URL = config('SOURCE_URL', default='')
# How many people each doubtful word of «ساهم» is asked of before a reviewer weighs it (apps/quality/services/words.py).
WORD_ANSWERS = config('WORD_ANSWERS', default=3, cast=int)
OPEN_DATA_DIR = config('OPEN_DATA_DIR', default=str(CORPUS_DIR / 'open'))
# The dump's downloads (/api/open/ and /api/open/latest/<file>), closed on 2 Nov 2026 until the curated data is
# ready: closed, they answer 403 `open_data.closed` and /data says it is coming. The files and
# export_open_data stay; the site's own API is not touched, the app reads it.
# Since 16 Nov 2026 it has three positions (apps/opendata/services/gate.py): `closed`, `request` (the database and the
# keyed API are given to a person the staff accepted) and `open`. The old True reads `open`, False `closed`.
OPEN_DATA = config('OPEN_DATA', default='closed')
# Access on request (apps.opendata). The terms a request accepts: their date is their version.
ACCESS_TERMS = '2026-11-16'
# The sizes of limit an access is given when it is accepted: requests a minute, calls a day, articles a day. A
# partner's access carries its own numbers.
ACCESS_SIZES = {'try': {'minute': 30, 'calls': 1000, 'articles': 2000},
                'app': {'minute': 120, 'calls': 20000, 'articles': 10000}}
ACCESS_MONTHS = 12               # an access lasts this long unless its end date is set otherwise
ACCESS_KEYS = 2                  # live keys an access may hold: one can replace the other without a break
ACCESS_ASK_AGAIN_DAYS = 30       # a declined account may ask again after this many days
ACCESS_ANSWER_DAYS = 5           # the working days /data promises an answer within
ACCESS_DOWNLOADS_A_DAY = 5       # files of an edition an access may take in a day
# Where nginx sends an edition's data files from (deploy/nginx.conf, an internal location aliasing OPEN_DATA_DIR): Django
# decides who may have a file and answers with X-Accel-Redirect to it. Empty (development, the tests), Django streams the
# file itself. Production: /_open.
OPEN_DATA_ACCEL = config('OPEN_DATA_ACCEL', default='')
# Who is written to when a request arrives (comma-separated addresses); empty, nobody.
ACCESS_LETTER_TO = [a.strip() for a in config('ACCESS_LETTER_TO', default='').split(',') if a.strip()]
# The site's own address (link previews, the open data's references, sitemaps): set it in production.
SITE_URL = config('SITE_URL', default='http://localhost:5190')
# The built web app (its index.html is the shell a law's address is answered with: corpus/services/heads.py).
WEB_DIST = config('WEB_DIST', default=str(BASE_DIR.parent / 'web' / 'dist'))

# What the site counts (apps.analytics, the analytics review, 15 Nov 2026): tasks, never people. Closed, the door
# (POST /api/measure/) answers 204 and writes nothing. The events are kept ANALYTICS_DAYS days; their counts for good.
ANALYTICS_OPEN = config('ANALYTICS_OPEN', default=True, cast=bool)
ANALYTICS_DAYS = config('ANALYTICS_DAYS', default=90, cast=int)
# nginx's access log, where `count_machines` reads yesterday's machines each night (apps/analytics/services/machines.py):
# the file rotated the night before last (compressed), last night's and today's, since a day's lines span the three
# (deploy/logrotate-nginx). Comma-separated; a missing one is passed over.
NGINX_LOGS = [p.strip() for p in config('NGINX_LOGS', default='/var/log/nginx/law/access.log.2.gz,'
                                                             '/var/log/nginx/law/access.log.1,'
                                                             '/var/log/nginx/law/access.log').split(',') if p.strip()]
# Who gets the Monday letter of the week's counts (`analytics_letter`): addresses separated by commas; empty, nobody.
ANALYTICS_LETTER_TO = config('ANALYTICS_LETTER_TO', default='',
                             cast=lambda v: [a.strip() for a in v.split(',') if a.strip()])

# The discussion layer (the decisions of 19 Oct 2026, D1–D14).
# Readers write only once the legal groundwork is done (D12: the CNDP declaration, the terms and the privacy page
# reviewed by a Moroccan lawyer): until then every write answers discussion.closed. Dev and tests open it.
DISCUSSION_OPEN = config('DISCUSSION_OPEN', default=False, cast=bool)
# The development's demo people (seed_demo_*, «demo-…»): off where the public reads, so no fictional notary answers a
# reader (N1 of the read-and-trusted review, 27 Oct 2026); `recount_discussions` after changing it.
SHOW_DEMO_PEOPLE = config('SHOW_DEMO_PEOPLE', default=False, cast=bool)
# Accounts made before this were the development's: the public site's database began as its copy (25 Oct 2026).
DEMO_UNTIL = datetime(2026, 10, 25, tzinfo=UTC)
# How long a process keeps the list of those accounts (counters.demo); tests read it each time.
DEMO_IDS_KEPT = 60
# New accounts (27 Oct 2026): closed by default, every sign-up answers
# registration.closed and the web offers none; accounts already made still sign in. Dev and tests open it.
REGISTRATION_OPEN = config('REGISTRATION_OPEN', default=False, cast=bool)
# «المتابعة بحساب Google» (9 Nov 2026, apps/accounts/services/google.py): off without a
# client id, from Google Cloud's console (an OAuth client of type «Web application», the redirect
# https://3adala.com/auth/google). The web's id first; GOOGLE_OAUTH_EXTRA_CLIENT_IDS, comma-separated, for a phone's.
GOOGLE_OAUTH_CLIENT_ID = config('GOOGLE_OAUTH_CLIENT_ID', default='')
GOOGLE_OAUTH_CLIENT_IDS = [c.strip() for c in f"{GOOGLE_OAUTH_CLIENT_ID},{config('GOOGLE_OAUTH_EXTRA_CLIENT_IDS', default='')}"
                           .split(',') if c.strip()]
# The check before publishing (29 Oct 2026): a model reads each post and comment and answers publish,
# return (to its author, with a rule) or hold (for a moderator); it never writes what readers see. 'model' asks
# CHECK_MODEL; 'pass' publishes on the fixed patterns alone (development without a key, and the tests); 'markers'
# stands in for the model while developing (check._markers). When the
# check cannot run, or the month's CHECK_BUDGET_USD is spent, the post waits for a moderator (C2).
DISCUSSION_CHECK = config('DISCUSSION_CHECK', default='model')
CHECK_MODEL = config('CHECK_MODEL', default='claude-haiku-5-5')
# One try, a few seconds: a check that fails holds the post for a moderator, and the writer's request holds a worker
# while it waits (two tries of ten seconds held one for twenty).
CHECK_TIMEOUT_S = config('CHECK_TIMEOUT_S', default=6.0, cast=float)
CHECK_BUDGET_USD = config('CHECK_BUDGET_USD', default=20.0, cast=float)
# Voices and pictures in the topics (C1 of 29 Oct 2026): off at launch. The model reads no voice, and pictures of
# papers carry names and card numbers.
DISCUSSION_MEDIA = config('DISCUSSION_MEDIA', default=False, cast=bool)
# Voices, pictures and profession cards people send: outside git and outside any public folder (it may be a link to
# another disk). Never served as files: apps.media serves them by state.
UPLOADS_DIR = Path(config('UPLOADS_DIR', default=str(BASE_DIR.parent / 'uploads')))
VOICE_SECONDS = 120
# Two minutes at Safari's AAC rate with room to spare; the browser records 48 kbps Opus (720 KB).
VOICE_MAX_BYTES = 6 * 1024 * 1024
# How long a link an <audio> carries works; the player asks for another when it resumes later.
VOICE_LINK_SECONDS = 30 * 60
# A voice or a picture uploaded and never published is deleted after this.
DRAFT_HOURS = 24

# The discussion's letters are sent by a job (send_notice_letters), this far apart: the mail provider takes a few a
# second (Resend: two).
NOTICE_LETTER_PACE_S = config('NOTICE_LETTER_PACE_S', default=0.5, cast=float)

# The six-digit code that proves an email address (D3).
EMAIL_CODE_TTL_MINUTES = 15
EMAIL_CODE_MAX_TRIES = 5
EMAIL_CODES_PER_HOUR = 5
# The letters go through Resend (3 Nov 2026) when RESEND_API_KEY is set. Since 4 Nov 2026 they come from the site's
# own domain, mail.3adala.com, to be verified there (DKIM, SPF, DMARC) before the key is set. Without a key, SMTP as
# before, or whatever EMAIL_BACKEND
# names (dev prints letters, the tests keep them). A call to Resend waits REQUESTS_TIMEOUT at most: a letter is sent
# inside a request.
RESEND_API_KEY = config('RESEND_API_KEY', default='')
ANYMAIL = {'RESEND_API_KEY': RESEND_API_KEY, 'REQUESTS_TIMEOUT': (3.05, 10)}
EMAIL_BACKEND = config('EMAIL_BACKEND', default='anymail.backends.resend.EmailBackend' if RESEND_API_KEY
                       else 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = config('EMAIL_HOST', default='localhost')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_TIMEOUT = 10
# The address letters come from; the name beside it is the reader's language's («قانون», SITE_NAME: mail.from_name).
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default=f'{SITE_NAME} <noreply@localhost>')
SERVER_EMAIL = DEFAULT_FROM_EMAIL
# A reset link (/reset) works this long, and once: a new password, a new address or a sign-in ends it.
PASSWORD_RESET_TIMEOUT = 3 * 60 * 60
# The mails anyone may make us send one account (a reset link, a code to prove an address):
# one per account and kind every ACCOUNT_MAIL_GAP_S, at most ACCOUNT_MAIL_PER_DAY a day; past it, answered as sent.
ACCOUNT_MAIL_GAP_S = 60
ACCOUNT_MAIL_PER_DAY = 5
# And per inbox, whichever account asks: codes and reset links each, a day (mail.may_reach).
ACCOUNT_MAIL_PER_ADDRESS = 3
# The brake on wrong passwords (apps/accounts/services/brake.py): LOGIN_BRAKE_FAILURES wrong passwords
# from one address on one account within the window and that address waits on that account; LOGIN_BRAKE_ACCOUNT_FAILURES
# from anywhere and the account waits. The «auth» throttle counts an address, and a city can sit behind one address. A
# reset link still gets the account's holder in, and lifts both.
LOGIN_BRAKE_FAILURES = 10
LOGIN_BRAKE_ACCOUNT_FAILURES = 50
LOGIN_BRAKE_WINDOW_S = 15 * 60
LOGIN_BRAKE_LOCK_S = 15 * 60

# The site in the assistants (the MCP review, MC1–MC25, 3 Nov 2026).
# The site is the OAuth authorization server (apps.oauth) for one resource, its MCP server (apps.mcp, the law-mcp service
# at /mcp). The issuer and the resource are the site's address: an assistant keeps them, so they change only with it.
OAUTH_ISSUER = config('OAUTH_ISSUER', default=SITE_URL.rstrip('/'))
MCP_RESOURCE = config('MCP_RESOURCE', default=SITE_URL.rstrip('/') + '/mcp')
OAUTH_ACCESS_SECONDS = 60 * 60
OAUTH_REFRESH_DAYS = 60
OAUTH_REQUEST_SECONDS = 10 * 60      # a request waiting for the person's answer on /connect
OAUTH_CODE_SECONDS = 60
CIMD_KEEP_SECONDS = 24 * 60 * 60     # a client's metadata document is read again after a day
# The hosts whose metadata documents the server fetches (apps/oauth/services/clients.py): the assistants it names on the
# consent page. A fetch leaves from the server's own connection, so any other client registers (/oauth/register), which
# fetches nothing. Comma-separated, exact host names.
OAUTH_METADATA_HOSTS = [h.strip() for h in config('OAUTH_METADATA_HOSTS', default='claude.ai,claude.com,chatgpt.com,openai.com')
                        .split(',') if h.strip()]
OAUTH_METADATA_SECONDS = 5           # a whole fetch, from the connection to the last byte
OAUTH_METADATA_REFUSAL_SECONDS = 5 * 60   # a document that could not be had or was refused is not asked for again before
# Who may call it (3 Nov 2026: open for now, the sign-in kept for later): 'open', no
# sign-in, a token still read when one is sent (the account's own limits then apply); 'required', every call needs a
# account on the site (the sign-in stays built, advertised and tested either way: tools that need an account come later).
MCP_AUTH = config('MCP_AUTH', default='open')
# Per account (C4, «tight»): calls a minute and a day, and the article bodies served a day.
MCP_QUOTAS = {'minute': config('MCP_QUOTA_MINUTE', default=20, cast=int), 'day': config('MCP_QUOTA_DAY', default=300, cast=int),
              'articles': config('MCP_QUOTA_ARTICLES', default=600, cast=int)}
# Without an account: a platform's users share one wide limit (they all arrive from its addresses), an hour's, so one
# user who spends it holds the others for the rest of that hour, not the day; the requests a minute and an hour, the
# article bodies an hour. A ChatGPT user, known by the conversation subject ChatGPT sends, has its own share an hour
# inside its platform's. A direct caller has its own, a day's, tighter than the site's public API
# (apps/mcp/services/origin.py). Every request to /mcp counts, not only tool calls.
MCP_PLATFORM_LIMITS = {'minute': config('MCP_PLATFORM_MINUTE', default=600, cast=int),
                       'hour': config('MCP_PLATFORM_HOUR', default=5000, cast=int),
                       'articles': config('MCP_PLATFORM_ARTICLES', default=10000, cast=int)}
MCP_SUBJECT_LIMITS = {'minute': config('MCP_SUBJECT_MINUTE', default=20, cast=int),
                      'hour': config('MCP_SUBJECT_HOUR', default=150, cast=int),
                      'articles': config('MCP_SUBJECT_ARTICLES', default=300, cast=int)}
MCP_ADDRESS_LIMITS = {'minute': config('MCP_ADDRESS_MINUTE', default=30, cast=int),
                      'day': config('MCP_ADDRESS_DAY', default=1000, cast=int),
                      'articles': config('MCP_ADDRESS_ARTICLES', default=2000, cast=int)}
# The site's day of reading (apps/corpus/services/reading.py, 4 Nov 2026: so that one crawler cannot copy the whole
# site and its law in a day): the articles and printed pages a reader is given a day. READING_BUDGET to each
# browser (its cookie); READING_BUDGET to all the requests without the cookie from one address together; ten times
# READING_BUDGET (30,000) to everything read from one address together, browsers included (an IPv6 address by its /56);
# READING_BUDGET to a reader the check let past. 0 turns it off. A key (X-Api-Key) is read by its access, with the
# access's own articles a day (ACCESS_SIZES), whatever this says.
READING_BUDGET = config('READING_BUDGET', default=3000, cast=int)
# The passes the check gives one address a day, only to a reader past their day: each is READING_BUDGET more, so a
# crawler that buys solved checks is held too. Many readers share a mobile address, and an honest one only reaches the
# day when its address's ceiling is spent: ten lets that many of them past.
READING_PASSES = config('READING_PASSES', default=10, cast=int)
# A ceiling for every browser of one network operator together (its ASN, from DB-IP's database), the articles a day; 0,
# the default, sets none. It is off on purpose: one Moroccan mobile operator carries a large part of the honest readers,
# so a ceiling per operator can lock a city out. It is for whoever runs the site to set, well above an operator's busiest
# day, to stop a crawler that walks through many networks of one provider.
READING_OPERATOR_CEILING = config('READING_OPERATOR_CEILING', default=0, cast=int)
# Cloudflare's Turnstile, the check past a day's reading (both keys from Cloudflare's dashboard). Without them the
# reader is told to come back tomorrow.
TURNSTILE_SITE_KEY = config('TURNSTILE_SITE_KEY', default='')
TURNSTILE_SECRET_KEY = config('TURNSTILE_SECRET_KEY', default='')
# Search engines (the search-engines review, 9 Nov 2026; apps.seo). A law's page drawn by the app's components on the server
# (IX1): the drawing service (web/scripts/ssr-server.mjs, the law-ssr unit) at SSR_URL; empty, the head alone, as in
# development and the tests. SSR_TIMEOUT: seconds before the page goes with its head alone.
SSR_URL = config('SSR_URL', default='')
SSR_TIMEOUT = config('SSR_TIMEOUT', default=3.0, cast=float)
# A law's answer larger than this (bytes) is not drawn: a giant table would outlast SSR_TIMEOUT on every visit.
SSR_MOST = config('SSR_MOST', default=1_000_000, cast=int)
# Seconds no page is sent to the drawing service after it gave no answer in time, said it was busy (503) or was down:
# the pages go with their head alone meanwhile, and no worker waits on it (apps/seo/services/ssr.py).
SSR_REST = config('SSR_REST', default=10.0, cast=float)
# Whether search engines may index the site: 'open' or 'closed'. nginx says noindex on every page while it is closed
# (deploy.sh writes /etc/nginx/law-indexing.conf from this line of the server's .env, IX13); IndexNow is told nothing
# until it is open (IX14). INDEXING_OPENED: the day it opened (YYYY-MM-DD); the sitemaps give a wave more every two
# weeks from it (wave 1: the codes, laws, dahirs and the pages people land on; 2: decrees and decisions; 3: orders and
# every article). SITEMAP_WAVE, when set, says the wave instead.
INDEXING = config('INDEXING', default='closed')
INDEXING_OPENED = config('INDEXING_OPENED', default='')
SITEMAP_WAVE = config('SITEMAP_WAVE', default=0, cast=int)
SITEMAPS_DIR = config('SITEMAPS_DIR', default=str(CORPUS_DIR / 'seo' / 'sitemaps'))
# IndexNow's key (Bing, Yandex and the others it tells): empty, one is derived from SECRET_KEY (it is published anyway,
# at /indexnow.txt).
INDEXNOW_KEY = config('INDEXNOW_KEY', default='')
# The MCP service's threads for the tools (each holds a database connection while it works).
MCP_THREADS = config('MCP_THREADS', default=4, cast=int)
