"""Access on request in the admin: the requests waiting for the staff's answer, the accesses with their use, and the
read-only lists behind them (keys, days of use, downloads, the log of every act).

A request is decided on its own page: accept (what is granted, the size, a partner's numbers, the end date), ask for
more (one line) or decline (one of five reasons), each a small form whose answer the service writes with its letter
(services/requests.py). An access is ended or renewed the same way (services/access.py). Only a superuser decides, and
never on their own request; the rows themselves are never typed over here. The services log every act, whichever door
it came by (the site's access desk, these pages, the account's own page): a request's and an access's page shows its
history, and «Events» lists them all.

A key is made by its holder, on the account page; only its hash is kept, and never shown."""
from datetime import timedelta

from django import forms
from django.conf import settings
from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist, PermissionDenied
from django.db.models import Q, Sum
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from apps.accounts.services.refusals import Refused
from apps.opendata.models import Access, AccessDay, ApiKey, Download, Event, Request
from apps.opendata.services import access as accesses
from apps.opendata.services import requests as asked
from config.admin import ReadOnly, admin_link, changelist_link, rows_table

SHOWN = 20
USE_DAYS = 30
HISTORY = 50

# What a refusal of the services means, for the person deciding (the API's refusals are codes the web translates).
REFUSALS = {
    'not_superuser': 'Only a superuser decides.',
    'own': 'Nobody decides their own request.',
    'decided': 'This request was decided already.',
    'live': 'The account already holds a live access.',
    'past': 'The end date must come after today.',
    'ended': 'This access is ended.',
    'required': 'Grant the API, the database or both.',
}


def refusal(exc: Refused) -> str:
    return REFUSALS.get(exc.code, f'{exc.field}: {exc.code}')


def sizes_help() -> str:
    named = '; '.join(f'{name}: {s["minute"]} a minute, {s["calls"]:,} calls and {s["articles"]:,} articles a day'
                      for name, s in settings.ACCESS_SIZES.items())
    return f'{named}. A partner has its own three numbers below.'


class AcceptForm(forms.Form):
    api = forms.BooleanField(required=False, label='The API')
    data = forms.BooleanField(required=False, label='The database')
    size = forms.ChoiceField(choices=Access.Size.choices)
    minute = forms.IntegerField(min_value=1, required=False, label='Requests a minute',
                                help_text='A partner only; empty, the app size\'s.')
    calls = forms.IntegerField(min_value=1, required=False, label='Calls a day',
                               help_text='A partner only; empty, the app size\'s.')
    articles = forms.IntegerField(min_value=1, required=False, label='Articles a day',
                                  help_text='A partner only; empty, the app size\'s.')
    ends_on = forms.DateField(label='End date', widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['size'].help_text = sizes_help()


class AskForm(forms.Form):
    line = forms.CharField(max_length=asked.LINE_MOST, label='What you ask',
                           widget=forms.TextInput(attrs={'size': 80, 'dir': 'auto'}),
                           help_text='One line, sent to the person in a letter and shown on their account page.')


class DeclineForm(forms.Form):
    reason = forms.ChoiceField(choices=Request.Reason.choices, widget=forms.RadioSelect,
                               help_text='The letter says it in the person\'s language, with the day they may ask again.')


class EndForm(forms.Form):
    reason = forms.ChoiceField(choices=[(c, Access.Ended(c).label) for c in accesses.BY_THE_STAFF],
                               widget=forms.RadioSelect,
                               help_text='Its keys stop at once; a letter tells the holder why.')


class RenewForm(forms.Form):
    ends_on = forms.DateField(label='New end date', widget=forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'))


class Decisions:
    """The small forms on a row's own page: `acts` names each one (its address, title, form, what it does)."""
    acts: dict = {}

    def get_urls(self):
        name = self.model._meta.model_name
        return [*(path(f'<int:pk>/{act}/', self.admin_site.admin_view(self._acting(act)), name=f'opendata_{name}_{act}')
                  for act in self.acts), *super().get_urls()]

    def _acting(self, act):
        def view(request, pk):
            return self.form_view(request, pk, act)
        return view

    def form_view(self, request, pk, act):
        if not request.user.is_superuser:
            raise PermissionDenied
        title, form_class, initial, do = self.acts[act]
        obj = get_object_or_404(self.get_queryset(request), pk=pk)
        form = form_class(request.POST or None, initial=initial(obj))
        back = reverse(f'admin:opendata_{self.model._meta.model_name}_change', args=[obj.pk])
        if request.method == 'POST' and form.is_valid():
            try:
                done = do(obj, request.user, form.cleaned_data)
            except Refused as exc:
                form.add_error(None, refusal(exc))
            else:
                self.log_change(request, obj, done)
                self.message_user(request, done)
                return redirect(back)
        return TemplateResponse(request, 'admin/opendata/decide.html', {
            **self.admin_site.each_context(request), 'opts': self.model._meta, 'title': title, 'subtitle': str(obj),
            'original': obj, 'facts': self.facts(obj), 'form': form, 'back': back})

    def links(self, obj):
        name = self.model._meta.model_name
        return format_html_join(' · ', '<a href="{}">{}</a>', (
            (reverse(f'admin:opendata_{name}_{act}', args=[obj.pk]), title) for act, (title, *_) in self.acts.items()))


class RequestState(admin.SimpleListFilter):
    """The list opens on the requests waiting for the staff; «every state» shows them all."""
    title, parameter_name = 'state', 'state'

    def lookups(self, request, model_admin):
        return [*Request.State.choices, ('all', 'every state')]

    def value(self):
        return super().value() or Request.State.WAITING

    def choices(self, changelist):
        yield from list(super().choices(changelist))[1:]        # Django's «All» would open on the waiting ones again

    def queryset(self, request, queryset):
        value = self.value()
        return queryset if value == 'all' else queryset.filter(state=value)


def history(events, **lookup) -> str:
    """A row's acts, oldest first (HISTORY at most), as a small table: when, who, what, its details; `lookup` filters
    «Events» to them."""
    rows = list(events.select_related('by').order_by('at', 'pk')[:HISTORY])
    return rows_table(('when', 'who', 'what', 'details'), [
        (f'{timezone.localtime(e.at):%Y-%m-%d %H:%M}', e.by.username if e.by_id else '—', e.get_act_display(),
         ', '.join(f'{k} {v}' for k, v in sorted(e.details.items())) or '—') for e in rows],
        changelist_link(Event, 'in the log', **lookup))


def _accept_initial(r: Request) -> dict:
    """What the accept form starts with: what was asked; a change request starts from its access as it is."""
    if r.change_of_id:
        a = r.change_of
        return {'api': r.wants_api, 'data': r.wants_data, 'size': r.wanted_size or a.size, 'minute': a.minute,
                'calls': a.calls, 'articles': a.articles, 'ends_on': a.ends_on}
    return {'api': r.wants_api, 'data': r.wants_data,
            'size': Access.Size.TRY if r.volume == Request.Volume.SMALL else Access.Size.APP,
            'ends_on': accesses.default_end()}


def _accept(r: Request, by, data: dict) -> str:
    made = asked.accept(r, by, api=data['api'], data=data['data'], size=data['size'], ends_on=data['ends_on'],
                        minute=data['minute'], calls=data['calls'], articles=data['articles'])
    return f'Accepted: {made.size}, until {made.ends_on:%Y-%m-%d}. A letter told the person.'


def _ask(r: Request, by, data: dict) -> str:
    asked.ask(r, by, data['line'])
    return 'Asked. A letter told the person; the request waits for their answer.'


def _decline(r: Request, by, data: dict) -> str:
    asked.decline(r, by, data['reason'])
    return f'Declined ({r.get_reason_display()}). A letter told the person.'


@admin.register(Request)
class RequestAdmin(Decisions, ReadOnly):
    list_display = ('created_at', 'name', 'kind', 'account', 'asks', 'volume', 'commercial', 'state', 'days_waiting')
    list_select_related = ('user',)
    list_filter = (RequestState, 'kind', 'volume', 'commercial')
    search_fields = ('name', 'user__username', 'user__display_name', 'user__email')
    search_help_text = 'Part of the name given, or of the account\'s username, display name or address.'
    readonly_fields = ('account', 'account_age', 'address', 'wants', 'changes', 'decide', 'who_decides', 'earlier',
                       'its_access', 'its_history')
    acts = {
        'accept': ('Accept…', AcceptForm, lambda r: _accept_initial(r), _accept),
        'ask': ('Ask for more…', AskForm, lambda r: {'line': r.asked}, _ask),
        'decline': ('Decline…', DeclineForm, lambda r: {}, _decline),
    }

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'decided_by', 'access', 'change_of')

    def facts(self, obj):
        """What the decision is about, above its form."""
        return (f'{obj.name} ({obj.get_kind_display().lower()}, account {obj.user.username}): {obj.purpose} '
                f'Asks for {self.asks(obj)}; volume {obj.get_volume_display().lower()}; '
                f'{"commercial" if obj.commercial else "not commercial"}.'
                + (f' Asked: {obj.asked} Answered: {obj.answer or "nothing yet"}' if obj.asked else ''))

    def get_ordering(self, request):
        """The queue the longest-waiting first (since it was sent, or since its account answered what was asked); a
        list of every state, or of decided ones, newest first."""
        return ('waiting_since', 'pk') if request.GET.get('state', 'waiting') in Request.OPEN else ('-created_at', '-pk')

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {'subtitle': ' '.join(asked.lines(asked.counted())),
                                                 **(extra_context or {})})

    def get_fieldsets(self, request, obj=None):
        may = (obj is not None and request.user.is_superuser and obj.state in Request.OPEN
               and obj.user_id != request.user.pk)
        decision = ('state', 'reason', 'decided_by', 'decided_at', 'created_at',
                    'decide' if may else 'who_decides')
        return [
            ('Who asks', {'fields': ('name', 'kind', 'account', 'account_age', 'address')}),
            ('What for', {'fields': ('purpose', 'wants', 'changes', 'wanted_size', 'runs_at', 'volume', 'commercial',
                                     'terms')}),
            ('What was asked of them', {'fields': ('asked', 'answer')}),
            ('The decision', {'fields': decision}),
            ('Around it', {'fields': ('earlier', 'its_access', 'its_history')}),
        ]

    @admin.display(description='account', ordering='user__username')
    def account(self, obj):
        return admin_link(obj.user, obj.user.username)

    @admin.display(description='the account\'s age')
    def account_age(self, obj):
        return f'{(timezone.now() - obj.user.date_joined).days:,} days, since {obj.user.date_joined:%Y-%m-%d}'

    @admin.display(description='its address')
    def address(self, obj):
        proven = obj.user.email_proven_at
        return f'{obj.user.email}: proven on {proven:%Y-%m-%d}' if proven else f'{obj.user.email}: not proven'

    @admin.display(description='asks for')
    def asks(self, obj):
        return ' + '.join(w for w, on in (('API', obj.wants_api), ('database', obj.wants_data)) if on) or '—'

    @admin.display(description='asks for')
    def wants(self, obj):
        return self.asks(obj)

    @admin.display(description='waiting', ordering='waiting_since')
    def days_waiting(self, obj):
        return f'{(timezone.now() - obj.waiting_since).days} days' if obj.state in Request.OPEN else '—'

    @admin.display(description='decide')
    def decide(self, obj):
        return self.links(obj)

    @admin.display(description='decide')
    def who_decides(self, obj):
        return 'Decided.' if obj.state not in Request.OPEN else 'Only a superuser decides, never on their own request.'

    @admin.display(description='its earlier requests')
    def earlier(self, obj):
        rows = list(Request.objects.filter(user_id=obj.user_id).exclude(pk=obj.pk).order_by('-created_at')[:SHOWN])
        return rows_table(('sent', 'state', 'reason', 'decided'), [
            (admin_link(r, f'{r.created_at:%Y-%m-%d}'), r.get_state_display(), r.get_reason_display() or '—',
             f'{r.decided_at:%Y-%m-%d}' if r.decided_at else '—') for r in rows])

    @admin.display(description='changes')
    def changes(self, obj):
        """A request to change an access: that access."""
        a = obj.change_of
        return format_html('{} · {}, {}', admin_link(a, f'access {a.pk}'), a.get_size_display(),
                           self.asks(Request(wants_api=a.api, wants_data=a.data))) if a else '—'

    @admin.display(description='its history')
    def its_history(self, obj):
        return history(obj.events.all(), request=obj.pk)

    @admin.display(description='its access')
    def its_access(self, obj):
        try:
            a = obj.access
        except ObjectDoesNotExist:
            return '—'
        return format_html('{} · {}, until {}', admin_link(a, a.get_state_display()), a.get_size_display(),
                           f'{a.ends_on:%Y-%m-%d}')


class Ends(admin.SimpleListFilter):
    title, parameter_name = 'end date', 'ends'

    def lookups(self, request, model_admin):
        return [('soon', f'within {asked.WINDOW_DAYS} days'), ('passed', 'passed')]

    def queryset(self, request, queryset):
        today = timezone.localdate()
        if self.value() == 'soon':
            return queryset.filter(ends_on__gte=today, ends_on__lte=today + timedelta(days=asked.WINDOW_DAYS))
        if self.value() == 'passed':
            return queryset.filter(ends_on__lt=today)
        return queryset


def _end(a: Access, by, data: dict) -> str:
    accesses.end_by_staff(a, by, data['reason'])
    return f'Ended ({a.get_ended_reason_display()}). Its keys stopped; a letter told the holder.'


def _renew(a: Access, by, data: dict) -> str:
    accesses.renew(a, by, data['ends_on'])
    return f'Renewed until {a.ends_on:%Y-%m-%d}.'


@admin.register(Access)
class AccessAdmin(Decisions, ReadOnly):
    """Each access with its calls and articles of the last USE_DAYS days, read in the list's own query."""
    list_display = ('user', 'size', 'api', 'data', 'state', 'ends_on', 'calls_30', 'articles_30', 'created_at')
    list_select_related = ('user',)
    list_filter = ('state', Ends, 'size', 'api', 'data')
    search_fields = ('user__username', 'user__email', 'request__name')
    search_help_text = 'Part of the account\'s username or address, or of the name its request gave.'
    ordering = ('-state', 'ends_on')                    # live before ended, the nearest end first
    fieldsets = [
        ('Who holds it', {'fields': ('user', 'its_request', 'created_at')}),
        ('What it opens', {'fields': ('api', 'data', 'size', 'minute', 'calls', 'articles', 'its_limits')}),
        ('Its life', {'fields': ('state', 'ends_on', 'renewed_at', 'ended_at', 'ended_reason', 'ended_by', 'act')}),
        ('Its use', {'fields': ('use', 'its_keys', 'its_days')}),
        ('Its history', {'fields': ('its_history',)}),
    ]
    readonly_fields = ('its_request', 'its_limits', 'act', 'use', 'its_keys', 'its_days', 'its_history')
    acts = {
        'end': ('End access…', EndForm, lambda a: {}, _end),
        'renew': ('Renew…', RenewForm, lambda a: {'ends_on': accesses.default_end()}, _renew),
    }

    def get_queryset(self, request):
        since = timezone.localdate() - timedelta(days=USE_DAYS - 1)
        recent = Q(days__day__gte=since)
        return (super().get_queryset(request).select_related('user', 'request', 'ended_by')
                .annotate(calls_30=Sum('days__calls', filter=recent), articles_30=Sum('days__articles', filter=recent)))

    def changelist_view(self, request, extra_context=None):
        return super().changelist_view(request, {'subtitle': ' '.join(asked.lines(asked.counted())),
                                                 **(extra_context or {})})

    def facts(self, obj):
        """What the decision is about, above its form."""
        return (f'{obj.user.username}: {self.its_limits(obj)}, until {obj.ends_on:%Y-%m-%d}; '
                f'{self.use(obj)} in the last {USE_DAYS} days.')

    @admin.display(description=f'calls, {USE_DAYS} days', ordering='calls_30')
    def calls_30(self, obj):
        return f'{obj.calls_30 or 0:,}'

    @admin.display(description=f'articles, {USE_DAYS} days', ordering='articles_30')
    def articles_30(self, obj):
        return f'{obj.articles_30 or 0:,}'

    @admin.display(description='its request')
    def its_request(self, obj):
        return admin_link(obj.request, obj.request.name or f'request {obj.request_id}')

    @admin.display(description='its limits')
    def its_limits(self, obj):
        n = obj.limits()
        return f'{n["minute"]:,} a minute, {n["calls"]:,} calls and {n["articles"]:,} articles a day'

    @admin.display(description='end or renew')
    def act(self, obj):
        return self.links(obj) if obj.state == Access.State.LIVE else '—'

    @admin.display(description=f'the last {USE_DAYS} days')
    def use(self, obj):
        return f'{obj.calls_30 or 0:,} calls, {obj.articles_30 or 0:,} articles'

    @admin.display(description='its keys')
    def its_keys(self, obj):
        rows = list(obj.keys.order_by('-created_at')[:SHOWN])
        return rows_table(('name', 'prefix', 'made', 'last used', 'ended'), [
            (k.name or '—', f'{k.prefix}…', f'{k.created_at:%Y-%m-%d}',
             f'{k.last_used_on:%Y-%m-%d}' if k.last_used_on else '—', f'{k.ended_at:%Y-%m-%d}' if k.ended_at else '—')
            for k in rows], changelist_link(ApiKey, 'every key', access=obj.pk))

    @admin.display(description='its history')
    def its_history(self, obj):
        return history(obj.events.all(), access=obj.pk)

    @admin.display(description='its days')
    def its_days(self, obj):
        rows = list(obj.days.order_by('-day')[:USE_DAYS])
        return rows_table(('day', 'calls', 'articles', 'by door'), [
            (f'{d.day:%Y-%m-%d}', f'{d.calls:,}', f'{d.articles:,}',
             ', '.join(f'{door} {n:,}' for door, n in sorted(d.doors.items())) or '—') for d in rows],
            changelist_link(Download, 'its downloads', access=obj.pk))


@admin.register(ApiKey)
class ApiKeyAdmin(ReadOnly):
    list_display = ('prefix', 'name', 'access', 'created_at', 'last_used_on', 'ended_at')
    list_select_related = ('access',)
    search_fields = ('=prefix', 'name')
    search_help_text = 'Its first characters, or what its holder calls it.'
    ordering = ('-created_at',)
    fields = ('access', 'name', 'prefix', 'created_at', 'last_used_on', 'ended_at')


@admin.register(AccessDay)
class AccessDayAdmin(ReadOnly):
    """What an access used in a day: counts only."""
    list_display = ('day', 'access', 'calls', 'articles', 'doors')
    list_select_related = ('access',)
    list_filter = (('day', admin.DateFieldListFilter),)
    search_fields = ('access__user__username',)
    search_help_text = 'Part of the holder\'s username.'
    ordering = ('-day', '-pk')


@admin.register(Download)
class DownloadAdmin(ReadOnly):
    """A file of an edition given to an access."""
    list_display = ('at', 'access', 'edition', 'file', 'by')
    list_select_related = ('access',)
    list_filter = ('by',)
    search_fields = ('access__user__username', 'file', '=edition')
    search_help_text = 'Part of the holder\'s username or of the file\'s name, or the edition\'s whole date.'
    ordering = ('-at',)


@admin.register(Event)
class EventAdmin(ReadOnly):
    """Every act on a request or an access, whichever door it came by: the services write it, nobody types it."""
    list_display = ('at', 'by', 'act', 'request', 'access', 'what')
    list_select_related = ('by', 'request', 'access')
    list_filter = ('act', ('at', admin.DateFieldListFilter))
    search_fields = ('by__username', 'request__name', 'request__user__username', 'access__user__username')
    search_help_text = 'Part of who acted, of the name a request gave, or of the account it is about.'
    ordering = ('-at', '-pk')
    fields = ('at', 'by', 'act', 'request', 'access', 'details')

    @admin.display(description='details')
    def what(self, obj):
        return ', '.join(f'{k} {v}' for k, v in sorted(obj.details.items())) or '—'
