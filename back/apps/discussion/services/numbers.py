"""The monthly count of contributions, reports and acts, published on the rules page (the page's «A monthly count
of reports and acts, published»). Counts only: no name, no address. The development's people count nowhere: not their
contributions, not the reports on them or by them, not the acts on them or by them (the public site counted the demo's
25 reports and 9 approvals of October 2026 against 0 contributions)."""
from datetime import date, datetime, time

from django.db.models import Count
from django.utils import timezone

from apps.discussion.models import Action, Appeal, Ban, Check, Contribution, Report
from apps.discussion.services import counters


def month(year: int, month_no: int) -> dict:
    start = date(year, month_no, 1)
    end = date(year + (month_no == 12), month_no % 12 + 1, 1)
    # The month's bounds as moments in Morocco's time, so the dates are compared as they are stored and indexed (a date
    # taken of every row read all ten million of the load test, 54 s).
    since, until = (timezone.make_aware(datetime.combine(d, time.min)) for d in (start, end))
    span = {'created_at__gte': since, 'created_at__lt': until}
    # Everything written in the month (its dates' own index), less what the development's people wrote (theirs);
    # the held ones from the index of those held, few.
    every = Contribution.objects.filter(**span)
    demo = counters.demo()
    written_n = every.count() - (every.filter(demo).count() if demo else 0)
    held_n = every.exclude(held_reasons=[]).exclude(demo).count()
    reports = (Report.objects.filter(**span).exclude(counters.demo('contribution__author__'))
               .exclude(counters.demo('reporter__')))
    reasons = dict(reports.values_list('reason').annotate(n=Count('pk')))
    acts = Action.objects.filter(**span).exclude(counters.demo('actor__')).exclude(counters.demo('target__'))
    verbs = dict(acts.values_list('verb').annotate(n=Count('pk')))
    checks = dict(Check.objects.filter(**span).exclude(counters.demo('user__')).values_list('outcome')
                  .annotate(n=Count('pk')))
    return {
        'month': f'{year:04d}-{month_no:02d}',
        'contributions': written_n,
        'held': held_n,
        'reports': {r: reasons.get(r, 0) for r in Report.Reason.values},
        'acts': {v: verbs.get(v, 0) for v in ('approve', 'keep', 'remove', 'restore', 'lock', 'ban', 'ban_confirm',
                                                'unban', 'appeal_lift', 'appeal_keep', 'reveal')},
        # The model's check (29 Oct 2026): what it answered, and how often a moderator published what it held.
        'checks': {o: checks.get(o, 0) for o in Check.Outcome.values},
        'overturned': Check.objects.filter(**span, outcome__in=[Check.Outcome.HOLD, Check.Outcome.UNAVAILABLE],
                                           contribution__in=Action.objects.filter(verb=Action.Verb.APPROVE)
                                           .values('contribution')).exclude(counters.demo('user__')).count(),
        'pauses': Ban.objects.filter(started_at__gte=since, started_at__lt=until)
        .exclude(counters.demo('user__')).count(),
        'appeals': Appeal.objects.filter(**span).exclude(counters.demo('user__')).count(),
    }
