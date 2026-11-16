"""Signing days that cannot be (RD4 of the readers review): 16 texts were dated in the future (a dahir of 1932
signed «2032», one of 1935 «2935») and 6 before 1912 (a Hijri year read as the Gregorian one: «1413-06-06» for 6 June
1993). Each is put right from what the text itself prints, and only then:

- the Gregorian day in its own title («… صادر في 15 من ذي الحجة 1413 (6 يونيو 1993) …»), when it falls in the year
  before its issue;
- else the same day and month in the year of the issue that printed it (or the year before, for a text of December
  printed in January), when that falls in the 200 days before the issue.
A text neither rule dates is listed and left. Prints what it would do; `--write` records it.

    mend_dates            # the list
    mend_dates --write
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.consolidation.services.instructions import date_in, plain
from apps.corpus.models import Text

FIRST = date(1912, 1, 1)


def right_day(signed: date, issued: date | None, title: str) -> date | None:
    """The day a text was signed, from an impossible one: None when nothing it prints dates it."""
    if issued is None:
        return None
    said = date_in(plain(title or ''))
    if said and timedelta(0) <= issued - said <= timedelta(days=400):
        return said
    for year in (issued.year, issued.year - 1):
        try:
            day = signed.replace(year=year)
        except ValueError:          # 29 February of a year that has none
            continue
        if timedelta(0) <= issued - day <= timedelta(days=200):
            return day
    return None


class Command(BaseCommand):
    help = 'Put right the signing days that fall in the future or before 1912, from the text\'s own title and issue.'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true')

    def handle(self, *args, write, **opts):
        texts = (Text.objects.filter(Q(signed_on__gt=date.today()) | Q(signed_on__lt=FIRST))
                 .select_related('first_published_in').order_by('signed_on'))
        mended = left = 0
        for text in texts:
            issued = text.first_published_in.date if text.first_published_in_id else None
            day = right_day(text.signed_on, issued, text.title_ar)
            if day is None:
                left += 1
                self.stdout.write(f'{text.akn_uri}: {text.signed_on} (printed {issued}): nothing dates it, left')
                continue
            mended += 1
            self.stdout.write(f'{text.akn_uri}: {text.signed_on} -> {day} (printed {issued})')
            if write:
                text.signed_on = day
                text.save(update_fields=['signed_on', 'updated_at'])
        self.stdout.write(f'{mended} days {"put right" if write else "to put right (not written)"}, {left} left')
