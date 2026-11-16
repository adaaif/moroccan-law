"""What `manage.py check --deploy` refuses about the fetchers."""
from django.conf import settings
from django.core.checks import Error, Tags, register


@register(Tags.security, deploy=True)
def fetchers_named(app_configs, **kwargs):
    """A server's fetchers tell the sites they read who runs them (apps/sources/services/fetch.py). The setting has no
    default, so a deploy that forgot it stops here rather than at the night's first fetch."""
    if settings.FETCH_USER_AGENT.strip():
        return []
    return [Error('FETCH_USER_AGENT is empty: the fetchers would refuse to run.',
                  hint="Set it in the server's .env to the site's name and a page that says who runs it, such as "
                       '«example/1 (+https://example.org/about)» (back/.env.example).',
                  id='sources.E001')]
