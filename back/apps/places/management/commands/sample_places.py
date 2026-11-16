"""PL3 of the places review: mentions drawn at random for a person to read (a provisional check): half
naming a state, half a Moroccan place, each with its words around it and its address. Written as JSON for the checking
page; the same seed draws the same sample. `--before 1956` draws from the old Bulletin only (BH4 of
the posts-from-No.-1 review, 6 Nov 2026: its old spellings read before any post counts them)."""
import json
import random

from django.core.management.base import BaseCommand

from apps.corpus.models import Article
from apps.corpus.services.addresses import article_path, text_path
from apps.places.models import Mention
from apps.places.services.finder import _snippet


class Command(BaseCommand):
    help = 'Draw mentions at random for a person to read (PL3).'

    def add_arguments(self, parser):
        parser.add_argument('--each', type=int, default=200)
        parser.add_argument('--seed', type=int, default=20261101)
        parser.add_argument('--out', required=True)
        parser.add_argument('--before', type=int, help='only mentions dated before this year')

    def handle(self, *args, each, seed, out, before=None, **opts):
        rng = random.Random(seed)
        drawn = []
        for group, kinds in (('foreign', ('country', 'gone')), ('home', ('city', 'commune', 'province', 'region'))):
            found = Mention.objects.filter(printed=True, place__kind__in=kinds)
            if before:
                found = found.filter(date__year__lt=before)
            ids = list(found.values_list('pk', flat=True))
            drawn += [(group, pk) for pk in rng.sample(ids, min(each, len(ids)))]
        rows = {m['pk']: m for m in Mention.objects.filter(pk__in=[pk for _, pk in drawn]).values(
            'pk', 'uri', 'eid', 'at', 'form', 'date', 'issue', 'page', 'place__slug', 'place__name_ar', 'place__kind')}
        bodies = {(u, e): b for u, e, b in Article.objects.filter(
            version__text__akn_uri__in={r['uri'] for r in rows.values()}, version__language='ar', version__consolidation='as_published',
            eid__in={r['eid'] for r in rows.values() if r['eid']}).values_list('version__text__akn_uri', 'eid', 'body')}
        from apps.corpus.models import Text
        titles = dict(Text.objects.filter(akn_uri__in={r['uri'] for r in rows.values()}).values_list('akn_uri', 'title_ar'))
        sample = []
        for n, (group, pk) in enumerate(drawn, 1):
            r = rows[pk]
            body = bodies.get((r['uri'], r['eid'])) if r['eid'] else titles.get(r['uri'], '')
            sample.append({'n': n, 'group': group, 'place': r['place__slug'], 'name': r['place__name_ar'], 'kind': r['place__kind'],
                           'form': r['form'], 'snippet': _snippet(body or '', r['at'], len(r['form'])) if body else None,
                           'date': r['date'].isoformat(), 'issue': r['issue'], 'page': r['page'],
                           'path': article_path(r['uri'], r['eid']) if r['eid'] else text_path(r['uri'])})
        with open(out, 'w', encoding='utf-8') as f:
            json.dump(sample, f, ensure_ascii=False, indent=1)
        self.stdout.write(f'{len(sample)} mentions drawn')
