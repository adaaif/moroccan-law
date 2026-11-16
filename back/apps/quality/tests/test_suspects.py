"""FX9 of the mended-Bulletin review: words a reading may have wrong, flagged for free and confirmed by a person."""
from collections import Counter
from datetime import UTC, date, datetime

import pytest

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.quality.models import Correction, Suspect
from apps.discussion.tests.conftest import make_user
from apps.quality.services import suspects
from apps.sources.models import Document, Issue, OcrRun, Page

pytestmark = pytest.mark.django_db


def page_of(text, number=30):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'h{number}', path=f'{number}.pdf',
                                  mime='application/pdf', bytes=1, language='ar', page_count=8,
                                  fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    Issue.objects.create(edition='general_ar', number=number, date=date(1913, 11, 28), document=doc,
                         first_page_number=221)
    return Page.objects.create(document=doc, index=7, printed_number=228, kind='scan', text=text)


def test_words_one_shape_apart_differ_by_their_dots():
    assert suspects.shape('الحيزة') == suspects.shape('الخبزة')
    assert suspects.shape('يمنع') != suspects.shape('يمنح')          # a real word for another: no shape to tell


def test_a_word_seen_once_beside_a_common_neighbour_is_flagged():
    page = page_of('الخبز ٠٫٣٠ الحيزة ٠٫٣٥ السكر')
    counts = Counter({'الحيزه': 1, 'الخبزه': 400, 'السكر': 900, 'الخبز': 300})
    [s] = suspects.rare([page], counts, suspects.neighbours(counts))
    assert (s.word, s.suggestion, s.signal) == ('الحيزة', 'الخبزه', 'rare')


def test_glued_latin_letters_are_flagged():
    page = page_of('اوائل شعباeffective... 1329')
    [s] = suspects.glued([page])
    assert s.word.startswith('شعباeffective') and s.signal == 'glued'
    # A failed attempt's run of letters is kept to its column, and so are the words around it.
    page = page_of('اوائل شهر ' + 'شعبا' + 'e' * 300 + ' سنة 1329 هجرية', number=31)
    [s] = suspects.glued([page])
    assert (len(s.word), len(s.context), s.context[:16]) == (120, 300, 'اوائل شهر شعباee')


def test_a_copy_that_reads_other_dots_flags_the_word():
    page = page_of('المعلم البنائى ٥ بساسط الحدام ٢٫٥٠')
    OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='copy 31', text='المعلم البنائى ٥ بساسط الخدام ٢٫٥٠')
    [s] = suspects.copies()
    assert (s.word, s.suggestion, s.signal) == ('الحدام', 'الخدام', 'copies')


def test_confirming_puts_the_word_right_in_the_page_and_its_articles():
    page = page_of('المعلم البنائى ٥ بساسط الحدام ٢٫٥٠ التجار ٧٫٥٠')
    text = Text.objects.create(akn_uri='/akn/ma/act/texte/1913-11-28/bo30-5', type='other', title_ar='بيان',
                               first_published_in=page.document.issue)
    v = Version.objects.create(text=text, language='ar', valid_from=date(1913, 11, 28), source_pages='228-228',
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='', eid='art_1', body='بساسط الحدام ٢٫٥٠ التجار')
    s = Suspect.objects.create(page=page, word='الحدام', suggestion='الخدام', context='٥ بساسط الحدام ٢٫٥٠ التجار',
                               signal='rare')
    assert suspects.confirm(s) == 1
    page.refresh_from_db()
    assert 'الخدام ٢٫٥٠' in page.text
    assert Article.objects.get().body == 'بساسط الخدام ٢٫٥٠ التجار'
    assert Correction.objects.filter(path='/bo/general_ar/30#p7').exists()
    assert Suspect.objects.get().status == 'confirmed'


def test_a_suspect_whose_word_is_gone_leaves_the_queue():
    page = page_of('المعلم البنائى ٥ بساسط الخدام ٢٫٥٠')
    Suspect.objects.create(page=page, word='الحدام', suggestion='الخدام', signal='rare')
    Suspect.objects.create(page=page, word='البنائى', suggestion='البنائي', signal='rare')
    assert suspects.prune() == 1
    assert list(Suspect.objects.values_list('word', flat=True)) == ['البنائى']


def bo_page(number, year, text, *, edition='general_ar', copy_of=None, index=0, path=None):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'{edition}{number}', mime='application/pdf',
                                  path=path or f'{edition}/{number}.pdf', bytes=1, language='ar', page_count=1,
                                  fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    Issue.objects.create(edition=edition, number=number, date=date(year, 3, 1), document=doc, copy_of=copy_of)
    return Page.objects.create(document=doc, index=index, printed_number=index + 1, kind='scan', text=text)


def test_the_vocabulary_counts_the_arabic_bulletins_words_folded():
    bo_page(1, 1913, 'الأولى إقلِيم الأولى ٣')                              # a vowel mark is no break in a word
    bo_page(2, 1913, 'إقليم الإقليم', edition='translation_fr')            # the French edition's Arabic is not counted
    assert suspects.vocabulary() == Counter({'الاولي': 2, 'اقليم': 1})
    assert suspects.vocabulary(Page.objects.filter(document__issue__number=2)) == Counter({'اقليم': 1, 'الاقليم': 1})


def test_a_rare_word_takes_its_most_common_neighbour_two_letters_apart_at_most():
    page = page_of('الحيزة جحخ ببب رزر سشس صضص')
    counts = Counter({'الحيزه': 1, 'الخبزه': 400, 'الجيزه': 150,      # two dots apart and more common than one dot apart
                      'جحخ': 1, 'خجح': 500,                              # three letters apart
                      'ببب': 1, 'تتت': 900, 'ننن': 800, 'ثثث': 700, 'ببن': 600,   # the fourth neighbour is not asked
                      'رزر': 2, 'ررر': 900,                              # seen twice: not rare
                      'سشس': 1, 'سسس': 99,                               # not a hundred times as often
                      'صضص': 1, 'صصص': 100})
    found = suspects.rare([page], counts, suspects.neighbours(counts))
    # One suspect a word, with its most common neighbour.
    assert [(s.word, s.suggestion, s.evidence) for s in found] == [('الحيزة', 'الخبزه', {'seen': 1, 'neighbour': 400}),
                                                                  ('صضص', 'صصص', {'seen': 1, 'neighbour': 100})]
    assert found[0].context == 'الحيزة جحخ ببب رزر سشس'


def test_a_neighbour_is_a_common_word_of_three_letters_or_more():
    common = suspects.neighbours(Counter({'الخبزه': 60, 'الجيزه': 49, 'نبت': 50, 'من': 900}))
    assert dict(common) == {suspects.shape('الخبزه'): [('الخبزه', 60)], suspects.shape('نبت'): [('نبت', 50)]}


def test_copies_vote_for_the_dots_they_read():
    page = page_of('المعلم البنائى ٥ بساسط الحدام ٢٫٥٠')
    for variant, text in (('copy 31', 'المعلم البنائى ٥ بسائط الخدام ٢٫٥٠'), ('copy 32', 'المعلم البنائى ٥ بساسط الخدام ٢٫٥٠'),
                          ('copy 33', 'المعلم البنائى ٥ بساسط الجدام ٢٫٥٠'), ('copy 34', ''),
                          # The page's own readings are no copies, however many.
                          ('page-1596', 'المعلم البنائى ٥ بساسط الحذام ٢٫٥٠'),
                          ('page-3192', 'المعلم البنائى ٥ بساسط الحذام ٢٫٥٠'),
                          ('columns-3192', 'المعلم البنائى ٥ بساسط الحذام ٢٫٥٠')):
        OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant=variant, text=text)
    # «بسائط» is another shape: no dots to vote on.
    assert [(s.word, s.suggestion, s.evidence) for s in suspects.copies()] == [('الحدام', 'الخدام', {'readings': 2})]


class Tesseract:
    """Tesseract as `suspects.tesseract` runs it: each call kept with its arguments (the image's temporary place left
    out) and the size of the image it was given; it prints its reading on stdout."""

    def __init__(self, reading):
        import subprocess
        self.reading, self.calls, self.run = reading, [], subprocess.run

    def __call__(self, args, **kw):
        import subprocess

        from PIL import Image
        if args[0] != 'tesseract':
            return self.run(args, **kw)
        with Image.open(args[1]) as image:
            self.calls.append({'args': [args[0], *args[2:]], 'size': image.size, 'format': image.format, 'options': kw})
        return subprocess.CompletedProcess(args, 0, stdout=self.reading + '\n', stderr='')


def scanned(settings, tmp_path, monkeypatch, reading, number=1925, year=1925, text=''):
    """A scanned page of the Bulletin as a real image-only PDF under the corpus folder, and Tesseract's reading of it."""
    import subprocess

    from apps.translations.tests.files import scan_pdf
    settings.CORPUS_DIR = tmp_path
    scan_pdf(tmp_path / 'issues' / f'BO_{number}.pdf', ['columns'])
    page = bo_page(number, year, text, path=f'issues/BO_{number}.pdf')
    fake = Tesseract(reading)
    monkeypatch.setattr(subprocess, 'run', fake)
    return page, fake


def test_tesseract_flags_a_rare_word_it_reads_with_the_dots_of_a_common_one(settings, tmp_path, monkeypatch):
    page, fake = scanned(settings, tmp_path, monkeypatch, 'قرار الخبزة السكر الجيزة الحليب ثمن بيت كلب بثن بن',
                         text='قرار الحيزة السكر الحيزة الحليب ثمن نبت كتب نتن ثن')
    counts = Counter({'الحيزه': 2, 'الخبزه': 50, 'الجيزه': 49,     # common enough at fifty, not at 49
                      'نبت': 3, 'بيت': 900,                            # three times in the Bulletin: not rare
                      'كلب': 900,                                      # another shape
                      'نتن': 1, 'بثن': 80, 'بن': 900})                 # «ثن»: two letters, no word to judge
    found = suspects.tesseract([page], counts)
    assert [(s.word, s.suggestion, s.signal, s.context) for s in found] == [
        ('الحيزة', 'الخبزة', 'tesseract', 'قرار الحيزة السكر الحيزة الحليب ثمن'),
        ('نتن', 'بثن', 'tesseract', 'الحليب ثمن نبت كتب نتن ثن')]
    assert fake.calls == [{'args': ['tesseract', 'stdout', '-l', 'ara', '--psm', '3'], 'size': (2000, 2800),
                           'format': 'PNG', 'options': {'capture_output': True, 'text': True, 'timeout': 300}}]


def test_flag_suspects_counts_each_signal_on_the_years_asked_and_keeps_them_on_write(capsys):
    from django.core.management import call_command
    bo_page(1960, 1960, 'الخبزة ' * 150 + 'الجيزة')                # counted, never flagged: after 1955
    bo_page(1912, 1912, 'شعباeffective')                                # before 1913
    bo_page(100, 1914, 'شعباeffective', edition='translation_fr')
    cover = bo_page(610, 1925, 'الخبزة')
    bo_page(611, 1925, 'شعباeffective', copy_of=Issue.objects.get(pk=cover.document.issue.pk))   # a copy of 610
    words = ' '.join(f'كلمة{x}xyz' for x in ('ab', 'cd', 'ef', 'gh', 'ij', 'kl'))
    page = bo_page(30, 1914, f'المعلم البنائى بساسط الحيزة التجار والصناع والفلاحين بالمدينة {words}')
    OcrRun.objects.create(page=page, engine='claude-haiku-5-5', variant='copy 31', text=page.text.replace('بساسط', 'بشاسط'))
    call_command('flag_suspects')
    out = capsys.readouterr().out.splitlines()
    assert out[:2] == ['counting every word of the Bulletin…', '8 words flagged: glued 6, rare 1, copies 1']
    assert out[2:4] == ['  rare: «الحيزة» → «الخبزه»  …المعلم البنائى بساسط الحيزة التجار والصناع والفلاحين بالمدينة…',
                        # Each example's words around it cut at 70 letters.
                        '  glued: «كلمةabxyz» → «»  …التجار والصناع والفلاحين بالمدينة كلمةabxyz كلمةcdxyz كلمةefxyz كلمةgh…']
    assert len(out) == 2 + 1 + 5 + 1 and out[-1] == '  copies: «بساسط» → «بشاسط»  …المعلم البنائى بساسط الحيزة التجار والصناع والفلاحين…'
    assert not Suspect.objects.exists()                                  # a dry run
    call_command('flag_suspects', '--write', '--signals', 'glued,rare')
    call_command('flag_suspects', '--write', '--signals', 'glued')        # again: nothing twice
    assert capsys.readouterr().out.splitlines()[-1] == '7 open in the review queue'
    assert {(s.page_id, s.signal) for s in Suspect.objects.all()} == {(page.pk, 'glued'), (page.pk, 'rare')}
    call_command('flag_suspects', '--signals', 'glued', '--from', '1912', '--to', '1912')
    assert capsys.readouterr().out.splitlines()[0] == '1 words flagged: glued 1'


def test_flag_suspects_reads_pages_with_tesseract_when_asked(settings, tmp_path, monkeypatch, capsys):
    import subprocess

    from django.core.management import call_command

    from apps.translations.tests.files import scan_pdf
    settings.CORPUS_DIR = tmp_path
    bo_page(1960, 1960, 'الخبزة ' * 60)
    pages = []
    for number in (1925, 1926):
        scan_pdf(tmp_path / 'issues' / f'BO_{number}.pdf', ['columns'])
        pages.append(bo_page(number, 1925, 'قرار الحيزة السكر', path=f'issues/BO_{number}.pdf'))
    bo_page(1927, 1925, 'IV')                                     # no Arabic word to read again
    fake = Tesseract('قرار الخبزة السكر')
    monkeypatch.setattr(subprocess, 'run', fake)
    call_command('flag_suspects', '--signals', '', '--tesseract', '1')
    assert len(fake.calls) == 1                                   # as many pages as asked
    assert capsys.readouterr().out.splitlines() == [
        'counting every word of the Bulletin…', '1 words flagged: tesseract 1',
        '  tesseract: «الحيزة» → «الخبزة»  …قرار الحيزة السكر…']
    call_command('flag_suspects', '--signals', '', '--tesseract', '5', '--write')
    assert capsys.readouterr().out.splitlines()[-1] == '2 open in the review queue'
    assert {s.page_id for s in Suspect.objects.all()} == {p.pk for p in pages} and len(fake.calls) == 3


def test_confirming_puts_right_only_the_place_its_neighbours_name():
    page = page_of('الحدام ٢٫٥٠ التجار ثم بساسط الحدام ٣')
    issue = page.document.issue
    text = Text.objects.create(akn_uri='/akn/ma/act/texte/1913-11-28/bo30-5', type='other', title_ar='بيان',
                               first_published_in=issue)
    held = Version.objects.create(text=text, language='ar', valid_from=date(1913, 11, 28), source_pages='227-229',
                                  consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=held, order=1, label='', eid='art_1', body='الحدام ٢٫٥٠ التجار')
    Article.objects.create(version=held, order=2, label='', eid='art_2', body='بساسط الحدام ٣')        # other neighbours
    elsewhere = Text.objects.create(akn_uri='/akn/ma/act/texte/1913-11-28/bo30-6', type='other', title_ar='بيان',
                                    first_published_in=issue)
    other = Version.objects.create(text=elsewhere, language='ar', valid_from=date(1913, 11, 28), source_pages='221-226',
                                   consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=other, order=1, label='', eid='art_1', body='الحدام ٢٫٥٠ التجار')   # pages before
    after = Text.objects.create(akn_uri='/akn/ma/act/texte/1913-11-28/bo30-8', type='other', title_ar='بيان',
                                first_published_in=issue)
    later = Version.objects.create(text=after, language='ar', valid_from=date(1913, 11, 28), source_pages='229-240',
                                   consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=later, order=1, label='', eid='art_1', body='الحدام ٢٫٥٠ التجار')   # pages after
    unnumbered = Text.objects.create(akn_uri='/akn/ma/act/texte/1913-11-28/bo30-7', type='other', title_ar='بيان',
                                     first_published_in=issue)
    v = Version.objects.create(text=unnumbered, language='ar', valid_from=date(1913, 11, 28),
                               consolidation=Consolidation.AS_PUBLISHED)
    Article.objects.create(version=v, order=1, label='', eid='art_1', body='الحدام ٢٫٥٠ التجار')
    reviewer = make_user('reviewer', staff=True)
    # The word first in its context: nothing before it to find it by.
    s = Suspect.objects.create(page=page, word='الحدام', suggestion='الخدام', context='الحدام ٢٫٥٠ التجار ثم',
                               signal='copies')
    assert suspects.confirm(s, reviewer) == 1
    page.refresh_from_db()
    assert page.text == 'الخدام ٢٫٥٠ التجار ثم بساسط الحدام ٣'
    assert list(Article.objects.order_by('pk').values_list('body', flat=True)) == [
        'الخدام ٢٫٥٠ التجار', 'بساسط الحدام ٣', 'الحدام ٢٫٥٠ التجار', 'الحدام ٢٫٥٠ التجار', 'الحدام ٢٫٥٠ التجار']
    c = Correction.objects.get(path='/bo/general_ar/30#p7')
    assert (c.wrong, c.right, c.before, c.after, c.decided_by, c.source, c.status) == (
        'الحدام', 'الخدام', '', 'التجار', reviewer, 'page', 'applied')
    assert c.evidence == {'suspect': s.pk, 'signal': 'copies', 'read_on': str(c.decided_at.date())}
    article = Correction.objects.get(path='/ma/texte/1913-11-28/bo30-5/art_1')
    assert (article.wrong, article.right, article.before, article.after, article.source, article.status,
            article.decided_by, article.evidence) == ('الحدام', 'الخدام', '', 'التجار', 'page', 'applied', reviewer, c.evidence)
    s.refresh_from_db()
    assert (s.status, s.decided_by) == ('confirmed', reviewer) and s.decided_at is not None


def test_confirming_the_last_word_of_its_context_and_one_already_gone():
    page = page_of('بساسط الحدام')
    s = Suspect.objects.create(page=page, word='الحدام', suggestion='الخدام', context='بساسط الحدام', signal='rare')
    assert suspects.confirm(s) == 0
    assert Correction.objects.get().before == 'بساسط' and Correction.objects.get().after == ''
    # A word read right since: the page stays as it is.
    gone = page_of('بساسط الخدام', number=31)
    s = Suspect.objects.create(page=gone, word='الحدام', suggestion='الخدام', context='بساسط الحدام', signal='rare')
    suspects.confirm(s)
    gone.refresh_from_db()
    assert gone.text == 'بساسط الخدام' and Suspect.objects.get(pk=s.pk).status == 'confirmed'


def test_a_suspect_without_a_suggestion_is_put_right_by_hand():
    s = Suspect.objects.create(page=page_of('شعباeffective'), word='شعباeffective', signal='glued')
    with pytest.raises(ValueError, match='put right by hand'):
        suspects.confirm(s)
    assert Suspect.objects.get().status == 'open' and not Correction.objects.exists()
