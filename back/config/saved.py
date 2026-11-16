"""The name of a file a reader saves (an export, a dump, a table): the site's name first, «3adala-articles.docx»."""
from django.conf import settings


def file_name(what: str) -> str:
    return f'{settings.SITE_NAME}-{what}'
