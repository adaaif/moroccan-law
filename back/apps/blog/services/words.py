"""Words in the law year by year, for «كلمات دخلت القانون» (the blog's third post, B6 of the blog-first-post review, 31 Oct
2026): for each word of the post's list, the texts whose articles carry one of its forms, each year from 1956, among
the texts read that year; the first text that carries it; and its stops. A text counts in the year of the issue that
first published it, with its words as published (its Arabic version as published), so a word a later amendment brought
never counts in a text's first year.

A word is found folded, on both sides: an alef with its hamza above or below, or its madda, is an alef, a final yā
written as alif maqṣūra is a yā, and the elongations go («الامازيغية» in 1983 is «الأمازيغية», «الإصطناعي» in 1994 is
«الاصطناعي»: the post's first counting missed both). A word with `since` counts from that day only: «درهم» before
the dirham was created is a family's or a place's name («بودرهم»).

Each word's `stops` (meta.yaml) are the milestones a person read on their pages: its first mention, the first text
whose subject it is, the laws that govern it since. Each is resolved here to its text, issue, page and article; a first
mention must hold one of the word's forms in its article, a subject in its title or its article, or the count stops. A
stop in a text the site has not cut yet names its issue and page and opens the issue. `checks` lists the words whose
counted first text comes before their first stop: a page for a person to read before the post is published again.

One pass over the articles (about five minutes on the full corpus), so the post is counted on the search copy, not the
live server; then one query for the first texts and two for the stops."""
from collections import defaultdict
from datetime import date

from django.db.models import Q

from apps.corpus.models import Article, Consolidation, Text
from apps.corpus.services.addresses import article_path, text_path
from apps.sources.models import Edition

DATE = 'version__text__first_published_in__date'
TEXT = 'version__text'
FOLD = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ى': 'ي', 'ـ': None})


def fold(words: str) -> str:
    return words.translate(FOLD)


def _issue_key(number, suffix) -> str:
    return f'{number}-bis' if suffix else str(number)


def count(meta: dict) -> dict:
    first_year, last_year = meta['span']
    words = [w for group in meta['groups'] for w in group['words']]
    forms = {w['key']: [fold(f) for f in w['forms']] for w in words}
    since = {w['key']: date.fromisoformat(str(w['since'])) for w in words if w.get('since')}
    # A misread article (meta.yaml's `misread`) never counts for its word: its text by address, one query.
    misread_uris = {m['text'] for w in words for m in w.get('misread', [])}
    ids = dict(Text.objects.filter(akn_uri__in=misread_uris).values_list('akn_uri', 'id')) if misread_uris else {}
    misread = {w['key']: {(ids.get(m['text']), m['eid']) for m in w.get('misread', [])} for w in words}
    texts: dict[int, set] = defaultdict(set)
    found: dict[str, dict[int, set]] = {k: defaultdict(set) for k in forms}
    firsts: dict[str, tuple] = {}
    # A report the Bulletin prints (Bank Al-Maghrib's year, «تقرير والي بنك المغرب …») is not a text of law: left out
    # (31 Oct 2026, once cut it brought «الحماية الاجتماعية» to 1974 and «التغيرات المناخية» to 1982).
    rows = (Article.objects.filter(version__language='ar', version__consolidation=Consolidation.AS_PUBLISHED,
                                   version__text__first_published_in__edition=Edition.GENERAL_AR,
                                   **{f'{DATE}__year__gte': first_year, f'{DATE}__year__lte': last_year})
            .exclude(version__text__title_ar__startswith='تقرير').exclude(version__text__title_ar__startswith='التقرير')
            .order_by().values_list(DATE, TEXT, 'order', 'eid', 'body').iterator(chunk_size=5000))
    for day, text_id, order, eid, body in rows:
        texts[day.year].add(text_id)
        words_of = fold(body)
        for key, fs in forms.items():
            if (key in since and day < since[key]) or (text_id, eid) in misread[key]:
                continue
            if any(f in words_of for f in fs):
                found[key][day.year].add(text_id)
                if key not in firsts or (day, text_id, order) < firsts[key][:3]:
                    firsts[key] = (day, text_id, order, eid)
    named = {t['id']: t for t in Text.objects.filter(id__in={f[1] for f in firsts.values()})
             .values('id', 'akn_uri', 'title_ar', 'first_published_in__number', 'first_published_in__suffix',
                     'first_published_page')}
    years = list(range(first_year, last_year + 1))
    stops = resolve_stops(words, forms)
    out, checks = [], []
    for w in words:
        key, first = w['key'], firsts.get(w['key'])
        t = named[first[1]] if first else None
        counted = {
            'date': first[0].isoformat(), 'title': t['title_ar'],
            'issue': _issue_key(t['first_published_in__number'], t['first_published_in__suffix']),
            'page': t['first_published_page'], 'path': article_path(t['akn_uri'], first[3]),
        } if first else None
        word = {'key': key, 'years': [len(found[key].get(y, ())) for y in years], 'first': counted}
        if w.get('open'):
            word['open'] = w['open']
        if key in stops:
            word['stops'] = stops[key]
            claimed = next((s for s in stops[key] if s['kind'] == 'first'), None)
            if counted and claimed and counted['date'] < claimed['date']:
                checks.append({'key': key, 'counted': counted['date'], 'stop': claimed['date'], 'path': counted['path']})
        out.append(word)
    return {'span': [first_year, last_year], 'texts': [len(texts.get(y, ())) for y in years], 'words': out,
            'checks': checks}


def resolve_stops(words: list[dict], forms: dict[str, list[str]]) -> dict[str, list[dict]]:
    """Each word's stops as the post shows them: {date, kind, ar, fr, title, issue, page, path}, in time order. Raises
    ValueError when a stop is not what meta.yaml says: its text missing, its day not its issue's, or a first mention or
    a subject without the word."""
    wanted = [(w['key'], s) for w in words for s in w.get('stops', [])]
    uris = {s['text'] for _, s in wanted if s.get('text')}
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in=uris).select_related('first_published_in')}
    articles: dict[tuple[str, str], dict] = {}
    numbers = {str(s['art']) for _, s in wanted if s.get('art')}
    eids = {s['eid'] for _, s in wanted if s.get('eid')}
    for a in (Article.objects.filter(Q(number__in=numbers) | Q(eid__in=eids), version__text__akn_uri__in=uris,
                                     version__language='ar')
              .values('version__text__akn_uri', 'version__consolidation', 'number', 'eid', 'printed_page', 'body')
              .order_by('version__valid_from')):
        k = (a['version__text__akn_uri'], a['eid'] if a['eid'] in eids and a['number'] not in numbers else a['number'])
        # The article as first published when the corpus has it, else the copy it holds (Adala's, the SGG's).
        if k not in articles or a['version__consolidation'] == Consolidation.AS_PUBLISHED:
            articles[k] = a
    out: dict[str, list[dict]] = defaultdict(list)
    for key, s in wanted:
        day, where = str(s['date']), f'{key}, stop of {s["date"]}'
        stop = {'date': day, 'kind': s['kind'], 'ar': s['ar'], 'fr': s['fr'], 'title': s.get('title', ''),
                'issue': str(s.get('issue', '')), 'page': s.get('page')}
        if s.get('text'):
            t = texts.get(s['text'])
            if t is None:
                raise ValueError(f'{where}: no text {s["text"]}')
            stop['title'] = t.title_ar
            if t.first_published_in_id:
                stop['issue'] = _issue_key(t.first_published_in.number, t.first_published_in.suffix)
                stop['page'] = t.first_published_page
                if t.first_published_in.date.isoformat() != day:
                    raise ValueError(f'{where}: its issue is of {t.first_published_in.date}')
            elif not stop['issue']:
                raise ValueError(f'{where}: {s["text"]} has no issue; name it in meta.yaml')
            named = str(s['art']) if s.get('art') else s.get('eid')
            article = articles.get((s['text'], named)) if named else None
            if named and article is None:
                raise ValueError(f'{where}: no article {named} in {s["text"]}')
            stop['path'] = article_path(t.akn_uri, article['eid']) if article else text_path(t.akn_uri)
            if s.get('page'):
                stop['page'] = s['page']        # the page the word stands on, when the article runs over several
            elif article and article['printed_page'] and t.first_published_in_id:
                stop['page'] = article['printed_page']
            held = fold(article['body'] if article else '') + ' ' + (fold(t.title_ar) if s['kind'] == 'subject' else '')
            if s['kind'] in ('first', 'subject') and not any(f in held for f in forms[key]):
                raise ValueError(f'{where}: the word is not in {s["text"]} {named or ""}')
        else:
            if not (stop['issue'] and stop['page'] and stop['title']):
                raise ValueError(f'{where}: a text not cut yet needs its issue, page and title as printed')
            stop['path'] = f'/bo/general_ar/{stop["issue"]}'
        out[key].append(stop)
    for key in out:
        out[key].sort(key=lambda s: s['date'])
    return dict(out)
