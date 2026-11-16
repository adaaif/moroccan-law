"""What the library said wrong about its own books, mended (W11 of the library-search review, 10 Nov 2026). Reads and reports;
`--write` applies. Run it again at will: what is already right is left alone.

1. The tax code's articles 226 to 248 stood under a «book» named by a sentence («الكتاب مقررو هذه اللجان …»): a wrapped
   line of art. 225 bis that starts on «الكُتّاب», the committees' secretaries. The edition is read again with the rule
   mended (`dgi.NUMBERED`): the 36 articles get their headings back, and art. 225 bis the words it lost.
2. The DOC and the land-registration dahir, kept as compiled codes, carried no signing day: no date found them. Both
   are of 9 Ramadan 1331 (12 August 1913), as their own titles print it.
3. Titles that swallowed their text's first heading («… يتعلق بالجماعات قسم تمهيدي أحكام عامة») lose it.
4. The library's books whose status is still unknown are named with the reason (a condition a person must confirm).

    manage.py mend_library            # what it would change
    manage.py mend_library --write
"""
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.corpus.models import Article, Text

SIGNED = {'/akn/ma/act/code/doc': (date(1913, 8, 12), '9 رمضان 1331'),
          '/akn/ma/act/code/land-registration': (date(1913, 8, 12), '9 رمضان 1331')}
TAX = '/akn/ma/act/code/cgi'


class Command(BaseCommand):
    help = __doc__

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='apply what is reported')

    def handle(self, *args, write, **opts):
        touched: set[int] = set()
        with transaction.atomic():
            touched |= self.tax_headings(write)
            touched |= self.signing_days(write)
            touched |= self.swallowed_titles(write)
            if not write:
                transaction.set_rollback(True)
        self.unknown_status()
        if write and touched:
            from apps.search.services import index
            n = index.rebuild(list(Text.objects.filter(pk__in=touched)), log=lambda *_: None)
            self.stdout.write(f'search entries written again: {n}')
        self.stdout.write('written' if write else 'nothing written (run with --write)')

    def tax_headings(self, write: bool) -> set[int]:
        from apps.consolidation.services import dgi

        text = Text.objects.filter(akn_uri=TAX).first()
        version = text.latest_version() if text else None
        if version is None or not version.source_document_id:
            self.stdout.write('1. the tax code is not held here')
            return set()
        path = Path(settings.CORPUS_DIR) / version.source_document.path
        if not path.exists():
            self.stdout.write(f'1. the tax code\'s edition is not on this disk ({path}): its headings are left as they are')
            return set()
        fresh = {a.number: a for a in dgi.read(str(path)).text.articles}
        held = list(Article.objects.filter(version=version).order_by('order'))
        moved, mended, tried = [], [], set()
        for before, a in zip([None, *held], held):
            new = fresh.get(a.number)
            if new is None or list(a.heading_path) == list(new.heading_path):
                continue
            # A heading the mended rule no longer takes for one is a line of the article before: its words go back there.
            lost = a.heading_path[0] if a.heading_path and not (dgi.NUMBERED.match(a.heading_path[0]) or dgi.sgg.DIVISION.match(a.heading_path[0])) else ''
            if lost and before is not None and lost not in tried and lost not in before.body:
                tried.add(lost)                              # once, at the first article it heads: the line is the one before's
                body = self.put_back(before.body, '\n'.join(fresh[before.number].lines) if before.number in fresh else '', lost)
                if body:
                    mended.append((before, body))
                else:
                    self.stdout.write(f'   the words «{lost[:50]}…» were not put back in {before.label}: their place was not found')
            moved.append((a, list(new.heading_path)))
        self.stdout.write(f'1. the tax code: {len(moved)} articles get their headings back'
                          + (f' ({moved[0][0].label} to {moved[-1][0].label})' if moved else ''))
        for a, body in mended:
            self.stdout.write(f'   {a.label}: {len(body) - len(a.body)} characters of its own sentence put back')
        if write:
            for a, path_ in moved:
                a.heading_path = path_
            Article.objects.bulk_update([a for a, _ in moved], ['heading_path'])
            for a, body in mended:
                a.body = body
                a.save(update_fields=['body'])
        return {text.pk} if moved or mended else set()

    @staticmethod
    def put_back(body: str, fresh: str, lost: str) -> str:
        """`body` with the `lost` words back where the edition read again has them: between the same words before and
        after. Empty when that place is not found once."""
        at = fresh.find(lost)
        if at < 0:
            return ''
        before, after = fresh[:at].rstrip()[-24:], fresh[at + len(lost):].lstrip()[:24]
        k = body.find(before)
        if not before or not after or k < 0 or body.count(before) != 1:
            return ''
        end = k + len(before)
        rest = body[end:].lstrip()
        if not rest.startswith(after):
            return ''
        return f'{body[:end]} {lost} {rest}'

    def signing_days(self, write: bool) -> set[int]:
        out = set()
        for uri, (day, hijri) in SIGNED.items():
            text = Text.objects.filter(akn_uri=uri).first()
            if text is None or (text.signed_on == day and text.signed_on_hijri == hijri):
                continue
            self.stdout.write(f'2. {uri}: signed on {day} ({hijri}), was {text.signed_on or "no day"}')
            if write:
                Text.objects.filter(pk=text.pk).update(signed_on=day, signed_on_hijri=hijri)
            out.add(text.pk)
        if not out:
            self.stdout.write('2. the two compiled codes carry their signing day')
        return out

    def swallowed_titles(self, write: bool) -> set[int]:
        from apps.corpus.services.titles import _SWALLOWED

        out = set()
        for text in Text.objects.filter(title_ar__regex=r'(أحكام|احكام|مقتضيات)\s+عامة\s*$').only('id', 'akn_uri', 'title_ar'):
            title = _SWALLOWED.sub('', text.title_ar).rstrip(' ،.:-')
            if title == text.title_ar or len(title) < 12:
                continue
            self.stdout.write(f'3. {text.akn_uri}: «…{text.title_ar[len(title) - 24:]}» → «…{title[-24:]}»')
            if write:
                Text.objects.filter(pk=text.pk).update(title_ar=title)
            out.add(text.pk)
        if not out:
            self.stdout.write('3. no title ends on its text\'s first heading')
        return out

    def unknown_status(self) -> None:
        from apps.consolidation.services.engine import standing
        from apps.corpus.services.find import _books

        uris = [b['uri'] for b in _books().values()]
        unknown = list(Text.objects.filter(akn_uri__in=uris, status='unknown'))
        if not unknown:
            self.stdout.write('4. every book of the library has a status')
        for text in unknown:
            why = standing(text)
            self.stdout.write(f'4. {text.akn_uri}: status unknown'
                              + (f'; it takes effect on a condition a person must confirm: «{why["in_force_when"][:120]}…»' if why.get('in_force_when') else ''))
