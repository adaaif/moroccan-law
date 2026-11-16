"""Laws read into the text before them, cut again from the issue's page readings (T3 of the work plan).

    recut_swallowed                 # name them, issue by issue
    recut_swallowed --issue 7383    # one issue
    recut_swallowed --write         # load them and give the host articles back their own words
"""
from django.core.management.base import BaseCommand

from apps.corpus.services import recut
from apps.sources.models import Edition, Issue


class Command(BaseCommand):
    help = 'Find (and with --write, load) the texts an issue prints that no text from it holds.'

    def add_arguments(self, parser):
        parser.add_argument('--issue', type=int)
        parser.add_argument('--write', action='store_true')
        parser.add_argument('--no-files', action='store_true', help='repair the database only (FX6)')
        parser.add_argument('--empty', action='store_true', help='only issues that hold a title-only text (1956 on)')

    def handle(self, *args, issue=None, write=False, **opts):
        issues = Issue.objects.filter(edition=Edition.GENERAL_AR, document__isnull=False).order_by('number', 'suffix')
        if issue:
            issues = issues.filter(number=issue)
        if opts.get('empty'):
            # The issues that hold a text with a title and nothing under it (FX6 of the mended-Bulletin review).
            from django.db.models import Count
            from apps.corpus.models import Version
            empty = (Version.objects.filter(consolidation='as_published', text__first_published_in__date__gte='1956-01-01')
                     .annotate(n=Count('articles')).filter(n=0).exclude(preamble__regex=r'.{200}')
                     .values_list('text__first_published_in', flat=True))
            issues = issues.filter(pk__in=set(empty))
        found = left = 0
        for one in issues:
            steps = recut.plan(one)
            for p in steps:
                if p['item'] is None:
                    left += 1
                    self.stdout.write(f'{one.key}: {p["printed"]} p.{p["page"]} left alone ({p["why"]})')
                    continue
                found += 1
                host = p['host']
                self.stdout.write(f'{one.key}: {p["kind"]} {p["printed"]} p.{p["page"]}, '
                                  f'{len(p["item"]["articles"])} articles'
                                  + (f', its dahir in {host.version.text.akn_uri} {host.label}' if host else ', dropped'))
            if write and any(p['item'] for p in steps):
                self.stdout.write(f'  {recut.repair(one, log=self.stdout.write, files=not opts.get("no_files"))}')
        self.stdout.write(f'{found} texts to cut again, {left} left alone')
