"""An article's changes as the tools give them: those the site read in the amending text and holds as fact (checked,
confirmed, read: the site shows them so) are part of the answer; a reading in conflict or unclear is not. The tools kept
only the witnesses' notes, so an article a law changed was said to have «no change recorded»."""
from datetime import date

import pytest

from apps.consolidation.models import Change
from apps.mcp.services import law

pytestmark = pytest.mark.django_db


def test_a_change_read_in_the_bulletin_is_in_the_articles_answer_and_a_doubtful_one_is_not(labour):
    for state, number, by, issue, on in (('confirmed', '51', '12-10', 5956, date(2011, 7, 28)),
                                         ('read', '52', '13-11', 6030, date(2012, 3, 1)),
                                         ('conflict', '51', '14-12', 6150, date(2013, 5, 2))):
        Change.objects.create(text_uri=labour.akn_uri, number=number, verb='modified', source='reading', state=state,
                              by_kind='law', by_number=by, issue=issue, page=1, published_on=on)
    meta = law.fetch('/ma/loi/65-99/art_51')[0]['metadata']
    assert [(c['on'], c['by'], c['bo']) for c in meta['changes']] == [('2011-07-28', 'law 12-10', '5956')]
    text, data, _ = law.read_articles('/ma/loi/65-99/art_51', count=2, on='2004-01-01')
    assert '(Changed after 2004-01-01: on 2011-07-28; it then read otherwise.)' in text
    assert '(Changed after 2004-01-01: on 2012-03-01; it then read otherwise.)' in text
    assert 'No change to this article' not in text
    assert [len(a['changes']) for a in data['articles']] == [1, 1]
