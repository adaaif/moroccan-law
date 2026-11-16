"""B6 and B7 of the search plan without a model or a database: Darija in Latin letters spelled the way the law writes
its words, a long article cut into pieces under its header, and two rankings fused."""
from apps.search.services import meaning, spelling


def test_a_long_article_is_cut_between_sentences_each_piece_under_its_header():
    count = lambda s: len(s.split())          # a word a token, for the test
    short = meaning.pieces('النص › المادة 1', 'جملة قصيرة.', count)
    assert short == ['النص › المادة 1\nجملة قصيرة.']
    body = ' '.join(f'جملة رقم {i} فيها كلمات كثيرة جدا.' for i in range(300))
    parts = meaning.pieces('النص › المادة 2', body, count)
    assert len(parts) > 1 and all(p.startswith('النص › المادة 2\n') for p in parts)
    assert all(count(p) <= meaning.PIECE_TOKENS + 20 for p in parts)


def test_an_annex_is_read_only_to_its_first_characters_cut_between_words():
    from apps.search.management.commands.embed_passages import _first
    annex = ' '.join(['جدول'] * 5000)
    assert _first(annex, 0) == annex and _first('قصير', 8000) == 'قصير'
    first = _first(annex, 8000)
    assert len(first) <= 8000 and first.endswith('جدول') and annex.startswith(first)


def test_two_rankings_fuse_and_a_nearest_article_joins_the_hits():
    words = [(1, 'article', '/ma/loi/1', '/ma/loi/1/art_1', 'law', 9.0), (2, 'text', '/ma/loi/2', '/ma/loi/2', 'law', 8.0)]
    near = [('/ma/loi/3/art_5', '/ma/loi/3', 0.81), ('/ma/loi/1/art_1', '/ma/loi/1', 0.80)]
    fused = meaning.fuse(words, near, {'/ma/loi/3/art_5': (7, '/ma/loi/3', 'decree'), '/ma/loi/1/art_1': (1, '/ma/loi/1', 'law')})
    assert [f[0] for f in fused] == [1, 7, 2]           # found both ways first
    assert fused[1][:5] == (7, 'article', '/ma/loi/3', '/ma/loi/3/art_5', 'decree')


def test_darija_in_latin_letters_is_spelled_as_the_law_writes(monkeypatch):
    import ma_law
    monkeypatch.setattr(spelling, 'term_counts', lambda: {ma_law.stem('قانون'): 900})      # the index counts stems
    monkeypatch.setattr(spelling, 'french_words', lambda: {'permis': 300})
    spelling.word.cache_clear()
    assert spelling.word('9anoun') == 'قانون'
    assert spelling.word('l9anoun') == 'القانون'
    assert spelling.word('wach') == 'واش' and spelling.word('permis') == 'permis'
    assert spelling.arabizi('wach mol dar y9der ykhrjni') is not None
    assert spelling.arabizi('délai de préavis') is None


def test_the_topics_darija_in_latin_letters_is_read_without_a_digit_and_a_mixed_question_is_left_alone(monkeypatch):
    """UX7 of the phone-test review: «kra dyal dar» opened a Guelmim governor's order; every word of it is the
    topics' Darija. «vignette tomobil chhal» is understood by its French word, as before."""
    monkeypatch.setattr(spelling, 'term_counts', dict)
    monkeypatch.setattr(spelling, 'french_words', lambda: {'vignette': 300})
    spelling.word.cache_clear()
    assert spelling.arabizi('kra dyal dar') == 'الكراء ديال الدار'
    assert spelling.arabizi('Tredouni mn lkhedma') == 'طردوني من الخدمة'
    assert spelling.arabizi('tlaq') == 'الطلاق'
    assert spelling.arabizi('vignette tomobil chhal') is None
    assert spelling.arabizi('fusion cnops cnss date') is None


def test_a_weighted_sum_leans_on_meaning_when_told():
    words = [(1, 'article', '/a', '/a/art_1', 'law', 10.0), (2, 'article', '/b', '/b/art_1', 'law', 2.0)]
    near = [('/b/art_1', '/b', 0.9), ('/a/art_1', '/a', 0.3)]
    entries = {'/a/art_1': (1, '/a', 'law'), '/b/art_1': (2, '/b', 'law')}
    assert [f[0] for f in meaning.fuse(words, near, entries, 0.8)] == [1, 2]     # BM25's word mostly
    assert [f[0] for f in meaning.fuse(words, near, entries, 0.2)] == [2, 1]     # meaning's mostly


def test_a_word_one_slip_away_is_put_right(monkeypatch):
    import ma_law
    counts = {ma_law.stem(ma_law.fold(w)): n for w, n in [('الطلاق', 900), ('الغلاف', 5000), ('الحضانة', 400), ('الحمانة', 30),
                                                          ('الشقاق', 60), ('حاجة', 80), ('مرجع', 300), ('شريط', 40),
                                                          ('نقطة', 500), ('لا', 1000)]}
    monkeypatch.setattr(spelling, 'term_counts', lambda: counts)
    # ق for ف is a slip people make: it beats a commoner word one change away.
    assert spelling.correct('الطلاف') == 'الطلاق'
    assert spelling.correct('الحظانة') == 'الحضانه'
    assert spelling.correct('الطلاق') is None              # the index's own word
    assert spelling.corrected('الطلاف للشقاق') == 'الطلاق للشقاق'
    # Several words the law never uses are Darija, not slips: «نرجع» is not «مرجع», nor «شريتها» «شريطها».
    assert spelling.corrected('نرجع حاجة شريتها') is None
    assert spelling.corrected('لـ0 نقطة') is None           # a word with a digit is no slip («لـ0» was made «لا»)
