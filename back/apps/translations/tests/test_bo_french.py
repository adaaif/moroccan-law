"""The French read from a scanned French BO (Q6 of the road plan): Tesseract's slips put right before the cut."""
from PIL import Image, ImageDraw

from apps.corpus.services.french import split_articles
from apps.translations.management.commands.load_bo_french import fill_gaps, parts, tidy


def test_headings_misread_by_tesseract_are_given_back():
    assert tidy('Aïticle 55') == 'Article 55'
    assert tidy('| Article 44 | .') == 'Article 44'
    assert tidy('Article 22]') == 'Article 221'
    assert tidy('ART. 4. — Tout conducteur') == 'Article 4. – Tout conducteur'
    assert tidy('ARt, 14. - Le permis') == 'Article 14. – Le permis'
    assert tidy('ART. [16. — Lorsqu’une chaussée') == 'Article 116. – Lorsqu’une chaussée'
    assert tidy('ART, 15. — la durée') == 'Article 15. – la durée'           # «ART.» opens no reference
    assert tidy('ARTICLE PREMIER. — Au sens') == 'Article premier. – Au sens'
    # A reference that opens a line stays a line.
    assert tidy('Article 3 de la loi susvisée') == 'Article 3 de la loi susvisée'
    assert tidy('Au. 5, de la') == 'Au. 5, de la'


def test_the_running_head_specks_and_capital_titles_leave_the_text():
    assert tidy("1431 (30-9-2016) N OFFICIEL N° 5878 bis—21 chaoual 3 si l'accident") == "3 si l'accident"
    assert tidy('1644 BULLETIN OFFICIEL N° 5874 7 chaoual 1431 (16-9-2010)') == ''
    assert tidy('1431 (30-9-2016)') == '' and tidy('a') == ''
    assert tidy("LES RÈGLES D'USAGE SPECIAL DES VOIES") == ''
    assert tidy('l. immédiatement, entre') == '1. immédiatement, entre'
    assert tidy("l'administration fixe") == "l'administration fixe"


def test_an_article_whose_figures_were_lost_is_found_between_its_neighbours():
    lines = [(1, x) for x in ['ARTICLE PREMIER. — Texte.', 'ART. IS. — Sont interdits sur les autoroutes.',
                              'ART. 3. — Autre.']]
    articles = split_articles([(p, tidy(x)) for p, x in lines])
    assert [a['number'] for a in articles] == ['1', '3']
    assert fill_gaps(articles) == 1
    assert [(a['number'], a['body']) for a in articles] == [('1', 'Texte.'), ('2', 'Sont interdits sur les autoroutes.'),
                                                            ('3', 'Autre.')]


def test_a_constitutions_misread_heads_and_its_preamble():
    # BO 5964 bis (the 2011 constitution): «a Article 166» (a speck), «Article $» and «Article 49» between 39 and 41.
    assert tidy('a Article 166') == 'Article 166'
    assert tidy('PREAMBULE') == 'PREAMBULE' and tidy('DE LA ROYAUTE') == ''
    lines = [(1, x) for x in ['Article premier', 'Le Maroc est une monarchie.', 'Article $',
                              "L'arabe demeure la langue officielle de l'Etat.", 'Article 3', 'La loi est suprême.']]
    articles = split_articles([(p, tidy(x)) for p, x in lines])
    assert fill_gaps(articles) == 1
    assert [(a['number'], a['body']) for a in articles][1] == ('2', "L'arabe demeure la langue officielle de l'Etat.")


def test_columns_over_a_part_printed_across_are_read_first():
    # BO 5964 bis p. 1928: the last articles in two columns, then a rule across and the Council's decision.
    page = Image.new('L', (1000, 1400), 255)
    draw = ImageDraw.Draw(page)
    for y in range(120, 900, 30):
        draw.rectangle((60, y, 470, y + 12), fill=0)
        draw.rectangle((530, y, 940, y + 12), fill=0)
    draw.rectangle((40, 960, 960, 966), fill=0)
    for y in range(1000, 1300, 30):
        draw.rectangle((60, y, 940, y + 12), fill=0)
    left, right, across = parts(page)
    assert left.size[0] < 530 and right.size[0] < 530
    assert 900 <= left.size[1] <= 966 and across.size[1] == 1400 - left.size[1]
