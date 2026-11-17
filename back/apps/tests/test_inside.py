"""A name from an address never leaves its folder, and the patterns a reader's words go through stay quick (the code
scanning's alerts on the public repository, 17 Nov 2026)."""
import time

import pytest

from apps.blog.services import posts
from apps.corpus.services.find.query import _LETTERS
from apps.corpus.services.find.typed import spelled
from apps.corpus.services.heads import cut
from apps.topics.services import kit
from apps.topics.services.kit import folders
from config.inside import inside


def test_a_name_stays_inside_its_folder(tmp_path):
    assert inside(tmp_path, 'family') == tmp_path / 'family'
    assert inside(tmp_path, 'a', 'b.xml') == tmp_path / 'a' / 'b.xml'
    for name in ('..', '../x', 'a/../../x', '/etc/passwd', '', '.'):
        assert inside(tmp_path, name) is None, name
    assert inside(f'{tmp_path}/', 'x') == tmp_path / 'x'            # the folder's own spelling does not matter
    assert inside(tmp_path / 'ab', '..', 'abc', 'x') is None        # a neighbour whose name begins alike is outside


@pytest.mark.parametrize('slug', ['..', '../blog', '../../config', '/etc', ''])
def test_a_slug_that_leaves_names_no_topic_and_no_post(slug):
    assert not folders.folder(slug).exists()
    assert kit.load(slug) is None
    assert posts.meta(slug) is None and posts.figures(slug) is None


def test_a_topic_and_a_post_are_still_found(db):
    assert kit.load('family')['hub'] and folders.folder('family').is_dir()
    assert posts.meta('minimum-wage') and posts.meta('seventy-years') == posts.meta('from-no-1')


def test_a_sitemap_or_an_edition_with_a_path_for_a_name_is_not_found(api, settings, tmp_path):
    settings.SITEMAPS_DIR = str(tmp_path)
    (tmp_path / 'sitemaps').mkdir()
    (tmp_path / 'sitemaps' / 'laws-1.xml').write_text('<urlset/>')
    (tmp_path / 'secret-1.xml').write_text('no')
    assert api.get('/sitemaps/laws-1.xml').status_code == 200
    for name in ('..%2Fsecret-1.xml', 'laws-1.xml%2F..', 'LAWS-1.xml', 'laws-123456.xml', 'a' * 30 + '-1.xml'):
        assert api.get(f'/sitemaps/{name}').status_code == 404, name
    from apps.opendata.services import editions
    assert editions.find('..') is None and editions.find('2026-11-17/..') is None and editions.find('') is None


def quick(act) -> float:
    began = time.perf_counter()
    act()
    return time.perf_counter() - began


def test_a_readers_words_are_read_quickly_whatever_they_hold():
    """Four letters with long runs of spaces between them took minutes; «ظ» and 300 spaces a fifth of a second."""
    assert quick(lambda: _LETTERS.match(('ا' + ' ' * 75) * 4 + 'x')) < 0.05
    assert quick(lambda: spelled('ظ' + ' ' * 300 + 'x')) < 0.05
    assert quick(lambda: spelled('ظ' + ' ' * 90 + '.' + ' ' * 90 + 'ش' + ' ' * 90 + 'x')) < 0.05
    assert quick(lambda: spelled(('ق' + ' ' * 148) * 2 + 'x')) < 0.05
    assert quick(lambda: cut(' ' * 5000 + 'x', 4000)) < 0.05


def test_the_short_forms_read_as_before():
    for said in ('ق ل ع', 'ق.ل.ع', 'ق . ل . ع', 'ق.ل.ع.', 'م  ج', 'ق ل ع ا م'):
        assert _LETTERS.match(said), said
    for said in ('قلع', 'ق..ل', 'ق ل ع ا م ن', 'q l', 'ق ل ع x'):
        assert not _LETTERS.match(said), said
    assert spelled('ق 31.08') == 'القانون رقم 31.08' and spelled('ق. 31.08') == 'القانون رقم 31.08'
    assert spelled('ظ.ش 1.58.376') == 'الظهير الشريف رقم 1.58.376' and spelled('ظ ش. 1.58.376') == 'الظهير الشريف رقم 1.58.376'
    assert spelled('ظ 1.58.376') == 'الظهير الشريف رقم 1.58.376' and spelled('ق31.08') == 'ق31.08'
    assert spelled('المادة 225 المكررة') == 'المادة 225 مكررة'


def test_a_line_is_cut_on_a_whole_word():
    assert cut('one two three', 20) == 'one two three'
    assert cut('one two three', 9) == 'one two…' and cut('one two three', 8) == 'one two…' and cut('one two three', 7) == 'one…'
    assert cut('onetwothree', 5) == 'onetw…' and cut(' one', 2) == '…'
