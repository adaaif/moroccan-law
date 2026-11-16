"""The sample a stranger loads in one command (load_sample): the 2011 Constitution and BO 7278, with their French, read
through the public API with no corpus files on the machine."""
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.corpus.models import Article, Text
from apps.translations.models import FrenchText

pytestmark = pytest.mark.django_db


def test_the_sample_loads_into_an_empty_database_and_reads(api):
    call_command('load_sample')
    assert Text.objects.count() == 12 and Article.objects.count() == 340 and FrenchText.objects.count() == 2
    constitution = api.get('/api/corpus/at/ma/dahir/1-11-91/').json()
    assert constitution['type'] == 'constitution'
    issue = api.get('/api/corpus/issues/general_ar/7278/')
    assert issue.status_code == 200 and issue.json()['number'] == 7278
    page = api.get('/api/sources/documents/2/pages/0/')
    assert page.status_code == 200 and 'الجريدة الرسمية' in page.json()['text']
    # The PDFs are not in the sample: a page's picture is not there, said as such, never a 500.
    assert api.get('/api/sources/documents/2/pages/0/image/').status_code == 404
    with pytest.raises(CommandError, match='empty database'):
        call_command('load_sample')
