from django.apps import AppConfig


class SeoConfig(AppConfig):
    """What search engines and the assistants' crawlers are given (the search-engines review, 9 Nov 2026): the published
    crawlers' addresses, the sitemaps, robots.txt and IndexNow. The law's pages they read are corpus's
    (apps/corpus/services/heads.py)."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.seo'
