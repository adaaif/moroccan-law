"""The law in the admin, for looking: texts, versions, articles, the links between texts and the addresses that lead to
them. Every row comes from the pipeline and is put right through the quality app's corrections (a correction applied
is applied again after every reload, and bumps the kept answers): typed over here it would be lost at the next load
and the site would go on showing what it kept. So nothing is added, changed or deleted here."""
import re

from django.contrib import admin
from django.db.models import Count, Q

from apps.corpus.models import Alias, Article, Mention, Text, Version
from apps.corpus.services.addresses import article_path, split_path, text_path
from config.admin import Large, ReadOnly, admin_link, changelist_link, on_site, rows_table, site_address

SHOWN = 20          # versions on a text's page, articles on a version's page; the rest one link away


def typed_address(term: str) -> tuple[str, str] | None:
    """An address pasted into a search box, as (the text's akn_uri, the article's eid or ''): the site's
    («https://…/ma/loi/2013/67-12/art_34», «/ma/loi/2013/67-12») or Akoma Ntoso's («/akn/ma/act/loi/2013/67-12»)."""
    term = re.sub(r'^https?://[^/]+', '', term.strip()).split('?')[0].split('#')[0].rstrip('/')
    if term.startswith('/akn/'):
        head, _, last = term.rpartition('/')
        return (head, last) if last.startswith('art_') else (term, '')
    if term.startswith('/ma/'):
        return split_path(term)
    return None


def text_number(term: str) -> str:
    """A text's number as the corpus keeps it: «67.12» → «67-12», «1.03.194» → «1-03-194»."""
    return term.strip().replace('.', '-').replace('/', '-')


def texts_numbered(term: str):
    number = text_number(term)
    return Text.objects.filter(Q(number=number) | Q(number_as_printed=term.strip())).values('pk')


@admin.register(Text)
class TextAdmin(Large, ReadOnly):
    list_display = ('akn_uri', 'type', 'number_as_printed', 'short_title', 'status', 'signed_on', 'first_published_in')
    list_display_links = ('akn_uri',)
    list_select_related = ('first_published_in',)
    list_filter = ('type', 'status')
    search_fields = ('title_ar',)
    search_help_text = ('An address (/ma/loi/2013/67-12, or pasted from the site), a number (67.12, 1-03-194), or '
                        'words of the Arabic or French title.')
    fieldsets = [
        ('The text', {'fields': ('akn_uri', 'type', 'number', 'number_as_printed', 'title_ar', 'title_fr', 'aliases',
                                 'status')}),
        ('Signed and published', {'fields': ('signed_on', 'signed_on_hijri', 'authority', 'promulgating_dahir',
                                             'first_published_in', 'first_published_page', 'rubric', 'bo_section')}),
        ('Its versions', {'fields': ('versions_table',)}),
        ('The row', {'classes': ('collapse',), 'fields': ('created_at', 'updated_at')}),
    ]
    readonly_fields = ('versions_table',)

    def view_on_site(self, obj):
        return site_address(text_path(obj.akn_uri))

    def get_search_results(self, request, queryset, search_term):
        found = typed_address(search_term)
        if found:
            return queryset.filter(akn_uri=found[0]), False
        if search_term.strip() and re.fullmatch(r'[\d.\-/]+', search_term.strip()):
            return queryset.filter(pk__in=texts_numbered(search_term)), False
        term = search_term.strip()
        if not term:
            return queryset, False
        return queryset.filter(Q(title_ar__icontains=term) | Q(title_fr__icontains=term)), False

    @admin.display(description='title')
    def short_title(self, obj):
        title = obj.title_ar or obj.title_fr
        return title[:90] + ('…' if len(title) > 90 else '')

    @admin.display(description='versions (newest first)')
    def versions_table(self, obj):
        rows = list(obj.versions.annotate(articles_held=Count('articles')).order_by('-valid_from', '-pk')[:SHOWN + 1])
        more = changelist_link(Version, 'every version of this text', text=obj.pk) if len(rows) > SHOWN else None
        return rows_table(
            ('from', 'to', 'language', 'consolidation', 'articles'),
            [(admin_link(v, str(v.valid_from)), v.valid_to or '—', v.language, v.get_consolidation_display(),
              v.articles_held) for v in rows[:SHOWN]], more)


@admin.register(Version)
class VersionAdmin(Large, ReadOnly):
    list_display = ('text', 'language', 'valid_from', 'valid_to', 'consolidation', 'source_pages')
    list_select_related = ('text',)
    list_filter = ('language', 'consolidation')
    search_fields = ('text__number',)
    search_help_text = 'The text\'s address (/ma/loi/2013/67-12) or number (67.12).'
    fieldsets = [
        ('The version', {'fields': ('text', 'language', 'valid_from', 'valid_to', 'consolidation', 'source_document',
                                    'source_pages')}),
        ('Before and after the articles', {'classes': ('collapse',), 'fields': ('preamble', 'closing')}),
        ('Translated by a machine', {'classes': ('collapse',),
                                     'fields': ('translated_from', 'translated_by', 'translated_at')}),
        ('Its articles', {'fields': ('articles_table',)}),
    ]
    readonly_fields = ('articles_table',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('text', 'source_document')

    def view_on_site(self, obj):
        return site_address(text_path(obj.text.akn_uri))

    def get_search_results(self, request, queryset, search_term):
        found = typed_address(search_term)
        if found:
            return queryset.filter(text__akn_uri=found[0]), False
        if search_term.strip():
            return queryset.filter(text__in=texts_numbered(search_term)), False
        return queryset, False

    @admin.display(description='articles (in order)')
    def articles_table(self, obj):
        rows = list(obj.articles.order_by('order').only('pk', 'version_id', 'order', 'label', 'eid', 'printed_page')
                    [:SHOWN + 1])
        more = changelist_link(Article, 'every article of this version', version=obj.pk) if len(rows) > SHOWN else None
        return rows_table(
            ('order', 'label', 'page', 'on the site'),
            [(a.order, admin_link(a, a.label), a.printed_page or '—',
              on_site(article_path(obj.text.akn_uri, a.eid)) if a.eid else '—') for a in rows[:SHOWN]], more)


@admin.register(Article)
class ArticleAdmin(Large, ReadOnly):
    list_display = ('label', 'version__text', 'version__language', 'version__valid_from', 'version__consolidation',
                    'printed_page', 'on_the_site')
    list_select_related = ('version__text',)
    list_filter = ('version__language',)
    search_fields = ('number',)
    search_help_text = ('An article\'s address (/ma/loi/2013/67-12/art_34, or pasted from the site), or a text\'s '
                        'number and the article\'s: «67.12 34». The words are searched on the site.')
    fields = ('version', 'order', 'label', 'number', 'eid', 'printed_page', 'heading_path', 'body')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('version__text')

    def view_on_site(self, obj):
        return site_address(article_path(obj.version.text.akn_uri, obj.eid)) if obj.eid else None

    def get_search_results(self, request, queryset, search_term):
        found = typed_address(search_term)
        if found:
            uri, eid = found
            rows = queryset.filter(version__text__akn_uri=uri)
            return (rows.filter(eid=eid) if eid else rows), False
        words = search_term.split()
        if not words:
            return queryset, False
        if len(words) > 2:
            return queryset.none(), False
        rows = queryset.filter(version__text__in=texts_numbered(words[0]))
        return (rows.filter(number=text_number(words[1])) if len(words) == 2 else rows), False

    @admin.display(description='on the site')
    def on_the_site(self, obj):
        return on_site(article_path(obj.version.text.akn_uri, obj.eid), 'open') if obj.eid else '—'


@admin.register(Mention)
class MentionAdmin(Large, ReadOnly):
    list_display = ('from_uri', 'from_eid', 'kind', 'to_uri', 'to_number', 'state', 'short_words')
    list_filter = ('kind', 'state')
    search_fields = ('=from_uri', '=to_uri')
    search_help_text = 'A text\'s address (/ma/… or /akn/…): the links from it and to it.'

    def view_on_site(self, obj):
        return site_address(article_path(obj.from_uri, obj.from_eid) if obj.from_eid.startswith('art_')
                            else text_path(obj.from_uri))

    def get_search_results(self, request, queryset, search_term):
        found = typed_address(search_term)
        if found:
            return queryset.filter(Q(from_uri=found[0]) | Q(to_uri=found[0])), False
        return super().get_search_results(request, queryset, search_term)

    @admin.display(description='words')
    def short_words(self, obj):
        return obj.words[:80]


@admin.register(Alias)
class AliasAdmin(ReadOnly):
    list_display = ('alias', 'uri', 'reason')
    list_filter = ('reason',)
    search_fields = ('alias', 'uri')
    search_help_text = 'Part of either address; an address pasted from the site finds its text\'s aliases.'
    ordering = ('alias',)

    def get_search_results(self, request, queryset, search_term):
        found = typed_address(search_term)
        if found:
            return queryset.filter(Q(alias=found[0]) | Q(uri=found[0])), False
        return super().get_search_results(request, queryset, search_term)
