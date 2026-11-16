"""Letters of another alphabet read into Arabic words (T3 of the work plan): «وحרר» for «وحرر», «البaccalوريا» for
«البكالوريا». The BO never prints an Arabic letter touching a Latin or Hebrew one, so each such word is a misreading.
Every page was read twice; the second reading is a witness. Where it prints, between the same neighbours, one Arabic
word the BO prints elsewhere, that word is the fix, applied and listed in «ما صححناه» with its page. Where it does
not, the word waits for a person with the page image."""
import re
from collections import Counter

from django.utils import timezone

from apps.corpus.models import Article, Consolidation
from apps.corpus.services.addresses import article_path
from apps.quality.models import Correction
from apps.quality.services.proofread import printed_words
from apps.sources.models import OcrRun, Page

TOUCH = re.compile(r'[ء-ي][a-z֐-׿]|[a-z֐-׿][ء-ي]')
EDGE = '«»"\'()[]{}،؛:.,;!?…-–*'
ARABIC = re.compile(r'[ء-يـ]+')


def core(token: str) -> str:
    return token.strip(EDGE)


def flagged() -> list[dict]:
    """Every word of the texts as published with an Arabic letter touching a Latin or Hebrew one."""
    out = []
    rows = (Article.objects.filter(version__consolidation=Consolidation.AS_PUBLISHED, version__language='ar')
            .values_list('version__text__akn_uri', 'eid', 'body', 'version__source_document_id'))
    for uri, eid, body, doc in rows.iterator(chunk_size=2000):
        tokens = re.sub(r'<[^>]+>', ' ', body).split()
        for i, t in enumerate(tokens):
            word = core(t)
            if '\\n' in word or not TOUCH.search(word):
                continue
            out.append({'path': article_path(uri, eid), 'word': word, 'doc': doc,
                        'before': core(tokens[i - 1]) if i else '', 'after': core(tokens[i + 1]) if i + 1 < len(tokens) else ''})
    return out


def _between(text: str, before: str, after: str) -> str | None:
    """The one word a reading prints between the same two neighbours, if it prints them so once."""
    if not (before and after):
        return None
    found = re.findall(r'(?<![\w])[^\w\s]*' + re.escape(before) + r'[^\w\s]*\s+(\S+)\s+[^\w\s]*' + re.escape(after)
                       + r'(?![\w])', text)
    return core(found[0]) if len(found) == 1 else None


def _same_ends(wrong: str, right: str) -> bool:
    """The fix keeps the Arabic the misreading has around its foreign letters: «وحרר» → «وح…», «البaccalوريا» →
    «الب…وريا»."""
    letters = [m.span() for m in re.finditer(r'[a-z\u0590-\u05FF]+', wrong)]
    head, tail = wrong[:letters[0][0]], wrong[letters[-1][1]:]
    return right.startswith(head) and right.endswith(tail) and len(right) > len(head) + len(tail)


def witness(item: dict) -> dict | None:
    """The second reading's word for a flagged one: {right, page, engine, variant}, or None."""
    for page in Page.objects.filter(document_id=item['doc'], text__contains=item['word']).only('id', 'printed_number'):
        for run in OcrRun.objects.filter(page=page).only('text', 'engine', 'variant'):
            if not run.text or item['word'] in run.text:
                continue
            right = _between(run.text, item['before'], item['after'])
            if right and ARABIC.fullmatch(right) and _same_ends(item['word'], right):
                return {'right': right, 'page': page.printed_number, 'engine': run.engine, 'variant': run.variant}
    return None


def suggest(words: Counter | None = None, log=print) -> dict:
    """Records each flagged word's fix. A witness word the BO prints elsewhere is applied; any other waits."""
    words = printed_words() if words is None else words
    known = set(Correction.objects.values_list('path', 'wrong'))
    counts = Counter()
    made = []
    for item in flagged():
        counts['flagged'] += 1
        if (item['path'], item['word']) in known:
            counts['known'] += 1
            continue
        w = witness(item)
        if w is None:
            counts['no witness'] += 1
            continue
        sure = words.get(w['right'], 0) >= 2
        counts['applied' if sure else 'waiting'] += 1
        made.append(Correction(path=item['path'], wrong=item['word'][:200], right=w['right'][:200],
                               source=Correction.Source.WITNESS,
                               status=Correction.Status.APPLIED if sure else Correction.Status.SUGGESTED,
                               decided_at=timezone.now() if sure else None,
                               evidence={'page': w['page'], 'engine': w['engine'], 'variant': w['variant'],
                                         'printed': words.get(w['right'], 0)}))
        known.add((item['path'], item['word']))
    Correction.objects.bulk_create(made, ignore_conflicts=True)
    return dict(counts)


def apply_witnessed() -> int:
    """Puts each applied witness fix into its article (and again after a reload, as every applied correction is)."""
    from apps.corpus.services.addresses import split_path
    from apps.quality.services.corrections import put_right
    changed = 0
    for c in Correction.objects.filter(source=Correction.Source.WITNESS, status=Correction.Status.APPLIED):
        uri, eid = split_path(c.path)
        for a in Article.objects.filter(version__text__akn_uri=uri, version__language='ar', eid=eid):
            body = put_right(a.body, c)
            if body != a.body:
                a.body = body
                a.save(update_fields=['body'])
                changed += 1
    return changed
