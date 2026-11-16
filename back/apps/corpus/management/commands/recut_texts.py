"""An issue's texts cut again from its page readings, by code (no model): after a fix to how lines are read off the
pages (a running head read mid-column, 24 Oct 2026), each text's articles in texts.json are cut afresh from its own
lines; what the model read (its title, dates, kind) is kept. Then `reload_issues <key> --write` shows it.

    recut_texts 5932             # what would change
    recut_texts 5932 --write
"""
import json

from django.core.management.base import BaseCommand, CommandError

from apps.corpus.services.issue_structure import issue_lines, segment_issue, split_articles
from apps.corpus.services.recut import workdir
from apps.sources.models import Edition, Issue


class Command(BaseCommand):
    help = "Cut an issue's texts again from its page readings, keeping what the model read."

    def add_arguments(self, parser):
        parser.add_argument('keys', nargs='+')
        parser.add_argument('--write', action='store_true')

    def handle(self, *args, keys, write=False, **opts):
        for key in keys:
            number, suffix = Issue.parse_key(key)
            issue = Issue.objects.select_related('document').get(edition=Edition.GENERAL_AR, number=number, suffix=suffix)
            work = workdir(issue)
            if not (work / 'texts.json').exists():
                raise CommandError(f'{key}: no texts.json')
            toc = json.loads((work / 'toc.json').read_text())
            texts = json.loads((work / 'texts.json').read_text())
            lines = issue_lines(issue)
            spans = segment_issue(issue, toc)
            changed = 0
            for item, span in zip(texts, spans):
                if span is None or item.get('stop') in ('not_found', 'recut'):
                    continue
                part = lines[span[0]:span[1]]
                cut = split_articles(part)
                before = [(a.get('number'), a.get('body')) for a in item['articles']]
                after = [(a.get('number'), a.get('body')) for a in cut['articles']]
                if before != after:
                    changed += sum(1 for x, y in zip(before, after) if x != y) + abs(len(before) - len(after))
                    self.stdout.write(f'  {item["toc"]["title"][:70]}: {len(before)} → {len(after)} articles')
                item.update(pages=[part[0][0], part[-1][0]], front=cut['front'], articles=cut['articles'], tail=cut['tail'])
            self.stdout.write(f'{key}: {changed} articles cut otherwise' + ('' if write else ' (not written)'))
            if write:
                (work / 'texts.json').write_text(json.dumps(texts, ensure_ascii=False, indent=1))
