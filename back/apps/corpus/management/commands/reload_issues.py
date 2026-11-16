"""Load BO issues again from their texts.json, oldest first: after a fix to the loader (a whole text, a rubric from the
contents) or to texts.json itself (recut_swallowed, split_glued, a table row given back), so the corpus shows it.

After each issue, a version this texts.json did not write is swept when its words stand in one it did (an older
run's texts). Before loading, a
text that holds versions from two issues is parted. A loader of 18 Oct 2026 put two texts with one
address into one row: the Constitutional Court's decision 261.26 (BO 7479) and a minister's order also numbered
261.26 (BO 7489), so the court's page showed the order's two articles (215 texts so). Their BO versions are dropped,
and each issue's load gives its text back its own, at its own address (`settle`).

    reload_issues                     # what it would do
    reload_issues --write             # every issue that has a texts.json
    reload_issues 7213 7228 --write   # these, and the issues of the texts they share
"""
import json
import time
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count, Q

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.services.issue_structure import load_texts
from apps.sources.models import Edition, Issue


class Command(BaseCommand):
    help = 'Load issues again from their texts.json, oldest first, parting texts that hold two issues\' versions.'

    def add_arguments(self, parser):
        parser.add_argument('keys', nargs='*', help='issue keys (7213, 7465-bis); none for every issue')
        parser.add_argument('--write', action='store_true')
        parser.add_argument('--covers', action='store_true', help='load covers and copies too (FX3)')

    def handle(self, *args, keys, write=False, **opts):
        issues = Issue.objects.filter(edition=Edition.GENERAL_AR, document__isnull=False)
        published = Q(versions__consolidation=Consolidation.AS_PUBLISHED, versions__language='ar')
        shared = list(Text.objects.annotate(n=Count('versions', filter=published)).filter(n__gt=1))
        documents = set(Version.objects.filter(text__in=shared, consolidation=Consolidation.AS_PUBLISHED, language='ar')
                        .values_list('source_document_id', flat=True))
        wanted = {Issue.parse_key(k) for k in keys}
        chosen = [i for i in issues if not keys or (i.number, i.suffix) in wanted or i.document_id in documents]
        chosen = [i for i in chosen if (self.workdir(i) / 'texts.json').exists()]
        # A copy has no pages of its own and a cover's texts took the fullest cut of its copies (FX3 of
        # the mended-Bulletin review): their texts.json would bring back what folding put right, unless asked for by name.
        folded = {i.pk for i in chosen if i.copy_of_id} | set(
            Issue.objects.filter(copies__isnull=False, pk__in=[i.pk for i in chosen]).values_list('pk', flat=True))
        if folded and not opts.get('covers'):
            self.stdout.write(f'{len(folded)} covers and copies left as they are (--covers loads them)')
            chosen = [i for i in chosen if i.pk not in folded]
        chosen.sort(key=lambda i: (i.date, i.number, i.suffix))
        self.stdout.write(f'{len(shared)} texts hold versions from two issues; {len(chosen)} issues to load')
        if not write:
            for t in shared[:20]:
                self.stdout.write(f'  {t.akn_uri}: {t.title_ar[:80]}')
            return
        with transaction.atomic():
            Version.objects.filter(text__in=shared, consolidation=Consolidation.AS_PUBLISHED, language='ar').delete()
            Text.objects.filter(pk__in=[t.pk for t in shared]).update(first_published_in=None)
        start = time.monotonic()
        for n, issue in enumerate(chosen, 1):
            texts = json.loads((self.workdir(issue) / 'texts.json').read_text())
            written: set[int] = set()
            counts = load_texts(issue, texts, written)
            # What an earlier texts.json made and this one makes elsewhere (an order once filed as a decision) goes
            # when its words, nine letters in ten, stand in a text this load wrote. One whose words this texts.json
            # lost stays: BO 7547's was described again on 19 Oct and found 9 of its 61 texts; the corpus keeps the
            # earlier 52.
            stale = Version.objects.filter(source_document=issue.document, consolidation=Consolidation.AS_PUBLISHED,
                                           language='ar').exclude(pk__in=written)
            held = '\n'.join(Article.objects.filter(version_id__in=written).values_list('body', flat=True)) if stale else ''
            for v in stale.select_related('text'):
                bodies = [b for b in v.articles.values_list('body', flat=True) if len(b) >= 80]
                # Nine letters in ten: what is left is «ينشر هذا القرار بالجريدة الرسمية.» and a signature.
                if not bodies or sum(len(b) for b in bodies if b[:300] in held) < 0.9 * sum(len(b) for b in bodies):
                    continue
                self.stdout.write(f'  swept {v.text.akn_uri}: {v.text.title_ar[:70]}')
                text = v.text
                v.delete()
                if not text.versions.exists() and not text.finance_laws.exists():
                    text.delete()
                elif text.first_published_in_id == issue.pk:
                    text.first_published_in = None
                    text.save(update_fields=['first_published_in'])
            self.stdout.write(f'{n}/{len(chosen)} {issue.key} {issue.date}: {counts} ({time.monotonic() - start:.0f} s)')
        from apps.sources.services import coverage
        coverage.refresh()

    @staticmethod
    def workdir(issue: Issue) -> Path:
        return Path(settings.CORPUS_DIR) / 'reports' / 'issues' / issue.key
