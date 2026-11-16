"""The doubtful words a visitor settles on «ساهم» (/open-source): one printed line, the two readings the site holds, and
which one the page prints. Each word is asked of WORD_ANSWERS people; a reviewer then confirms it against the page in
the admin (services/suspects.py `confirm`): no word of the law changes on what visitors said alone.

A suspect is askable when it is open, its signal one of two real readings of the page (`reread`, `copies`) or a word
seen nowhere else (`rare`), and its suggestion differs from its word. It is placed when its line was found on the
page's image (services/place.py). An answer keeps the suspect, the answer and the time: nothing about the person."""
from datetime import datetime, time
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Q, Subquery
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.quality.models import Answer, Suspect
from apps.quality.services.place import where
from apps.sources.models import Issue
from apps.sources.services.render import OCR_WIDTH

SIGNALS = (Suspect.Signal.REREAD, Suspect.Signal.COPIES, Suspect.Signal.RARE)
ASKABLE = Q(status=Suspect.Status.OPEN, signal__in=SIGNALS) & ~Q(suggestion='') & ~Q(suggestion=F('word'))
PLACED = Q(place__has_key='box')
MOST_SKIPPED = 100


def askable():
    return Suspect.objects.filter(ASKABLE)


def figures() -> dict:
    """How many words there are to settle, how many may be asked now, how many were answered enough, and the answers
    ever and since Morocco's midnight. Two queries."""
    n = settings.WORD_ANSWERS
    counts = Suspect.objects.aggregate(
        words=Count('pk', filter=ASKABLE),
        ready=Count('pk', filter=ASKABLE & PLACED & Q(asked__lt=n)),
        settled=Count('pk', filter=Q(status=Suspect.Status.OPEN, asked__gte=n)))
    midnight = timezone.make_aware(datetime.combine(timezone.localdate(), time.min))
    counts |= Answer.objects.aggregate(answers=Count('pk'), today=Count('pk', filter=Q(created_at__gte=midnight)))
    return counts


def skipped(raw: str) -> list[int]:
    """The ids of `?not=3,9,12`: a hundred at most, anything that is not a number passed over."""
    out = []
    for part in (raw or '').split(',')[:MOST_SKIPPED]:
        part = part.strip()
        if part.isascii() and part.isdigit() and len(part) <= 18:
            out.append(int(part))
    return out


def one(skip: list[int]) -> dict | None:
    """A word that may be asked now, the least asked first and at random among equals, never one of `skip`. One query."""
    # The word is chosen among the suspects alone; only the one chosen is joined to its page, document and issue.
    chosen = askable().filter(PLACED, asked__lt=settings.WORD_ANSWERS).exclude(pk__in=skip).order_by('asked', '?')
    s = (Suspect.objects.filter(pk=Subquery(chosen.values('pk')[:1])).select_related('page__document__issue')
         .only('word', 'suggestion', 'context', 'place', 'page__index', 'page__printed_number',
               'page__document__language', 'page__document__issue__number', 'page__document__issue__suffix',
               'page__document__issue__date').first())
    if s is None:
        return None
    raw = s.context.split()
    k = where(s.context, s.word)
    before, after = (raw[:k], raw[k + 1:]) if k is not None else ([], [])
    readings = [{'key': 'word', 'text': s.word}, {'key': 'suggestion', 'text': s.suggestion}]
    if s.pk % 2:                       # odd: the suggestion first, so neither side is always the reading as it stands
        readings.reverse()
    page, doc = s.page, s.page.document
    try:
        issue = doc.issue
    except Issue.DoesNotExist:
        issue = None
    left, top, right, bottom = _pixels(s.place)
    mark = None
    if s.place.get('mark'):
        width = s.place['size'][0]
        ml, mr = (round(x * width) for x in s.place['mark'])
        mark = {'x': round((ml - left) / (right - left), 4), 'w': round((mr - ml) / (right - left), 4)}
    # The word's own line inside the strip, which holds the lines above and below it too.
    line = None
    if s.place.get('line'):
        lt, lb = (round(y * s.place['size'][1]) for y in s.place['line'])
        line = {'y': round((lt - top) / (bottom - top), 4), 'h': round((lb - lt) / (bottom - top), 4)}
    return {
        'id': s.pk,
        'readings': readings,
        'before': ' '.join(before),
        'after': ' '.join(after),
        'strip': {'url': f'/api/quality/words/{s.pk}/strip/', 'width': right - left, 'height': bottom - top,
                  'mark': mark, 'line': line},
        'source': {'issue': {'number': issue.number, 'suffix': issue.suffix, 'date': issue.date.isoformat()}
                   if issue else None,
                   'page': page.printed_number, 'document_id': doc.pk, 'page_index': page.index,
                   'language': doc.language},
    }


def say(pk: int, says: str) -> None:
    """One person's answer about word `pk`: kept with its time, and the word's count of answers raised in the database,
    together. Refuses an answer that is not one of the four, and a word that is not askable and placed."""
    if says not in Answer.Says.values:
        raise Refused('says', 'invalid')
    with transaction.atomic():
        if not askable().filter(PLACED, pk=pk).update(asked=F('asked') + 1):
            raise Refused('word', 'not_found', 404)
        Answer.objects.create(suspect_id=pk, says=says)


def _pixels(place: dict) -> tuple[int, int, int, int]:
    """The strip's box in the render's pixels, as the strip is cut and as its size is given."""
    width, height = place['size']
    left, top, right, bottom = place['box']
    return round(left * width), round(top * height), round(right * width), round(bottom * height)


def strip(suspect: Suspect) -> Path | None:
    """The cut of the printed page around the word, as WebP, made once from the page's render and kept under the
    corpus's drawn files; its path, or None when the word is not placed or the page's render is not on this machine.
    Never renders a PDF nor runs Tesseract: a crop of a picture already there, a few hundredths of a second, made at
    most once for each placed word, so it is drawn without the drawing limits a reader's page image is under."""
    from PIL import Image

    from config import drawing

    if not (suspect.place or {}).get('box'):
        return None
    page = suspect.page
    folder = page.document.sha256[:16]
    render = Path(settings.CORPUS_DIR) / 'renders' / folder / f'{page.index:04d}-{OCR_WIDTH}.png'
    box = _pixels(suspect.place)
    name = f'{folder}-{page.index:04d}-{suspect.pk}-{"-".join(map(str, box))}.webp'      # a new place, a new strip
    out = Path(settings.CORPUS_DIR) / 'drawn' / 'strips' / name
    if not out.exists() and not render.exists():
        return None

    def draw(part: Path) -> None:
        with Image.open(render) as image:
            image.convert('L').crop(box).save(part, 'WEBP', quality=80, method=4)
    return drawing.picture(out, draw)
