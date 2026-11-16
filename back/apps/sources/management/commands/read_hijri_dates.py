"""Every issue's Hijri date, read from its masthead (U13 of the Moroccan-design review); free. --write keeps them."""
from django.core.management.base import BaseCommand

from apps.sources.models import Issue, Page
from apps.sources.services.hijri import read


class Command(BaseCommand):
    help = "Reads each issue's Hijri date from its first page's masthead."

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')
        parser.add_argument('--all', action='store_true', help='also issues that have one')

    def handle(self, *args, **opts):
        issues = Issue.objects.exclude(document=None)
        if not opts['all']:
            issues = issues.filter(hijri_date='')
        issues = list(issues)
        first = {p.document_id: p for p in Page.objects.filter(document_id__in={i.document_id for i in issues}, index=0)
                 .only('document_id', 'text', 'layer_text')}
        found = []
        for i in issues:
            p = first.get(i.document_id)
            words = read((p.text or p.layer_text or '') if p else '', i.date)
            if words:
                i.hijri_date = words
                found.append(i)
        if opts['write']:
            Issue.objects.bulk_update(found, ['hijri_date'], batch_size=500)
        self.stdout.write(f'{len(found)} of {len(issues)} issues dated in Hijri' + ('' if opts['write'] else ' (not written: --write)'))
