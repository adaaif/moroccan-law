"""Where the law was read, for looking: the files as fetched, the Bulletin's issues, their pages and every engine's
reading of a page. The ingest and the readers write them; a file's path, hash, type and size are what the public file
endpoint serves (services/files.py), and a page's text is chosen by the pipeline and mended through corrections. So
nothing is added, changed or deleted here."""
import re

from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from apps.corpus.models import Text
from apps.sources.models import Document, Issue, OcrRun, Page
from config.admin import Large, ReadOnly, admin_link, changelist_link, on_site, rows_table, site_address

SHOWN = 20


def issue_key(term: str) -> tuple[int, str] | None:
    """«7533», «7465-bis», «BO 7465 bis» → (7533, '') or (7465, 'bis')."""
    m = re.fullmatch(r'(?:BO\s*)?(\d{1,6})(?:[\s-]*([a-z]+))?', term.strip(), re.IGNORECASE)
    return (int(m.group(1)), (m.group(2) or '').lower()) if m else None


def pages_of(term: str):
    """«7533» → the pages of that issue's files; «7533 12» → its printed page 12 (or the file's 12th page)."""
    words = term.split()
    key = issue_key(words[0]) if words else None
    if key is None or len(words) > 2 or (len(words) == 2 and not words[1].isdecimal()):
        return None
    documents = Issue.objects.filter(number=key[0], suffix=key[1], document__isnull=False).values('document_id')
    rows = Page.objects.filter(document_id__in=documents)
    if len(words) == 2:
        n = int(words[1])
        rows = rows.filter(printed_number=n) | rows.filter(index=n - 1)
    return rows.values('pk')


@admin.register(Document)
class DocumentAdmin(ReadOnly):
    list_display = ('path', 'source', 'kind', 'language', 'page_count', 'producer', 'fetched_at')
    list_filter = ('source', 'kind', 'language')
    search_fields = ('path', 'title', 'url', '=sha256')
    search_help_text = 'Part of the file\'s path, title or address where it was fetched; or its whole SHA-256.'
    ordering = ('-fetched_at',)
    fieldsets = [
        ('The file', {'fields': ('source', 'kind', 'language', 'title', 'url', 'fetched_at', 'the_file')}),
        ('As stored', {'fields': ('path', 'sha256', 'mime', 'bytes', 'page_count', 'producer')}),
        ('What it holds', {'fields': ('its_issue', 'its_pages')}),
        ('Read from the file', {'classes': ('collapse',), 'fields': ('meta',)}),
    ]
    readonly_fields = ('the_file', 'its_issue', 'its_pages')

    @admin.display(description='the file')
    def the_file(self, obj):
        url = reverse('sources-document-file', args=[obj.pk])
        return format_html('<a href="{}" target="_blank" rel="noopener">open it as fetched</a>', url)

    @admin.display(description='issue')
    def its_issue(self, obj):
        issue = Issue.objects.filter(document=obj).first()
        return admin_link(issue) if issue else '—'

    @admin.display(description='pages')
    def its_pages(self, obj):
        return changelist_link(Page, 'its pages', document=obj.pk)


@admin.register(Issue)
class IssueAdmin(ReadOnly):
    list_display = ('key', 'edition', 'date', 'hijri_date', 'document', 'copy_of', 'on_the_site')
    list_select_related = ('document', 'copy_of')
    list_filter = ('edition', ('copy_of', admin.EmptyFieldListFilter))
    search_fields = ('=number',)
    search_help_text = 'An issue\'s number: 7533, 7465-bis.'
    ordering = ('-date', '-number')
    fieldsets = [
        ('The issue', {'fields': ('edition', 'number', 'suffix', 'date', 'hijri_date', 'first_page_number',
                                  'copy_of')}),
        ('Its file and texts', {'fields': ('document', 'its_pages', 'texts_table')}),
    ]
    readonly_fields = ('its_pages', 'texts_table')

    def view_on_site(self, obj):
        return site_address(f'/bo/{obj.edition}/{obj.key}')

    def get_search_results(self, request, queryset, search_term):
        if not search_term.strip():
            return queryset, False
        key = issue_key(search_term)
        if key is None:
            return queryset.none(), False
        return queryset.filter(number=key[0], **({'suffix': key[1]} if key[1] else {})), False

    @admin.display(description='issue', ordering='number')
    def key(self, obj):
        return f'BO {obj.key}'

    @admin.display(description='on the site')
    def on_the_site(self, obj):
        return on_site(f'/bo/{obj.edition}/{obj.key}', 'open')

    @admin.display(description='pages')
    def its_pages(self, obj):
        return changelist_link(Page, 'its pages', document=obj.document_id) if obj.document_id else '—'

    @admin.display(description='texts first published in it')
    def texts_table(self, obj):
        rows = list(Text.objects.filter(first_published_in=obj).order_by('first_published_page', 'pk')
                    .only('pk', 'akn_uri', 'type', 'number', 'title_ar', 'first_published_page')[:SHOWN + 1])
        more = (changelist_link(Text, 'every text of this issue', first_published_in=obj.pk) if len(rows) > SHOWN
                else None)
        return rows_table(('page', 'text', 'title'),
                          [(t.first_published_page or '—', admin_link(t), t.title_ar[:90]) for t in rows[:SHOWN]], more)


@admin.register(Page)
class PageAdmin(Large, ReadOnly):
    list_display = ('document', 'index', 'printed_number', 'kind', 'text_source', 'layer_letters')
    list_select_related = ('document',)
    list_filter = ('kind', 'text_source', 'document__source')
    search_fields = ('=printed_number',)
    search_help_text = 'An issue\'s number, and a page: «7533» for its pages, «7533 12» for its printed page 12.'
    fieldsets = [
        ('The page', {'fields': ('document', 'index', 'printed_number', 'kind', 'text_source', 'on_the_site')}),
        ('Its text', {'fields': ('text',)}),
        ('The file\'s own text layer', {'classes': ('collapse',), 'fields': ('layer_text', 'layer_letters')}),
        ('How it was read', {'classes': ('collapse',), 'fields': ('quality', 'readings_table')}),
    ]
    readonly_fields = ('on_the_site', 'readings_table')

    def view_on_site(self, obj):
        return site_address(f'/pages/{obj.document_id}/{obj.index}')

    def get_search_results(self, request, queryset, search_term):
        if not search_term.strip():
            return queryset, False
        pages = pages_of(search_term)
        return (queryset.filter(pk__in=pages) if pages is not None else queryset.none()), False

    @admin.display(description='on the site')
    def on_the_site(self, obj):
        image = reverse('sources-page-image', args=[obj.document_id, obj.index])
        return format_html('{} · <a href="{}" target="_blank" rel="noopener">the page image</a>',
                           on_site(f'/pages/{obj.document_id}/{obj.index}', 'the page with its reading'), image)

    @admin.display(description='every engine\'s reading')
    def readings_table(self, obj):
        rows = list(obj.ocr_runs.order_by('-created_at').only(
            'pk', 'page_id', 'engine', 'variant', 'prompt_version', 'cost_usd', 'stop_reason', 'created_at')[:SHOWN])
        return rows_table(('when', 'engine', 'how', 'prompt', 'cost (USD)', 'stopped'),
                          [(admin_link(r, f'{r.created_at:%Y-%m-%d %H:%M}'), r.engine, r.variant or '—',
                            r.prompt_version or '—', r.cost_usd, r.stop_reason or '—') for r in rows])


@admin.register(OcrRun)
class OcrRunAdmin(Large, ReadOnly):
    list_display = ('created_at', 'page', 'engine', 'variant', 'prompt_version', 'input_tokens', 'output_tokens',
                    'cost_usd')
    list_select_related = ('page__document',)
    search_fields = ('=engine', '=batch_id')
    search_help_text = 'An engine\'s whole name or a batch\'s id; or an issue and a page: «7533 12».'
    fieldsets = [
        ('The reading', {'fields': ('page', 'engine', 'variant', 'prompt_version', 'image_px', 'created_at')}),
        ('Its price', {'fields': ('input_tokens', 'output_tokens', 'cost_usd', 'batch_id', 'stop_reason', 'seconds')}),
        ('What it read', {'classes': ('collapse',), 'fields': ('text',)}),
    ]

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('page__document')

    def get_search_results(self, request, queryset, search_term):
        pages = pages_of(search_term) if search_term.strip() and search_term.split()[0][:1].isdigit() else None
        if pages is not None:
            return queryset.filter(page__in=pages), False
        return super().get_search_results(request, queryset, search_term)
