"""A person's data, to take away or to delete (law 09-08: access and erasure).

Deleting an account keeps the text of its contributions, signed «حساب محذوف»: answers hang on them and readers
learned from them. Its voices and pictures are erased; its votes go with the points they gave; its follows (of a post,
a topic, a law), notices and codes go; the check's verdicts lose its name; its access to the data ends and its requests
for one lose what was typed in them; and the account row is emptied so nobody can sign in with it or find its name
again. A fixed number of queries, whatever the account wrote."""
from django.contrib.auth.hashers import make_password
from django.db import transaction
from django.db.models import Count, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.accounts.models import EmailCode
from apps.accounts.services.refusals import Refused
from apps.discussion.models import Check, Contribution, Follow, Notice, Point, Report, Useful
from apps.discussion.services import counters, points
from apps.media.services import files
from apps.opendata.services import access as accesses


def export(user) -> dict:
    from apps.explain.models import Helpful, Report as ExplainReport, Revision as ExplainRevision
    from apps.follows.models import Follow as Followed

    return {
        'account': {'username': user.username, 'email': user.email, 'display_name': user.display_name,
                    'preferred_language': user.preferred_language, 'address_form': user.address_form,
                    'joined': user.date_joined, 'email_proven_at': user.email_proven_at,
                    'email_notices': user.email_notices, 'karma': points.total(user),
                    'agreed_to_the_check_at': user.check_consent_at},
        'contributions': [
            {'id': c.pk, 'path': c.discussion.path, 'kind': c.kind, 'title': c.title, 'body': c.body,
             'about': c.about, 'quote': c.quote,
             'anonymous': c.anonymous, 'created_at': c.created_at, 'edited_at': c.edited_at,
             'voice_seconds': c.clip.duration_ms / 1000 if c.clip_id else None,
             'pictures': c.n_pictures, 'removed': bool(c.removed_at), 'deleted': bool(c.deleted_at)}
            for c in Contribution.objects.filter(author=user).select_related('discussion', 'clip')
            .annotate(n_pictures=Count('pictures')).order_by('created_at')],
        'useful_given': Useful.objects.filter(user=user).count(),
        # What the model's check answered on what this account wrote: codes only, never the words.
        'checks': [{'outcome': c.outcome, 'rule': c.rule, 'created_at': c.created_at}
                   for c in Check.objects.filter(user=user).order_by('created_at')],
        'reports_filed': [{'reason': r.reason, 'status': r.status, 'created_at': r.created_at}
                          for r in Report.objects.filter(reporter=user)],
        'following_discussions': list(Follow.objects.filter(user=user).values_list('path', flat=True)),
        'following_laws_and_topics': list(Followed.objects.filter(user=user).values_list('path', flat=True)),
        'explanations_written': [{'path': r.explanation.path, 'register': r.explanation.register,
                                  'headline': r.headline, 'body': r.body, 'created_at': r.created_at}
                                 for r in ExplainRevision.objects.filter(author=user).select_related('explanation')],
        'explanations_found_helpful': Helpful.objects.filter(user=user).count(),
        'explanation_reports_filed': [{'reason': r.reason, 'status': r.status, 'created_at': r.created_at}
                                      for r in ExplainReport.objects.filter(reporter=user)],
        # Access on request: its requests, accesses, day counts and downloads, and the acts on them (not who decided);
        # never a key.
        **accesses.export(user),
    }


def _recount(model, votes, related: str, field: str, ids) -> None:
    """A vote count (`useful_count`, `helpful_count`) counted again for these rows, in one update."""
    counted = (votes.objects.filter(**{related: OuterRef('pk')}, counted=True).values(related)
               .annotate(n=Count('id')).values('n')[:1])
    model.objects.filter(pk__in=ids).update(**{field: Coalesce(Subquery(counted, output_field=IntegerField()), Value(0))})


def delete_account(user, password: str) -> None:
    from apps.explain.models import Explanation, Helpful
    from apps.follows.models import Follow as Followed

    if not user.check_password(password or ''):
        raise Refused('password', 'invalid')
    with transaction.atomic():
        mine = list(Contribution.objects.filter(author=user).select_related('clip').prefetch_related('pictures'))
        files.erase([f for c in mine for f in (c.clip, *c.pictures.all())])
        votes = list(Useful.objects.filter(user=user).values_list('pk', 'contribution_id'))
        Point.objects.filter(source=Point.Source.USEFUL, ref__in=[str(pk) for pk, _ in votes]).update(
            voided_at=timezone.now())
        Useful.objects.filter(user=user).delete()
        _recount(Contribution, Useful, 'contribution', 'useful_count', {c for _, c in votes})
        helped = list(Helpful.objects.filter(user=user).values_list('explanation_id', flat=True))
        Helpful.objects.filter(user=user).delete()
        _recount(Explanation, Helpful, 'explanation', 'helpful_count', set(helped))
        Follow.objects.filter(user=user).delete()
        Followed.objects.filter(user=user).delete()
        Notice.objects.filter(user=user).delete()
        EmailCode.objects.filter(user=user).delete()
        from apps.oauth.services.tokens import end_all
        end_all(user)
        accesses.leave(user)
        Check.objects.filter(user=user).update(user=None)
        user.username = f'deleted-{user.pk}'
        user.email = f'deleted-{user.pk}@deleted.invalid'
        user.display_name = ''
        user.password = make_password(None)
        user.is_active = False
        user.email_notices = False
        user.check_consent_at = None
        user.google_sub = None
        user.deleted_at = timezone.now()
        user.save()
        if mine:
            counters.every_discussion()
