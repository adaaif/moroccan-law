"""One issue for each printed cover (FX3 of the mended-Bulletin review, 2 Nov 2026). The early Bulletin printed two numbers
or more under one cover («عددي 85 و 86», «عدد 304 لغاية 309», «عدد 572-573»; BO 610 is «عدد 610 — 637», after which
the Arabic edition took the French numbering). The SGG keeps one copy of the file per number, the copies a few
hundred bytes of metadata apart, and each copy became an issue with its own reading and its own texts: 81 extra Arabic
issues and 10 French ones, 2,809 pages, 526 texts.

Folding a copy into its cover keeps everything the copies are worth and nothing twice:
- the readings vote: three readings or more of a page give, word for word, what most of them read (BO 610's 28, BO
  304's 6); of two, the one with fewer signs of trouble (glued Latin letters, remarks, «...») is kept;
- every reading stays, moved to the cover's page as a run of its own («copy 611»), so nothing paid for is lost;
- the texts are matched across the copies by title and page; of each printed text the fullest cut (the most articles,
  the most words) is kept, under the cover's address when the cover has the text, and the others fold into it, their
  addresses leading there (`works.move`, reason «copy»);
- the copy keeps its row and its file (every fetched file is kept with its hash), names its cover (`copy_of`), and
  loses its pages."""
import difflib
import re
from collections import Counter, defaultdict

from django.db import transaction
from django.db.models import Count, Sum
from django.db.models.functions import Length

from apps.sources.models import Issue, OcrRun, Page

_FOLD = str.maketrans({'أ': 'ا', 'إ': 'ا', 'آ': 'ا', 'ٱ': 'ا', 'ى': 'ي', 'ة': 'ه', 'ؤ': 'و', 'ئ': 'ي'})
_MARKS = re.compile(r'[ً-ْـ]')
_WORD = re.compile(r'\S+')
_DIGITS = str.maketrans('٠١٢٣٤٥٦٧٨٩', '0123456789')
_GLUED = re.compile(r'[ء-ي][A-Za-z]|[A-Za-z][ء-ي]')


def groups(log=print) -> list[tuple[Issue, list[Issue]]]:
    """(cover, copies) for each cover stored under several numbers and not folded yet: issues of one edition whose
    numbers follow one another, with as many pages and files within 2 KB of one another (the SGG's copies differ in
    their metadata: BO 538's is 78 bytes shorter than 537's), whose first issue's cover prints the last number («عدد
    537 – و538 – و539», «عدد 610 — 637»), or whose files are the same size to the byte. The cover is the first
    number."""
    issues = list(Issue.objects.filter(copy_of__isnull=True, document__isnull=False, suffix='')
                  .select_related('document').order_by('edition', 'number'))
    covers = {p.document_id: p.text for p in Page.objects.filter(index=0, document__in=[i.document_id for i in issues])}
    out, k = [], 0
    while k < len(issues):
        run = [issues[k]]
        while (k + len(run) < len(issues) and (nxt := issues[k + len(run)]).edition == run[0].edition
               and nxt.number == run[-1].number + 1 and nxt.document.page_count == run[0].document.page_count
               and abs(nxt.document.bytes - run[0].document.bytes) <= 2000):
            run.append(nxt)
        k += len(run)
        if len(run) < 2:
            continue
        cover = covers.get(run[0].document_id, '').translate(_DIGITS)
        last = max((n for n in range(2, len(run) + 1)
                    if re.search(rf'(?<!\d){run[n - 1].number}(?!\d)', cover)
                    or all(i.document.bytes == run[0].document.bytes for i in run[:n])), default=0)
        if last < 2:
            log(f'  left alone: {run[0].edition} {", ".join(i.key for i in run)} (the cover does not print their numbers)')
            continue
        out.append((run[0], run[1:last]))
    return out


def _fold(word: str) -> str:
    return _MARKS.sub('', word).translate(_FOLD)


def trouble(text: str) -> int:
    """Signs a reading went wrong: words with Latin letters glued to Arabic ones, the model's remarks, «...»."""
    from apps.sources.services import remarks
    return len(_GLUED.findall(text)) + sum(remarks.found(text).values()) + text.count('...')


def vote(readings: list[str]) -> str:
    """What most readings read, word for word. The reading closest to all the others gives the page its shape (its
    lines, its tables); each of its words is replaced by another when more than half the readings, aligned to it, read
    that other word. Words a reading adds or drops are not voted on: the shape stays the backbone's."""
    readings = [r for r in readings if r and r.strip()]
    if len(readings) < 3:
        return min(readings, key=trouble) if readings else ''
    words = [[_fold(w) for w in _WORD.findall(r)] for r in readings]
    probe = list(range(len(readings)))[:9]

    def closeness(k: int) -> float:
        return sum(difflib.SequenceMatcher(None, words[k], words[j], autojunk=False).ratio() for j in probe if j != k)

    spine = max(range(len(readings)), key=closeness)
    tokens = list(_WORD.finditer(readings[spine]))
    ballots = [Counter({words[spine][i]: 1}) for i in range(len(tokens))]
    spelled = [Counter({tokens[i].group(0): 1}) for i in range(len(tokens))]
    for k, other in enumerate(readings):
        if k == spine:
            continue
        raw = _WORD.findall(other)
        for op, a1, a2, b1, b2 in difflib.SequenceMatcher(None, words[spine], words[k], autojunk=False).get_opcodes():
            if op == 'equal' or (op == 'replace' and a2 - a1 == b2 - b1):
                for i, j in zip(range(a1, a2), range(b1, b2)):
                    ballots[i][words[k][j]] += 1
                    spelled[i][raw[j]] += 1
    out, last = [], 0
    for i, m in enumerate(tokens):
        word, n = ballots[i].most_common(1)[0]
        out.append(readings[spine][last:m.start()])
        if word != words[spine][i] and n * 2 > len(readings):
            out.append(next(s for s, _ in spelled[i].most_common() if _fold(s) == word))
        else:
            out.append(m.group(0))
        last = m.end()
    out.append(readings[spine][last:])
    return ''.join(out)


def _content(texts) -> dict[int, tuple[int, int]]:
    """Each text's published articles and words: what makes a cut the fuller one."""
    from apps.corpus.models import Article
    rows = (Article.objects.filter(version__text__in=texts, version__consolidation='as_published')
            .values('version__text').annotate(n=Count('pk'), letters=Sum(Length('body'))))
    return {r['version__text']: (r['n'], r['letters'] or 0) for r in rows}


def _key(title: str) -> str:
    return re.sub(r'\W+', ' ', _fold(title or '')).strip()


def clusters(cover: Issue, copies: list[Issue]) -> list[list]:
    """The texts of a cover and its copies, one list per printed text: the cover's texts first, then each copy's
    matched one to one to the closest title (eight in ten of its letters alike), the nearer place in the issue
    breaking a tie. Pages are no guide: a copy's texts may stand on pages counted from another start (BO 88)."""
    from apps.corpus.models import Text
    members = [cover, *copies]
    by_member = defaultdict(list)
    for t in Text.objects.filter(first_published_in__in=members).order_by('first_published_page', 'pk'):
        by_member[t.first_published_in_id].append(t)
    groups_: list[list] = [[t] for t in by_member[cover.pk]]
    for copy in copies:
        free = list(range(len(groups_)))
        mine = by_member[copy.pk]
        for place, t in enumerate(mine):
            best, score = None, (0.0, 0.0)
            for g in free:
                s = difflib.SequenceMatcher(None, _key(groups_[g][0].title_ar), _key(t.title_ar), autojunk=False).ratio()
                near = -abs(g / max(len(groups_), 1) - place / max(len(mine), 1))
                if (s, near) > score:
                    best, score = g, (s, near)
            if best is not None and score[0] >= 0.8:
                groups_[best].append(t)
                free.remove(best)
            else:
                groups_.append([t])
    return groups_


def _address_under(cover: Issue, uri: str) -> str:
    """A copy's text kept as the cover's: its address names the cover («…/bo86-3» → «…/bo85-9»), when it named the
    copy; numbered texts («/dahir/1-56-051») keep theirs. A number no text or alias holds."""
    from apps.corpus.models import Alias, Text
    m = re.match(r'^(.*/bo)\d+(?:-[a-z]+)?-(\d+)$', uri)
    if not m:
        return uri
    k = 1
    while (Text.objects.filter(akn_uri=f'{m.group(1)}{cover.key}-{k}').exists()
           or Alias.objects.filter(alias=f'{m.group(1)}{cover.key}-{k}').exists()):
        k += 1
    return f'{m.group(1)}{cover.key}-{k}'


@transaction.atomic
def fold(cover: Issue, copies: list[Issue], log=print) -> dict:
    """Fold `copies` into `cover` (see the module's docstring). Returns what was done."""
    from apps.corpus.models import Alias, Text
    from apps.corpus.services import works
    from apps.quality.services.corrections import reapply_pages

    done = Counter()
    members = [cover, *copies]
    pages = defaultdict(dict)                 # index → issue pk → page
    for p in Page.objects.filter(document__in=[m.document_id for m in members]).select_related('document__issue'):
        pages[p.index][p.document.issue.pk] = p
    for _index, row in sorted(pages.items()):
        mine = row.get(cover.pk)
        if mine is None:
            continue
        readings = [row[m.pk].text for m in members if m.pk in row]
        text = vote(readings)
        if len(readings) >= 2:          # kept as a run, so choosing a page's reading again keeps this one
            OcrRun.objects.create(page=mine, engine='vote', text=text,
                                  variant=f'vote of {len(readings)} readings' if len(readings) >= 3 else 'kept of 2 readings')
            done['voted' if len(readings) >= 3 else 'kept of two'] += 1
        mine.text = text
        reapply_pages([mine])
        mine.save(update_fields=['text'])
        for m in copies:
            if m.pk in row:
                for run in OcrRun.objects.filter(page=row[m.pk]):
                    run.page, run.variant = mine, f'copy {m.key}' + (f': {run.variant}' if run.variant else '')[:40]
                    run.save(update_fields=['page', 'variant'])
                    done['runs moved'] += 1
    # The texts: the fullest cut of each, under the cover.
    content = _content(Text.objects.filter(first_published_in__in=members))
    kept, gone = [], []
    for group in clusters(cover, copies):
        best = max(group, key=lambda t: (content.get(t.pk, (0, 0)), t.first_published_in_id == cover.pk))
        home = next((t for t in group if t.first_published_in_id == cover.pk), None)
        titles = Counter(t.title_ar for t in group if t.title_ar)
        title = titles.most_common(1)[0][0] if titles and titles.most_common(1)[0][1] > 1 else best.title_ar
        if home is None:                       # a text the cover's cut missed: the fullest copy's becomes the cover's
            home = best
            new = _address_under(cover, best.akn_uri)
            old = best.akn_uri
            Text.objects.filter(pk=best.pk).update(first_published_in=cover, akn_uri=new)
            if new != old:
                works.move(old, new, Alias.Reason.COPY)
                gone.append(old)
            home.refresh_from_db()
            done['texts the cover lacked'] += 1
        elif best.pk != home.pk:               # a copy cut the text fuller: its words go to the cover's text
            languages = list(best.versions.filter(consolidation='as_published').values_list('language', flat=True))
            home.versions.filter(consolidation='as_published', language__in=languages).delete()
            best.versions.filter(consolidation='as_published').update(text=home)
            done['fuller cut taken from a copy'] += 1
        fields = {f: getattr(best, f) for f in ('signed_on', 'signed_on_hijri', 'number', 'number_as_printed',
                                                 'authority') if getattr(best, f) and not getattr(home, f)}
        if title and title != home.title_ar:
            fields['title_ar'] = title
        if fields:
            Text.objects.filter(pk=home.pk).update(**fields)
        for twin in group:
            if twin.pk != home.pk:
                gone.append(twin.akn_uri)
                works.fold_copy(twin, home)
                done['texts folded'] += 1
        kept.append(home.pk)
    # The copies: their numbers lead to the cover; their readings live on the cover's pages.
    for m in copies:
        Page.objects.filter(document=m.document_id).delete()
        Issue.objects.filter(pk=m.pk).update(copy_of=cover, first_page_number=cover.first_page_number)
        done['copies'] += 1
    done['kept'], done['gone'] = kept, gone
    return done
