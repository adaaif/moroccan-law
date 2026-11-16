from django.apps import AppConfig


class DiscussionConfig(AppConfig):
    name = 'apps.discussion'
    default_auto_field = 'django.db.models.BigAutoField'

    def ready(self):
        # A discussion's answers kept for readers (S14 of the performance audit) are not served again once anything
        # they show changes: a contribution, a vote, a count, a karma, a name, a voice or a picture.
        from django.contrib.auth import get_user_model
        from django.db.models.signals import post_delete, post_save

        from apps.discussion.models import Contribution, Discussion, Point, Useful
        from apps.media.models import Clip, Picture

        for model in (Contribution, Discussion, Useful, Point, Clip, Picture, get_user_model()):
            post_save.connect(_talk_changed, sender=model, dispatch_uid=f'talk-save-{model.__name__}')
            post_delete.connect(_talk_changed, sender=model, dispatch_uid=f'talk-delete-{model.__name__}')


def _talk_changed(sender, update_fields=None, **kwargs):
    if update_fields is not None and set(update_fields) <= {'last_login'}:
        return      # signing in changes nothing a reader sees
    from apps.corpus.services import generation
    generation.bump('talk')
