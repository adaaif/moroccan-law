"""Switch off the accounts the code made for itself (models.RESERVED_PREFIXES and RESERVED_DOMAINS: the development's
demo people, the end-to-end tests', the load test's), wherever a copy of a development database brought them: each
password made unusable, the account switched off, its staff rights, groups and permissions taken away, its reviewer
appointments ended, its sessions and assistants' connections ended. A deleted account's emptied row is already all of
that and is left alone.

Without --write it only lists what it would change. `check --deploy` refuses a server while any of them is active."""
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User, reserved_accounts


class Command(BaseCommand):
    help = 'List, then with --write switch off, the accounts the code made for itself (demo-, load-, deleted-).'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='Change the accounts; without it, only list them.')

    def handle(self, *args, write=False, **options):
        from apps.discussion.models import Reviewer

        rows = list(User.objects.filter(reserved_accounts()).order_by('pk')
                    .only('id', 'username', 'password', 'is_active', 'is_staff', 'is_superuser'))
        ids = [u.pk for u in rows]
        reviewing = set(Reviewer.objects.filter(user_id__in=ids, ended_at=None).values_list('user_id', flat=True))
        rights = (set(User.groups.through.objects.filter(user_id__in=ids).values_list('user_id', flat=True))
                  | set(User.user_permissions.through.objects.filter(user_id__in=ids).values_list('user_id', flat=True)))

        def what(u) -> list[str]:
            return [word for word, on in (('active', u.is_active), ('password', u.has_usable_password()),
                                          ('staff', u.is_staff), ('superuser', u.is_superuser),
                                          ('reviewer', u.pk in reviewing), ('rights', u.pk in rights)) if on]

        found = [(u, what(u)) for u in rows]
        found = [(u, words) for u, words in found if words]
        for u, words in found:
            self.stdout.write(f'  {u.pk:>7}  {u.username:32}  {", ".join(words)}')
        self.stdout.write(f'{len(found)} of {len(rows)} reserved accounts can still do something.')
        if not found:
            return
        if not write:
            self.stdout.write('Nothing changed: run again with --write.')
            return

        from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken, OutstandingToken

        from apps.oauth.models import Grant

        now = timezone.now()
        users = [u for u, _ in found]
        ids = [u.pk for u in users]
        for u in users:
            u.password, u.is_active, u.is_staff, u.is_superuser = make_password(None), False, False, False
        with transaction.atomic():
            User.objects.bulk_update(users, ['password', 'is_active', 'is_staff', 'is_superuser'], batch_size=500)
            User.groups.through.objects.filter(user_id__in=ids).delete()
            User.user_permissions.through.objects.filter(user_id__in=ids).delete()
            ended = Reviewer.objects.filter(user_id__in=ids, ended_at=None).update(ended_at=now)
            live = OutstandingToken.objects.filter(user_id__in=ids, expires_at__gt=now, blacklistedtoken__isnull=True)
            BlacklistedToken.objects.bulk_create([BlacklistedToken(token_id=pk) for pk in live.values_list('pk', flat=True)],
                                                 ignore_conflicts=True)
            Grant.objects.filter(user_id__in=ids, revoked_at=None).update(revoked_at=now)
        self.stdout.write(f'Switched off {len(users)} accounts; {ended} reviewer appointments ended.')
