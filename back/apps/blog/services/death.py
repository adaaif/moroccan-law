"""The death penalty in the law, for «الإعدام في القانون المغربي» (the blog's twentieth post, S12 of
the first-principles review, 7 Nov 2026).

The penal code is drawn article by article: every article of our copy (Adala's, 2024), in order, with its group (the
meta's, from each group's first article) and, for the articles that name the death penalty, the clause that names it, as
that copy writes it (one query). The articles that name it must be the meta's, no more and no fewer: any difference lands
in `checks`. Every reference (each article's page in the 1963 printing or in law 03.03, the other texts, the procedure,
the CNDH's reports) is tied to its issue, its page and its text with `clock.tie` (three queries), and the articles quoted
get their addresses (one query)."""
import re

from apps.blog.services import clock
from apps.corpus.models import Article, Consolidation
from apps.corpus.services.addresses import article_path
from apps.sources.models import Edition

DEATH = re.compile(r'الإعدام|الاعدام')


def _ref(key: str, r: dict, akn: str | None = None) -> dict:
    return {'key': key, 'edition': Edition.GENERAL_AR, 'issue': r['issue'], 'bis': r.get('bis', False), 'page': r['page'],
            'akn': r.get('akn', akn)}


def _refs(meta: dict) -> list[dict]:
    code = meta['code']
    refs = [_ref(f"p-{a['n']}", {'issue': a.get('issue', code['issue']), 'bis': a.get('bis', 'issue' not in a and code['bis']),
                                 'page': a['page']}, a.get('akn', code['akn'])) for a in meta['articles']]
    o = meta['others']
    refs += [_ref(f"m-{a['n']}", {'issue': o['military']['issue'], 'page': a['page']}, o['military']['akn']) for a in o['military']['arts']]
    refs += [_ref(k, o[k]) for k in ('railway', 'food')] + [_ref('victims', o['victims'])]
    refs += [_ref(f"s-{s['key']}", s) for s in meta['steps']]
    refs += [_ref(f"w-{s['key']}", s['was'], s['was'].get('akn', code['akn'])) for s in meta['steps'] if s.get('was')]
    c = meta['cndh']
    refs += [_ref(f"c-{y['year']}", y) for y in c['years']] + [_ref(f'c-{k}', c[k]) for k in ('halt', 'pardons', 'vote')]
    return refs


def _clause(body: str) -> str:
    """The sentence of an article that names the death penalty, as its copy writes it."""
    sentences = re.split(r'(?<=[.؛])\s+', ' '.join(body.split()))
    hit = next((s for s in sentences if DEATH.search(s)), body)
    return hit if len(hit) <= 420 else '… ' + hit[max(0, DEATH.search(hit).start() - 260):DEATH.search(hit).start() + 140] + ' …'


def _code(meta: dict) -> tuple[list[dict], list[dict]]:
    """Every article of the code in its order, with its group; the ones that name the death penalty with their clause."""
    rows = list(Article.objects.filter(version__text__akn_uri=meta['code']['akn'], version__language='ar',
                                       version__consolidation=Consolidation.ADALA)
                .order_by('order').values_list('eid', 'number', 'body'))
    starts = {g['from']: g['key'] for g in meta['groups']}
    named = {a['n'] for a in meta['articles']}
    cells, checks, group = [], [], meta['groups'][0]['key']
    for eid, _number, body in rows:
        group = starts.get(eid, group)
        n = eid.removeprefix('art_')
        cell = {'n': n, 'g': group}
        if DEATH.search(body or ''):
            cell['clause'] = _clause(body)
            if n not in named:
                checks.append({'article': n, 'why': 'names the death penalty, not in the meta'})
        cells.append(cell)
    seen = {c['n'] for c in cells if 'clause' in c}
    checks += [{'article': n, 'why': 'in the meta, but its words no longer name the death penalty'} for n in sorted(named - seen)]
    return cells, checks


def _articles(meta: dict) -> dict:
    """The articles the post quotes outside the penal code, by key: their addresses on the site (one query)."""
    o = meta['others']
    quoted = {f"m-{a['n']}": (o['military']['akn'], a['n']) for a in o['military']['arts']}
    quoted |= {'railway': (o['railway']['akn'], o['railway']['art']), 'food': (o['food']['akn'], '1')}
    quoted |= {f"s-{s['key']}": (s['akn'], s['art']) for s in meta['steps']}
    have = set(Article.objects.filter(version__text__akn_uri__in={a for a, _ in quoted.values()},
                                      eid__in={f'art_{n}' for _, n in quoted.values()}).values_list('version__text__akn_uri', 'eid'))
    return {k: article_path(akn, f'art_{n}') for k, (akn, n) in quoted.items() if (akn, f'art_{n}') in have}


def count(meta: dict) -> dict:
    cells, checks = _code(meta)
    return {'texts': clock.tie(_refs(meta)), 'cells': cells, 'articles': _articles(meta), 'checks': checks}
