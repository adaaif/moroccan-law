"""Measures the public answers (S20 of the performance audit, 24 Oct 2026): for each, the queries it makes and the query
shapes it repeats (a query inside a loop), its time cold and warm, its size raw and compressed. Run it before a release
and after changing a page's code:

    manage.py perf_report [--runs 5] [--only topic] [--kept] [--json out.json]

The samples come from the database it runs on: the issue with the most texts, the longest text, the text citing the
most others, the busiest discussion and its most active author, every topic. The answers kept in Redis are set aside
unless --kept (the code is measured, not the cache). It writes nothing but the searches' log.

Search's answers have a time budget (B27 of the search plan): the server's p95 for each kind of search, checked here
with each stage the answer's Server-Timing header names (config/timing.py)."""
import gzip
import json
import statistics
import time
from collections import Counter
from urllib.parse import quote

from django.conf import settings
from django.core.cache.backends.locmem import LocMemCache
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.db.models import Count
from django.test import Client, override_settings

from config.querylog import shape

SLOW_MS = 300
REPEATS = 5
# B27: a question (with meaning and a reranker) 300 ms, a citation or a code's name 80, a suggestion 50.
BUDGET_MS = {'search': 300, 'search in Darija': 300, 'search in French': 300, 'search page 2': 300,
             'search nothing found': 300, 'search a citation': 80, 'search a name': 80, 'suggest': 50, 'suggest a word': 50}


class GenerationsOnly(LocMemCache):
    """The answers cache while measuring: the generations are kept, so what a process holds in memory by them (the
    titles suggestions read, the shelf) stays as in production; the answers are not, so the code is measured."""

    def add(self, key, *args, **kwargs):
        return key.startswith('gen:') and super().add(key, *args, **kwargs)

    def set(self, key, *args, **kwargs):
        if key.startswith('gen:'):
            super().set(key, *args, **kwargs)

    def set_many(self, data, *args, **kwargs):
        return super().set_many({k: v for k, v in data.items() if k.startswith('gen:')}, *args, **kwargs)


def samples() -> list[tuple[str, str]]:
    """(name, address) for every public answer worth watching, chosen from this database."""
    from apps.corpus.models import Article, Mention, Text
    from apps.corpus.services.addresses import text_path
    from apps.discussion.models import Cite, Contribution, Discussion
    from apps.sources.models import Issue
    from apps.topics.services import kit, topics

    out = [('issues', '/api/corpus/issues/'), ('shelf', '/api/corpus/shelf/'), ('library', '/api/corpus/library/'), ('issue map', '/api/corpus/issues/map/'), ('find', '/api/corpus/find/?q=%D8%B8%D9%87%D9%8A%D8%B1%202%20%D8%A3%D9%83%D8%AA%D9%88%D8%A8%D8%B1%201984'),
           ('year', '/api/corpus/years/1958/'), ('situations', '/api/corpus/situations/'),
           ('budget', '/api/budget/laws/'), ('topics', '/api/topics/'), ('explain new', '/api/explain/new/'),
           ('explain week', '/api/explain/week/'), ('answered', '/api/discussion/answered/'),
           ('questions', '/api/discussion/questions/'), ('numbers', '/api/discussion/numbers/'),
           ('places', '/api/discussion/places/')]
    issue = Issue.objects.annotate(n=Count('texts_first_published')).order_by('-n').first()
    if issue:
        out += [('issue', f'/api/corpus/issues/{issue.edition}/{issue.key}/'),
                ('issue quality', f'/api/corpus/issues/{issue.edition}/{issue.key}/quality/')]
        if issue.document_id:
            out.append(('a page of it', f'/api/sources/documents/{issue.document_id}/pages/3/'))
    longest = Article.objects.values('version__text').annotate(n=Count('id')).order_by('-n').first()
    if longest:
        path = text_path(Text.objects.get(pk=longest['version__text']).akn_uri)
        out += [('longest text', f'/api/corpus/at{path}/?window=30'), ('its articles 300-340', f'/api/corpus/at{path}/?from=300&count=40'),
                ('its explanations', f'/api/explain/text/?path={quote(path)}'),
                ('find in it', f'/api/search/in/?path={quote(path)}&q={quote("الضمان")}')]
    citing = Mention.objects.values('from_uri').annotate(n=Count('id')).order_by('-n').first()
    if citing and (text := Text.objects.filter(akn_uri=citing['from_uri']).first()):
        out.append(('text citing most', f'/api/corpus/at{text_path(text.akn_uri)}/?window=30'))
    busiest = Discussion.objects.filter(path__startswith='/talk/').order_by('-count').first()
    if busiest:
        out += [('busiest topic', f'/api/discussion/feed/?place={quote(busiest.path)}&sort=active&page=1'),
                ('its best this month', f'/api/discussion/feed/?place={quote(busiest.path)}&sort=top&page=1')]
        post = (Contribution.objects.filter(discussion=busiest, parent=None).order_by('-reply_count').first())
        if post:
            out.append(('its longest post', f'/api/discussion/posts/{post.pk}/'))
        author = (Contribution.objects.filter(discussion=busiest, anonymous=False).values('author__username')
                  .annotate(n=Count('id')).order_by('-n').first())
        if author:
            out.append(('its most active author', f"/api/discussion/people/{author['author__username']}/"))
    cited = Cite.objects.values('path', 'text_path').annotate(n=Count('id')).order_by('-n').first()
    if cited:
        out += [('most cited article', f"/api/discussion/cited/?path={quote(cited['path'])}"),
                ('its counts', f"/api/discussion/counts/?text={quote(cited['text_path'])}")]
    for topic in topics.load():
        out.append((f"topic {topic['slug']}", f"/api/topics/{topic['slug']}/"))
        found = kit.load(topic['slug'])
        if found and found.get('journeys'):
            key = next(iter(found['journeys']))
            out.append((f"{topic['slug']} journey", f"/api/topics/{topic['slug']}/journeys/{key}/"))
    # Search's own cases (B27 of the search plan): a citation, a Darija question, French, a page 2, nothing found.
    out += [('search', f'/api/search/?q={quote("التعويض عن الفصل")}'), ('suggest', f'/api/search/suggest/?q={quote("مدونة")}'),
            ('search a citation', f'/api/search/?q={quote("ف 418 ق.ل.ع")}'),
            ('search a name', f'/api/search/?q={quote("مدونة الشغل")}'),
            ('search in Darija', f'/api/search/?q={quote("واش مول الدار يقدر يخرجني بلا إنذار")}'),
            ('search in French', f'/api/search/?q={quote("licenciement abusif")}'),
            ('search page 2', f'/api/search/?q={quote("الكراء")}&page=2'),
            ('search nothing found', f'/api/search/?q={quote("قزحية زمردية")}'),
            ('suggest a word', f'/api/search/suggest/?q={quote("الكرا")}'),
            ('follows news', '/api/follows/news/?' + '&'.join(f'path={quote(p)}' for p in
                                                             [o[1].split('/api/corpus/at')[-1].split('/?')[0] for o in out
                                                              if o[1].startswith('/api/corpus/at')][:3] + ['/topics/housing']))]
    return out


class Command(BaseCommand):
    help = 'Measure every public answer: queries, repeated query shapes, time, size.'

    def add_arguments(self, parser):
        parser.add_argument('--runs', type=int, default=5, help='warm runs after the first (median)')
        parser.add_argument('--only', default='', help='only the samples whose name or address holds this')
        parser.add_argument('--kept', action='store_true', help='with the answers kept in Redis')
        parser.add_argument('--json', default='', help='write the measures to this file')

    def handle(self, *args, **opts):
        caches = settings.CACHES if opts['kept'] else {**settings.CACHES, 'answers': {
            'BACKEND': f'{__name__}.GenerationsOnly', 'LOCATION': 'perf-report'}}
        with override_settings(CACHES=caches, ALLOWED_HOSTS=[*settings.ALLOWED_HOSTS, 'testserver']):
            # As a worker starts (config/wsgi.py): the topics' folders and what a suggestion reads, read first.
            from apps.search.services import search
            from apps.topics.services import kit
            kit.warm()
            search.warm()
            client = Client()
            rows = [self.measure(client, name, url, opts['runs']) for name, url in samples()
                    if not opts['only'] or opts['only'] in name or opts['only'] in url]
        flagged = 0
        self.stdout.write(f"{'answer':28} {'queries':>7} {'cold ms':>8} {'warm ms':>8} {'p95 ms':>7} {'KB':>7} {'gz KB':>6}")
        for r in rows:
            budget = BUDGET_MS.get(r['name'])
            flags = (' N+1' if r['repeats'] else '') + (' slow' if r['warm_ms'] > SLOW_MS else '') + \
                (f' over {budget} ms' if budget and r['p95_ms'] > budget else '') + \
                ('' if r['status'] == 200 else f" {r['status']}")
            flagged += bool(flags)
            self.stdout.write(f"{r['name'][:28]:28} {r['queries']:>7} {r['cold_ms']:>8.0f} {r['warm_ms']:>8.0f} "
                              f"{r['p95_ms']:>7.0f} {r['kb']:>7.1f} {r['gz_kb']:>6.1f}{flags}")
            if r['stages']:
                self.stdout.write('    ' + ' · '.join(f'{name} {ms:.0f}' for name, ms in r['stages'].items()))
            for n, sql in r['repeats']:
                self.stdout.write(f'    {n}× {sql[:140]}')
        self.stdout.write(f'{len(rows)} answers, {flagged} flagged')
        # A suggestion over its budget fails the report (N12 of the read-and-trusted review): it answers each key typed.
        slow = [r['name'] for r in rows if r['name'].startswith('suggest') and r['p95_ms'] > BUDGET_MS[r['name']]]
        if opts['json']:
            with open(opts['json'], 'w') as f:
                json.dump(rows, f, ensure_ascii=False, indent=1)
        if slow:
            raise CommandError(f"over {BUDGET_MS['suggest']} ms: {', '.join(slow)}")

    @staticmethod
    def measure(client, name: str, url: str, runs: int) -> dict:
        times, seen, stages = [], Counter(), {}
        for _ in range(runs + 1):
            seen = Counter()

            def watch(execute, sql, params, many, context):
                seen[shape(sql)] += 1  # noqa: B023 (called in this iteration)
                return execute(sql, params, many, context)
            with connection.execute_wrapper(watch):
                t0 = time.perf_counter()
                r = client.get(url)
                body = r.content
                times.append((time.perf_counter() - t0) * 1000)
            for part in filter(None, r.get('Server-Timing', '').split(', ')):
                stage, _, ms = part.partition(';dur=')
                stages.setdefault(stage, []).append(float(ms))
        warm = sorted(times[1:] or times)
        return {'name': name, 'url': url, 'status': r.status_code, 'queries': sum(seen.values()),
                'repeats': [(n, sql) for sql, n in seen.most_common() if n > REPEATS],
                'cold_ms': round(times[0], 1), 'warm_ms': round(statistics.median(warm), 1),
                # With few runs the p95 is the slowest warm one.
                'p95_ms': round(warm[min(len(warm) - 1, int(len(warm) * 0.95))], 1),
                # Each stage's median over the warm runs.
                'stages': {k: round(statistics.median(v[1:] or v), 1) for k, v in stages.items()},
                'kb': round(len(body) / 1024, 1), 'gz_kb': round(len(gzip.compress(body)) / 1024, 1)}
