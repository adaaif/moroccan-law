"""B15 of the search plan without a database: the sentence that answers, the number in the law's own words."""
import ma_law

from apps.search.services import answer

BODY = ('يجب على المكري أن يوجه إنذارا بالإفراغ.\n'
        'ويمنح المكتري أجلا لا يقل عن ستة أشهر إذا كان الإفراغ لعيب، و15 يوما في الحالات الأخرى.')


def text(segments, kind):
    return [s['t'] for s in segments if s[kind]]


def test_a_question_about_an_amount_gets_the_sentence_that_states_it_its_number_in_bold():
    q = 'شحال عندي باش نخرج من الدار ملي يجيني الإنذار بالإفراغ'
    assert answer.asks(q) and answer.asks_amount(q)
    s = answer.best_sentence(BODY, ma_law.search_terms(q), amount=True)
    assert ''.join(x['t'] for x in s).startswith('ويمنح المكتري')
    assert text(s, 'num') == ['ستة أشهر', 'و15 يوما'] and 'الإفراغ' in text(s, 'hit')


def test_another_question_gets_the_sentence_with_most_of_its_words_and_nothing_in_bold():
    q = 'واش خاص المكري يوجه إنذار بالإفراغ؟'
    s = answer.best_sentence(BODY, ma_law.search_terms(q), amount=answer.asks_amount(q))
    assert ''.join(x['t'] for x in s) == 'يجب على المكري أن يوجه إنذارا بالإفراغ.'
    assert not text(s, 'num')


def test_b9s_fact_counts_only_where_it_stands_word_for_word_and_no_pattern_did():
    body = 'يستحق الأجير تعويضا يساوي ثلث الأجرة عن كل يوم.'
    s = answer.best_sentence(body, ma_law.search_terms('شحال التعويض'), amount=True, facts=['ثلث الأجرة', 'نصف الأجرة'])
    assert text(s, 'num') == ['ثلث الأجرة']


def test_words_and_names_are_not_questions():
    assert not answer.asks('مدونة الأسرة') and not answer.asks('الطلاق')
