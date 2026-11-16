"""Count a blog post's figures again from the database: `manage.py blog_figures from-no-1`. Only reads; the
figures land in the post's folder, to be read, checked and committed with the post."""
from django.core.management.base import BaseCommand, CommandError

from apps.blog.services import posts


class Command(BaseCommand):
    help = "Count a blog post's figures from the database into its folder."

    def add_arguments(self, parser):
        parser.add_argument('slug', choices=sorted(posts.COUNTS))

    def handle(self, *args, slug, **options):
        try:
            path = posts.write_figures(slug)
        except KeyError as e:
            raise CommandError(f'No post {e} to count.') from e
        totals = posts.figures(slug).get('totals', {})
        self.stdout.write(f'{path}: ' + ', '.join(f'{k} {v:,}' for k, v in totals.items()))
