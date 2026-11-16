"""A finance bill as filed in Parliament, or as a chamber voted it (the finance-bill review, P1, P2, P17):

    load_bill sources/mef/plf2027/corps-plf-2027_Ar.pdf sources/mef/plf2027/corps-PLF2027-fr.pdf \
        --number 60.26 --year 2027 --on 2026-10-20 --stage filed --url https://www.finances.gov.ma/…

The Arabic becomes a version of the bill's own text (`/akn/ma/act/projet-loi/60-26`, `Consolidation.BILL`, dated by
its stage; a later stage is a version more, so the page compares what Parliament changed), the French beside it; then
what its articles would change in other texts is read as proposals (`Change.Source.BILL`, `State.PROPOSED`), dated by
its «Dates d'effet», never applied. The bill is never law: the BO's finance law replaces it (P22)."""
from datetime import date
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.consolidation.models import Change
from apps.consolidation.services import engine
from apps.consolidation.services.versions import text_at
from apps.corpus.models import Article, Consolidation, Status, Text, Version
from apps.corpus.services import works
from apps.parliament.services import finance_bill
from apps.sources.models import DocumentKind, Source
from apps.sources.services.ingest import ingest_file
from apps.translations.models import FrenchArticle, FrenchText

STAGES = ('filed', 'representatives', 'councillors', 'second_reading')


class Command(BaseCommand):
    help = 'Load a finance bill (Arabic and French) as a bill, and read what it would change as proposals.'

    def add_arguments(self, parser):
        parser.add_argument('arabic')
        parser.add_argument('french')
        parser.add_argument('--number', required=True, help='as printed: 60.26')
        parser.add_argument('--year', type=int, required=True, help='the budget year')
        parser.add_argument('--on', required=True, help='the day of the stage (filing, a chamber\'s vote)')
        parser.add_argument('--stage', default='filed', choices=STAGES)
        parser.add_argument('--url', default='')

    def handle(self, *args, arabic, french, number, year, on, stage, url, **opts):
        day = date.fromisoformat(on)
        docs = {}
        for lang, rel in (('ar', arabic), ('fr', french)):
            path = Path(settings.CORPUS_DIR) / rel
            if not path.exists():
                raise CommandError(f'{rel}: not found')
            docs[lang] = ingest_file(path, source=Source.MEF, kind=DocumentKind.PARLIAMENT, language=lang,
                                     url=url and url.replace('_Ar.pdf', f'_{lang.capitalize()}.pdf'),
                                     meta={'stage': stage, 'bill': number, 'year': year})
        ar = finance_bill.read_arabic(str(Path(settings.CORPUS_DIR) / arabic))
        fr = finance_bill.read_french(str(Path(settings.CORPUS_DIR) / french))
        if len(ar.articles) < 20 or len(ar.articles) != len(fr.articles):
            raise CommandError(f'articles: {len(ar.articles)} Arabic, {len(fr.articles)} French')
        key = number.replace('.', '-')
        uri = works.address('bill', key)
        title_ar = f'مشروع قانون المالية رقم {number} للسنة المالية {year}'
        title_fr = f'Projet de loi de finances n° {key} pour l’année budgétaire {year}'
        with transaction.atomic():
            text, created = text_at(uri, title_ar)
            Text.objects.filter(pk=text.pk).update(title_ar=title_ar, title_fr=title_fr, type='bill', number=key,
                                                    status=Status.UNKNOWN)
            text.refresh_from_db()
            text.versions.filter(consolidation=Consolidation.BILL, valid_from=day).delete()
            version = Version.objects.create(text=text, language='ar', valid_from=day, consolidation=Consolidation.BILL,
                                             source_document=docs['ar'], source_pages=f'1-{docs["ar"].page_count}')
            Article.objects.bulk_create([
                Article(version=version, order=k, label=a.label, number=a.number, eid=f'art_{a.number}',
                        heading_path=a.heading_path, body=a.body, printed_page=a.page + 1)
                for k, a in enumerate(ar.articles, 1)])
            FrenchText.objects.update_or_create(text_uri=uri, defaults={
                'type': 'bill', 'number': key, 'title': title_fr, 'signed_on': None, 'issue_number': 0,
                'issue_date': day, 'document_sha': docs['fr'].sha256, 'pages': f'1-{docs["fr"].page_count}'})
            FrenchArticle.objects.filter(text_uri=uri).delete()
            FrenchArticle.objects.bulk_create([FrenchArticle(text_uri=uri, order=k, label=a.label, number=a.number,
                                                             body=a.body, printed_page=a.page + 1)
                                               for k, a in enumerate(fr.articles, 1)])
        proposals = read_bill(text, fr.articles)
        self.stdout.write(f'{uri}: {len(ar.articles)} articles (Arabic), {len(fr.articles)} French, stage {stage} on {day}; '
                          f'layer {ar.stats}; {proposals} proposed changes' + ('  (new text)' if created else ''))


def read_bill(text: Text, french_articles) -> int:
    """What the bill's articles would change, read by the links pipeline's own reader and kept as proposals: source
    «bill», state «proposed», each dated by the bill's «Dates d'effet» where it names the article; never applied."""
    out = engine.Read()
    engine.read_text(text, out)
    dates: dict[str, tuple[str, str, bool]] = {}
    for a in french_articles:
        if 'Dates d’effet' in a.body:
            dates.update(finance_bill.dates_of_effect(a.body))
    # The code articles the bill names, from its French lead (the Arabic layer garbles «و-11II»): a quoted line that
    # only refers to another article («المادة 252-I-ألف أدناه») is no change of its own.
    named = finance_bill.code_articles(next((a.body for a in french_articles if 'code général des impôts' in a.body
                                             and 'sont modifiées et complétées' in a.body), ''))
    rows, seen = [], set()
    for c in out.changes:
        if c.text_uri == '/akn/ma/act/code/cgi':
            if named and c.number not in named:
                continue
            if (c.number, c.verb) in seen:
                continue
            seen.add((c.number, c.verb))
        c.source, c.state = Change.Source.BILL, Change.State.PROPOSED
        if c.text_uri == '/akn/ma/act/code/cgi' and c.number.split('-')[0] in {k.split('-')[0] for k in dates}:
            found = dates.get(c.number) or dates.get(c.number.split('-')[0])
            if found:
                c.effective_on, c.effective_rule, c.effective_words = date.fromisoformat(found[0]), Change.Rule.STATED, found[1]
                if found[2]:
                    c.detail = {**(c.detail or {}), 'partial': True}
        rows.append(c)
    with transaction.atomic():
        Change.objects.filter(source=Change.Source.BILL, by_uri=text.akn_uri).delete()
        Change.objects.bulk_create(rows, batch_size=1000)
    return len(rows)
