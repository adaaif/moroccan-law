"""recount_discussions (deploy runs it): the posts waiting for an answer counted again, or every post with --posts,
then every discussion from its posts; the answers kept for the conversation are not served again."""
import pytest
from django.core.management import call_command

from apps.corpus.services import generation
from apps.discussion.models import Contribution, Discussion
from apps.discussion.tests.conftest import make_user

pytestmark = pytest.mark.django_db


def test_the_counts_are_made_again_from_what_a_reader_may_see(capsys, settings):
    # The answers kept, as Redis keeps them on the site (the suite's own keep nothing).
    settings.CACHES = {**settings.CACHES, 'answers': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
                                                      'LOCATION': 'recount'}}
    asker, other = make_user('asker'), make_user('other')
    room = Discussion.objects.create(path='/talk/work', text_path='/talk/work')
    # Counts as a bulk write leaves them: the first post says one comment and no answer, the second none.
    waiting = Contribution.objects.create(discussion=room, author=asker, kind='question', title='سؤال', body='؟',
                                          reply_count=1)
    quiet = Contribution.objects.create(discussion=room, author=asker, kind='post', title='منشور', body='.')
    first = Contribution.objects.create(discussion=room, parent=waiting, author=other, kind='comment', body='جواب')
    last = Contribution.objects.create(discussion=room, parent=waiting, reply_to=first, author=asker, kind='comment',
                                       body='شكرا')
    Contribution.objects.create(discussion=room, parent=quiet, author=other, kind='comment', body='تعليق')
    Contribution.objects.create(discussion=room, parent=quiet, author=other, kind='comment', body='محيد',
                                removed_at=last.created_at)
    before = generation.current('talk')

    call_command('recount_discussions')
    waiting.refresh_from_db(), quiet.refresh_from_db(), room.refresh_from_db()
    assert (waiting.reply_count, waiting.conversation_count, waiting.people_count) == (2, 1, 2)
    assert (waiting.answered_at, waiting.answer_id, waiting.active_at) == (first.created_at, first.pk, last.created_at)
    assert quiet.reply_count == 0                                   # no comment counted yet: not waiting
    assert (room.count, room.open_questions, room.last_at) == (2 + 2, 0, last.created_at)
    assert capsys.readouterr().out == '1 posts and 1 discussions counted again\n'
    assert generation.current('talk') != before

    call_command('recount_discussions', posts=True)
    quiet.refresh_from_db(), room.refresh_from_db()
    assert (quiet.reply_count, room.count) == (1, 2 + 3)
    assert capsys.readouterr().out == '2 posts and 1 discussions counted again\n'
