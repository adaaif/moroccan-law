"""`trim_french_divisions` (N15 of the read-and-trusted review): the next part's heading taken out of the stored French
articles' ends, counted first, saved with --write."""
from io import StringIO

import pytest
from django.core.management import call_command

from apps.translations.models import FrenchArticle

pytestmark = pytest.mark.django_db

ENDS = "Le délai doit être mentionné dans la décision visée à l'article 63 ci-dessus."


def test_the_next_parts_heading_is_counted_then_taken_out_with_write():
    article = dict(text_uri='/akn/ma/act/loi/65-99', label='Article 65')
    run_in = FrenchArticle.objects.create(**article, order=1, number='65',
                                          body=f'{ENDS}\nSection VI : Du licenciement pour motifs économiques')
    clean = FrenchArticle.objects.create(**article, order=2, number='66', body='Le salarié est informé.\n')
    said = StringIO()
    call_command('trim_french_divisions', stdout=said)
    assert said.getvalue() == '1 French articles to trim (--write)\n'
    run_in.refresh_from_db()
    assert run_in.body.endswith('économiques')                  # counted, not saved
    said = StringIO()
    call_command('trim_french_divisions', '--write', stdout=said)
    assert said.getvalue() == '1 French articles trimmed\n'
    run_in.refresh_from_db()
    clean.refresh_from_db()
    assert (run_in.body, clean.body) == (ENDS, 'Le salarié est informé.\n')    # a trailing line end is no heading
