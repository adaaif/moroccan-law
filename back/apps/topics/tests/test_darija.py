"""People ask in every person, gender and word order (HM1, HM9, HM10 of the hard-moment review, 7 Nov 2026): a
door's words meet them on the verb, a generic word picks no door, and a question that asks a figure gets the door whose
figure it is."""
import pytest

from apps.sources.services.compare import fold
from apps.topics.services import kit
from apps.topics.services.darija import core, door_key

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('typed, verb', [
    ('شداتو', 'شد'), ('شدوه', 'شد'), ('شدوني', 'شد'), ('شدوها', 'شد'), ('كيطردونيش', 'طرد'), ('طردوها', 'طرد'),
    ('يطلقني', 'طلق'), ('نطلق', 'طلق'), ('بغا', 'بغ'), ('بغات', 'بغ'), ('بغيت', 'بغ'), ('مولات', 'مول'), ('زادت', 'زاد'),
    ('علينا', 'علي'), ('عليا', 'علي'), ('كتبتزني', 'بتز'), ('كيبتزوني', 'بتز'), ('تنصب', 'نصب'), ('نصبو', 'نصب'),
    ('يخرجني', 'خرج'), ('خرجوني', 'خرج'),
])
def test_a_verb_in_any_person_is_one_word(typed, verb):
    assert core(fold(typed)) == verb


@pytest.mark.parametrize('kept', ['البوليس', 'الكراء', 'ولدي', 'شحال', 'jrawni', 'تشد', 'دار'])
def test_nouns_latin_and_short_words_stay(kept):
    assert core(fold(kept)) == fold(kept)


def test_a_door_word_that_coring_does_not_change_needs_no_key():
    assert door_key(fold('مول الدار')) is None
    assert door_key(fold('زاد عليا فالكرا')) == 'زاد علي فالكرا'
    assert door_key(fold('تشد')) is None
    assert door_key(fold('شدوه البوليس')) == 'شد البوليس'


def _drafts(settings):
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()


@pytest.mark.parametrize('question, ref', [
    ('ولدي شداتو البوليس البارح', 'journeys/custody'),
    ('شدوني البوليس شحال يقدرو يخليوني', 'journeys/custody'),
    ('طردوها من الخدمة', 'journeys/dismissed'),
    ('مولات الدار بغات تخرجني', 'journeys/eviction'),
    ('راجلي بغا يطلقني', 'pages/ways'),
    ('تسرقات ليا لاكارط', 'journeys/card-lost'),
])
def test_other_persons_reach_the_door(settings, question, ref):
    _drafts(settings)
    assert kit.matching(question)[0]['ref'] == ref


@pytest.mark.parametrize('question', ['شنو حقوقي مع مول الدار', 'التعويض عن الضرر'])
def test_a_generic_word_picks_no_door(settings, question):
    _drafts(settings)
    assert not [d for d in kit.matching(question) if d['topic'] in ('consumer', 'health')]


def test_the_notice_is_answered_by_its_own_door_not_the_ninety_days(settings):
    _drafts(settings)
    first = kit.matching('شحال ديال الإنذار قبل الطرد')[0]
    assert first['title']['ar'] == 'أجل الإخطار قبل الطرد'


def test_a_tie_between_topics_goes_to_the_topic_the_question_names(settings):
    _drafts(settings)
    assert kit.matching('الإفراغ من أجل الاستعمال الشخصي')[0]['topic'] == 'housing'


def test_a_negation_glued_on_reads_as_the_two_words():
    assert core(fold('مخلصونيش')) == 'ما خلص'
    assert core(fold('ماخلصونيش')) == 'ما خلص'
    assert door_key(fold('ما خلصونيش')) == 'ما خلص'


def test_a_noun_meets_its_plural_but_alone_keeps_its_feminine():
    assert door_key(fold('مخالفة التعمير')) == 'مخالف التعمير'
    assert core(fold('مخالفات')) == 'مخالف'
    assert door_key(fold('خدامة')) is None      # a domestic worker is not any «خدام»


@pytest.mark.parametrize('question, title', [
    ('السلام عليكم انا خدام فشركة 8 سنين ومخلصونيش', 'ما خلصونيش'),
    ('الخدامة فالدار طردتها', 'خدامة فالدار'),
    ('مخالفات التعمير', 'بنيت بلا رخصة'),
    ('شحال الذعيرة ديال الضو الأحمر', 'شحال غادي نخلص؟'),
])
def test_the_readers_own_words_open_their_door_first(settings, question, title):
    _drafts(settings)
    assert kit.matching(question)[0]['title']['ar'] == title


def test_the_nearest_doors_need_two_words_outside_the_topic_named(settings):
    _drafts(settings)
    assert next(d['title']['ar'] for d in kit.nearest('الكرا ديالي تزاد بزاف', 'housing')) == 'زاد عليا فالكرا'
    # A rare word alone is no reason: «سنين» and «حزت» do not make a worker's question a land door.
    assert not [d for d in kit.nearest('السلام عليكم انا خدام فشركة 8 سنين') if d['topic'] == 'land']


# ── RD8 of the readers review: the door that fits the question, not one word of it ──────────────────────────────

def _answered(question):
    """The doors the search answers with, and the one it only offers as a guess."""
    found = kit.matching(question)
    return [d['slug'] for d in found if not d.get('unsure')], [d['slug'] for d in found if d.get('unsure')]


def test_a_door_that_only_shares_another_topics_word_is_a_guess(settings):
    _drafts(settings)
    # «الكوسيون» is public procurement's guarantee, and the tenant's deposit: the question names the housing by «مول الدار».
    assert _answered('مول الدار ما بغاش يرجع ليا الكوسيون') == ([], ['business-markets-guarantee'])
    assert _answered('augmentation loyer maximum') == ([], ['tax-rent'])
    # A word no named topic owns stands, and so does a door of the topic's own folder.
    assert _answered('sextorsion que faire plainte')[0][:1] == ['digital-extortion']
    assert _answered('congé annuel payé combien de jours')[0][:1] == ['work-leave']
    assert 'papers-birth' in _answered('كيفاش نسجل ولدي فالحالة المدنية')[0]


@pytest.mark.parametrize('question,door', [
    ('بعت دار شحال غادي نخلص ديال الضريبة', 'tax-sell'),          # was the road's fine tool, by «شحال غادي نخلص»
    ('فين نشكي بالباطرون', 'work-where'),                        # was the consumer's complaint
    ('ما خلصتش الضريبة فالوقت', 'tax-late'),                     # was the worker's unpaid wages
    ('كيفاش نصرح بمدخول الكراء', 'tax-rent'),
    ('شحال من نقطة فالبيرمي', 'road-points'),                    # was the papers' licence
    ("bail commercial indemnité d'éviction", 'housing-shop'),    # was the home tenant's eviction
    ('شريت تيليفون وخسر ليا من بعد سيمانة', 'consumer-defect'),
    ('سقوط الحضانة بزواج الأم', 'family-children'),              # was the marriage file: its words come first
])
def test_the_door_the_question_is_about_leads(settings, question, door):
    _drafts(settings)
    assert _answered(question)[0][0] == door


def test_a_word_that_only_asks_for_a_delay_opens_no_door(settings):
    _drafts(settings)
    # «délai» was the work's dates tool for every question: a supplier's invoice, an appeal.
    assert _answered('délai appel jugement civil') == ([], [])
    assert [d['slug'] for d in kit.nearest('délai appel jugement civil', 'justice')][:1] == ['justice-appeal-civil']
    assert kit.nearest('واش غادي نربح القضية ديالي') == []          # «غادي» joins words; the finance bill's tool is not near
