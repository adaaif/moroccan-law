"""B10 of the search plan: write apps/search/data/thesaurus.json from the candidates and Haiku's drafts, each legal term
grounded in the index's words, with the articles that define it or are about it and the concepts it goes with
(services/thesaurus.py). Owner-provisional until lawyers read it. No API.

    manage.py build_thesaurus"""
import json
from collections import Counter
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.search.models import SearchEntry
from apps.search.services import thesaurus
from apps.search.services.index import term_counts


class Command(BaseCommand):
    help = 'Write the thesaurus from its drafts (B10).'

    def handle(self, *args, **opts):
        path = Path(settings.CORPUS_DIR) / thesaurus.DRAFTS
        drafts = json.loads(path.read_text())['drafts'] if path.exists() else {}
        definitions = list(SearchEntry.objects.filter(kind=SearchEntry.Kind.ARTICLE).filter(
            Q(body__contains='يقصد ب') | Q(body__contains='يراد ب')).values_list('path', 'body'))
        concepts = thesaurus.build(thesaurus.candidates(), drafts, term_counts(), definitions)
        thesaurus.FILE.write_text(json.dumps({
            'about': ('B10 of the search plan: one thesaurus for the whole law, a concept a slug (the legal term folded). '
                      'From the everyday-words list, the topics\' doors, the explained concepts and B9\'s concepts; the '
                      'French, Darija and English words drafted by Haiku 5.5 (draft_thesaurus); every term grounded in '
                      'the index. checked: owner-provisional, until lawyers read it.'),
            'date': date.today().isoformat(), 'checked': 'owner-provisional', 'concepts': concepts},
            ensure_ascii=False, indent=1) + '\n')
        thesaurus.load.cache_clear()
        words = Counter(k for c in concepts.values() for k in ('darija', 'arabizi', 'fr', 'en') for _ in c[k])
        self.stdout.write(f'{len(concepts)} concepts written ({sum(1 for c in concepts.values() if c["defines"])} with a '
                          f'defining article, {sum(1 for c in concepts.values() if c["related"])} with related ones); '
                          f'people\'s words: {dict(words)}')
