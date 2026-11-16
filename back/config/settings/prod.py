from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

if SECRET_KEY == INSECURE_SECRET_KEY or len(SECRET_KEY) < 50:  # noqa: F405
    raise ImproperlyConfigured('Set a real SECRET_KEY (50+ characters) for production.')

DEBUG = False
ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=Csv())

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# What `check --deploy` asks of Django that nginx, in front of it, answers for every request (tools/ci/backend.sh check
# fails on any other warning): W004, Strict-Transport-Security (deploy/nginx-headers.conf); W008, plain http sent to
# https ($law_to_https in deploy/nginx.conf); W019, X-Frame-Options, which nginx sets on every answer with Django's
# own hidden (SAMEORIGIN, DENY for /connect, none for /embed/: $law_xfo in deploy/nginx.conf).
SILENCED_SYSTEM_CHECKS = ['security.W004', 'security.W008', 'security.W019']

# One proxy (nginx) in front: the client is the address it appended to X-Forwarded-For, never an address a
# client wrote there itself (the public API's limits count by it).
REST_FRAMEWORK = {**REST_FRAMEWORK, 'NUM_PROXIES': 1}  # noqa: F405

# The law's pages drawn on the server (IX1 of the search-engines review): the law-ssr unit beside gunicorn.
SSR_URL = config('SSR_URL', default='http://127.0.0.1:8043')

# Redis is required (S13 of the performance audit): the request limits must hold across workers. The limits' counts go
# to their own store that never evicts when COUNTERS_REDIS_URL names it (deploy/compose.yml's «counters»).
CACHES = redis_caches(config('REDIS_URL'), DATABASES['default']['NAME'], config('COUNTERS_REDIS_URL', default=''))  # noqa: F405

# Each worker keeps its connection between requests (S19): opening a Postgres connection for each one costs time.
# Health checks drop one the server closed. Development keeps 0 (runserver answers each request on a new thread).
DATABASES['default']['CONN_MAX_AGE'] = config('CONN_MAX_AGE', default=600, cast=int)  # noqa: F405
DATABASES['default']['CONN_HEALTH_CHECKS'] = True  # noqa: F405
# No just-in-time compiling: the site asks short questions, and Postgres compiled the ones it guessed costly (a post of
# a hundred thousand comments, the month's counts, search's words), most of a slow query's time (the load test of
# 30 Oct 2026).
DATABASES['default'].setdefault('OPTIONS', {})['options'] = '-c jit=off'  # noqa: F405
