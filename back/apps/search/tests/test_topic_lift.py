"""A question that names a topic ranks what the topic rests on higher (R6 of the road plan)."""
from datetime import date

import pytest

from apps.corpus.models import Article, Text, Version
from apps.search.services import search
from apps.search.services.search import bm25
from apps.topics.services import kit

pytestmark = pytest.mark.django_db


def test_a_question_in_a_topics_words_lifts_the_articles_it_cites():
    code = Text.objects.create(akn_uri='/akn/ma/act/loi/52-05', type='law', number='52-05', title_ar='مدونة السير')
    v = Version.objects.create(text=code, language='ar', valid_from=date(2016, 8, 11), consolidation='sgg')
    Article.objects.create(version=v, order=1, label='المادة 38', number='38', eid='art_38', body='الحامل.')
    Article.objects.create(version=v, order=2, label='المادة 37', number='37', eid='art_37', body='رخصة.')
    bm25._rests_on.cache_clear()
    texts, arts = bm25._topic_lift('Comment renouveler mon permis de conduire ?')      # a door's words: the road
    # By address (B24 of the search plan): the road code and its renewal article, not the article beside it.
    assert '/ma/loi/52-05' in texts and '/ma/loi/52-05/art_38' in arts and '/ma/loi/52-05/art_37' not in arts
    assert '/ma/loi/52-05' not in bm25._topic_lift('عقد الشغل محدد المدة')[0]          # the work topic's words
    road_texts, road_articles = bm25._rests_on('road', kit.stamp('road'))
    assert '/ma/loi/52-05' in road_texts and '/ma/loi/52-05/art_38' in road_articles


def test_a_questions_everyday_words_are_searched_by_what_they_mean_alone():
    from apps.search.services import vocab
    vocab.entries.cache_clear()
    assert vocab.meanings('واش الصابو قانوني؟') == 'توقيف المركبات'
    assert vocab.meanings('إلى شدوك البوليس بلا كاسك شنو دير') == 'خوذات واقية'
    assert vocab.meanings('حكم المحكمة') == ''
    assert search.asked_words('Comment renouveler mon permis de conduire au Maroc ?') == 'renouveler permis conduire'


def test_a_doors_articles_carry_their_official_french_on_a_french_page():
    """RD12 of the readers review: «congé de maternité» was answered in French over the Labour Code's articles in Arabic."""
    from apps.translations.models import FrenchArticle
    FrenchArticle.objects.create(text_uri='/akn/ma/act/loi/65-99', order=152, label='Article 152', number='152',
                                 body='La salariée en état de grossesse dispose d\'un congé de maternité de quatorze semaines.')
    rows = [{'path': '/ma/loi/65-99/art_152', 'label': 'المادة 152', 'number': '152', 'text': {}, 'body': 'تتمتع الأجيرة…'},
            {'path': '/ma/loi/65-99/art_153', 'label': 'المادة 153', 'number': '153', 'text': {}, 'body': 'لا يمكن تشغيل…'}]
    out = search.door_french(rows)
    assert out[0]['french'] == {'label': 'Article 152', 'body': 'La salariée en état de grossesse dispose d\'un congé de maternité de quatorze semaines.'}
    assert 'french' not in out[1]                     # no French held: the Arabic stays, as before
    assert search.door_french([]) == []


def test_now_is_a_word_that_asks():
    """RD7: «شحال السميك دابا» sent the texts to a 1968 report on the word «دابا»."""
    assert search.asked_words('شحال السميك دابا') == search.asked_words('شحال السميك')
    assert search.asked_words('combien le smig maintenant') == search.asked_words('combien le smig')


def test_another_countrys_law_is_told_from_a_treaty():
    """RD11 of the readers review: «قانون الشغل الفرنسي» opened the Moroccan Labour Code without a word."""
    from apps.search.api.views import FOREIGN_LAW
    for q in ('قانون الشغل الفرنسي', 'مدونة الأسرة الجزائرية', 'code du travail français', 'droit algérien de la famille', 'Constitution française'):
        assert FOREIGN_LAW.search(q), q
    for q in ('اتفاقية الضمان الاجتماعي مع فرنسا', 'قانون الشغل', 'convention fiscale Maroc France', 'القانون الجنائي المغربي', 'code du travail'):
        assert not FOREIGN_LAW.search(q), q
