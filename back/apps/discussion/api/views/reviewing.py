"""The moderators' desk: the queue's tabs and each card as a reviewer sees it, their acts on a contribution, a
discussion's lock, pauses and appeals decided, the ledger, a covered picture, and staff appointing and ending
moderators."""
from rest_framework import status
from rest_framework.response import Response

from apps.accounts.api.errors import RefusingView, require_types
from apps.accounts.services.refusals import Refused
from apps.discussion.models import Contribution, Rule
from apps.discussion.services import gates, points, review, thread
from apps.media.models import State
from apps.media.services import links


def _review_card(user, c: Contribution, ctx, desk: review.Desk) -> dict:
    """A contribution as a reviewer sees it: whatever its state, its files by signed link, what held it, its reports
    counted by reason (never who), the author's record, its earlier wordings. No name when anonymous."""
    clip = c.clip if c.clip and c.clip.state != State.ERASED else None
    card = thread.card(c, ctx)
    if clip:
        card['voice'] = {**links.clip(clip), 'id': str(clip.pk), 'duration_ms': clip.duration_ms, 'peaks': clip.peaks}
    open_reports = review.open_reports(c)
    reasons: dict[str, int] = {}
    for r in open_reports:
        reasons[r.reason] = reasons.get(r.reason, 0) + 1
    from apps.discussion.services import places

    if places.is_place(c.discussion.path):
        label = thread._labels([c.discussion.path])[c.discussion.path]
    else:
        label = thread.label_of(desk.anchors.get(c.discussion.path))
    return {**card, **thread.where(c, user, reviewing=True), 'label': label, 'held_reasons': c.held_reasons,
            'held_spans': c.held_spans, 'deleted': bool(c.deleted_at), 'removed': bool(c.removed_at),
            'hidden': bool(c.hidden_at), 'rule': c.removed_rule or None,
            'waiting_since': c.held_at or (open_reports[0].created_at if open_reports else None),
            'reports': {'reasons': reasons, 'details': [r.details for r in open_reports if r.details],
                        'moments': [r.moment_ms for r in open_reports if r.moment_ms is not None],
                        'takedowns': [{'details': r.details, 'contact': r.contact} for r in open_reports
                                      if r.takedown]},
            'record': review.record(user, c, desk), 'revisions': [r.body for r in c.revisions.all()],
            'context': review.context(c, desk), 'author': card['author'] if not c.anonymous else None}


class ReviewQueueView(RefusingView):
    """GET ?tab=held|reported|appeals|pauses."""
    throttle_scope = 'account'

    def get(self, request):
        user = request.user
        if not review.is_reviewer(user):
            raise Refused('review', 'not_reviewer', 403)
        tab = request.query_params.get('tab', 'held')
        rows = review.queue(user, tab, limit=50)
        counts = review.counts(user)
        if tab in ('held', 'reported'):
            ctx, desk = thread.Context(user, rows), review.Desk(rows, user)
            items = [_review_card(user, c, ctx, desk) for c in rows]
        elif tab == 'appeals':
            vias = [a.contribution or a.ban.via for a in rows]
            ctx, desk = thread.Context(user, [v for v in vias if v]), review.Desk(vias, user)
            items = [{'id': a.pk, 'text': a.text, 'created_at': a.created_at,
                      'on': 'contribution' if a.contribution_id else 'pause',
                      'pause': {'until': a.ban.until, 'rule': a.ban.rule} if a.ban_id else None,
                      'contribution': _review_card(user, via, ctx, desk) if via else None}
                     for a, via in zip(rows, vias)]
        else:
            items = [{'id': b.pk, 'until': b.until, 'rule': b.rule, 'note': b.note, 'started_at': b.started_at,
                      'waiting_second_eye': bool(b.permanent_asked_by_id),
                      'asked_by_me': b.permanent_asked_by_id == user.pk,
                      'who': None if (b.via and b.via.anonymous) else b.user.shown_name,
                      'path': b.via.discussion.path if b.via else None} for b in rows]
        return Response({'tab': tab, 'counts': counts, 'items': items, 'rules': Rule.values, 'staff': user.is_staff,
                         'median_hours': gates.review_hours()})


class ReviewActView(RefusingView):
    """POST {act: approve|keep|remove|restore|pause|reveal|redact|send_back|trust|untrust|duplicate, rule, note, days}."""
    throttle_scope = 'account'

    def post(self, request, pk):
        user, d = request.user, request.data
        require_types(d, words=('act', 'note', 'rule'), ids=('of',))
        act, note = d.get('act'), d.get('note', '')
        if act == 'approve':
            review.approve(user, pk, note)
        elif act == 'keep':
            review.keep(user, pk, note)
        elif act == 'remove':
            review.remove(user, pk, d.get('rule', ''), note)
        elif act == 'restore':
            review.restore(user, pk, note)
        elif act == 'pause':
            review.pause(user, pk, days=d.get('days'), rule=d.get('rule', ''), note=note)
        elif act == 'reveal':
            return Response(review.reveal(user, pk, note))
        elif act == 'redact':
            review.redact(user, pk, d.get('spans') or [], note, publish=d.get('publish', True) is not False)
        elif act == 'send_back':
            review.send_back(user, pk, note)
        elif act in ('trust', 'untrust'):
            review.trust(user, pk, act == 'trust', note)
        elif act == 'duplicate':
            review.duplicate(user, pk, d.get('of') or None, note)
        else:
            raise Refused('act', 'invalid')
        return Response({'ok': True})


class ReviewLockView(RefusingView):
    throttle_scope = 'account'
    def post(self, request):
        d = request.data
        require_types(d, words=('path', 'note'))
        # «false» as a string locked a topic: only true locks.
        found = review.lock(request.user, d.get('path', ''), d.get('locked') in (True, 'true', '1', 1), d.get('note', ''))
        return Response({'locked': bool(found.locked_at)})


class ReviewPauseView(RefusingView):
    throttle_scope = 'account'
    def post(self, request, pk):
        require_types(request.data, words=('act', 'note'))
        act = request.data.get('act')
        if act == 'confirm':
            review.confirm_permanent(request.user, pk, request.data.get('note', ''))
        elif act == 'lift':
            review.lift(request.user, pk, request.data.get('note', ''))
        else:
            raise Refused('act', 'invalid')
        return Response({'ok': True})


class ReviewAppealView(RefusingView):
    throttle_scope = 'account'
    def post(self, request, pk):
        require_types(request.data, words=('outcome', 'note'))
        review.decide_appeal(request.user, pk, request.data.get('outcome', ''), request.data.get('note', ''))
        return Response({'ok': True})


class LedgerView(RefusingView):
    throttle_scope = 'account'
    def get(self, request):
        rows = review.ledger(request.user)
        staff = request.user.is_staff
        return Response({'actions': [
            {'verb': a.verb, 'created_at': a.created_at, 'rule': a.rule or None, 'note': a.note,
             'actor': a.actor.shown_name if a.actor else None,
             'target': None if (a.target_hidden and not staff) or a.target is None else a.target.shown_name,
             'path': a.path or None, 'contribution': a.contribution_id} for a in rows]})


class ReviewPictureView(RefusingView):
    """POST multipart {picture}: the reviewer's covered copy replaces the contribution's picture (M3)."""
    throttle_scope = 'uploads'

    def post(self, request, pk, picture_id):
        require_types(request.data, words=('note',))
        review.redact_picture(request.user, pk, picture_id, request.FILES.get('picture'), request.data.get('note', ''))
        return Response({'ok': True})


class ReviewersView(RefusingView):
    """Staff: appoint each topic's moderators from its community, end them (M12, 29 Oct 2026). GET ?place=
    adds the people whose words that topic found most useful, by the karma they earned there."""
    throttle_scope = 'account'

    def get(self, request):
        if not request.user.is_staff:
            raise Refused('review', 'staff_only', 403)
        from apps.accounts.models import User
        from apps.discussion.models import Reviewer
        from apps.discussion.services import counters, places

        rows = list(Reviewer.objects.filter(ended_at=None).select_related('user').order_by('appointed_at'))
        karma = points.karma({r.user_id for r in rows})
        out = {'reviewers': [{'user': r.user_id, 'username': r.user.username, 'name': r.user.shown_name,
                              'text_paths': r.text_paths, 'karma': karma.get(r.user_id, 0),
                              'appointed_at': r.appointed_at} for r in rows],
               'places': [{'path': p.path, 'slug': p.slug, 'name': p.name} for p in places.all_places()]}
        place = request.query_params.get('place', '')
        if place:
            place = places.find(place).path
            ranked = points.in_place(place, leave_out=[r.user_id for r in rows if place in (r.text_paths or [])])
            people = {u.pk: u for u in User.objects.filter(pk__in=[u for u, _ in ranked], deleted_at=None,
                                                             is_active=True).exclude(counters.demo(''))}
            out['candidates'] = [{'user': u, 'username': people[u].username, 'name': people[u].shown_name,
                                  'karma_here': n} for u, n in ranked if u in people]
        return Response(out)

    def post(self, request):
        """{username, places: ['family', …]} or {username, text_paths}: a moderator of these topics; {username,
        everywhere: true} for all of them. No place chosen is refused."""
        from apps.accounts.models import User
        from apps.discussion.services import places

        require_types(request.data, lists=('places', 'text_paths'))
        target = User.objects.filter(username__iexact=str(request.data.get('username', '')).strip(),
                                     deleted_at=None).first()
        if target is None:
            raise Refused('username', 'not_found', 404)
        chosen = request.data.get('places')
        if chosen:
            paths = [places.find(p if str(p).startswith(places.PREFIX) else f'{places.PREFIX}{p}').path
                     for p in (chosen if isinstance(chosen, list) else str(chosen).split(','))]
        else:
            paths = request.data.get('text_paths') or []
            if isinstance(paths, str):
                paths = [p.strip() for p in paths.split(',') if p.strip()]
        review.appoint(request.user, target, paths, everywhere=request.data.get('everywhere') in (True, 'true', '1'))
        return Response({'ok': True}, status=status.HTTP_201_CREATED)


class ReviewerView(RefusingView):
    """Staff: DELETE /review/reviewers/<id>/ ends one moderator's appointments. A view of its own: when the list's view
    served this address too, a GET or POST here, or a DELETE on the list, answered 500."""
    throttle_scope = 'account'

    def delete(self, request, user_id):
        from apps.accounts.models import User

        target = User.objects.filter(pk=user_id).first()
        if target is None:
            raise Refused('username', 'not_found', 404)
        review.dismiss(request.user, target)
        return Response(status=status.HTTP_204_NO_CONTENT)
