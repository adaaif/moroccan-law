"""A French article ends where the next part's heading begins (N15 of the read-and-trusted review)."""
from apps.translations.services.divisions import trim

LABOUR_65 = ("Le délai précité doit être mentionné dans la décision de licenciement visée à l'article 63 ci-dessus.\n"
             "Section VI : Du licenciement pour motifs technologiques structurels ou économiques et de la fermeture des "
             "entreprises")


def test_the_next_parts_heading_leaves_the_article():
    assert trim(LABOUR_65).endswith("visée à l'article 63 ci-dessus.")
    assert trim('Le directeur arrête le règlement.\nChapitre III\nDes instances de concertation') == \
        'Le directeur arrête le règlement.'
    assert trim('Il est institué un comité.\nSection II : Attributions\nSous-section 1 : Le pôle médical') == \
        'Il est institué un comité.'


def test_a_sentence_that_names_a_part_stays():
    body = "Les dispositions de la section 2 s'appliquent.\nSection 3 du présent chapitre s'applique aux apprentis."
    assert trim(body) == body
