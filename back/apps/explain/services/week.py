"""«هذا الأسبوع في الجريدة الرسمية» (R13 of the for-everyone review): a week of the Bulletin officiel, Monday to Sunday.
First the texts someone told in plain words, under the headline they wrote and a reviewer checked; then every other
text of the general section, for specialists. Which texts matter to people is a person's call, never the machine's.

Since 1 Nov 2026 (/new drawn again from the newest issues) every text of the week comes, the special section's too
(`special_texts`: appointments, delegations, licences, until then only counted); a series of texts of one form is marked
(`series`, `part`; services/series.py); a text that makes rules (a dahir, a law, a decree) brings its first article's
first words as printed (`first`), and what it applies (`applies`) beside what it changes; each issue its pages."""
from datetime import date, timedelta

from django.db.models import OuterRef, Subquery

from apps.consolidation.models import Change
from apps.corpus.models import Article, Mention, Text
from apps.corpus.services.addresses import text_path
from apps.corpus.services.codes import display_name
from apps.explain.services import series
from apps.explain.services.explanations import checked
from apps.follows.services.news import name
from apps.sources.models import Edition, Issue
from apps.topics.services import topics

CHANGED_MOST = 3
# The kinds whose first words the week shows: those that make rules, when they stand alone (a series is named instead).
OPENED = {'constitution', 'organic_law', 'law', 'dahir', 'decree_law', 'decree'}
FIRST_WORDS = 420
WEEKS_SHOWN, WEEKS_AFTER = 13, 4


def week(day: date | None = None) -> dict:
    """The week holding `day`, else the week of the newest issue."""
    general = Issue.objects.filter(edition=Edition.GENERAL_AR)
    if day is None:
        day = general.order_by('-date').values_list('date', flat=True).first() or date.today()
    monday = day - timedelta(days=day.weekday())
    sunday = monday + timedelta(days=6)
    issues = list(general.filter(date__range=(monday, sunday)).select_related('document').order_by('-date', '-number'))
    texts = list(Text.objects.filter(first_published_in__in=issues).select_related('first_published_in')
                 .order_by('-first_published_in__date', 'first_published_page', 'id'))
    paths = {text_path(t.akn_uri): t for t in texts}
    told: dict[str, dict] = {}
    for e in checked().filter(path__in=[p for p, t in paths.items() if t.bo_section != 'special']).exclude(headline=''):
        told.setdefault(e.path, {})[e.register] = {'headline': e.headline, 'body': e.body}
    changed, applied = _links([t.akn_uri for t in texts])
    rows = [{'path': p, 'type': t.type, 'title': t.title_ar, 'name': display_name(t), 'title_fr': t.title_fr,
             'number': t.number_as_printed, 'section': 'special' if t.bo_section == 'special' else 'general',
             'issue': {'number': t.first_published_in.number, 'suffix': t.first_published_in.suffix,
                       'date': t.first_published_in.date, 'key': t.first_published_in.key},
             'page': t.first_published_page, 'topic': topics.of_title(t.title_ar), 'changes': changed.get(t.akn_uri, []),
             'applies': applied.get(t.akn_uri, []), 'told': told.get(p), 'series': None, 'part': '', 'first': None}
            for p, t in paths.items()]
    # The Bulletin's order within the week: by day, then by page (the query's order is the newest issue first).
    rows.sort(key=lambda r: (r['issue']['date'], r['issue']['key'], r['page'] or 10 ** 9))
    people = [r for r in rows if r['told']]
    rest = [r for r in rows if not r['told'] and r['section'] == 'general']
    special = [r for r in rows if r['section'] == 'special']
    found = {**series.fold(rest, general=True), **series.fold(special, general=False)}
    _first_words([r for r in people + rest if r['type'] in OPENED and not r['series']], paths)
    return {
        'from': monday, 'to': sunday,
        'issues': [{'number': i.number, 'suffix': i.suffix, 'date': i.date, 'key': i.key, 'edition': i.edition,
                    'hijri': i.hijri_date, 'first_page': i.first_page_number,
                    'pages': i.document.page_count if i.document_id else None,
                    'special': sum(1 for t in texts if t.first_published_in_id == i.pk and t.bo_section == 'special')}
                   for i in issues],
        'people': people, 'rest': rest, 'special_texts': special, 'series': found,
        'prev': monday - timedelta(days=7) if general.filter(date__lt=monday).exists() else None,
        'next': monday + timedelta(days=7) if general.filter(date__gt=sunday).exists() else None,
        'weeks': _around(general, monday),
    }


def _around(general, monday: date) -> list[dict]:
    """The weeks around this one, oldest first, for stepping by sight: each Monday and how many issues and pages it
    printed. Eight weeks before it and up to four after, as far as the Bulletin goes."""
    newest = general.order_by('-date').values_list('date', flat=True).first() or monday
    last = min(monday + timedelta(weeks=WEEKS_AFTER), newest - timedelta(days=newest.weekday()))
    first = min(monday, last) - timedelta(weeks=WEEKS_SHOWN - 1 - max(0, (last - monday).days // 7))
    weeks = {first + timedelta(weeks=k): {'issues': 0, 'pages': 0} for k in range((last - first).days // 7 + 1)}
    for day, pages in general.filter(date__range=(first, last + timedelta(days=6))).values_list('date', 'document__page_count'):
        w = weeks[day - timedelta(days=day.weekday())]
        w['issues'] += 1
        w['pages'] += pages or 0
    return [{'from': d, **v} for d, v in weeks.items()]


def _first_words(rows: list[dict], paths: dict[str, Text]) -> None:
    """The first article of each text as printed, its label and its opening words: the law said by itself."""
    if not rows:
        return
    first = Article.objects.filter(version__text=OuterRef('pk'), version__language='ar').order_by('version__valid_from', 'order')
    opened = {pk: (label, body) for pk, label, body in
              Text.objects.filter(pk__in=[paths[r['path']].pk for r in rows])
              .annotate(label=Subquery(first.values('label')[:1]), body=Subquery(first.values('body')[:1]))
              .values_list('pk', 'label', 'body') if body}
    for r in rows:
        if (o := opened.get(paths[r['path']].pk)):
            body = o[1].strip()
            r['first'] = {'label': o[0], 'body': body if len(body) <= FIRST_WORDS else body[:FIRST_WORDS].rsplit(' ', 1)[0] + ' …'}


def _links(uris: list[str]) -> tuple[dict[str, list[dict]], dict[str, list[dict]]]:
    """What each text changes, as the links pipeline read it, and what it applies («بتطبيق»): the texts, named as people
    call them."""
    changes = (Change.objects.filter(by_uri__in=uris).exclude(source=Change.Source.MODEL)
               .values_list('by_uri', 'text_uri').distinct())
    applies = (Mention.objects.filter(from_uri__in=uris, kind=Mention.Kind.APPLIES, state=Mention.State.RESOLVED)
               .values_list('from_uri', 'to_uri').distinct())
    both: list[dict[str, list[str]]] = [{}, {}]
    for kept, pairs in zip(both, (changes, applies)):
        for by, uri in pairs:
            if uri != by and uri not in kept.setdefault(by, []):
                kept[by].append(uri)
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in={u for k in both for us in k.values() for u in us})}
    return tuple({by: [{'path': text_path(u), 'name': name(texts[u])} for u in us if u in texts][:CHANGED_MOST]
                  for by, us in kept.items()} for kept in both)
