"""The BO's French translation edition read and kept beside the Arabic (C3)."""
from apps.corpus.services import french


def test_article_headings_and_their_numbers():
    assert french.article_number('Article premier') == '1'
    assert french.article_number('ARTICLE 12') == '12'
    assert french.article_number('Article 2 bis') == '2-bis'
    assert french.article_number('Article 7.1') == '7-1'
    m = french._ARTICLE.match('Article premier. – Au sens de la présente loi, on entend par :')
    assert m.group('head') == 'Article premier' and m.group('rest') == 'Au sens de la présente loi, on entend par :'


def test_a_texts_lines_cut_into_articles_quoted_ones_left_in_their_article():
    lines = [(1489, 'Loi n° 046-26 relative au système statistique national'), (1489, 'TITRE PREMIER'),
             (1489, 'Article premier'), (1489, 'Au sens de la présente loi, on entend par :'),
             (1489, '– Autorité publique de la statistique : le Haut-commissariat'), (1489, 'au plan ;'),
             (1490, 'Article 2'), (1490, 'L’article 5 est ainsi modifié :'), (1490, '« Article 5. – Le texte nouveau.'),
             (1490, 'Fait à Rabat, le 28 juillet 2026.')]
    articles = french.split_articles(lines)
    assert [(a['label'], a['number'], a['page']) for a in articles] == [('Article premier', '1', 1489), ('Article 2', '2', 1490)]
    assert articles[0]['body'].splitlines() == ['Au sens de la présente loi, on entend par :',
                                                '– Autorité publique de la statistique : le Haut-commissariat au plan ;']
    assert articles[0]['heading_path'] == ['TITRE PREMIER']
    assert '« Article 5. – Le texte nouveau.' in articles[1]['body'] and 'Fait à' not in articles[1]['body']


def test_a_law_is_known_by_its_own_number_not_its_dahirs():
    title = ('Dahir n° 1-25-70 du 26 rejeb 1447 (16 janvier 2026) portant promulgation de la loi organique n° 53-25 '
             'modifiant la loi organique n° 27-11')
    assert french._number_in(title) == '53-25'
    assert french._number_in("Arrêté du ministre de l'intérieur n° 503-26 du 23 ramadan 1447") == '503-26'
    assert french.clean('Haut￾commissariat\xa0') == 'Haut-commissariat '
