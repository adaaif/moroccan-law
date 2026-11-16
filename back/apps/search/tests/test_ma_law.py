"""ma_law (the Rust crates through PyO3) against the vectors the Rust and WASM builds pass too."""
import json
import time
from pathlib import Path

import ma_law
import pytest

VECTORS = Path(__file__).resolve().parents[4] / 'crates' / 'vectors'


def vectors(name):
    return json.loads((VECTORS / f'{name}.json').read_text())


@pytest.mark.parametrize('v', vectors('fold'), ids=lambda v: v['in'])
def test_fold(v):
    assert ma_law.fold(v['in']) == v['out']


@pytest.mark.parametrize('v', vectors('terms'), ids=lambda v: v['in'])
def test_search_terms(v):
    assert ma_law.search_terms(v['in']) == v['out']


@pytest.mark.parametrize('v', vectors('layout'), ids=lambda v: v['in'])
def test_layout(v):
    assert [t for _, t in ma_law.layout_candidates(v['in'])] == v['out']


@pytest.mark.parametrize('v', vectors('cite'), ids=lambda v: v['in'])
def test_citations(v):
    got = ma_law.parse_query(v['in']) if v.get('query') else ma_law.parse_citations(v['in'])
    # The vectors name the fields they pin (issue_suffix only where an issue is «bis»).
    assert [{k: c[k] for k in w} for c, w in zip(got, v['want'])] == v['want'] and len(got) == len(v['want'])
    for c in got:
        assert v['in'][c['start']:c['end']] == c['raw']


@pytest.mark.parametrize('v', vectors('arabizi'), ids=lambda v: (v.get('word') or v['query'])[:40])
def test_arabizi(v):
    if 'word' in v:
        assert v['has'] in ma_law.arabizi_spellings(v['word'], 48)
    else:
        assert ma_law.is_arabizi(v['query']) == v['arabizi']


def test_a_long_word_is_spelled_at_once():
    """OP4 of the open-source audit: the spellings of a long word took seconds, minutes for 2,000 letters (every pick
    copied for each letter at each step). Its spellings stay the same, the likeliest first."""
    word = '3' + 'a' * 1999
    started = time.perf_counter()
    got = ma_law.arabizi_spellings(word, 48)
    assert time.perf_counter() - started < 5
    assert got == ['ع' + 'ا' * (1999 - n) for n in range(48)]


def test_a_long_text_with_many_matches_is_read_once():
    """OP4: a megabyte holding a common word took seconds, each match's place counted from the start of the text, and
    «ابحث في هذا النص» reads every article of a text so."""
    sentence = 'يعاقب بغرامة من 0 إلى 5 دراهم وفي حالة العود ترفع الغرامة إلى 0 درهم '
    times = 2_000_000 // len(sentence)
    text = sentence * times
    started = time.perf_counter()
    spans = ma_law.find_folded(text, '0')
    assert time.perf_counter() - started < 5
    assert len(spans) == 2 * times and all(text[a:b] == '0' for a, b in spans)
    assert ma_law.find_folded(text, 'الغرامة')[-1] == (len(text) - 19, len(text) - 12)
