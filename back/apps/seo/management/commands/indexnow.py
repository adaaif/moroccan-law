"""Nightly (deploy/nightly.sh): IndexNow told of the texts that changed since its last run, with their articles, and of
the Bulletin's issues that came (apps/seo/services/indexnow.py). The first run after the site opens tells nothing: the
sitemaps carry the whole site. Nothing while INDEXING is not 'open'."""
import json
from datetime import datetime, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.corpus.models import Article, Text, Version, latest_ids
from apps.corpus.services.addresses import text_path
from apps.seo.services import indexnow
from apps.sources.models import Issue


def changed_since(since: datetime) -> list[str]:
    """The addresses of the texts changed since then, their articles, and the new issues they came in (four queries)."""
    texts = list(Text.objects.filter(updated_at__gte=since, versions__isnull=False).distinct()
                 .values_list('id', 'akn_uri'))
    newest = latest_ids(Version.objects.filter(text_id__in=[pk for pk, _ in texts]).order_by()
                        .values_list('id', 'text_id', 'valid_from', 'consolidation'))
    by_version = {v: t for t, v in newest.items()}
    paths = {pk: text_path(uri) for pk, uri in texts}
    out = list(paths.values())
    for version_id, eid in Article.objects.filter(version_id__in=list(by_version)).values_list('version_id', 'eid'):
        out.append(f'{paths[by_version[version_id]]}/{eid}')
    # A new issue: one dated this month whose texts came since (an issue holds no time of its own).
    issues = (Issue.objects.filter(texts_first_published__updated_at__gte=since, date__gte=since.date() - timedelta(days=31))
              .distinct().values_list('edition', 'number', 'suffix'))
    for edition, number, suffix in issues:
        out.append(f"/bo/{edition}/{number}{f'-{suffix}' if suffix else ''}")
    return out


class Command(BaseCommand):
    help = 'Tell IndexNow of the addresses changed since its last run.'

    def handle(self, *args, **options):
        state = Path(settings.SITEMAPS_DIR).parent / 'indexnow.json'
        now = timezone.now()
        if settings.INDEXING != 'open':
            self.stdout.write('closed to search engines: nothing told')
            return
        try:
            since = datetime.fromisoformat(json.loads(state.read_text())['since'])
        except (OSError, ValueError, KeyError):
            since = None
        told = indexnow.submit(changed_since(since)) if since else 0
        state.parent.mkdir(parents=True, exist_ok=True)
        state.write_text(json.dumps({'since': now.isoformat()}))
        self.stdout.write(f'told {told:,} addresses' if since else 'first run: the sitemaps carry the site; from now on')
