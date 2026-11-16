"""`manage.py blog_figures <slug>`: a post's figures counted again from the database and kept beside its meta, the
file the site then serves. The posts' folder is a temporary one here: the real posts' kept figures are never touched."""
import json
from datetime import date

import pytest
import yaml
from django.core.management import CommandError, call_command

from apps.blog.services import posts
from apps.corpus.models import Consolidation, TextType
from apps.sources.models import Edition

from .rows import issue, page, text, version

pytestmark = pytest.mark.django_db


@pytest.fixture
def folder(tmp_path, monkeypatch):
    """The posts' folder, empty; a post's meta.yaml written into it as the command reads it."""
    monkeypatch.setattr(posts, 'ROOT', tmp_path)
    posts.meta.cache_clear()
    posts.figures.cache_clear()

    def write(slug, meta):
        (tmp_path / slug).mkdir()
        (tmp_path / slug / 'meta.yaml').write_text(yaml.safe_dump(meta, allow_unicode=True), encoding='utf-8')
        return tmp_path / slug
    yield write
    # The next test reads the real posts again, not this folder's.
    posts.meta.cache_clear()
    posts.figures.cache_clear()


def test_a_recount_keeps_the_grand_viziers_figures_beside_the_post_and_the_site_serves_them_at_once(folder, capsys):
    """«محمد المقري»: each text whose closing as published names him, once, by its year and kind; a year's Resident General
    is the one most named, the first a closing names counting; the years between run on with nothing."""
    where = folder('mokri', {'name_re': 'المقري|المقرى', 'clip': {'issue': 1000, 'page': 3},
                             'residents': [{'key': 'saint', 're': 'سان'}, {'key': 'steeg', 're': 'ستيغ'}],
                             'signed': [{'year': 1925, 'issue': 650, 'page': 12, 'akn': '/akn/ma/act/dahir/1925-1'}]})
    (where / 'figures.json').write_text('{"total": 0}\n', encoding='utf-8')
    assert posts.figures('mokri') == {'total': 0}          # what the site served until the recount

    y25, y26, y28 = issue(650, date(1925, 3, 3)), issue(700, date(1926, 1, 5)), issue(800, date(1928, 6, 1))
    page(y25, 2, 12)
    # The last is created first: the first and the last are the Bulletin's order, not the rows'. Its closing names no
    # Resident: its year has none.
    last = text('/akn/ma/act/dahir/1929-1', TextType.DAHIR, issue(900, date(1929, 2, 1)), title='ظهير  شريف\nفي التسجيل')
    version(last, closing='سجل … محمد المقري')
    version(text('/akn/ma/act/arrete/1928-9', TextType.ORDER, y28), closing='وكتب بالرباط … محمد المقرى. اطلع عليه … لوسيان سان')
    first = text('/akn/ma/act/dahir/1925-1', TextType.DAHIR, y25, title='ظهير شريف')
    version(first, closing='سجل … الصدر الأعظم محمد المقري. الإقامة العامة ستيغ')
    # A second Arabic version as published of the same text is still one text.
    version(first, closing='سجل … الصدر الأعظم محمد المقري. الإقامة العامة ستيغ', valid_from=date(1925, 4, 1))
    # 1926: two closings name both Residents (the first in the meta's list counts), one names Steeg alone.
    for n, kind, closing in ((1, TextType.DECISION, 'المقري … سان … ستيغ'), (2, TextType.ORDER, 'المقري سان ستيغ'),
                             (3, TextType.ORDER, 'المقري ستيغ')):
        version(text(f'/akn/ma/act/arrete/1926-{n}', kind, y26), closing=closing)
    # Not his: another name as published; his name only in a machine's version, or in a French one; the French edition.
    other = text('/akn/ma/act/dahir/1926-4', TextType.DAHIR, y26)
    version(other, closing='محمد بن فلان')
    version(other, closing='المقري', consolidation=Consolidation.MACHINE)
    version(other, closing='المقري', language='fr', valid_from=date(1926, 2, 1))
    version(text('/akn/ma/act/dahir/1926-5', TextType.DAHIR, issue(700, date(1926, 1, 5), edition=Edition.TRANSLATION_FR)),
            closing='المقري')

    call_command('blog_figures', 'mokri')

    kept = where / 'figures.json'
    expected = {
        'years': [{'year': 1925, 'dahir': 1, 'order': 0, 'other': 0, 'resident': 'steeg'},
                  {'year': 1926, 'dahir': 0, 'order': 2, 'other': 1, 'resident': 'saint'},
                  {'year': 1927, 'dahir': 0, 'order': 0, 'other': 0, 'resident': None},
                  {'year': 1928, 'dahir': 0, 'order': 1, 'other': 0, 'resident': 'saint'},
                  {'year': 1929, 'dahir': 1, 'order': 0, 'other': 0, 'resident': None}],
        'total': 6,
        'first': {'date': '1925-03-03', 'title': 'ظهير شريف', 'path': '/ma/dahir/1925-1'},
        'last': {'date': '1929-02-01', 'title': 'ظهير شريف في التسجيل', 'path': '/ma/dahir/1929-1'},
        'texts': {'clip': {'path': None},
                  's-1925': {'issue': '650', 'edition': 'general_ar', 'published': '1925-03-03', 'page': 12,
                             'viewer': f'/pages/{y25.document_id}/2', 'path': '/ma/dahir/1925-1'}},
    }
    raw = kept.read_text(encoding='utf-8')
    assert json.loads(raw) == expected
    # Kept compact, its Arabic as letters, one line.
    assert raw == json.dumps(json.loads(raw), ensure_ascii=False, separators=(',', ':')) + '\n'
    assert posts.figures('mokri') == expected
    assert capsys.readouterr().out == f'{kept}: \n'


def test_a_recount_prints_the_totals_and_a_copy_issues_words_are_not_a_year_of_their_own(folder, capsys):
    """The first post: the command prints its totals with their thousands; an issue whose file is another's (a copy) is
    no year of the table, though its text's words are read."""
    folder('from-no-1', {'span': [1914, 1915]})
    no82 = issue(82, date(1914, 11, 23), pages=1200, first_page=1)
    version(text('/akn/ma/act/dahir/1914-1', TextType.DAHIR, no82), 'نص من ثلاث')
    copy = issue(83, date(1915, 1, 4), copy_of=no82)
    version(text('/akn/ma/act/dahir/1915-1', TextType.DAHIR, copy), 'كلمتان هنا')

    call_command('blog_figures', 'from-no-1')

    f = posts.figures('from-no-1')
    assert f['years'] == [[1914, 1, 0, 1200, 1, 3, 1, 0, 0, 0, 0, 0, 0, 0, 1200]] and f['copies'] == {'1915': 1}
    assert capsys.readouterr().out == (f"{posts.ROOT / 'from-no-1' / 'figures.json'}: issues 1, bis 0, pages 1,200, texts 1, words 3, "
                                       'dahir 1, law 0, decree 0, order 0, decision 0, other 0, report_issues 0, report_pages 0\n')


def test_a_post_without_its_meta_is_not_counted(folder):
    with pytest.raises(CommandError, match=r"No post 'mokri' to count\."):
        call_command('blog_figures', 'mokri')
    assert not (posts.ROOT / 'mokri').exists()
