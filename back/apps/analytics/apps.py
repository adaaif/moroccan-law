from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    """What the site counts to decide its work (the analytics review, 15 Nov 2026): pages shown, tools' steps, speeds
    and errors, by the hour, never who did them. The registry declares each measure; POST /api/measure/ is its one
    door."""
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.analytics'
