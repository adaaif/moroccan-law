"""What a person read on the French pages is put right at every load of a text's French (Q6 of the road plan)."""
from apps.translations.management.commands import load_bo_french


def test_french_read_on_the_page_is_put_right_and_a_table_read_whole_replaces_its_body(tmp_path, monkeypatch):
    (tmp_path / 'road_fr.yaml').write_text("""
language: fr
text: /ma/loi/52-05
fixes:
  - {arts: [221], wrong: 'l. immédiatement', right: '1. immédiatement'}
  - {arts: [221], wrong: 'pas là', right: 'là'}
bodies:
  '99': |
    | 01 | Homicide | 14 |
""")
    monkeypatch.setattr(load_bo_french, 'FIXES', tmp_path)
    articles = [{'number': '221', 'body': 'l. immédiatement, entre les mains'}, {'number': '99', 'body': '14 02 Homicide'}]
    missed = load_bo_french.read_on_pages('/ma/loi/52-05', articles)
    assert articles[0]['body'] == '1. immédiatement, entre les mains'
    assert articles[1]['body'] == '| 01 | Homicide | 14 |'
    assert missed == ['road_fr.yaml: art. 221 «pas là»']
    assert load_bo_french.read_on_pages('/ma/loi/17-99', [{'number': '1', 'body': 'x'}]) == []
