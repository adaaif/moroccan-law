"""Where each book held from a file was first printed (RD5 of the readers review; services/pages_witness.py,
`first_print`): its signing day from its own heading, then the Arabic issue whose pages hold its articles and the page
they start on. Prints what it finds; `--write` records the day, the issue and the page on the text, only where the
text had none and the issue names the text and holds a fifth of its articles (half, for a text with no number).

    find_first_issues --library                 # the library's books held from a file
    find_first_issues /akn/ma/act/loi/70-03 --write
"""
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.corpus.models import Text
from apps.quality.services.pages_witness import LAYERS, cited_day, first_print, signed_day
from apps.sources.models import Issue


def fits(text: Text, day: date) -> bool:
    """Whether a day can be the text's own by the year its number carries: a dahir or a decree «2.04.143» is of 2004
    or the year after, a law «65.99» was signed between 1999 and 2007 (the Labour Code: 2003). A heading that cites
    another text gives that text's day: decree 2.04.143 read «12 August 1913», the land registration dahir's."""
    parts = [p for p in text.number.split('-') if p.isdigit()]
    if text.type in ('law', 'organic_law') and len(parts) == 2:
        short, wait = parts[1], 8
    elif len(parts) == 3:
        short, wait = parts[1], 2
    elif len(parts) == 2:
        short, wait = parts[1], 2            # a royal decree «514.65», an order «1319.15»
    else:
        return text.type not in ('law', 'organic_law', 'decree', 'dahir', 'decree_law')
    if len(short) != 2:
        return False
    # Numbered dahirs begin in 1956 and numbered laws later: «58» is 1958, «13» is 2013.
    year = (1900 if int(short) >= 56 else 2000) + int(short)
    return year <= day.year <= year + wait


class Command(BaseCommand):
    help = 'Find the issue and page that first printed a text held from a file.'

    def add_arguments(self, parser):
        parser.add_argument('uris', nargs='*')
        parser.add_argument('--library', action='store_true', help="every book of the library held from a file")
        parser.add_argument('--write', action='store_true', help='record what is found where the text names nothing')

    def handle(self, *args, uris, library, write, **opts):
        if library:
            from apps.corpus.services.addresses import split_path
            from apps.corpus.services.library import catalogue
            paths = [b['path'] for branch in catalogue()['branches'] for b in branch['books'] if b.get('path')]
            uris = sorted(Text.objects.filter(akn_uri__in=[split_path(p)[0] for p in paths], versions__consolidation__in=LAYERS)
                          .distinct().values_list('akn_uri', flat=True))
        if not uris:
            raise CommandError('name a text, or --library')
        days = issues = 0
        for uri in uris:
            text = Text.objects.filter(akn_uri=uri).select_related('first_published_in').first()
            if text is None:
                raise CommandError(f'{uri}: not in the corpus')
            day = text.signed_on or signed_day(text)
            # A day one citation alone gives is kept only when the issue found from it holds the text.
            lone = bool(day) and not text.signed_on and cited_day(text) == (day, 1)
            r = first_print(text, day=None if text.first_published_in_id else day)
            line = f'{uri}: signed {day or "?"}'
            fields = []
            # The issue names the text and holds a fifth of its articles; with no number to name, half of them.
            sure = r.get('issue') and r['found'] >= (0.2 if r['named'] else 0.5) * r['articles']
            if day and not text.signed_on and day <= date.today() and (sure or (not lone and fits(text, day))):
                text.signed_on = day
                fields.append('signed_on')
                days += 1
            if r.get('issue'):
                line += (f' · BO {r["number"]}{" " + r["suffix"] if r["suffix"] else ""} of {r["date"]}, page {r["page"]}: '
                         f'{r["found"]} of {r["articles"]} articles')
                if r['next']:
                    line += f' (next: BO {r["next"][0][1]} with {r["next"][0][0]})'
                if not text.first_published_in_id and sure:
                    text.first_published_in = Issue.objects.get(pk=r['issue'])
                    text.first_published_page = r['page']
                    fields += ['first_published_in', 'first_published_page']
                    issues += 1
                elif not text.first_published_in_id:
                    line += '  [too few: not recorded]'
            else:
                line += f' · {r.get("error")}'
            self.stdout.write(line)
            if write and fields:
                text.save(update_fields=[*fields, 'updated_at'])
        self.stdout.write(f'{len(uris)} texts: {days} days and {issues} first issues {"recorded" if write else "found (not written)"}')
