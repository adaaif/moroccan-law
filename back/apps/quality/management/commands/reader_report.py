"""The week as readers lived it (row 20 of the reader-experience review): the searches that found nothing, the ones that
found texts but led nowhere, how searches were read, the pages slow to show their content, and whether the topics'
pages helped («هل ساعدك هذا؟», F15 of the family plan), and the words a stray space still cuts in two in today's
texts (N3 of the read-and-trusted review: a reload never brings them back unseen). Searches about violence are a count
only (F14). Everything it reads is anonymous. Markdown on stdout, or into --out."""
from datetime import timedelta
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db.models import Count, Sum
from django.utils import timezone

from apps.quality.models import Correction, PageTiming
from apps.quality.services import proofread
from apps.search.models import SearchLog
from apps.topics.models import Helped, ToolUse

TOP = 25
SLOW_MS = 2500


def percentile(values: list[int], p: float) -> int:
    values = sorted(values)
    return values[min(len(values) - 1, int(p * len(values)))] if values else 0


class Command(BaseCommand):
    help = 'The weekly report of searches without an answer and slow pages.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7)
        parser.add_argument('--out', help='write the Markdown here')

    def handle(self, *args, days, out, **options):
        since = timezone.now() - timedelta(days=days)
        every = SearchLog.objects.filter(at__gte=since)
        private = every.filter(understood_as='private').count()
        logs = every.exclude(understood_as='private')
        total = logs.count()
        lines = [f'# Readers — {days} days to {timezone.localdate():%Y-%m-%d}', '',
                 f'{total} searches; {logs.filter(results=0).count()} found nothing; '
                 f'{logs.filter(results__gt=0, opened__isnull=True).count()} found texts but led nowhere; '
                 f'{private} about violence, counted and never kept as typed.', '']

        def table(title: str, rows) -> None:
            lines.extend([f'## {title}', ''])
            rows = list(rows)
            if not rows:
                lines.extend(['None.', ''])
                return
            lines.extend(['| Searched | Times |', '| --- | --- |'])
            lines.extend(f'| {r["folded"]} | {r["n"]} |' for r in rows)
            lines.append('')

        table('Found nothing (for the everyday-words list and the shelf)',
              logs.filter(results=0).values('folded').annotate(n=Count('id')).order_by('-n')[:TOP])
        table('Found texts, none opened (the ranking to look at)',
              logs.filter(results__gt=0, opened__isnull=True).values('folded').annotate(n=Count('id')).order_by('-n')[:TOP])

        lines.extend(['## How searches were read', '', '| Read as | Searches | Opened an answer |', '| --- | --- | --- |'])
        for r in logs.values('understood_as').annotate(n=Count('id')).order_by('-n'):
            opened = logs.filter(understood_as=r['understood_as'], opened__isnull=False).count()
            lines.append(f'| {r["understood_as"] or "—"} | {r["n"]} | {round(100 * opened / r["n"])} % |')
        first = logs.filter(opened__isnull=False)
        if first.exists():
            top3 = first.filter(opened__lte=3).count()
            lines.append(f'\nThe answer opened was among the first three in {round(100 * top3 / first.count())} % of searches that opened one.')
        lines.append('')

        lines.extend(['## Pages, time to their main content', '',
                      f'| Page | Loads | Median | 75th percentile | Over {SLOW_MS / 1000:g} s |', '| --- | --- | --- | --- | --- |'])
        timings = PageTiming.objects.filter(on__gte=since.date())
        for kind, label in PageTiming.Kind.choices:
            ms = list(timings.filter(kind=kind).values_list('ms', flat=True))
            if ms:
                slow = sum(m > SLOW_MS for m in ms)
                lines.append(f'| {label} | {len(ms)} | {percentile(ms, .5) / 1000:.1f} s | {percentile(ms, .75) / 1000:.1f} s | '
                             f'{round(100 * slow / len(ms))} % |')
        lines.extend(['', "## Did the topics' pages help", ''])
        answers = Helped.objects.filter(created_at__gte=since)
        if answers.exists():
            lines.extend(['| Page | Yes | No | Not clear | Not my case | Seems wrong |', '| --- | --- | --- | --- | --- | --- |'])
            for r in answers.values('path').annotate(n=Count('id')).order_by('-n')[:TOP]:
                mine = answers.filter(path=r['path'])
                no = mine.filter(helped=False)
                lines.append(f'| {r["path"]} | {mine.filter(helped=True).count()} | {no.count()} | '
                             f'{no.filter(reason="unclear").count()} | {no.filter(reason="not_mine").count()} | '
                             f'{no.filter(reason="wrong").count()} |')
        else:
            lines.append('None.')
        lines.extend(['', "## How the topics' tools were used", ''])
        uses = ToolUse.objects.filter(on__gte=since.date())
        if uses.exists():
            events = [e for e, _ in ToolUse.Event.choices]
            lines.extend(['| Page | ' + ' | '.join(events) + ' |', '| --- |' + ' --- |' * len(events)])
            for r in uses.values('path').annotate(n=Sum('count')).order_by('-n')[:TOP]:
                mine = {u['event']: u['count'] for u in uses.filter(path=r['path']).values('event').annotate(count=Sum('count'))}
                lines.append(f'| {r["path"]} | ' + ' | '.join(str(mine.get(e, 0)) for e in events) + ' |')
        else:
            lines.append('None.')
        # Words cut in two (N3): what the proofreader finds in the texts as they stand, by text, and how many of them
        # wait for a person on /corrections.
        found = list(proofread.splits(proofread.printed_words()))
        waiting = set(Correction.objects.filter(source=Correction.Source.SPLIT, status=Correction.Status.SUGGESTED)
                      .values_list('path', 'wrong'))
        lines.extend(['', '## Words cut in two', ''])
        if found:
            by_text: dict[str, list] = {}
            for path, wrong, *_ in found:
                by_text.setdefault(path.rsplit('/', 1)[0], []).append((path, wrong))
            lines.extend([f'{len(found)} in {len({p for p, *_ in found})} articles; '
                          f'{sum((p, w) in waiting for p, w, *_ in found)} proposed on /corrections '
                          '(`proofread --split` proposes the rest).', '',
                          '| Text | Words | Articles |', '| --- | --- | --- |'])
            for text_path, rows in sorted(by_text.items(), key=lambda x: -len(x[1]))[:TOP]:
                lines.append(f'| {text_path} | {len(rows)} | {len({p for p, _ in rows})} |')
        else:
            lines.append('None.')
        text = '\n'.join(lines) + '\n'
        if out:
            Path(out).write_text(text)
            self.stdout.write(f'written to {out}')
        else:
            self.stdout.write(text)
