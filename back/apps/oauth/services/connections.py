"""«التطبيقات المتصلة» on the account page (MC8): each live connection, what it did this month, and its end."""
from django.db.models import Sum
from django.utils import timezone

from apps.accounts.services.refusals import Refused
from apps.oauth.models import Day, Grant
from apps.oauth.services import clients


def listed(user) -> list[dict]:
    """Two queries, whatever the number of connections."""
    grants = list(Grant.objects.filter(user=user, revoked_at=None).select_related('client').order_by('-created_at'))
    month = timezone.localdate().replace(day=1)
    used = dict(Day.objects.filter(grant__in=grants, day__gte=month).values('grant').annotate(n=Sum('calls'))
                .values_list('grant', 'n'))
    out = []
    for g in grants:
        known = clients.known_as(g.client)
        out.append({'id': g.pk, 'name': known or g.client.name, 'known': bool(known), 'domain': clients.shown_domain(g.client),
                    'since': g.created_at, 'used_at': g.used_at, 'calls_this_month': used.get(g.pk, 0)})
    return out


def end(user, grant_id: int) -> None:
    if not Grant.objects.filter(user=user, pk=grant_id, revoked_at=None).update(revoked_at=timezone.now()):
        raise Refused('connection', 'not_found', 404)
