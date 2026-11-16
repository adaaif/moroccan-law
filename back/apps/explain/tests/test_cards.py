"""The cards to forward, beyond the first ones (R14 of the for-everyone review): a version assembled after the amendments, or
a text the Bulletin's issue is not known for, says so instead of a page; a question asked in a topic names the topic, and
the article it started from when it did; a French «باختصار» reads from the left; an answer sits in the teal of people's
answers; a text no topic holds carries no topic's colour; and a word wider than the column, or an empty paragraph,
never makes an empty line."""
from datetime import date

import pytest
from PIL import Image

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.discussion.models import Contribution, Discussion
from apps.discussion.services import review
from apps.discussion.tests.conftest import ARTICLE as PATH, lease, make_user, uploads  # noqa: F401  (fixtures)
from apps.explain.services import cards, explanations

pytestmark = pytest.mark.django_db
TEXT = '/ma/loi/2013/67-12'
ASSEMBLED = {'consolidated': True, 'words': 'نص بعد التعديلات · غير رسمي'}
PRINTED = {'consolidated': False, 'words': 'الجريدة الرسمية 6208 · الصفحة 12'}
# Where a card's sheet begins and ends across (cards.OUTER + cards.PAD from each edge).
LEFT, RIGHT = 108, 972


@pytest.fixture
def reviewer(lease):
    staff, salma = make_user('staff', staff=True), make_user('salma')
    review.appoint(staff, salma, [TEXT])
    return salma


def rgb(colour: str) -> tuple:
    return tuple(int(colour[k:k + 2], 16) for k in (1, 3, 5))


def rows_of(img: Image.Image, colour: str, x: int = LEFT + 10) -> list[int]:
    """The rows where the column at `x` is in this colour: where a box of it is drawn."""
    return [y for y in range(img.height) if img.getpixel((x, y)) == rgb(colour)]


def ink_across(img: Image.Image, top: int, bottom: int) -> tuple[int, int]:
    """From where to where across the dark ink of these rows reaches (the labels are lighter)."""
    dark = img.crop((0, top, img.width, bottom)).convert('L').point(lambda v: 255 if v < 80 else 0)
    box = dark.getbbox()
    return box[0], box[2]


def unofficial_text() -> Text:
    """A text whose Bulletin issue the site does not know, no topic's words in its title."""
    text = Text.objects.create(akn_uri='/akn/ma/act/decret/2-26-50', type='decree', number='2-26-50',
                               title_ar='مرسوم رقم 2.26.50 بتحديد شيء', first_published_page=40)
    Version.objects.create(text=text, language='ar', valid_from=date(2026, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
    return text


def test_an_assembled_version_or_an_unknown_issue_is_said_and_no_page(reviewer, lease):
    assert cards.content(path=PATH)['source'] == PRINTED
    assembled = Version.objects.create(text=lease, language='ar', valid_from=date(2020, 1, 1),
                                       consolidation=Consolidation.MACHINE)
    Article.objects.create(version=assembled, order=1, label='المادة 34', number='34', eid='art_34', body='نص.')
    assert cards.content(path=PATH)['source'] == ASSEMBLED
    unofficial_text()
    c = cards.content(path='/ma/decret/2-26-50')
    assert (c['kind'], c['source'], c['date'], c['topic'], c['headline']) == ('text', ASSEMBLED, '', None, '')


@pytest.mark.needs('fribidi')
def test_a_text_no_topic_holds_carries_no_topics_colour(reviewer):
    unofficial_text()
    bar = (RIGHT - 60, 44 + 64 + 84 + 64 - 26)       # the topic's stripe under the head, at its right
    housing = cards.draw(cards.content(path=TEXT), 'post')
    plain = cards.draw(cards.content(path='/ma/decret/2-26-50'), 'post')
    assert housing.getpixel(bar) == rgb(cards.TOPICS['housing']) and plain.getpixel(bar) == rgb(cards.SHEET)


def test_a_question_in_a_topic_names_the_topic_and_the_article_it_started_from(reviewer):
    place = Discussion.objects.create(path='/talk/housing', text_path='/talk/housing')
    asker, answerer = make_user('karim'), make_user('nadia')
    found = {}
    for about in (PATH, f'{TEXT}/art_99', ''):
        q = Contribution.objects.create(discussion=place, author=asker, kind='question', title='الزيادة في الكراء',
                                        body='واش يقدر يزيد 15%؟', about=about)
        a = Contribution.objects.create(discussion=place, author=answerer, kind='comment', parent=q, body='لا، 8% فقط.')
        found[about] = cards.content(answer=a.pk)
        assert found[about]['link'] == f'/talk/housing/{q.pk}'
    assert {k: v for k, v in found[PATH].items() if k != 'link'} == {
        'kind': 'answer', 'question': 'الزيادة في الكراء — واش يقدر يزيد 15%؟', 'answer': 'لا، 8% فقط.', 'label': 'سؤال',
        'name': 'السكن والكراء', 'source': PRINTED}
    # An article gone since, or none: the topic's discussion is the source.
    assert found[f'{TEXT}/art_99']['source'] == found['']['source'] == {'consolidated': True, 'words': 'النقاش · السكن والكراء'}


@pytest.mark.needs('fribidi')
def test_an_answer_sits_in_the_teal_of_peoples_answers(reviewer):
    place = Discussion.objects.create(path='/talk/housing', text_path='/talk/housing')
    q = Contribution.objects.create(discussion=place, author=make_user('karim'), kind='question', body='واش يقدر يزيد 15%؟')
    a = Contribution.objects.create(discussion=place, author=make_user('nadia'), kind='comment', parent=q, body='لا.')
    img = cards.draw(cards.content(answer=a.pk), 'story')
    assert img.size == (1080, 1920)
    assert len(rows_of(img, cards.TALK_WASH)) > 100 and rows_of(img, cards.PEOPLE_WASH) == []


@pytest.mark.needs('fribidi')
def test_the_answers_box_holds_the_answers_words_and_not_the_questions(reviewer):
    place = Discussion.objects.create(path='/talk/housing', text_path='/talk/housing')
    asker, answerer = make_user('karim'), make_user('nadia')

    def box(question: str, answer: str) -> tuple:
        """The teal box of the card of this answer to this question: where it is, and what is drawn in it."""
        q = Contribution.objects.create(discussion=place, author=asker, kind='question', body=question)
        a = Contribution.objects.create(discussion=place, author=answerer, kind='comment', parent=q, body=answer)
        img = cards.draw(cards.content(answer=a.pk), 'post')
        rows = rows_of(img, cards.TALK_WASH)
        return rows[0], rows[-1], img.crop((0, rows[0], img.width, rows[-1] + 1)).tobytes()

    first = box('واش يقدر يزيد 15%؟', 'لا، 8% فقط.')
    # Another answer to the same question: the same box, other words in it.
    other_answer = box('واش يقدر يزيد 15%؟', 'نعم، 10% للمحل.')
    assert other_answer[:2] == first[:2] and other_answer[2] != first[2]
    # Another question, one line as well, with the same answer: the box is drawn the same.
    assert box('واش يقدر يزيد 20%؟', 'لا، 8% فقط.') == first


@pytest.mark.needs('fribidi')
def test_a_french_explanation_reads_from_the_left_and_an_arabic_one_from_the_right(reviewer):
    said = {'fr': 'Huit au plus.', 'ar': 'ثمانية على الأكثر.'}
    across = {}
    for register, words in said.items():
        explanations.save(reviewer, PATH, register, words)
        c = cards.content(path=PATH, register=register)
        assert c['explained'] == {'body': words, 'register': register}
        img = cards.draw(c, 'post')
        box = rows_of(img, cards.PEOPLE_WASH)
        across[register] = ink_across(img, box[0], box[-1])
    assert across['fr'][0] < LEFT + 60 and across['fr'][1] < 540
    assert across['ar'][0] > 540 and across['ar'][1] > RIGHT - 60


@pytest.mark.needs('fribidi')
def test_a_word_wider_than_the_column_or_an_empty_paragraph_makes_no_empty_line():
    pen = cards.Pen(Image.new('RGB', (400, 100)), 0, 200, 0)
    font = cards._font('ReadexPro.ttf', 20, 400)      # the cards' own face, as the cards wrap with it
    assert pen.wrap('x' * 60 + ' y', font, 9, rtl=False) == ['x' * 60, 'y']
    assert pen.wrap('a\n\nb', font, 9, rtl=False) == ['a', 'b']
