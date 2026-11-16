"""The wording a person gives an amendment whose «……» the machine could not place (the health review, S3): each
article whole as it reads once changed, from a file in apps/consolidation/data/wordings/. Kept as a resolved «unplaced»
doubt (its `detail['wording']`), which `engine.apply_to` reads in place of the dotted reading; then the links run again
for the text. A file's `in_force` ({since, because}) says when a text whose entry into force hangs on a condition took
effect (a resolved «when» doubt, which `engine.standing` reads). Running a file again changes nothing.

    apply_wordings apps/consolidation/data/wordings/amo_65_00_27_22.yaml
"""
from pathlib import Path

import yaml
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.consolidation.models import Doubt
from apps.consolidation.services import engine
from apps.corpus.models import Text


class Command(BaseCommand):
    help = 'Give dotted amendments their whole wording, then run the links for the text they change.'

    def add_arguments(self, parser):
        parser.add_argument('paths', nargs='+')

    def handle(self, *args, **opts):
        texts = set()
        for path in opts['paths']:
            spec = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
            if spec.get('in_force'):
                # When a text whose entry into force hangs on a condition took effect, as a person found it.
                Doubt.objects.update_or_create(
                    text_uri=spec['text'], number='', by_uri=spec['text'], reason=Doubt.Reason.WHEN,
                    status=Doubt.Status.RESOLVED,
                    defaults={'resolved_at': timezone.now(), 'note': f'{Path(path).name} ({spec.get("checked", "")})',
                              'detail': {'on': str(spec['in_force']['since']), 'because': spec['in_force'].get('because', ''),
                                         'checked': spec.get('checked', ''), 'file': Path(path).name}})
            for number, lines in (spec.get('articles') or {}).items():
                Doubt.objects.update_or_create(
                    text_uri=spec['text'], number=str(number), by_uri=spec['by'], reason=Doubt.Reason.UNPLACED,
                    status=Doubt.Status.RESOLVED,
                    defaults={'by_article': spec.get('by_article', ''), 'resolved_at': timezone.now(),
                              'note': f'{Path(path).name} ({spec.get("checked", "")})',
                              'detail': {'wording': lines, 'checked': spec.get('checked', ''), 'file': Path(path).name}})
            self.stdout.write(f'{path}: {len(spec.get("articles") or {})} articles worded'
                              + (f', in force since {spec["in_force"]["since"]}' if spec.get('in_force') else ''))
            texts.add(spec['text'])
        stats = engine.run(list(Text.objects.filter(akn_uri__in=texts)), log=self.stdout.write)
        self.stdout.write(str(stats))
