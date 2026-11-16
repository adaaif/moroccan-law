"""B7 of the search plan: an article longer than the model reads (512 tokens) is embedded in pieces of about 380 tokens,
each under its header, so its later words are found by meaning too. The tokenizer is set to cut what it reads at 512
tokens, as the model needs: counted through it, a long article measured 512 and was never cut, its words past the first
512 tokens never embedded."""
from datetime import date
from io import StringIO

import numpy as np
import pytest
from django.core.management import call_command

from apps.search.models import SearchEntry, SearchPassage
from apps.search.services.meaning import MAX_TOKENS, PIECE_TOKENS, Encoder
from apps.search.tests.model import stored

pytestmark = pytest.mark.django_db


def test_a_text_is_counted_whole_though_the_model_reads_its_first_512_tokens(model):
    enc = Encoder()
    assert enc.count('الكراء الإفراغ') == 3                 # the start token and a token a word
    # 1,001 tokens, and the start token of the piece read apart.
    assert enc.count(' '.join(['كلمة'] * 1000)) == 1002 > MAX_TOKENS


def test_an_article_longer_than_the_model_reads_is_embedded_in_pieces_under_its_header(model):
    sentence = 'يؤدي المكتري الكراء في أجله المحدد في العقد دون تأخير.'            # ten words
    body = ' '.join([sentence] * 120)                                          # 1,200 words
    SearchEntry.objects.create(kind='text', text_path='/ma/loi/67-12', path='/ma/loi/67-12', text_type='law',
                               name={'ar': 'قانون الكراء'})
    SearchEntry.objects.create(kind='article', text_path='/ma/loi/67-12', path='/ma/loi/67-12/art_3', label='المادة 3',
                               body=body, text_type='law', version_from=date(2013, 11, 28), year=2013)
    call_command('embed_passages', stdout=StringIO())
    parts = list(SearchPassage.objects.filter(path='/ma/loi/67-12/art_3').order_by('part').values_list('part', 'lang'))
    assert parts == [(k, 'ar') for k in range(4)]
    # Each piece is the header and whole sentences, under the size of a piece: nothing past the model's reading.
    enc = Encoder()
    pieces = [f'قانون الكراء › المادة 3\n{" ".join([sentence] * n)}' for n in (37, 37, 37, 9)]
    assert all(enc.count(p) <= PIECE_TOKENS + 10 < MAX_TOKENS for p in pieces)
    for (part, _), piece in zip(parts, pieces):
        assert np.allclose(stored(SearchPassage.objects.get(path='/ma/loi/67-12/art_3', part=part)), enc.encode([piece])[0],
                           atol=1e-3)
