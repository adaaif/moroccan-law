"""The search index built from the corpus: an entry for each article of each text's latest version, and one
for each text (its title, number and popular names), so a text with no articles loaded is found by name."""
import json
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path

import ma_law
from django.conf import settings
from django.db import transaction

from apps.consolidation.services.instructions import label_key
from apps.corpus.models import Article, Status, Text
from apps.corpus.services.codes import NAMES, TYPE_WEIGHT, code_of
from apps.search.models import SearchEntry
from apps.search.services.lemmas import lemmas
from apps.translations.models import FrenchArticle

POPULAR = Path(__file__).resolve().parent.parent / 'data' / 'popular_names.json'
APPROVAL = re.compile(r'يوافق بموجبه|بالموافقة على|portant approbation|approuvant')


@lru_cache(maxsize=1)
def popular() -> dict[str, list[str]]:
    return json.loads(POPULAR.read_text())['texts'] if POPULAR.exists() else {}


def names_of(text: Text) -> list[str]:
    """The names people give a text: a code's names, then the popular names list's."""
    code = code_of(text)
    return [*(NAMES.get(code, []) if code else []), *popular().get(text.akn_uri, [])]


def title_words(text: Text) -> str:
    """What a text's title entry holds: its title and popular names, and its number both ways (31-13, 31.13)."""
    parts = [text.title_ar, text.title_fr, *text.aliases, *names_of(text), text.number, text.number_as_printed]
    return ' '.join(p for p in parts if p)


# How often each term occurs in the corpus, for the bare forms below; written by a full rebuild.
TERMS = 'derived/search_terms.json'
BARE_MIN = 5         # the word without its «ل» or «ب» is this many times more common than with it («دعم» 3,460 to «لدعم» 546)
BARE_FLOOR = 50      # and common in its own right


@lru_cache(maxsize=1)
def term_counts() -> dict[str, int]:
    path = Path(settings.CORPUS_DIR) / TERMS
    return json.loads(path.read_text()) if path.exists() else {}


def count_terms(log=print) -> dict[str, int]:
    """Every term of every article, counted, and kept for the partial rebuilds that follow."""
    counts: Counter = Counter()
    for label, body in Article.objects.values_list('label', 'body').iterator(chunk_size=2000):
        counts.update(ma_law.index_terms(f'{label}\n{body}'))
    path = Path(settings.CORPUS_DIR) / TERMS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(counts), ensure_ascii=False))
    term_counts.cache_clear()
    log(f'search index: {len(counts)} distinct terms counted')
    return dict(counts)


def with_bare(terms: list[str]) -> list[str]:
    """The terms, and for a word that keeps a bare «ل» or «ب» («لدعم», «بإجازة»: the stem takes off «لل» and «بال», not
    these), the word without it when the corpus uses that far more often (H5 of the housing plan: «دعم السكن» did not
    reach the aid decree, which writes «لدعم السكن»). Only at index time: a query's «دعم» then meets the decree, and a
    query's «لدعم» still meets «لدعم»; «بطاقة» stays apart from «طاقة», both being common."""
    counts = term_counts()
    if not counts:
        return terms
    extra = []
    for t in terms:
        if len(t) >= 4 and t[0] in 'لب':
            rest = ma_law.stem(t[1:])
            n = counts.get(rest, 0)
            if n >= BARE_FLOOR and n >= BARE_MIN * max(counts.get(t, 0), 1) and rest not in extra:
                extra.append(rest)
    return terms + extra


def entries_for(text: Text, version=None, articles=(), french=None, changes=None) -> list[SearchEntry]:
    """A text's rows: its title row, with what an answer shows of the text, and a row an article of `version` (its
    latest), with what an answer shows of the article (B24 of the search plan). `french`: {article number: body};
    `changes`: {article label: the articles it changes} (changed_by)."""
    from apps.corpus.models import Consolidation
    from apps.corpus.services.addresses import article_path, text_path
    from apps.corpus.services.codes import display_name

    year = text.signed_on.year if text.signed_on else (
        text.first_published_in.date.year if text.first_published_in_id else None)
    # A law that only approves a treaty («قانون رقم … يوافق بموجبه على الاتفاقية…») weighs as the convention.
    approves = text.type == 'law' and APPROVAL.search(text.title_ar[:200])
    where = text_path(text.akn_uri)
    common = {'text_path': where, 'text_type': text.type, 'year': year, 'in_force': text.status != Status.REPEALED,
              'weight': TYPE_WEIGHT['convention'] if approves else TYPE_WEIGHT.get(text.type, 1.0),
              'version_from': version.valid_from if version else None,
              'consolidation': version.consolidation if version else ''}
    words = title_words(text)
    title_terms = ' '.join(with_bare(ma_law.index_terms(words)))
    out = [SearchEntry(kind=SearchEntry.Kind.TEXT, path=where, title_terms=title_terms, title_folded=ma_law.fold(words),
                       name=display_name(text), title=text.title_ar, number_as_printed=text.number_as_printed,
                       signed_year=text.signed_on.year if text.signed_on else None,
                       status=text.status, issue=text.first_published_in.key if text.first_published_in_id else '',
                       in_corpus=version is not None, **common)]
    published = version is not None and version.consolidation == Consolidation.AS_PUBLISHED
    for article in articles:
        # An article's official French is found with it (R6 of the road plan: «priorité à droite» found nothing).
        fr = (french or {}).get(label_key(article.label) or article.number, '')
        terms = with_bare(ma_law.index_terms(f'{article.label}\n{article.body}\n{fr}'))
        out.append(SearchEntry(kind=SearchEntry.Kind.ARTICLE, path=article_path(text.akn_uri, article.eid),
                               order=article.order, eid=article.eid, label=article.label,
                               heading_path=article.heading_path or [], body=article.body,
                               page=article.printed_page if published else None,
                               terms=' '.join(terms), lemma_terms=' '.join(lemmas(terms)),
                               changes=(changes or {}).get(article.label, []), title_terms=title_terms, **common))
    return out


def changed_by(texts) -> dict[str, dict[str, list[dict]]]:
    """{amending text's URI: {its article's label: [the article it changes, as an answer shows it]}} for the sound
    changes (read, confirmed or checked; never a repeal) to an article the site holds, in four queries (B16: an amending
    article came up beside the article it changes, and its card now says which and leads there)."""
    from apps.consolidation.models import Change, Verb
    from apps.corpus.models import Version, latest_ids
    from apps.corpus.services.addresses import article_path
    from apps.corpus.services.codes import display_name

    rows = list(Change.objects.filter(by_uri__in=[t.akn_uri for t in texts], state__in=SOUND)
                .exclude(verb=Verb.REPEALED).exclude(number='').exclude(by_article='')
                .order_by('pk').values_list('by_uri', 'by_article', 'text_uri', 'number', 'verb'))
    if not rows:
        return {}
    targets = {t.pk: t for t in Text.objects.filter(akn_uri__in={r[2] for r in rows})}
    latest = latest_ids(Version.objects.filter(text_id__in=targets).values_list('pk', 'text_id', 'valid_from', 'consolidation'))
    labels = {(targets[text_id].akn_uri, eid): label for text_id, eid, label in Article.objects.filter(
        version_id__in=latest.values(), eid__in={f'art_{r[3]}' for r in rows}).values_list('version__text_id', 'eid', 'label')}
    names = {t.akn_uri: display_name(t) for t in targets.values()}
    out: dict[str, dict[str, list[dict]]] = {}
    for by_uri, by_article, uri, number, verb in rows:
        label = labels.get((uri, f'art_{number}'))
        if label is None:
            continue
        shown = out.setdefault(by_uri, {}).setdefault(by_article, [])
        path = article_path(uri, f'art_{number}')
        if all(c['path'] != path for c in shown):
            shown.append({'path': path, 'label': label, 'verb': verb, 'name': names[uri]})
    return out


SOUND = ('read', 'confirmed', 'checked')
CHUNK = 500


def rebuild(texts=None, log=print) -> int:
    """The entries of `texts` (all texts when None) replaced by fresh ones, in one transaction: readers see the old rows
    or the new ones. A chunk of texts reads its versions, articles and French in a fixed number of queries (S8 of the
    performance audit). Returns the number written."""
    from apps.corpus.services.addresses import text_path

    if texts is None or not term_counts():
        count_terms(log)
    ids = list(Text.objects.order_by('pk').values_list('pk', flat=True)) if texts is None else sorted(t.pk for t in texts)
    written = 0
    with transaction.atomic():
        if texts is None:
            SearchEntry.objects.all().delete()      # a whole build leaves no row of a text since renamed or gone
        else:
            paths = [text_path(uri) for uri in Text.objects.filter(pk__in=ids).values_list('akn_uri', flat=True)]
            for i in range(0, len(paths), 5000):
                SearchEntry.objects.filter(text_path__in=paths[i:i + 5000]).delete()
        for i in range(0, len(ids), CHUNK):
            chunk = list(Text.objects.filter(pk__in=ids[i:i + CHUNK]).select_related('first_published_in')
                         .prefetch_related('versions'))
            latest = {t.pk: t.latest_version() for t in chunk}
            by_version: dict[int, list] = {}
            for article in Article.objects.filter(version_id__in=[v.pk for v in latest.values() if v]).order_by('version_id', 'order'):
                by_version.setdefault(article.version_id, []).append(article)
            french: dict[str, dict] = {}
            for uri, number, body in FrenchArticle.objects.filter(text_uri__in=[t.akn_uri for t in chunk]).values_list(
                    'text_uri', 'number', 'body'):
                french.setdefault(uri, {})[number] = body
            changes = changed_by(chunk)
            batch = []
            for text in chunk:
                version = latest[text.pk]
                batch.extend(entries_for(text, version, by_version.get(version.pk, []) if version else [],
                                         french.get(text.akn_uri), changes.get(text.akn_uri)))
            SearchEntry.objects.bulk_create(batch, batch_size=2000)
            written += len(batch)
    log(f'search index: {written} entries for {len(ids)} texts')
    return written
