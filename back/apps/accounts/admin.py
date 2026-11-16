"""Accounts in the admin: what a moderator needs about a person (their name, address, standing in the discussion and
the lists of what they wrote and what was done about it), never their password or a token. Sign-in codes and tokens
are read here, never added or changed: the sign-in services write them."""
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin, UserAdmin as DjangoUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import Group
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, format_html_join
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

from apps.accounts.models import EmailCode, User
from apps.discussion.models import Action, Ban, Contribution, Notice, Report, Reviewer, Trust
from apps.oauth.models import Grant
from config.admin import ReadOnly, changelist_link


class AccountCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')


class AccountChangeForm(UserChangeForm):
    password = None                     # the page says whether one is set, never its hash (`password_state`)

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    form = AccountChangeForm
    add_form = AccountCreationForm
    fieldsets = (
        # A proven address writes in the discussion; staff set it for an account they hand out (3 Nov 2026).
        ('The account', {'fields': ('username', 'password_state', 'email', 'email_proven_at', 'display_name',
                                    'preferred_language', 'google')}),
        ('In the discussion', {'fields': ('standing', 'their_rows')}),
        ('Their choices', {'classes': ('collapse',), 'fields': ('address_form', 'email_notices', 'check_consent_at')}),
        ('Rights', {'classes': ('collapse',), 'fields': ('is_active', 'is_staff', 'is_superuser', 'groups',
                                                         'user_permissions')}),
        ('Dates', {'fields': ('date_joined', 'last_login', 'deleted_at')}),
    )
    add_fieldsets = (
        (None, {'classes': ('wide',),
                'fields': ('username', 'email', 'password1', 'password2')}),
    )
    readonly_fields = ('password_state', 'google', 'standing', 'their_rows', 'address_form', 'email_notices',
                       'check_consent_at', 'date_joined', 'last_login', 'deleted_at')
    list_display = ('username', 'email', 'proven', 'display_name', 'preferred_language', 'is_staff', 'is_active',
                    'date_joined', 'last_login')
    list_filter = ('is_staff', 'is_superuser', 'is_active', ('email_proven_at', admin.EmptyFieldListFilter),
                   ('deleted_at', admin.EmptyFieldListFilter), 'preferred_language')
    search_fields = ('username', 'email', 'display_name')
    search_help_text = 'Part of the username, the address or the name shown.'
    ordering = ('-date_joined',)
    save_on_top = True

    def save_model(self, request, obj, form, change):
        """An address changed here is changed as the account's own page changes it (services.accounts.change_email): the
        Google binding goes with the old address, the assistants' connections end and the codes sent to the old address
        die. A binding left in place would still open the account for whoever made it under the old address."""
        moved = change and 'email' in form.changed_data
        if moved:
            obj.google_sub = None
        super().save_model(request, obj, form, change)
        if moved:
            from apps.accounts.models import EmailCode
            from apps.oauth.services.tokens import end_all
            now = timezone.now()
            EmailCode.objects.filter(user=obj, used_at=None, expires_at__gt=now).update(expires_at=now)
            end_all(obj)

    @admin.display(description='address proven', boolean=True, ordering='email_proven_at')
    def proven(self, obj):
        return obj.email_proven_at is not None

    @admin.display(description='password')
    def password_state(self, obj):
        """Set or not, never the hash; Django's own form sets a new one."""
        state = 'set' if obj.has_usable_password() else 'none (signs in through Google, or was voided)'
        url = reverse('admin:auth_user_password_change', args=[obj.pk])
        return format_html('{} · <a href="{}">set a new password</a>', state, url)

    @admin.display(description='Google', boolean=True)
    def google(self, obj):
        return bool(obj.google_sub)

    @admin.display(description='standing')
    def standing(self, obj):
        now = timezone.now()
        paused = Ban.objects.filter(user=obj, ended_at=None).exclude(until__lt=now).order_by('-started_at').first()
        lines = [
            ('paused', f'until {paused.until:%Y-%m-%d %H:%M}' if paused and paused.until else 'for good' if paused
             else 'no'),
            ('a reviewer', 'yes' if Reviewer.objects.filter(user=obj, ended_at=None).exists() else 'no'),
            ('trusted by a reviewer', 'yes' if Trust.objects.filter(user=obj, ended_at=None).exists() else 'no'),
        ]
        return format_html_join(' · ', '{}: {}', lines)

    @admin.display(description='their rows')
    def their_rows(self, obj):
        links = [
            changelist_link(Contribution, 'posts and comments', author=obj.pk),
            changelist_link(Report, 'reports they filed', reporter=obj.pk),
            changelist_link(Action, 'the ledger about them', target=obj.pk),
            changelist_link(Ban, 'pauses', user=obj.pk),
            changelist_link(Notice, 'what they were told', user=obj.pk),
            changelist_link(Grant, 'assistants connected', user=obj.pk),
            changelist_link(OutstandingToken, 'devices signed in', user=obj.pk),
        ]
        return format_html_join(' · ', '{}', ((link,) for link in links))


admin.site.unregister(Group)


@admin.register(Group)
class GroupAdmin(DjangoGroupAdmin):
    search_help_text = 'Part of the group\'s name.'


@admin.register(EmailCode)
class EmailCodeAdmin(ReadOnly):
    """The codes sent to prove an address: when, to whom and whether used. The code and the address are kept only as
    digests, and neither is shown."""
    list_display = ('created_at', 'user', 'purpose', 'tries', 'expires_at', 'used_at')
    list_select_related = ('user',)
    list_filter = ('purpose', ('used_at', admin.EmptyFieldListFilter))
    search_fields = ('user__username', 'user__email')
    search_help_text = 'Part of the account\'s username or address.'
    fields = ('user', 'purpose', 'tries', 'created_at', 'expires_at', 'used_at')
    ordering = ('-pk',)


class TokenState(admin.SimpleListFilter):
    title, parameter_name = 'state', 'state'

    def lookups(self, request, model_admin):
        return [('live', 'signed in'), ('ended', 'signed out'), ('expired', 'expired')]

    def queryset(self, request, queryset):
        now = timezone.now()
        if self.value() == 'live':
            return queryset.filter(blacklistedtoken__isnull=True, expires_at__gt=now)
        if self.value() == 'ended':
            return queryset.filter(blacklistedtoken__isnull=False)
        if self.value() == 'expired':
            return queryset.filter(blacklistedtoken__isnull=True, expires_at__lte=now)
        return queryset


admin.site.unregister(OutstandingToken)
admin.site.unregister(BlacklistedToken)


@admin.register(OutstandingToken)
class OutstandingTokenAdmin(ReadOnly):
    """A device's sign-in (its refresh token), never the token itself: who, since when, until when, and whether it was
    signed out."""
    list_display = ('created_at', 'user', 'expires_at', 'signed_out')
    list_select_related = ('user', 'blacklistedtoken')
    list_filter = (TokenState,)
    search_fields = ('user__username', '=jti')
    search_help_text = 'Part of the account\'s username, or a token\'s whole id (jti).'
    fields = ('user', 'jti', 'created_at', 'expires_at', 'signed_out')
    ordering = ('-pk',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'blacklistedtoken')

    @admin.display(description='signed out', boolean=True)
    def signed_out(self, obj):
        return hasattr(obj, 'blacklistedtoken')


@admin.register(BlacklistedToken)
class BlacklistedTokenAdmin(ReadOnly):
    list_display = ('blacklisted_at', 'token__user', 'token__created_at', 'token__expires_at')
    list_select_related = ('token__user',)
    search_fields = ('token__user__username', '=token__jti')
    search_help_text = 'Part of the account\'s username, or a token\'s whole id (jti).'
    fields = ('token', 'blacklisted_at')
    ordering = ('-pk',)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('token__user')
