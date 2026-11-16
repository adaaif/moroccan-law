"""When a text and its changes take effect, from what it says of itself: as printed, unless an official portal's copy
of a later wording states the day; and the version a text is read from as published (a bill's latest stage)."""
from datetime import date, timedelta

from apps.consolidation.models import Change
from apps.consolidation.services.instructions.dates import When, in_force
from apps.corpus.models import Article, Consolidation, Text, Version


def add_months(day: date, months: int) -> date:
    y, m = divmod(day.month - 1 + months, 12)
    year, month = day.year + y, m + 1
    for d in (day.day, 30, 29, 28):
        try:
            return date(year, month, d)
        except ValueError:
            continue
    return day


def takes_effect(when: When | None, published: date | None) -> tuple[date | None, str, str]:
    """(day, rule, words): when a text's changes start, from what it says of itself; on publication when it says
    nothing."""
    if when is None:
        return published, Change.Rule.PUBLICATION, ''
    if when.rule == 'publication':
        return published, Change.Rule.PUBLICATION, when.words
    if when.rule == 'stated':
        return when.on, Change.Rule.STATED, when.words
    if when.rule == 'after' and published:
        if when.next_week:
            return published + timedelta(days=7 - published.weekday()), Change.Rule.AFTER, when.words
        start = add_months(published.replace(day=1), 1) if when.next_month else published
        day = add_months(start, when.months) if when.months else start + timedelta(days=when.days)
        return day, Change.Rule.AFTER, when.words
    return None, Change.Rule.CONDITION, when.words


def own_rule(articles: list[Article]) -> When | None:
    """What a text says of its own entry into force: the last article that says it (its final provisions)."""
    for a in reversed(articles):
        when = in_force(a.body)
        if when is not None:
            return when
    return None


# The copies an official portal publishes as today's (corpus.services.links.OFFICIAL).
_PORTALS = (Consolidation.ADALA, Consolidation.SGG, Consolidation.DGI)


def own_start(text: Text, printed: Version, published: date | None) -> tuple[date | None, str, str]:
    """(day, rule, words) of a text's own entry into force: what it says as printed, unless a later law rewrote that
    clause and an official portal's copy states the day. The criminal procedure code printed «ابتداء من اليوم الأول
    للشهر التاسع عشر الموالي لنشره» (1 August 2004) and its art. 755 now says «ابتداء من فاتح أكتوبر من سنة 2003», the
    day every court took it up (RD3 of the readers review: the one text of the corpus so, 10 Nov 2026). Only a
    stated day is taken from the copy, read in its last articles."""
    said = takes_effect(own_rule(list(printed.articles.all())), published)
    copy = (text.versions.filter(language='ar', consolidation__in=_PORTALS, valid_from__gt=printed.valid_from)
            .order_by('-valid_from').first())
    if copy is not None:
        amended = own_rule(list(copy.articles.order_by('-order')[:30])[::-1])
        if amended is not None and amended.rule == 'stated' and amended.on != said[0]:
            return takes_effect(amended, published)
    return said


def as_published(text: Text) -> Version | None:
    # A bill is read as its latest stage says it (as filed, then as a chamber voted it); its changes are proposals.
    if text.type == 'bill':
        return text.versions.filter(consolidation=Consolidation.BILL).order_by('-valid_from').first()
    return text.versions.filter(consolidation=Consolidation.AS_PUBLISHED).order_by('valid_from').first()
