"""4. stand: where a text stands (in force, partly repealed, repealed, not yet in force) from the changes shown as
fact and its own dates."""
from datetime import date

from apps.consolidation.models import Change, Doubt, Verb
from apps.consolidation.services.engine.shared import SHOWN
from apps.consolidation.services.engine.when import as_published, own_start
from apps.corpus.models import Status, Text, TextType


def standing(text: Text, today: date | None = None) -> dict:
    """Where a text stands, from the changes shown as fact and its own dates: its status, what repealed it or will,
    and when it takes effect when that is still to come or on a condition."""
    today = today or date.today()
    out: dict = {'status': Status.UNKNOWN}
    if text.type == TextType.BILL:
        # A bill is not law: it stands nowhere until its law is published (P1).
        return out
    repeals = Change.objects.filter(text_uri=text.akn_uri, source=Change.Source.READING, verb=Verb.REPEALED,
                                    state__in=SHOWN).order_by('effective_on', 'published_on')
    whole = [c for c in repeals if not c.number]
    done = [c for c in whole if c.effective_on and c.effective_on <= today]
    version = as_published(text)
    if version is not None:
        published = text.first_published_in.date if text.first_published_in_id else text.signed_on
        on, rule, words = own_start(text, version, published)
        if rule == Change.Rule.CONDITION:
            # A person may say when the condition was met, and why (apply_wordings' `in_force`): 65.00's art. 147 waits
            # for the texts that install the funds' bodies, published on 18 Aug 2005.
            met = Doubt.objects.filter(text_uri=text.akn_uri, reason=Doubt.Reason.WHEN, status=Doubt.Status.RESOLVED,
                                       detail__has_key='on').values_list('detail', flat=True).first()
            if met is None:
                out['in_force_when'] = words
            elif date.fromisoformat(met['on']) > today:
                out['in_force_on'] = date.fromisoformat(met['on'])
            else:
                out['in_force_since'], out['in_force_because'] = date.fromisoformat(met['on']), met.get('because', '')
        elif on and on > today:
            out['in_force_on'] = on
    held = version is not None or text.versions.exists()
    if done:
        out['status'] = Status.REPEALED
        out['repealed'] = _brief(done[0])
    elif 'in_force_on' in out:
        out['status'] = Status.NOT_YET_IN_FORCE
    elif any(c.number and c.effective_on and c.effective_on <= today for c in repeals):
        out['status'] = Status.PARTLY_REPEALED
    elif held and 'in_force_when' not in out:
        out['status'] = Status.IN_FORCE
    pending = [c for c in whole if c not in done]
    if pending:
        out['repeal_pending'] = _brief(pending[0])
    return out


def _brief(c: Change) -> dict:
    return {'by_uri': c.by_uri, 'by_article': c.by_article, 'issue': c.issue, 'issue_bis': c.issue_bis, 'page': c.page,
            'on': c.effective_on, 'rule': c.effective_rule, 'words': c.effective_words or c.detail.get('clause', ''),
            'state': c.state}
