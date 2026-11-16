from django.apps import AppConfig


class ExplainConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.explain'

    def ready(self):
        # The explanations kept for readers (S14 of the performance audit) are not served again once one changes.
        from django.db.models.signals import post_delete, post_save

        from apps.explain.models import Explanation, Helpful, Revision

        for model in (Explanation, Revision, Helpful):
            post_save.connect(_explain_changed, sender=model, dispatch_uid=f'explain-save-{model.__name__}')
            post_delete.connect(_explain_changed, sender=model, dispatch_uid=f'explain-delete-{model.__name__}')


def _explain_changed(sender, instance=None, **kwargs):
    from apps.corpus.services import generation
    # A word's meaning is in the law's own answers too (HM35: a word is dotted once its meaning is checked).
    word = sender.__name__ == 'Explanation' and str(getattr(instance, 'path', '')).startswith('/words/')
    generation.bump('explain', *(['corpus'] if word else []))
