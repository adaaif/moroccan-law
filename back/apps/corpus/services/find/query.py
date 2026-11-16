"""A query read into its answers (`find`): a finance law by its year, a short form, an issue, a constitution's year, a
day with or without a kind, a kind with a year and a word, a citation, a name; then the answers, their texts read in
one query."""
import re
from datetime import timedelta

import ma_law

from apps.corpus.models import Text
from apps.corpus.services import hijri, works
from apps.corpus.services.addresses import text_path
from apps.corpus.services.find.kept import _AMENDS, _address, _books, _cited, _titled
from apps.corpus.services.find.typed import gregorian, kind_of, spelled, stems, title_stems, words


MOST = 6                                                    # answers at most, a note says how many more there are
DATED = {'dahir': ('dahir', 'law', 'decree_law'), 'law': ('law', 'organic_law', 'dahir', 'decree_law'), 'decree': ('decree',),
         'order': ('order',)}
ANY_DAY = ('dahir', 'law', 'organic_law', 'decree_law', 'constitution')
_YEAR = re.compile(r'(?:^| )(1[89]\d\d|20[0-4]\d)(?: |$)')
_FINANCE = re.compile(r'(?:^| )(?:قانون )?(?:ال)?ماليه(?: ل?سنه)? (\d{4})$|^(?:projet de )?loi de finances? (\d{4})$|^p?lf (\d{4})$')
_BILL = re.compile(r'(?:^| )مشروع(?: |$)|^projet |^plf ')
_FINANCE_TITLE = re.compile(r'قانون\s+(?:ال)?مالية(?:\s+رقم\s*[\d.]+)?\s+(?:لل|ل)سنة(?:\s+المالية)?\s+(\d{4})')
_LETTERS = re.compile(r'^(?:[ء-ي]\s*[.\s]\s*){1,4}[ء-ي]\s*\.?$')
_LATIN = re.compile(r'^[A-Za-z][A-Za-z.]{1,7}$')
_PROMULGATES = re.compile(r'بتنفيذ|promulgation')
_NEWEST = re.compile(r'^(?:اخر عدد|العدد الاخير|اخر جريده|الجريده الرسميه اليوم|جريده اليوم|هذا الاسبوع|جديد الجريده الرسميه|'
                     r'(?:le |la )?dernier(?:e)? (?:bulletin officiel|bulletin|bo|numero|edition)|cette semaine)$')
_CONSTITUTION = re.compile(r'^(?:ال)?دستور (?:ل?سنه |عام )?(\d{4})$|^(?:la )?constitution (?:de )?(\d{4})$')
_FRENCH_REF = re.compile(r'\b(?:b\.?\s?o\.?|bulletin officiel)\b', re.I)


def find(query: str, beyond: bool = False) -> dict:
    """{'query', 'understood': {...}, 'answers': [...]}: see the module's words. An answer is a text
    ({'kind': 'text', 'sure', 'why', 'path', 'type', 'number', 'name', 'subject', 'signed_on', 'hijri', 'status', 'issue',
    'page', 'book'}), an article ({'kind': 'article', 'sure', 'path', 'label', 'state', 'text'}), an issue the citation
    reader named ({'kind': 'issue', …}) or a note ({'kind': 'note', 'code', …}).

    `beyond`: only what the search suggestions do not read themselves (a finance law's year, a short form, a text's
    day, a kind with a year, a name a text had): the header's box asks for these and keeps its own citations (W3)."""
    q = ' '.join((query or '').split())[:300]
    out = {'query': q, 'understood': {}, 'answers': []}
    if len(q) < 2:
        return out
    q = spelled(q)                                           # before Darija's letters are read: «n°43-20» is no word
    from apps.search.services.spelling import arabizi
    latin = arabizi(q)
    if latin:
        q = out['understood']['read_as'] = latin
    folded = ma_law.fold(q)
    if _NEWEST.match(folded):
        out['understood']['newest'] = True                  # the browser answers with the newest issues it holds
        return out
    picked: list[dict] = []                                  # {'uri', 'sure', 'why', …} in order, the texts fetched at the end
    notes: list[dict] = []
    understood = out['understood']

    def pick(uri: str | None, sure: bool, why: str = '', **more) -> None:
        if uri and not any(p.get('uri') == uri and p.get('article') == more.get('article') for p in picked):
            picked.append({'uri': uri, 'sure': sure, 'why': why, **more})

    def done() -> dict:
        out['answers'] = _answers(picked) + notes
        return out

    # A finance law by its year; a bill is a bill.
    m = _FINANCE.search(folded)
    if m:
        year = next(g for g in m.groups() if g)
        bill = bool(_BILL.search(folded))
        understood.update(finance=int(year), bill=bill)
        found = _finance(year)
        if bill and found.get('bill'):
            pick(found['bill'], True, 'bill')
        elif bill:
            notes.append({'kind': 'note', 'code': 'no_bill', 'year': int(year)})
        if found.get('law') and not (bill and found.get('bill')):
            pick(found['law'], not bill, 'finance')
        elif not found.get('law') and not bill:
            notes.append({'kind': 'note', 'code': 'no_finance_law', 'year': int(year)})
        return done()

    # A short form: letters with dots or spaces, a Latin acronym, or one of the three people type joined.
    from apps.corpus.services.library import FORMER, SHORT, SHORT_JOINED
    plain = q.replace('أ', 'ا').replace('إ', 'ا').replace('آ', 'ا')
    letters = (folded.replace(' ', '') if _LETTERS.match(plain) or folded in SHORT_JOINED
               else q.lower().replace('.', '') if _LATIN.match(q) else '')
    if letters in SHORT:
        understood['short'] = True
        pick(_address(SHORT[letters]), True, 'short')
        if picked:
            return done()

    # A day, in either calendar, with or without the kind of text.
    kind = kind_of(folded)
    read = hijri.parse(q)
    day = estimate = None
    spoken = ''
    if read:
        converted = hijri.to_gregorian(*read[:3])
        if converted:
            day, estimate, spoken = converted[0], not converted[1], read[3]
    if day is None:
        g = gregorian(folded)
        if g:
            day, spoken = g
    cites = ma_law.parse_query(q)
    # A number without a dash is a day or a year read as a number («ظهير 9 رمضان», «ظهير 1958 …»): never a text's.
    cites = [c for c in cites if not (c.get('text_number') and '-' not in c['text_number'])]
    numbered = [c for c in cites if c.get('text_number') or c.get('code')]
    from apps.corpus.services.citations import resolve_many
    issues = [c for c in cites if c.get('kind') == 'issue' and c.get('issue')]
    if issues and not numbered:
        # An issue named as one («الجريدة الرسمية عدد 5167 بتاريخ …»): its date is the issue's, not a text's day.
        found = resolve_many(issues[:1])[0]
        if found['issue']:
            # A reference written for the French edition («B.O. n° 5210 … p. 667») names another book's pages: the
            # Arabic issue of that number is offered, never opened, and said to be the Arabic one (W10).
            french = bool(_FRENCH_REF.search(q)) and not re.search('[ء-ي]', q)
            if french:
                understood['french'] = True
            picked.append({'issue': {**found['issue'], 'number': issues[0]['issue'], 'suffix': issues[0].get('issue_suffix') or ''},
                           'sure': not french})
        return done()
    c = _CONSTITUTION.search(folded)
    if c:
        year = int(c.group(1) or c.group(2))
        understood['year'] = year
        for uri in Text.objects.filter(type='constitution', signed_on__year=year).values_list('akn_uri', flat=True):
            pick(uri, True, 'year')
        if not picked:
            notes.append({'kind': 'note', 'code': 'no_text_that_year', 'year': year})
        return done()
    if day and not any(c.get('text_number') for c in cites):
        as_hijri = hijri.from_gregorian(day)
        understood['day'] = {'date': day, 'hijri': hijri.said(*read[:3]) if read else hijri.said(*as_hijri) if as_hijri else '',
                             'estimate': bool(estimate), 'kind': kind}
        rest = words(folded.replace(ma_law.fold(spoken), ' '))
        rest = [w for w in rest if w not in {'صادر', 'مؤرخ', 'مورخ', 'يوم', 'تاريخ', 'بتاريخ', 'موافق'}]
        kinds = DATED.get(kind, ANY_DAY)
        rows = list(Text.objects.filter(signed_on=day, type__in=kinds).values_list('akn_uri', 'title_ar')[:80])
        near = None
        if not rows and kind:
            around = (Text.objects.filter(signed_on__range=(day - timedelta(days=2), day + timedelta(days=2)), type__in=kinds)
                      .values_list('akn_uri', 'title_ar', 'signed_on')[:80])
            by_gap: dict = {}
            for uri, title, signed in around:
                by_gap.setdefault(abs((signed - day).days), []).append((uri, title, signed))
            if by_gap:
                closest = by_gap[min(by_gap)]
                near, rows = closest[0][2], [(uri, title) for uri, title, _ in closest]
        if rest and len(rows) > 1:
            narrowed = [(uri, title) for uri, title in rows if any(w in title_stems(title or '') for w in rest)]
            rows = narrowed or rows
        cited = _cited(uri for uri, _ in rows)
        rows.sort(key=lambda r: -cited.get(r[0], 0))
        if near:
            notes.append({'kind': 'note', 'code': 'near_day', 'date': near})
        elif not rows and kind:
            notes.append({'kind': 'note', 'code': 'no_text_that_day', 'date': day})
        first, second = (cited.get(rows[0][0], 0) if rows else 0), (cited.get(rows[1][0], 0) if len(rows) > 1 else 0)
        for i, (uri, _) in enumerate(rows[:MOST]):
            # Sure: the one text of that kind and day; or the one the others cite, by far.
            sure = bool(kind) and not near and i == 0 and (len(rows) == 1 or (first >= 20 and first >= 4 * second))
            pick(uri, sure, 'day', cited=cited.get(uri, 0))
        if len(rows) > MOST:
            notes.append({'kind': 'note', 'code': 'more_that_day', 'n': len(rows) - MOST})
        return done()

    # A kind, a year and a word: «ظهير 1958 الحريات العامة».
    y = _YEAR.search(folded)
    if y and kind and not numbered:
        year = int(y.group(1))
        wanted = words(folded.replace(y.group(1), ' '))
        if wanted:
            understood.update(year=year, kind=kind)
            all_stems = stems(folded)
            for needed, targets, _why in FORMER:
                if all(w in all_stems for w in needed):
                    for target in targets:
                        uri = _address(target)
                        signed = uri and Text.objects.filter(akn_uri=uri, signed_on__year=year).values_list('pk', flat=True).first()
                        if signed:
                            pick(uri, False, 'year')
            rows = list(Text.objects.filter(type__in=DATED.get(kind, ANY_DAY), signed_on__year=year).values_list('akn_uri', 'title_ar')[:4000])
            held = {uri for uri, _ in rows}
            for key, book in _books().items():
                if book['uri'] in held and any(all(w in name for w in wanted) for name in book['names']):
                    pick(book['uri'], False, 'year', book=key)
            match = [uri for uri, title in rows if all(w in title_stems(title or '') for w in wanted)]
            if not match and len(wanted) > 1:
                match = [uri for uri, title in rows if wanted[0] in title_stems(title or '')]
            cited = _cited(match[:60])
            match.sort(key=lambda uri: -cited.get(uri, 0))
            for uri in match[:MOST - len(picked)]:
                pick(uri, False, 'year', cited=cited.get(uri, 0))
            if picked and len(picked) == 1:
                picked[0]['sure'] = True
            if not picked:
                notes.append({'kind': 'note', 'code': 'no_text_that_year', 'year': year})
            return done()

    if beyond:
        all_stems = stems(q)
        for needed, targets, why in FORMER:
            if all(w in all_stems for w in needed):
                for i, target in enumerate(targets):
                    pick(_address(target), len(targets) == 1, 'former', former=why if i == 0 else '')
        return done()

    # Citations: an article of a text, a text by its number (the law before the dahir that promulgates it). All of
    # them resolved together: about six queries whatever was pasted.
    articles = [c for c in cites if c.get('kind') == 'article']
    texts = [c for c in cites if c.get('kind') == 'text' and (c.get('text_number') or c.get('code'))]
    target = None
    if articles:
        article = articles[0]
        target = article if (article.get('code') or article.get('text_number')) else (
            {**texts[0], 'article': article['article'], 'kind': 'article'} if len(texts) == 1 else None)
    if target:
        found = resolve_many([target])[0]
        understood['article'] = target['article']
        if found['text']:
            uri = '/akn/ma/act' + found['text']['path'][3:]
            if found['article']:
                pick(uri, True, 'article', article={'path': found['article']['path'], 'label': found['article']['label'], 'state': 'found'})
            else:
                pick(uri, False, 'no_article', article={'path': found['text']['path'], 'label': '', 'state': 'text_only', 'asked': target['article']})
            return done()
        if target.get('text_number'):
            notes.append({'kind': 'note', 'code': 'not_held', 'number': target['text_number'].replace('-', '.'), 'type': target.get('text_kind') or ''})
            return done()
    by_number = [c for c in texts if c.get('text_number')]
    if by_number:
        laws = [c for c in by_number if c['text_number'].count('-') == 1 and c.get('text_kind') in (None, 'law', 'organic_law')]
        dahirs = [c for c in by_number if c.get('text_kind') == 'dahir']
        if laws and dahirs and _PROMULGATES.search(folded):
            understood['promulgated_by'] = dahirs[0]['text_number'].replace('-', '.')
            by_number = laws + [c for c in by_number if c not in laws]
        by_number = by_number[:3]
        understood['number'] = by_number[0]['text_number'].replace('-', '.')
        for i, (c, found) in enumerate(zip(by_number, resolve_many(by_number))):
            number = c['text_number'].replace('-', '.')
            if found['text'] and found['text']['in_corpus']:
                pick('/akn/ma/act' + found['text']['path'][3:], i == 0, 'number')
                continue
            other = None
            if c.get('text_kind') == 'dahir':
                # A dahir that only promulgates a law opens the law.
                other = Text.objects.filter(promulgating_dahir=number).values_list('akn_uri', flat=True).first()
                if other:
                    understood['promulgated_by'] = number
                    pick(other, i == 0, 'promulgated')
            elif c.get('text_kind') in (None, 'law'):
                # A finance law takes its bill's number: until the Bulletin prints the law, the number opens the bill.
                other = Text.objects.filter(akn_uri=works.address('law', c['text_number']).replace('/act/loi/', '/act/projet-loi/'),
                                            type='bill').values_list('akn_uri', flat=True).first()
                if other:
                    pick(other, i == 0, 'bill')
            if not other:
                notes.append({'kind': 'note', 'code': 'not_held', 'number': number, 'type': c.get('text_kind') or ''})
        return done()

    # A name: one a text had, a code or core law by any of its names, then a law by the words of its title.
    wanted = words(q)
    all_stems = stems(q)
    for needed, targets, why in FORMER:
        if all(w in all_stems for w in needed):
            for i, target in enumerate(targets):
                pick(_address(target), len(targets) == 1, 'former', former=why if i == 0 else '')
    if picked:
        return done()
    if not wanted:
        return done()
    exact, more, part = [], [], []
    for key, book in _books().items():
        best = 0
        for name in book['names']:
            in_name = all(any(x == w or (len(w) >= 3 and x.startswith(w)) for x in name) for w in wanted)
            in_query = all(x in wanted for x in name)
            if in_name and len(name) == len(wanted):
                best = max(best, 3)
            elif in_name:
                best = max(best, 2)
            elif in_query and sum(map(len, name)) >= 4:
                best = max(best, 1)
        (exact if best == 3 else more if best == 2 else part if best == 1 else []).append((not book['base'], key))
    for i, (_, key) in enumerate(sorted(exact)):
        pick(_books()[key]['uri'], i == 0 and len(exact) <= 2 and not y, 'name', book=key)
    for _, key in sorted(more)[:4]:
        pick(_books()[key]['uri'], not exact and len(more) == 1, 'name', book=key)
    held = {p['uri'] for p in picked}
    titled = [row for row in _titled(wanted) if row[0] not in held]
    standing = [row for row in titled if not row[3] and row[4] != 'repealed']
    for row in (standing + [r for r in titled if r not in standing])[:2 if picked else 4]:
        # A law by words of its title is offered, never opened for the reader: «آخر» is in many titles (W1).
        pick(row[0], False, 'title')
    if not exact and not more:
        for _, key in sorted(part)[:2]:
            pick(_books()[key]['uri'], False, 'maybe', book=key)
    return done()


def _finance(year: str) -> dict:
    """{'law': address, 'bill': address} of the finance law of a fiscal year (one query)."""
    out = {}
    rows = (Text.objects.filter(type__in=('law', 'bill'), title_ar__contains='مالية').filter(title_ar__contains=year)
            .values_list('akn_uri', 'type', 'title_ar'))
    for uri, kind, title in rows:
        m = _FINANCE_TITLE.search(title or '')
        if not m or m.group(1) != year or _AMENDS.search(ma_law.fold(title[:m.start()] if m.start() > 12 else '')):
            continue
        if 'التصفية' in title or 'المعدل' in title or 'تعديلي' in title:
            continue
        out.setdefault('bill' if kind == 'bill' else 'law', uri)
    return out


def _answers(picked: list[dict]) -> list[dict]:
    """The picked addresses as answers, their texts fetched in one query."""
    from apps.corpus.services.codes import display_name
    from apps.corpus.services.titles import subject
    uris = [p['uri'] for p in picked if p.get('uri')]
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in=uris).select_related('first_published_in')} if uris else {}
    book_of = {book['uri']: key for key, book in _books().items()}
    out = []
    for p in picked:
        if p.get('issue'):
            out.append({'kind': 'issue', 'sure': p['sure'], **p['issue']})
            continue
        text = texts.get(p['uri'])
        if text is None:
            continue
        issue = text.first_published_in
        brief = {'path': text_path(text.akn_uri), 'type': text.type, 'number': text.number_as_printed, 'name': display_name(text),
                 'subject': subject(text.title_ar), 'signed_on': text.signed_on, 'hijri': text.signed_on_hijri, 'status': text.status,
                 'issue': None if issue is None else {'number': issue.number, 'suffix': issue.suffix, 'key': issue.key, 'date': issue.date},
                 'page': text.first_published_page, 'book': p.get('book') or book_of.get(text.akn_uri)}
        if p.get('article'):
            out.append({'kind': 'article', 'sure': p['sure'], **p['article'], 'text': brief})
        else:
            why = 'bill' if text.type == 'bill' else p['why']
            out.append({'kind': 'text', 'sure': (p['sure'] and text.type != 'bill') or (p['sure'] and p['why'] == 'bill'), 'why': why,
                        'former': p.get('former', ''), 'cited': p.get('cited'), **brief})
    return out
