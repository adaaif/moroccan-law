"""The reviewers' powers (D10): the site's staff everywhere, appointed reviewers on their texts. Every act is a row of
the ledger written in the same transaction; a removal names a rule and its author is told which, and may appeal
once. Nobody decides about their own words, and an appeal goes to someone other than who acted.

«بدون اسم» stays hidden from reviewers: they act on the contribution, and a pause through it never names its author.
Only staff can reveal who wrote it, with a reason in the ledger (D6).

By subject: `reviewers` (who reviews where, appointing and ending them, and what every act shares), `desk` (the
queue's tabs, what a card shows beside the words, the ledger, the header's count), `acts` (approve, keep, remove,
restore, reveal, lock, redact, send back, trust, repeats) and `pauses` (pauses and appeals). Callers name it as one
module (`review.approve(…)`): this package re-exports its public names."""
from apps.discussion.services.review.acts import (KEPT, REDACTED, approve, duplicate, keep, lock, redact,
                                                  redact_picture, remove, restore, reveal, send_back, trust)
from apps.discussion.services.review.desk import (CARD_RELATED, PRIVATE, RULE_OF, SEVERITY, Desk, context, counts,
                                                  ledger, open_reports, queue, record, suggest, waiting_counts,
                                                  waiting_everywhere)
from apps.discussion.services.review.pauses import (BAN_DAYS, appeal, confirm_permanent, decide_appeal, lift,
                                                    pause)
from apps.discussion.services.review.reviewers import appoint, covers, dismiss, is_reviewer, reviewer

__all__ = ['KEPT', 'REDACTED', 'approve', 'duplicate', 'keep', 'lock', 'redact', 'redact_picture', 'remove', 'restore',
           'reveal', 'send_back', 'trust',
           'CARD_RELATED', 'PRIVATE', 'RULE_OF', 'SEVERITY', 'Desk', 'context', 'counts', 'ledger', 'open_reports',
           'queue', 'record', 'suggest', 'waiting_counts', 'waiting_everywhere',
           'BAN_DAYS', 'appeal', 'confirm_permanent', 'decide_appeal', 'lift', 'pause',
           'appoint', 'covers', 'dismiss', 'is_reviewer', 'reviewer']
