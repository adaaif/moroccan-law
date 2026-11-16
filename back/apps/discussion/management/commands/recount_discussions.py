"""Every discussion's counts again, from what a reader may see (deploy runs it: SHOW_DEMO_PEOPLE decides whether the
development's demo people count). Its posts first: those with comments and no answer yet each time (the few waiting,
and the first time, every post: the answers' columns of 30 Oct 2026); --posts, every post (after SHOW_DEMO_PEOPLE
changes)."""
from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.corpus.services import generation
from apps.discussion.services import counters


class Command(BaseCommand):
    help = 'Count every discussion again (after SHOW_DEMO_PEOPLE changes).'

    def add_arguments(self, parser):
        parser.add_argument('--posts', action='store_true', help='every post too, not only those waiting')

    def handle(self, *args, posts, **options):
        p = counters.every_post(None if posts else Q(reply_count__gt=0, answered_at=None))
        n = counters.every_discussion()
        generation.bump('talk')     # a bulk update sends no signal
        self.stdout.write(f'{p} posts and {n} discussions counted again')
