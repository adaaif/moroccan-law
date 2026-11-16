"""Register every file of CORPUS_DIR/samples/manifest.json (written by the sample fetcher)."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.sources.models import DocumentKind, Edition, Source
from apps.sources.services.ingest import ingest_file

KINDS = {
    'bo_issue': (Source.SGG_BO, DocumentKind.BO_ISSUE),
    'consolidated_text': (Source.SGG_CONSOLIDATED, DocumentKind.CONSOLIDATED_TEXT),
    'adala_text': (Source.ADALA, DocumentKind.TEXT),
    'court_decision': (Source.CONSTITUTIONAL_COURT, DocumentKind.COURT_DECISION),
    'parliament': (Source.PARLIAMENT, DocumentKind.PARLIAMENT),
    'local_bulletin': (Source.LOCAL_AUTHORITIES, DocumentKind.BULLETIN),
    'code_html': (Source.OTHER, DocumentKind.CODE_PAGE),
}
EDITIONS = {
    'general_ar': Edition.GENERAL_AR,
    'translation_fr': Edition.TRANSLATION_FR,
    'conventions_ar': Edition.CONVENTIONS_AR,
    'announcements_ar': Edition.ANNOUNCEMENTS_LEGAL,
}


class Command(BaseCommand):
    help = 'Register the sample documents and read their pages.'

    def handle(self, *args, **options):
        root = Path(settings.CORPUS_DIR) / 'samples'
        for item in json.loads((root / 'manifest.json').read_text()):
            source, kind = KINDS[item['kind']]
            issue = None
            if item['kind'] == 'bo_issue':
                issue = {'edition': EDITIONS[item['edition']], 'number': item['number'], 'date': item['date']}
            doc = ingest_file(root / item['path'], source=source, kind=kind, language=item['lang'],
                              url=item['url'] if item['url'].startswith('http') else '',
                              title=item.get('title', ''), issue=issue,
                              meta={k: item[k] for k in ('folder', 'court') if k in item})
            self.stdout.write(f'{doc.path}: {doc.page_count or "-"} pages')
