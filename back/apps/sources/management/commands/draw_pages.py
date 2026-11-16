"""Draw ahead the reading images of the pages the shelf's and the topics' named texts stand on (UX11 of
the phone-test review). A page's WebP is drawn on its first view and kept under CORPUS_DIR/renders (`web_image`), so the first reader of
a page waited 1.3–2.2 s; these are the pages most readers open. Run after a deploy, at the lowest priority:

    nice -n 19 manage.py draw_pages [--width 900] [--limit N]

A page already drawn is passed over, so a second run draws only what is new."""
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.corpus.api.views import OWN_FILE
from apps.corpus.models import Article, Text, Version, latest_ids
from apps.corpus.services import codes
from apps.sources.models import Page
from apps.sources.services.render import WEB_WIDTHS, web_image


class Command(BaseCommand):
    help = "Draw the reading images of the named texts' pages ahead of their first reader."

    def add_arguments(self, parser):
        parser.add_argument('--width', choices=WEB_WIDTHS, default='900', help="900 a phone's, 1600 a desk's or a zoom")
        parser.add_argument('--limit', type=int, default=0, help='at most this many pages drawn (0: all)')

    def handle(self, *args, width, limit, **opts):
        ids = [t.pk for t in codes.texts_of([k for k, _ in codes.SHELF + codes.MORE]).values() if t is not None]
        newest = latest_ids(Version.objects.filter(text_id__in=ids).order_by()
                            .values_list('id', 'text_id', 'valid_from', 'consolidation'))
        versions = {v.pk: v for v in Version.objects.filter(pk__in=newest.values()).only('id', 'text_id', 'consolidation',
                                                                                        'source_document_id')}
        issues = dict(Text.objects.filter(pk__in=ids).values_list('pk', 'first_published_in__document_id'))
        printed: dict[int, set[int]] = {}
        for version_id, page in (Article.objects.filter(version_id__in=versions).exclude(printed_page=None)
                                 .values_list('version_id', 'printed_page').distinct()):
            printed.setdefault(version_id, set()).add(page)
        # Where an article's page is, as a text's answer finds it: the SGG's or Adala's own file by position, the BO
        # issue by its printed folio.
        by_index: dict[int, set[int]] = {}
        by_folio: dict[int, set[int]] = {}
        for vid, folios in printed.items():
            v = versions[vid]
            if v.consolidation in OWN_FILE and v.source_document_id:
                by_index.setdefault(v.source_document_id, set()).update(f - 1 for f in folios)
            elif issues.get(v.text_id):
                by_folio.setdefault(issues[v.text_id], set()).update(folios)
        pages = [p for p in Page.objects.filter(document_id__in=by_index).select_related('document')
                 if p.index in by_index[p.document_id]]
        pages += [p for p in Page.objects.filter(document_id__in=by_folio).select_related('document')
                  if p.printed_number in by_folio[p.document_id]]
        self.stdout.write(f'{len(ids)} texts, {len(pages)} pages to have at {width} px')
        drawn = kept = failed = 0
        for page in pages:
            if limit and drawn >= limit:
                break
            done = Path(settings.CORPUS_DIR) / 'renders' / page.document.sha256[:16] / f'{page.index:04d}-{width}.webp'
            if done.exists():
                kept += 1
                continue
            try:
                web_image(page, int(width))
                drawn += 1
            except Exception as e:  # noqa: BLE001 — a page that cannot be drawn is said and passed
                failed += 1
                self.stderr.write(f'{page.document_id}/{page.index}: {e}')
        self.stdout.write(f'done: {drawn} drawn, {kept} already there, {failed} failed, at {width} px')
