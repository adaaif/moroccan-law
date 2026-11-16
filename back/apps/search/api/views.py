"""Search API: public, no session. GET /api/search/?q=, GET /api/search/people/?q=, GET /api/search/suggest/?q=, POST /api/search/resolve/,
POST /api/search/opened/ (which answer a search led to, for the weekly report), POST /api/search/event/ (what a reader
did with an answer, B3 of the search plan).

Every view cuts what it is sent to a stated length first (QUERY_MOST, TYPED_MOST, ADDRESS_MOST, WORD_MOST), before
anything reads it: a question of thousands of letters is read as its first few hundred."""
import re
from datetime import date

from django.conf import settings
from django.db import DatabaseError, connection
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.api.errors import errors_response
from apps.corpus.models import TextType
from apps.corpus.services import generation
from apps.corpus.services.citations import resolve_many
from apps.corpus.services.situations import titles
from apps.discussion.services import places, thread
from apps.opendata.throttles import PublicRate
from apps.places.services import finder
from apps.search.services import events, vocab
from apps.search.services.search.beside import door_french, topic_words, with_french
from apps.search.services.search.query import QUERY_MOST, TYPED_MOST, search
from apps.search.services.search.quotes import quoted
from apps.search.services.search.suggestions import suggest
from apps.search.services.search.within import find_in
from apps.topics.services import kit, topics
from config.timing import laps

MAX_CITATIONS = 300
ADDRESS_MOST = 200       # a text's address (/ma/loi/70-03), as events.PATH allows
WORD_MOST = 300          # a citation's words, as the reader's device sent them, and the type filter's list
SUGGEST_KEPT = 3600      # seconds a suggestion is kept: readers type the same beginnings within it; one typed once goes
_ARABIC = re.compile(r'[\u0600-\u06FF]')


def _asked(request, most: int) -> str:
    """The question sent, cut to `most` characters before anything reads it."""
    return request.query_params.get('q', '')[:most].strip()


class PublicView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [PublicRate]


# `isdecimal()`, not `isdigit()`: «²» is a digit to Python and no number to `int()`, which answered 500.

def _year(value: str | None) -> int | None:
    return int(value) if value and len(value) == 4 and value.isdecimal() and 1900 <= int(value) <= 2100 else None


def _page(value: str | None) -> int:
    """A page of answers, from 1; anything else, or more than four digits, is the first."""
    return int(value) if value and len(value) <= 4 and value.isdecimal() and int(value) > 0 else 1


class Search(PublicView):
    def get(self, request):
        p = request.query_params
        q = _asked(request, QUERY_MOST)
        types = [t for t in p.get('type', '')[:WORD_MOST].split(',') if t in TextType.values]
        page = _page(p.get('page'))
        try:
            out = search(q, types=types, years=(_year(p.get('from')), _year(p.get('to'))),
                         repealed=p.get('repealed') == '1', page=page, lang='fr' if p.get('lang') == 'fr' else 'ar')
        except DatabaseError:
            if connection.vendor == 'postgresql':
                raise
            # The index is ParadeDB's (the README, «Search»): on SQLite the site says so in its own error shape.
            return errors_response([('search', 'needs_postgres')], 503)
        if p.get('lang') == 'fr':
            with_french(out)
        lap = laps()
        # The life topics the question names in everyday words, Darija included (R1–R2 of the for-everyone review):
        # shown above the results, never changing them.
        # A question in Latin-letter Darija is read in its Arabic spelling (B6) by the topics and the doors too.
        asked = out.get('arabizi') or q
        # Words between quotes ask for the texts' own words as typed: no topic, door or gloss stands above them.
        exact = bool(out.get('exact'))
        out['topics'] = [] if exact else topics.matching(asked)
        # The doors and tools the question names in people's words, answered above the texts (X1 of the road tools
        # review): «شدني الرادار» opens the radar journey first.
        claimed = [] if exact else kit.matching(asked)
        if not claimed and not exact and asked != q:
            # Read as Darija in Arabic letters, it met no door: the doors hold Latin-letter words too («dkhel l compte»).
            claimed = kit.matching(q)
        # A door of a topic the question does not name is a guess, offered below, never the answer (RD8).
        out['doors'] = [d for d in claimed if not d.get('unsure')][:2]
        # No door names it: the nearest moments, asked back before any text (HM8 of the hard-moment review).
        out['nearest'] = ([] if exact or out['doors'] or out.get('jump') or out.get('famous')
                          else kit.nearest(asked, out['topics'][0]['slug'] if out['topics'] else None))
        if not (exact or out['doors'] or out.get('jump') or out.get('famous')):
            # After the doors of the topic it names, the guess: one door at most that only shares a word with it.
            near = {n['slug'] for n in out['nearest']}
            out['nearest'] = (out['nearest'] + [{k: v for k, v in d.items() if k not in ('unsure', 'mark')}
                                                for d in claimed if d.get('unsure') and d['slug'] not in near][:1])[:3]
        # A state or a Moroccan place named whole («الصين», «chine», «casa»): its page of every article that names it
        # (PL21 of the places review).
        out['place'] = None if exact or out.get('jump') else (finder.door(asked) or finder.door(q))
        # Its words of the law, each with the article of its texts that holds it best (P9 of the polish review).
        out['words'] = topic_words(out['topics'][0]['slug']) if out['topics'] and not out.get('jump') else []
        # The box that answers first (B15) gives way to a topic's doors and page, written and checked by people.
        # A famous article's card (famous.py) is that answer already.
        if out['topics'] or out['doors'] or out['place'] or out.get('famous'):
            out['answer'] = None
        # In the same answer, so nothing moves once drawn (U17 of the Moroccan-design review): the first topic's
        # situations for its card, and the articles the first door's answer rests on, shown right under it.
        if out['topics'] and not out.get('jump'):
            first = next((t for t in topics.load() if t['slug'] == out['topics'][0]['slug']), None)
            out['topics'][0]['situations'] = titles(first['situations'], settings.SHOW_DRAFTS)[:3] if first else []
        door = out['doors'][0] if out['doors'] and page == 1 and not out.get('jump') else None
        out['door_articles'] = kit.door_articles(door['topic'], door['ref']) if door else []
        if p.get('lang') == 'fr':
            door_french(out['door_articles'])
        lap('topics')
        # The question as typed with the law's words under its everyday forms (30 Oct 2026): «بغا يزيد فالكرا» over «الزيادة
        # في الوجيبة الكرائية». Arabic letters only: a French question's law words would be Arabic under French.
        out['said'] = (vocab.gloss(asked, out['doors'][0] if out['doors'] else None)
                       if not exact and not out.get('jump') and _ARABIC.search(asked) else [])
        # The questions people asked already (30 Oct 2026) come from /api/search/people/, asked beside this answer (PX10 of
        # the where-it-trips review: up to a second of a search went on them, after everything else). Kept empty for a page
        # loaded before the change.
        out['people'] = []
        # Another country's law asked for (RD11 of the readers review: «قانون الشغل الفرنسي» opened the Moroccan
        # Labour Code without a word): the page says what the site holds before what it found.
        out['foreign'] = bool(FOREIGN_LAW.search(q))
        return Response(out)


# A law word, then a country that is not Morocco, within a few words: «قانون الشغل الفرنسي», «code du travail français»,
# «droit algérien». A country named alone is a treaty's or a place's («اتفاقية مع فرنسا»).
FOREIGN_LAW = re.compile(
    r'(?:قانون|القانون|مدونة|المدونة|تشريع|التشريع|دستور|الدستور)\s+(?:\S+\s+){0,3}?(?:ال)?(?:فرنسي|جزائري|تونسي|مصري|إسباني|اسباني|بلجيكي|'
    r'كندي|سعودي|إماراتي|اماراتي|أمريكي|امريكي|ألماني|الماني|إيطالي|ايطالي|هولندي|بريطاني|تركي)(?:ة)?(?!\w)'
    r'|\b(?:droit|code|loi|législation|legislation|constitution)\b(?:\s+\S+){0,4}?\s+(?:français|française|algérien|algérienne|'
    r'tunisien|tunisienne|égyptien|égyptienne|espagnol|espagnole|belge|canadien|canadienne|allemand|allemande|italien|'
    r'italienne|américain|américaine|néerlandais|britannique|turc|turque)\b', re.IGNORECASE)


class People(PublicView):
    """GET /api/search/people/?q=: the questions people asked already in the topic the question names, each with its best
    answer, asked by the page beside /api/search/ so the law's answer never waits for them (PX10). Never for a search about
    violence, nor for a question that names no topic with a place in the discussion."""

    def get(self, request):
        from apps.search.services.search.asking import asked_words
        from apps.search.services.spelling import arabizi

        q = _asked(request, QUERY_MOST)
        asked = arabizi(q) or q
        found = topics.matching(asked) if q and not kit.private(asked) and not quoted(q)[0] else []
        place = f'{places.PREFIX}{found[0]["slug"]}' if found else ''
        if not place or not places.is_place(place):
            return Response({'topic': None, 'people': []})
        door = next(iter(kit.matching(asked)[:1]), None)
        door_words = kit.door_words(door['slug']) if door and door['topic'] == found[0]['slug'] else []
        return Response({'topic': found[0]['slug'],
                         'people': thread.asked_before(place, asked_words(asked) or asked, door_words)})


class FindIn(PublicView):
    """GET /api/search/in/?path=/ma/loi/70-03&q=النفقة: the articles of one text that hold the words (?any=1: any of
    them, for the marks a search leaves on the law: H2), and the forms the text writes them in."""

    def get(self, request):
        found = find_in(request.query_params.get('path', '')[:ADDRESS_MOST], _asked(request, TYPED_MOST),
                        any_word=request.query_params.get('any') == '1')
        if found is None:
            return Response({'errors': [{'field': 'path', 'code': 'not_found'}]}, status=404)
        return Response(found)


class Suggest(PublicView):
    """GET /api/search/suggest/?q=: what the box offers as a reader types, kept by the corpus generation, the drafts'
    setting and the words typed (an hour, SUGGEST_KEPT): readers type the same beginnings, each worked out once."""

    def get(self, request):
        q = _asked(request, TYPED_MOST)
        return generation.answer(['suggest', settings.SHOW_DRAFTS, q], lambda: suggest(q), timeout=SUGGEST_KEPT)


def _cited(c: dict) -> dict:
    """A citation as the device sent it, each field of the type ma_law gives it, cut to WORD_MOST; anything else is
    None (a list for a code's name, a word for an issue's number had answered 500)."""
    words = {k: (v[:WORD_MOST] if isinstance(v, str) else str(v) if isinstance(v, int) and not isinstance(v, bool)
                 else None) for k in ('kind', 'raw', 'article', 'text_kind', 'text_number', 'code', 'issue_suffix')
             for v in [c.get(k)]}
    issue = c.get('issue')
    issue = int(issue) if isinstance(issue, str) and re.fullmatch(r'[0-9]{1,6}', issue) else \
        issue if isinstance(issue, int) and not isinstance(issue, bool) else None
    places = {k: v if isinstance(v, int) and not isinstance(v, bool) else None for k in ('start', 'end') for v in [c.get(k)]}
    return {**words, 'issue': issue, **places}


class Resolve(PublicView):
    """The citation checker sends the citations ma_law found on the reader's device (never the document) and
    the document's date; each comes back with where it stands, all of them in a fixed number of queries."""

    def post(self, request):
        data = request.data if isinstance(request.data, dict) else {}
        citations = data.get('citations')
        if not isinstance(citations, list) or len(citations) > MAX_CITATIONS:
            return Response({'errors': [{'field': 'citations', 'code': 'invalid'}]}, status=400)
        try:
            since = date.fromisoformat(data['since']) if data.get('since') else None
        except (TypeError, ValueError):
            return Response({'errors': [{'field': 'since', 'code': 'invalid'}]}, status=400)
        clean = [_cited(c) for c in citations if isinstance(c, dict)]
        return Response({'results': resolve_many(clean, checker=True, since=since)})


class Opened(PublicView):
    """The first answer a search led to (row 20): its place, kept on the search's own anonymous row, and (B3) the
    address it opened. Searches that find texts but lead nowhere are what the weekly report reads."""

    def post(self, request):
        log, rank, path = request.data.get('log'), request.data.get('rank'), request.data.get('path') or ''
        if not isinstance(rank, int) or not 0 <= rank <= 500:
            return Response({'errors': [{'field': 'rank', 'code': 'invalid'}]}, status=400)
        refused = events.record(log, 'opened', path, rank)
        if refused and refused != [('log', 'not_found')]:
            return Response({'errors': [{'field': f, 'code': c} for f, c in refused]}, status=400)
        return Response(status=204)


class Event(PublicView):
    """What a reader did after a search (B3): opened, saved, shared or copied an answer, or said whether they found
    it. Tied to the search's anonymous row, nothing about the reader."""

    def post(self, request):
        d = request.data
        refused = events.record(d.get('log'), d.get('kind'), d.get('path') or '', d.get('rank'), d.get('seconds'))
        if refused:
            status = 404 if refused == [('log', 'not_found')] else 400
            return Response({'errors': [{'field': f, 'code': c} for f, c in refused]}, status=status)
        return Response(status=204)
