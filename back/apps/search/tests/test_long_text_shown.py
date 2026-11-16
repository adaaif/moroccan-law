"""What a long text shows of itself: the answer box's sentence past sixty words is the stretch around its first marked
word or number (B15), and a long article's snippet starts at its first quoted phrase, or at its start when it holds none
of the words (B27)."""
import ma_law

from apps.search.services import answer
from apps.search.services.search import snippets


def words(segments) -> str:
    return ''.join(s['t'] for s in segments)


def test_a_long_sentence_is_shown_around_its_first_marked_word_or_its_number():
    body = ' '.join(f'كلمة{i}' for i in range(30)) + ' يستحق الأجير تعويضا ' + ' '.join(f'لفظ{i}' for i in range(40)) + '.'
    shown = answer.best_sentence(body, ma_law.search_terms('الأجير'), amount=False)
    # Ten words before the first marked one, forty-five in all, and the cuts said.
    assert words(shown).startswith('… كلمة21 ') and words(shown).endswith(' لفظ32 …') and [s['t'] for s in shown if s['hit']] == ['الأجير']
    assert len(words(shown)[2:-2].split()) == answer.STRETCH[0]
    # Asked for an amount, the stretch opens on the number, as far as the marked word may lie before it.
    body = ' '.join(f'كلمة{i}' for i in range(5)) + ' الأجير ' + ' '.join(f'لفظ{i}' for i in range(50)) + ' أجل 15 يوما ' + \
        ' '.join(f'نص{i}' for i in range(20)) + '.'
    shown = answer.best_sentence(body, ma_law.search_terms('الأجير'), amount=True)
    assert words(shown).startswith('… لفظ41 ') and [s['t'] for s in shown if s['num']] == ['15 يوما']
    assert not any(s['hit'] for s in shown)          # the marked word fell before the stretch
    # A sentence that fits is shown whole, from its first word.
    assert words(answer.best_sentence('يستحق الأجير تعويضا.', ['اجير'], amount=False)) == 'يستحق الأجير تعويضا.'


def test_a_body_of_nothing_but_marks_has_no_sentence():
    assert answer.best_sentence('**** | ---', ['اجير'], amount=False) is None


def test_a_long_articles_snippet_starts_at_its_quoted_phrase_or_at_its_start():
    before = ' '.join(['جدول'] * 1200)
    body = f'{before} القوة القاهرة تعفي المدين {before}'
    shown = snippets.snippet(body, ma_law.search_terms('القوة القاهرة'), *snippets.SNIPPET, exact=['القوه القاهره'])
    assert words(shown).startswith('… جدول ') and words(shown).endswith(' جدول …')
    assert [s['t'] for s in shown if s['hit']] == ['القوة', 'القاهرة']
    assert words(shown).split().index('القوة') == snippets.SNIPPET[1] + 1        # five words before it, after the «…»
    # None of the words in it: its first words, the rest said to follow.
    shown = snippets.snippet(body, ma_law.search_terms('الإفراغ'), *snippets.SNIPPET)
    assert not words(shown).startswith('…') and words(shown).endswith(' …') and not any(s['hit'] for s in shown)
