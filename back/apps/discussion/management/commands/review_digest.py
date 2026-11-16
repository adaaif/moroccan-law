"""A letter to each reviewer when contributions have waited more than 12 hours in their area (M10), one a day at
most. Run it every hour from cron; it remembers what it sent as a notice on the reviewer's account."""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.services import mail
from apps.discussion.models import Notice, Reviewer
from apps.discussion.services import review

LATE = timedelta(hours=12)


class Command(BaseCommand):
    help = 'Tell reviewers what has waited over 12 hours, once a day at most.'

    def handle(self, *args, **options):
        # Who reviews where, who was told today, and what waits everywhere, each read once: a reviewer's tabs are the
        # rows of their area (`review.queue`'s), counted here without loading their cards.
        now = timezone.now()
        areas = {r.user_id: r.text_paths for r in Reviewer.objects.filter(ended_at=None)}
        people = set(areas) | set(User.objects.filter(is_staff=True, is_active=True).values_list('pk', flat=True))
        told = set(Notice.objects.filter(user_id__in=people, kind=Notice.Kind.DIGEST,
                                         created_at__gte=now - timedelta(days=1)).values_list('user_id', flat=True))
        rows = review.waiting_everywhere()
        letters = []
        for user in User.objects.filter(pk__in=people - told, deleted_at=None, is_active=True).order_by('pk'):
            paths = None if user.is_staff else areas[user.pk]
            mine = [row for row in rows if not paths or row[1] in paths]
            if any((held_at or post_review_at or now) <= now - LATE for _, _, held_at, post_review_at in mine):
                letters.append((user, len(mine)))
        Notice.objects.bulk_create([Notice(user=user, kind=Notice.Kind.DIGEST, detail=str(n), emailed_at=now)
                                    for user, n in letters])
        for user, n in letters:
            mail.send(user, 'digest', count=n, link=f'{settings.SITE_URL}/review')
        self.stdout.write(f'letters sent: {len(letters)}')
