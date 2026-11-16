"""`load_adala_french` (T1 of the work plan): Adala's French file of a text, read from its Word text layer, kept beside
the Arabic as of Adala's date. The files are real PDFs made here, their runs at their own sizes as Word sets them."""
import re
from datetime import date
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.corpus.models import Text
from apps.sources.models import DocumentKind, Source
from apps.sources.services.ingest import ingest_file
from apps.translations.models import FrenchArticle, FrenchText
from apps.translations.services import adala_fr
from apps.translations.tests.files import layer_pdf

pytestmark = pytest.mark.django_db

URI = '/akn/ma/act/arrete/02-11'
# Order 02.11 as Adala's French file sets it: the body at 14 points, a footnote's mark small beside its word, and at the
# page's foot, a point under the body, one of the article's items («1- …») and the footnote («2- …») the mark calls.
ORDER = [
    [[("Arrêté du ministre de l'équipement et du transport n° 02-11", 14)],
     [('ARTICLE PREMIER', 14)],
     [('Le permis de conduire étranger est échangé dans les conditions', 14), ('2', 8)],
     [('fixées en annexe.', 14)],
     [('ART. 2. - La demande est déposée auprès des services du ministère avec :', 14)],
     [('1- une copie du permis ;', 13)],
     [('2- Voir le décret n° 2-10-311 du 29 septembre 2010.', 13)]],
    [[("ART. 3. - Le directeur des transports est chargé de l'exécution du présent arrêté.", 14)]],
]


def adala(tmp_path, name, pages):
    path = layer_pdf(tmp_path / 'sources' / 'adala' / f'{name}.pdf', pages)
    return ingest_file(path, source=Source.ADALA, kind=DocumentKind.TEXT, language='fr',
                       url=f'https://example.org/{name}.pdf')


def load(path, **opts) -> str:
    out = StringIO()
    call_command('load_adala_french', path, stdout=out, **{
        'text': URI, 'title': 'Arrêté n° 02-11 relatif aux permis de conduire étrangers', 'as_of': '2011-03-01',
        'issue': 5932, 'issue_date': '2011-04-07', **opts})
    return out.getvalue()


def test_adalas_french_is_kept_beside_the_arabic_without_its_footnotes_and_with_the_annex_read_on_its_pages(
        tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    doc = adala(tmp_path, 'adala_02_11_fr', ORDER)
    Text.objects.create(akn_uri=URI, type='order', number='02-11', signed_on=date(2011, 1, 3))
    assert load('sources/adala/adala_02_11_fr.pdf') == \
        f'{URI}: 4 French articles, from Article premier to Annexe\n'
    articles = [(a.order, a.label, a.number, a.body, a.printed_page) for a in FrenchArticle.objects.filter(text_uri=URI)]
    assert articles[:3] == [
        (1, 'Article premier', '1', 'Le permis de conduire étranger est échangé dans les conditions fixées en annexe.', 1),
        (2, 'Article 2', '2', 'La demande est déposée auprès des services du ministère avec :\n1- une copie du permis ;', 1),
        (3, 'Article 3', '3', "Le directeur des transports est chargé de l'exécution du présent arrêté.", 2)]
    # The annex, a table the reader cannot follow, as it was read on the file's page images (consolidation's
    # page_tables.yaml).
    order, label, number, body, page = articles[3]
    assert (order, label, number, page) == (4, 'Annexe', 'annex', 5) and body.startswith('| Pays | Catégories de permis')
    french = FrenchText.objects.get(text_uri=URI)
    assert (french.type, french.number, french.signed_on, french.consolidated_to, french.title) == (
        'order', '02-11', date(2011, 1, 3), date(2011, 3, 1), 'Arrêté n° 02-11 relatif aux permis de conduire étrangers')
    assert (french.issue_number, french.issue_date, french.pages, french.document_sha) == (
        5932, date(2011, 4, 7), '1-2', doc.sha256)
    assert Text.objects.get(akn_uri=URI).title_fr == 'Arrêté n° 02-11 relatif aux permis de conduire étrangers'
    # Loaded again: the articles replaced, never doubled; the Arabic text's French title, once set, kept.
    load('sources/adala/adala_02_11_fr.pdf', title='Arrêté conjoint n° 02-11', as_of='2012-01-01')
    assert FrenchArticle.objects.filter(text_uri=URI).count() == 4
    assert (FrenchText.objects.get().consolidated_to, FrenchText.objects.get().title) == (
        date(2012, 1, 1), 'Arrêté conjoint n° 02-11')
    assert Text.objects.get(akn_uri=URI).title_fr == 'Arrêté n° 02-11 relatif aux permis de conduire étrangers'


def test_a_file_or_text_not_held_and_a_file_with_no_article_are_refused(tmp_path, settings):
    settings.CORPUS_DIR = tmp_path
    adala(tmp_path, 'adala_notice_fr', [[[('Avis aux usagers de la route', 14)], [('Le service est fermé.', 14)]]])
    with pytest.raises(CommandError, match=re.escape('sources/adala/adala_notice_fr.pdf or /akn/ma/act/arrete/02-11: not found')):
        load('sources/adala/adala_notice_fr.pdf')
    Text.objects.create(akn_uri=URI, type='order', number='02-11')
    with pytest.raises(CommandError, match=re.escape('sources/adala/missing.pdf or /akn/ma/act/arrete/02-11: not found')):
        load('sources/adala/missing.pdf')
    with pytest.raises(CommandError, match=re.escape('sources/adala/adala_notice_fr.pdf: no article read')):
        load('sources/adala/adala_notice_fr.pdf')
    assert not FrenchText.objects.exists()


def test_the_dgis_code_is_read_from_its_own_first_article_not_the_one_its_preface_names(tmp_path):
    # The tax code's French (consolidation's dgi.py reads it so): its preface names «Article premier de la loi de
    # finances» before the code's own «Article premier.-».
    path = layer_pdf(tmp_path / 'cgi_fr.pdf', [[
        [('CODE GENERAL DES IMPOTS', 14)],
        [("Article premier de la loi de finances n° 60-24 pour l'année budgétaire 2025", 14)],
        [("Article premier.- Sont soumises à l'impôt sur les sociétés les sociétés.", 14)],
        [('Article 2.- Sont exonérées les coopératives.', 14)]]])
    assert [(a['number'], a['body']) for a in adala_fr.read(str(path), start='Article premier.-')] == [
        ('1', "Sont soumises à l'impôt sur les sociétés les sociétés."), ('2', 'Sont exonérées les coopératives.')]
    assert adala_fr.read(str(path))[0]['body'].startswith('de la loi de finances n° 60-24')
