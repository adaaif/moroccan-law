"""What `manage.py check --deploy` refuses about accounts and their letters."""
from email.utils import parseaddr

from django.conf import settings
from django.core.checks import Error, Tags, register
from django.db import DatabaseError


@register(Tags.security, deploy=True)
def reserved_accounts_switched_off(app_configs, **kwargs):
    """An account the code made for itself (the development's demo people, the load test's, a deleted account's row)
    signs nobody in where the public reads: one that is active means a development database or seed reached the server.
    `retire_reserved_accounts --write` switches them off."""
    from apps.accounts.models import User, reserved_accounts

    try:
        active = User.objects.filter(reserved_accounts(), is_active=True).count()
    except DatabaseError:       # no database yet, or not migrated: nothing to judge
        return []
    if not active:
        return []
    return [Error(f'{active} active account(s) carry a name or an address the code keeps for its own accounts.',
                  hint='Run `manage.py retire_reserved_accounts` to see them, then again with --write.',
                  id='accounts.E001')]


@register(Tags.security, deploy=True)
def letters_have_a_sender(app_configs, **kwargs):
    """Letters leave from DEFAULT_FROM_EMAIL's address. Its default, at localhost, is no address anyone can answer or a
    mail provider will accept: a server sets its own, and a deploy that forgot stops here."""
    address = parseaddr(settings.DEFAULT_FROM_EMAIL)[1]
    domain = address.rpartition('@')[2].lower() if '@' in address else ''
    if domain and domain != 'localhost':
        return []
    return [Error(f'DEFAULT_FROM_EMAIL is {settings.DEFAULT_FROM_EMAIL!r}: letters would leave from no real address.',
                  hint="Set it in the server's .env to the site's sender, such as «example <noreply@example.org>» "
                       '(back/.env.example).',
                  id='accounts.E002')]
