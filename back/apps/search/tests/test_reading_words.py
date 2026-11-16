"""How a word typed is read before the search (B6, C2): a Latin-letter word opening on a doubled «a» is read with «ع», a
word no spelling fits stays as typed, a French word the corpus's French uses often stays French; a door's words are
none when the door is not its topic's; and the approved everyday words keep only what the reviewer kept."""
import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.search.services import spelling, vocab
from apps.translations.models import FrenchArticle

pytestmark = pytest.mark.django_db


def test_a_latin_word_is_spelled_as_the_law_writes_or_stays_as_typed():
    spelling.word.cache_clear()                     # no index counted here: the likeliest spelling is taken
    assert spelling.word('aandi') == 'عندي'                  # a doubled a opens on «ع», as «3andi»
    assert spelling.word('---') == '---'                     # nothing to spell it with
    FrenchArticle.objects.create(text_uri='/akn/ma/act/loi/52-05', order=1, label='Article 1', number='1',
                                 body=' '.join(['Le permis de conduire.'] * spelling.FRENCH_MIN))
    spelling.french_words.cache_clear()             # read once a process: this one read none above
    assert spelling.french_words()['permis'] == spelling.FRENCH_MIN
    spelling.word.cache_clear()
    assert spelling.word('permis') == 'permis'               # the French the corpus uses stays French
    assert spelling.word('kontra') != 'kontra'


def test_a_doors_words_are_none_when_no_door_of_its_topic_has_that_slug():
    assert vocab.door_forms({'topic': 'housing', 'slug': 'housing-no-such-door'}) == {}
    assert vocab.door_forms(None) == {}


def test_only_the_meanings_the_reviewer_kept_are_written(tmp_path, monkeypatch):
    target = tmp_path / 'everyday.json'
    target.write_text(json.dumps({'about': 'x', 'entries': []}))
    monkeypatch.setattr(vocab, 'FILE', target)
    review = tmp_path / 'review.json'
    review.write_text(json.dumps({
        'entries': [{'id': 'v1', 'order': 2, 'typed': 'CNSS', 'kind': 'acronyms', 'means': ['الضمان الاجتماعي', 'الصندوق']},
                    {'id': 'v2', 'order': 1, 'typed': 'كرا', 'kind': 'darija', 'means': ['الكراء']},
                    {'id': 'v3', 'order': 3, 'typed': 'patente', 'kind': 'french', 'means': ['الرسم المهني']}],
        'decisions': {'v1': {'verdict': 'approve', 'keep': [True, False], 'extra': ' الضمان الاجتماعي '},
                      'v2': {'verdict': 'approve', 'keep': [False], 'extra': ''},
                      'v3': {'verdict': 'approve'}},
    }, ensure_ascii=False))
    out = StringIO()
    call_command('apply_vocab', str(review), stdout=out)
    # The added meaning already kept is not kept twice; an entry with nothing ticked stays out; no ticks at all is none.
    assert json.loads(target.read_text())['entries'] == [
        {'typed': ['CNSS'], 'kind': 'acronyms', 'means': ['الضمان الاجتماعي']}]
    assert out.getvalue().strip() == '1 approved entries written to everyday.json'


def test_suggestions_read_darija_in_latin_letters_and_a_french_keyboard(api):
    from apps.search.models import SearchEntry
    SearchEntry.objects.create(kind='text', text_path='/ma/loi/91-97', path='/ma/loi/91-97', text_type='law',
                               title='القانون رقم 91.97 المتعلق بعقود الكراء', name={'ar': 'قانون الكراء'},
                               title_folded='القانون رقم 91.97 المتعلق بعقود الكراء')
    for typed in ('kra', 'hgmvhx'):          # Darija for «الكراء»; «الكراء» typed on a French keyboard
        r = api.get('/api/search/suggest/', {'q': typed})
        assert r.status_code == 200 and r.json()['repaired'] == 'الكراء', typed
        assert [t['path'] for t in r.json()['texts']] == ['/ma/loi/91-97'], typed
    assert api.get('/api/search/suggest/', {'q': 'الكراء'}).json()['repaired'] is None
