"""Keeps the retention table the rules page promises (D11), nightly:

- a voice or a picture never published: deleted after DRAFT_HOURS;
- a contribution a reviewer removed: kept 90 days for the reviewers, then its words and files erased;
- a contribution deleted under a report: kept until the report is decided, 30 days at most, then erased;
- decided reports: 90 days; the ledger: 365 days; email codes: once expired; notices: 180 days;
- earlier wordings (edits, redactions) and pictures a reviewer covered: 90 days;
- the model's verdicts before publishing (Check: no words, a code and what it cost): 90 days;
- a state of an explanation a reviewer removed: its words kept 90 days for the reviewers, then erased; decided
  reports of explanations: 90 days.
"""
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import EmailCode
from apps.discussion.models import Action, Check, Contribution, Notice, Report, Revision
from apps.discussion.services import compose
from apps.explain.models import Report as ExplainReport, Revision as ExplainRevision
from apps.media.models import Clip, Picture, State
from apps.media.services import files

# The days each thing is kept, as /privacy's ruler says them (apps/discussion/tests/test_privacy_page.py reads both).
KEEP_DAYS = {'removed': 90, 'reports': 90, 'ledger': 365, 'notices': 180, 'edits': 90, 'checks': 90}


class Command(BaseCommand):
    help = 'Erase what the retention table says is due.'

    def handle(self, *args, **options):
        now = timezone.now()
        drafts = [*Clip.objects.filter(state=State.DRAFT, created_at__lt=now - timedelta(hours=settings.DRAFT_HOURS)),
                  *Picture.objects.filter(state=State.DRAFT,
                                          created_at__lt=now - timedelta(hours=settings.DRAFT_HOURS))]
        files.erase(drafts)
        removed = Contribution.objects.filter(erased_at=None, removed_at__lt=now - timedelta(days=KEEP_DAYS['removed']))
        frozen = (Contribution.objects.filter(erased_at=None, deleted_at__isnull=False)
                  .filter(Q(frozen_until__lt=now) | ~Q(reports__status=Report.Status.OPEN)).distinct())
        # Erased together; counted as they were one by one (a contribution both removed and deleted counts twice).
        due = [c for c in [*removed, *frozen] if c.erased_at is None]
        compose.erase_many(list({c.pk: c for c in due}.values()))
        erased = len(due)
        reports = Report.objects.exclude(status=Report.Status.OPEN).filter(
            decided_at__lt=now - timedelta(days=KEEP_DAYS['reports'])).delete()[0]
        ledger = Action.objects.filter(created_at__lt=now - timedelta(days=KEEP_DAYS['ledger'])).delete()[0]
        codes = EmailCode.objects.filter(expires_at__lt=now - timedelta(days=1)).delete()[0]
        old_notices = Notice.objects.filter(created_at__lt=now - timedelta(days=KEEP_DAYS['notices'])).delete()[0]
        Revision.objects.filter(created_at__lt=now - timedelta(days=KEEP_DAYS['edits'])).delete()
        checks = Check.objects.filter(created_at__lt=now - timedelta(days=KEEP_DAYS['checks'])).delete()[0]
        explained = (ExplainRevision.objects.filter(removed_at__lt=now - timedelta(days=KEEP_DAYS['removed']))
                     .exclude(body='', headline='', note='')
                     .update(body='', headline='', note='', sources=[], held_spans=[]))
        reports += ExplainReport.objects.exclude(status=Report.Status.OPEN).filter(
            decided_at__lt=now - timedelta(days=KEEP_DAYS['reports'])).delete()[0]
        files.erase(list(Picture.objects.filter(replaced_by__isnull=False, erased_at=None,
                                                created_at__lt=now - timedelta(days=KEEP_DAYS['edits']))))
        self.stdout.write(f'drafts {len(drafts)}, contributions erased {erased}, reports {reports}, '
                          f'ledger rows {ledger}, codes {codes}, notices {old_notices}, checks {checks}, '
                          f'explanation states erased {explained}')
