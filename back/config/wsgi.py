import os

from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.prod')

application = get_wsgi_application()

# Each worker reads the topics' folders before it answers anyone (apps/topics/services/kit/folders.py, `warm`); a
# folder it cannot read is read again, and its error raised, on the topic's own request. Then what a suggestion reads on
# first use (apps/search/services/search/suggestions.py, `warm`: N12 of the read-and-trusted review).
try:
    from apps.topics.services import kit

    kit.warm()
    from apps.search.services import search

    search.warm()
except Exception:
    import logging

    logging.getLogger(__name__).exception('topics or suggestions not warmed')
finally:
    # gunicorn --preload (UX12 of the phone-test review): this runs once, in the master, and every worker forks
    # warm. A connection the warm-up opened must not be shared by the forks: each opens its own on first use.
    from django.core.cache import caches
    from django.db import connections

    connections.close_all()
    for c in caches.all(initialized_only=True):
        c.close()
