from django.apps import AppConfig


class SourcesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.sources'
    label = 'sources'

    def ready(self):
        from apps.sources import checks  # noqa: F401 — registers the deploy checks
