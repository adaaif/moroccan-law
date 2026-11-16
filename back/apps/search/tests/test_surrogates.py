"""B9 of the search plan without a model or a database: a text's articles go to Haiku in groups, each answer is matched
to its article by its letter, and a search that copies the article or gives its number is dropped."""
from types import SimpleNamespace

from apps.search.services import surrogates


def _article(path, body, label='الفصل 7', text='/ma/code/doc'):
    return SimpleNamespace(path=path, text_path=text, label=label, body=body, heading_path=[], version_from=None)


def test_a_texts_articles_go_together_up_to_the_group_size():
    rows = [_article(f'/ma/code/doc/art_{i}', 'نص قصير') for i in range(8)] + [_article('/ma/loi/1/art_1', 'نص', text='/ma/loi/1')]
    groups = surrogates.groups(rows)
    assert [len(g) for g in groups] == [surrogates.GROUP_MAX, 8 - surrogates.GROUP_MAX, 1]
    long = [_article(f'/ma/code/doc/art_{i}', 'ك' * 3500) for i in range(3)]
    assert [len(g) for g in surrogates.groups(long)] == [1, 1, 1]     # 3,500 + 3,500 is over GROUP_CHARS


def test_answers_are_matched_by_letter_and_the_rules_drop_copies_and_the_articles_number():
    body = 'لا يجوز للقاصر أن يبرم عقد البيع إلا بإذن وليه'
    chunk = [_article('/ma/code/doc/art_7', body), _article('/ma/code/doc/art_8', 'نص آخر', label='الفصل 8')]
    answer = lambda key, searches: {'key': key, 'context_ar': 'سياق', 'context_fr': 'contexte', 'searches': searches,
                                    'concepts': ['الأهلية'], 'role': 'prohibition', 'facts': []}
    results = {'s00000': {'data': {'articles': [
        answer('B', ['سؤال عن الفصل الآخر']),
        answer('[A]', ['واش الصغير يقدر يبيع', 'يبرم عقد البيع إلا بإذن', 'ما حكم الفصل 7', 'wach sghir y9der ybi3',
                       'mineur vente', 'minor sale', 'darija', 'الفصل 7 من ق.ل.ع'])]}}}
    rows, dropped, missing = surrogates.rows_from({'s00000': chunk}, results)
    first, second = rows
    assert first['path'] == '/ma/code/doc/art_7' and second['path'] == '/ma/code/doc/art_8'
    kept = [s['q'] for s in first['searches']]
    assert 'يبرم عقد البيع إلا بإذن' not in kept           # four words in a row of the article
    assert 'ما حكم الفصل 7' not in kept                     # its number, outside the professional register
    assert 'الفصل 7 من ق.ل.ع' in kept                       # a professional may name it
    assert dropped == 2 and missing == 0 and first['checked'] == 'owner-provisional'
