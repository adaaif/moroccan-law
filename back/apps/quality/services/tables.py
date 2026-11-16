"""Table rows the cut put in the wrong article (T3 of the work plan): decree 2.25.265's pension table ended at 900 DH,
and its last row («| 1000 | 2857 يوما فما فوق |») stood over the next article as its subject, because the cutter took
a short line above an article's heading for its subject. The cutter no longer does; the rows already cut so go back
to the end of the article above, in the corpus and in each issue's texts.json, so a reload keeps them there."""
import json
from itertools import pairwise
from pathlib import Path

from django.conf import settings
from django.db import transaction

from apps.corpus.models import Article, Consolidation


def _row(path: list) -> str | None:
    last = str(path[-1]) if path else ''
    return last if last.lstrip().startswith('|') else None


def _back(articles: list[dict]) -> int:
    """In a cut text's articles (texts.json), each subject that is a table row moved to the article above."""
    moved = 0
    for prev, a in pairwise(articles):
        row = _row(a.get('heading_path') or [])
        if row:
            prev['body'] = f'{prev["body"]}\n{row}'.strip()
            a['heading_path'] = a['heading_path'][:-1]
            moved += 1
    return moved


@transaction.atomic
def give_back(log=print) -> dict:
    moved = 0
    versions = (Article.objects.filter(version__consolidation=Consolidation.AS_PUBLISHED)
                .exclude(heading_path=[]).values_list('version_id', flat=True).distinct())
    for vid in versions.iterator():
        rows = list(Article.objects.filter(version_id=vid).order_by('order'))
        changed = {}
        for prev, a in pairwise(rows):
            row = _row(a.heading_path or [])
            if row:
                prev.body = f'{prev.body}\n{row}'.strip()
                a.heading_path = a.heading_path[:-1]
                changed.update({prev.pk: prev, a.pk: a})
                moved += 1
        Article.objects.bulk_update(list(changed.values()), ['body', 'heading_path'])
    files = 0
    for path in (Path(settings.CORPUS_DIR) / 'reports' / 'issues').glob('*/texts.json'):
        saved = json.loads(path.read_text())
        n = sum(_back(item.get('articles') or []) for item in saved)
        if n:
            kept = path.with_name('texts.before-rows.json')
            if not kept.exists():
                kept.write_text(path.read_text())
            path.write_text(json.dumps(saved, ensure_ascii=False, indent=1))
            files += 1
    log(f'{moved} table rows given back to the article above; {files} issues\' texts.json kept in step')
    return {'rows': moved, 'files': files}
