"""T1 of the work plan: Adala's French labour code, its Word lines joined back into paragraphs."""
from apps.translations.services.adala_fr import HEAD, _number, paragraphs


def test_printed_lines_run_on_into_paragraphs_and_list_items_stay_apart():
    lines = ["Le montant de l'indemnité de licenciement pour chaque année ou", 'fraction d’année de travail effectif est égal à :',
             "- 96 heures de salaire pour les cinq premières années d'ancienneté ;", '- 144 heures de salaire pour la période',
             "d'ancienneté allant de 6 à 10 ans ;", 'Des dispositions plus favorables au salarié peuvent être prévues.']
    assert paragraphs(lines) == [
        "Le montant de l'indemnité de licenciement pour chaque année ou fraction d’année de travail effectif est égal à :",
        "- 96 heures de salaire pour les cinq premières années d'ancienneté ;",
        "- 144 heures de salaire pour la période d'ancienneté allant de 6 à 10 ans ;",
        'Des dispositions plus favorables au salarié peuvent être prévues.']


def test_the_docs_sub_articles_are_their_own():
    # H4 of the housing plan: «Article 106-1», «Article 618-3 bis» are articles, numbered as the Arabic's.
    for line, number in [('Article 106-1', '106-1'), ('Article 618-3 bis', '618-3-bis'), ('Article premier', '1'),
                         ('Article 12 bis - Le texte', '12-bis')]:
        m = HEAD.match(line)
        assert _number(m.group(1), m.group(2)) == number


def test_titled_headings_with_their_marks_run_in_are_the_articles(monkeypatch):
    # The shelf, 27 Oct 2026: Adala's French nationality code sets each note's mark in the body's size, run into its
    # article's number («ARTICLE 32:» is art. 3, note 2; «ARTICLE 98» art. 9, note 8); the reader kept 5 of 46.
    from apps.translations.services import adala_fr

    lines = ['ARTICLE PREMIER : SOURCES DU DROIT EN MATIERE DE NATIONALITE', 'Les dispositions sont fixées par la loi.',
             'ARTICLE 2 : APPLICATION DANS LE TEMPS DES DISPOSITIONS RELATIVES A', 'LA NATIONALITE',
             'Les dispositions nouvelles', "s'appliquent.", 'ARTICLE 32 : NATIONALITE ET CODE DE LA FAMILLE',
             'Le champ est fixé.', 'SECTION 2: NATURALISATION', 'ARTICLE 43', 'Sauf opposition, peut acquérir.',
             '11 SECTION 3: REINTEGRATION', 'Chapitre premier : Dispositions générales', 'ARTICLE 54: MARIAGE',
             "La femme étrangère qui a épousé un Marocain, renvoyée à l'article 12."]

    class Page:
        def get_textpage(self):
            return None

    class Pdf(list):
        def close(self):
            pass

    monkeypatch.setattr(adala_fr.pdfium, 'PdfDocument', lambda path: Pdf([Page()]))
    monkeypatch.setattr(adala_fr, '_lines', lambda page: lines)
    monkeypatch.setattr(adala_fr, '_main_size', lambda pages: 12)
    monkeypatch.setattr(adala_fr, 'split_page', lambda page, main: (page, []))
    monkeypatch.setattr(adala_fr, '_without_notes', lambda page, main, marks: page)
    articles = [(a['number'], a['body']) for a in adala_fr.read('x.pdf')]
    assert articles == [
        ('1', 'SOURCES DU DROIT EN MATIERE DE NATIONALITE\nLes dispositions sont fixées par la loi.'),
        ('2', "APPLICATION DANS LE TEMPS DES DISPOSITIONS RELATIVES A LA NATIONALITE\nLes dispositions nouvelles s'appliquent."),
        ('3', 'NATIONALITE ET CODE DE LA FAMILLE\nLe champ est fixé.'), ('4', 'Sauf opposition, peut acquérir.'),
        ('5', "MARIAGE\nLa femme étrangère qui a épousé un Marocain, renvoyée à l'article 12.")]
