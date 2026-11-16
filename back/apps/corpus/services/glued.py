"""Articles glued together (H5 of the housing plan): where the BO's line breaks were lost, an article's body holds the
next one's heading as a line of its own («المادة467»), and two articles read as one (58.25's arts 466 and 467). Each
is cut at that line, by code; the issue's texts.json is kept in step, so a reload keeps the cut."""
import json
import re
from pathlib import Path

from django.conf import settings
from django.db import transaction

from apps.corpus.models import Article, Consolidation

LINE = re.compile(r'(?:^|\n)\s*(المادة|الفصل)\s*(\d+)\s*(?=\n|$)')


def _next_heading(article: Article) -> re.Match | None:
    """The line in the body that heads the article after this one (its number plus one), if there is one."""
    own = re.sub(r'\D', '', article.number or '')
    if not own:
        return None
    for m in LINE.finditer(article.body):
        if int(m.group(2)) == int(own) + 1:
            return m
    return None


def plan() -> list[tuple[Article, re.Match]]:
    rows = (Article.objects.filter(version__consolidation=Consolidation.AS_PUBLISHED,
                                   body__regex=r'(^|\n)\s*(المادة|الفصل)\s*[0-9]+\s*(\n|$)')
            .select_related('version__text', 'version__text__first_published_in'))
    return [(a, m) for a in rows if (m := _next_heading(a))]


@transaction.atomic
def repair(log=print, write: bool = False) -> int:
    done = 0
    for a, m in plan():
        word, number = m.group(1), m.group(2)
        head, tail = a.body[:m.start()].rstrip(), a.body[m.end():].strip()
        log(f'  {a.version.text.akn_uri} {a.label}: «{word} {number}» cut out ({len(tail)} letters)')
        if not write:
            done += 1
            continue
        later = list(Article.objects.filter(version=a.version, order__gt=a.order).order_by('-order'))
        for b in later:
            b.order += 1
            b.save(update_fields=['order'])
        a.body = head
        a.save(update_fields=['body'])
        Article.objects.create(version=a.version, order=a.order + 1, label=f'{word} {number}', number=number,
                               eid=f'art_{number}', body=tail, heading_path=a.heading_path, printed_page=a.printed_page)
        issue = a.version.text.first_published_in
        path = Path(settings.CORPUS_DIR) / 'reports' / 'issues' / issue.key / 'texts.json' if issue else None
        if path and path.exists():
            saved = json.loads(path.read_text())
            for item in saved:
                arts = item.get('articles') or []
                for k, x in enumerate(arts):
                    if x.get('label') == a.label and m.group(0).strip() in x.get('body', ''):
                        at = x['body'].find(m.group(0).strip())
                        arts.insert(k + 1, {**x, 'label': f'{word} {number}', 'body': x['body'][at + len(m.group(0).strip()):].strip()})
                        x['body'] = x['body'][:at].rstrip()
                        break
            path.write_text(json.dumps(saved, ensure_ascii=False, indent=1))
        done += 1
    return done
