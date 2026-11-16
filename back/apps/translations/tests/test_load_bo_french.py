"""`load_bo_french`: a text's official French read from a scanned French Bulletin (Q6 of the road plan; the
constitutions, C9). The pages are real image-only PDFs rendered by pdfium; Tesseract's readings and the meaning model's
vectors (`--align`) come from stand-ins in their own formats. Every step after them is the command's own."""
import re
import subprocess
from datetime import date
from io import StringIO
from types import SimpleNamespace as NS

import numpy as np
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.corpus.models import Consolidation, Text, Version
from apps.sources.models import Document
from apps.translations.management.commands import load_bo_french
from apps.translations.models import FrenchArticle, FrenchText
from apps.translations.tests.files import Tesseract, scan_pdf

pytestmark = pytest.mark.django_db

URI = '/akn/ma/act/dahir/1-11-91'
FILE = 'issues/bo_fr/BO_5964-bis_fr.pdf'
HEAD = 'BULLETIN OFFICIEL N° 5964 bis – 28 chaabane 1432 (30-7-2011)'

# What Tesseract reads on each part, in the order they are read: page 1900 is the issue's front page (the masthead and
# contents across, then two columns); 1901 two columns, the gutter cutting the running head in two; 1902 printed
# across; 1903, past the text's pages, the next text. Two folios are misread («1962», «1803»): the pages' offset is
# the one most heads agree on.
READINGS = [
    f'1900 {HEAD}\nSOMMAIRE\nTexte de la Constitution . . . . . . 1900',
    'Dahir n° 1-11-91 du 27 chaabane 1432 (29 juillet 2011)\nportant promulgation du texte de la Constitution.\n'
    'CONSTITUTION\nPREAMBULE\nFidèle à son choix irréversible de construire un Etat\n'
    'démocratique de droit, le Royaume du Maroc\npoursuit le processus de consolidation.\nTitre premier\n'
    "DE L'ETAT\nDISPOSITIONS GENERALES\nArticle premier\nLe Maroc est une monarchie constitutionnelle.",
    "Article 2\nLa souveraineté appartient à la nation.\nAïticle 8\nL'Islam est la religion de l'Etat.",
    '1901 BULLE\nArticle 4\nLe drapeau du Royaume est r0uge.\nArticle 6\n'
    "L'arabe demeure la langue officielle. Art 6. — La loi est l'expression suprême\nde la volonté de la nation.",
    'TIN OFFICIEL N° 5964 bis – 28 chaabane 1432 (30-7-2011)\nArticle 8\nLes partis politiques encadrent les citoyens.',
    f'1962 {HEAD}\nArticle 9\nLes syndicats contribuent à la défense des droits.\n'
    "Le texte en langue arabe a été publié dans l'édition générale du « Bulletin officiel » n° 5964 bis.",
    '1803 BULLE\nDécision du Conseil constitutionnel n° 815-2011',
    'TIN OFFICIEL N° 5964 bis – 28 chaabane 1432 (30-7-2011)\nArticle 10\nLe Conseil déclare la loi conforme.',
]
FIXES = """language: fr
text: /ma/dahir/1-11-91
fixes:
  - {arts: [4], wrong: 'r0uge', right: 'rouge'}
  - {arts: [7], wrong: 'citoyens,', right: 'citoyennes et citoyens,'}
bodies:
  '12': 'Article read whole on the page.'
"""


# The Arabic of the text as the site holds it (its reading lost the preamble and art. 7; its art. 9 is past the French
# pages given), each article a sentence the stand-in model reads for its meaning.
ARABIC = [('1', 'نظام الحكم بالمغرب نظام ملكية دستورية'), ('2', 'السيادة للأمة'), ('3', 'الإسلام دين الدولة'),
          ('4', 'علم المملكة هو اللواء الأحمر'), ('5', 'تظل العربية اللغة الرسمية للدولة'),
          ('6', 'القانون هو أسمى تعبير عن إرادة الأمة'), ('8', 'تساهم المنظمات النقابية في الدفاع عن الحقوق'),
          ('9', 'الانتخابات الحرة أساس التمثيل')]
# The words the stand-in model knows, French and Arabic alike: one meaning each.
MEANINGS = {'démocratique': 1, 'ديمقراطية': 1, 'monarchie': 2, 'ملكية': 2, 'souveraineté': 3, 'السيادة': 3,
            'religion': 4, 'دين': 4, 'drapeau': 5, 'علم': 5, 'arabe': 6, 'العربية': 6, 'loi': 7, 'القانون': 7,
            'partis': 8, 'syndicats': 9, 'النقابية': 9, 'الانتخابات': 10}


class Tokenizer:
    """`tokenizers.Tokenizer` for the meaning model: a text's ids, the start token first, then one id a known word."""

    @classmethod
    def from_file(cls, path):
        return cls()

    def enable_truncation(self, size):
        pass

    def encode(self, text):
        words = [w.strip('.,;:«»\'’').lower() for w in text.replace("'", ' ').split()]
        return NS(ids=[0] + [MEANINGS[w] for w in words if w in MEANINGS])

    def encode_batch(self, texts):
        return [self.encode(t) for t in texts]


class Session:
    """`onnxruntime.InferenceSession` running the model: one vector a text, its meanings counted (the start token,
    on every text, weighs half: texts with no meaning in common are still a little alike, as a real model's are)."""

    def __init__(self, path, options, providers):
        pass

    def get_outputs(self):
        return [NS(name='sentence_embedding')]

    def run(self, names, feeds):
        ids, mask = feeds['input_ids'], feeds['attention_mask']
        out = np.zeros((len(ids), 11), dtype=np.float32)
        for row, (line, seen) in enumerate(zip(ids, mask)):
            for i in line[seen == 1]:
                out[row, i] += 0.5 if i == 0 else 1
        return [out]


@pytest.fixture
def meaning_model(monkeypatch, settings, tmp_path):
    import onnxruntime
    import tokenizers
    settings.SEARCH_MODEL_DIR = str(tmp_path / 'models')
    monkeypatch.setattr(onnxruntime, 'InferenceSession', Session)
    monkeypatch.setattr(tokenizers, 'Tokenizer', Tokenizer)


def run(**opts) -> tuple[str, str]:
    out, err = StringIO(), StringIO()
    call_command('load_bo_french', FILE, stdout=out, stderr=err, **{
        'url': 'https://example.org/bo_5964-bis_fr.pdf', 'text': URI, 'pages': '1900-1902', 'issue': '5964-bis',
        'issue_date': '2011-07-30', 'title': 'Constitution du Royaume du Maroc', 'start': 'Dahir n° 1-11-91', **opts})
    return out.getvalue(), err.getvalue()


@pytest.fixture
def issue(tmp_path, settings, monkeypatch):
    """The scanned issue under the corpus, Tesseract's stand-in, the words a person read on its pages, and the Arabic
    text (whose reading lost its art. 7)."""
    settings.CORPUS_DIR = tmp_path
    scan_pdf(tmp_path / FILE, ['front', 'columns', 'across', 'columns'])
    tesseract = Tesseract(READINGS)
    monkeypatch.setattr(subprocess, 'run', tesseract)
    (tmp_path / 'fixes').mkdir()
    (tmp_path / 'fixes' / 'constitution_fr.yaml').write_text(FIXES)
    monkeypatch.setattr(load_bo_french, 'FIXES', tmp_path / 'fixes')
    text = Text.objects.create(akn_uri=URI, type='dahir', number='1-11-91', signed_on=date(2011, 7, 29),
                               title_ar='ظهير شريف رقم 1.11.91 بتنفيذ نص الدستور')
    version = Version.objects.create(text=text, language='ar', valid_from=date(2011, 7, 30),
                                     consolidation=Consolidation.AS_PUBLISHED)
    for k, (number, body) in enumerate(ARABIC):
        version.articles.create(order=k + 1, number=number, label=f'الفصل {number}', eid=f'art_{number}', body=body)
    # Its French as loaded before from a consolidation (Adala's): the Bulletin's replaces it, at the issue's date.
    FrenchText.objects.create(text_uri=URI, type='dahir', title='Constitution', issue_number=5964, issue_suffix='bis',
                              issue_date=date(2011, 7, 30), document_sha='a' * 64, pages='1-40',
                              consolidated_to=date(2011, 10, 26))
    FrenchArticle.objects.create(text_uri=URI, order=1, label='Article 180', number='180', body='Ancien texte.')
    return tesseract


def test_a_texts_french_is_read_from_its_scanned_pages_and_kept_beside_the_arabic(issue, meaning_model, tmp_path):
    said, err = run()
    assert said == f'{URI}: 9 French articles on pages 1900-1902, preamble to 9\n'
    # Each page cut where the Bulletin cuts it: the front page's masthead across, then its two columns at the gutter;
    # a page printed across read whole.
    assert issue.sizes == [(400, 76), (192, 484), (208, 484), (192, 560), (208, 560), (400, 560), (192, 560), (208, 560)]
    # Each part handed to Tesseract as a PNG, read as French, as one column of text (psm 4), its failure an error.
    assert {(*call['args'], *call['image']) for call in issue.calls} == {
        ('tesseract', '-', '-l', 'fra', '--psm', '4', '.png', 'PNG')}
    assert all(call['options'] == {'capture_output': True, 'text': True, 'check': True} for call in issue.calls)
    articles = [(a.order, a.label, a.number, a.body, a.printed_page) for a in FrenchArticle.objects.filter(text_uri=URI)]
    assert articles == [
        (1, 'Préambule', 'preamble', 'Fidèle à son choix irréversible de construire un Etat démocratique de droit, le '
                                     'Royaume du Maroc poursuit le processus de consolidation.', 1900),
        (2, 'Article premier', '1', 'Le Maroc est une monarchie constitutionnelle.', 1900),
        (3, 'Article 2', '2', 'La souveraineté appartient à la nation.', 1900),
        # «Aïticle 8» between 2 and 4 is 3; art. 5's heading, lost, is found inside art. 6's words.
        (4, 'Article 3', '3', "L'Islam est la religion de l'Etat.", 1900),
        (5, 'Article 4', '4', 'Le drapeau du Royaume est rouge.', 1901),
        (6, 'Article 5', '5', "L'arabe demeure la langue officielle.", 1901),
        (7, 'Article 6', '6', "La loi est l'expression suprême de la volonté de la nation.", 1901),
        # The last two headings' figures misread (they are 7 and 8): nothing on these pages tells, so they stay as read.
        (8, 'Article 8', '8', 'Les partis politiques encadrent les citoyens.', 1901),
        (9, 'Article 9', '9', 'Les syndicats contribuent à la défense des droits.', 1902)]
    # What a person read on the pages and is not found is said.
    assert err == ('  not found: constitution_fr.yaml: art. 7 «citoyens,»\n'
                   '  not found: constitution_fr.yaml: art. 12\n')
    doc = Document.objects.get(path=FILE)
    french = FrenchText.objects.get(text_uri=URI)
    assert (french.type, french.number, french.signed_on, french.title) == (
        'dahir', '1-11-91', date(2011, 7, 29), 'Constitution du Royaume du Maroc')
    assert (french.issue_number, french.issue_suffix, french.issue_date, french.pages, french.consolidated_to) == (
        5964, 'bis', date(2011, 7, 30), '1900-1902', None)
    assert french.document_sha == doc.sha256 and (doc.language, doc.url) == ('fr', 'https://example.org/bo_5964-bis_fr.pdf')
    assert Text.objects.get(akn_uri=URI).title_fr == 'Constitution du Royaume du Maroc'
    # Each page's reading is kept beside the file, its parts apart.
    kept = tmp_path / 'derived' / 'ocr_fr' / doc.sha256[:16]
    assert (kept / '1.txt').read_text().split('\f')[0] == READINGS[0] + '\n'
    assert sorted(p.name for p in kept.iterdir()) == ['1.txt', '2.txt', '3.txt', '4.txt']

    # Again with --align: nothing read twice, the articles numbered by the Arabic they say. A French article the Arabic
    # lacks keeps its number when no other holds it (the preamble), and is dropped when one does (art. 7, read «8»,
    # whose number goes to the article the Arabic numbers 8); the Arabic's art. 9 has no French here. A title the
    # Arabic text has is kept.
    said, _ = run(align=True, title='Texte de la Constitution')
    assert said.splitlines() == ["  aligned with the Arabic: 2 renumbered ['8→None', '9→8']",
                                 f'{URI}: 8 French articles on pages 1900-1902, preamble to 8']
    assert len(issue.sizes) == 8
    assert [(a.label, a.number, a.body[:16]) for a in FrenchArticle.objects.filter(text_uri=URI)] == [
        ('Préambule', 'preamble', 'Fidèle à son cho'), ('Article premier', '1', 'Le Maroc est une'),
        ('Article 2', '2', 'La souveraineté '), ('Article 3', '3', "L'Islam est la r"), ('Article 4', '4', 'Le drapeau du Ro'),
        ('Article 5', '5', "L'arabe demeure "), ('Article 6', '6', "La loi est l'exp"), ('Article 8', '8', 'Les syndicats co')]
    assert FrenchText.objects.get().title == 'Texte de la Constitution'
    assert Text.objects.get(akn_uri=URI).title_fr == 'Constitution du Royaume du Maroc'


def test_a_text_or_a_file_not_held_a_start_not_printed_and_pages_with_no_article_are_refused(issue, tmp_path):
    with pytest.raises(CommandError, match=re.escape('issues/bo_fr/BO_9999_fr.pdf or /akn/ma/act/dahir/1-11-91: not found')):
        call_command('load_bo_french', 'issues/bo_fr/BO_9999_fr.pdf', url='u', text=URI, pages='1-2', issue='9999',
                     issue_date='2011-07-30', title='t', start='s')
    with pytest.raises(CommandError, match='or /akn/ma/act/loi/99-99: not found'):
        run(text='/akn/ma/act/loi/99-99')
    with pytest.raises(CommandError, match='«Loi n° 99-99» not found on pages 1900-1902'):
        run(start='Loi n° 99-99')
    with pytest.raises(CommandError, match='no article read'):
        run(start='Le texte en langue arabe')
    assert FrenchText.objects.get().consolidated_to == date(2011, 10, 26)            # the French held stays
    assert list(FrenchArticle.objects.values_list('number', flat=True)) == ['180']


def test_pages_with_no_running_head_give_no_folio_and_a_law_with_no_preamble_is_its_articles(tmp_path, settings,
                                                                                               monkeypatch):
    settings.CORPUS_DIR = tmp_path
    scan_pdf(tmp_path / 'issues' / 'bo_fr' / 'BO_7000_fr.pdf', ['across'])
    scan_pdf(tmp_path / 'issues' / 'bo_fr' / 'BO_5874_fr.pdf', ['columns', 'columns', 'across'])
    # The law's first two pages in columns, the gutter cutting each running head in two: an even page's folio first
    # («1646 BULLE» | «TIN OFFICIEL N° 5874 …»), an odd page's last («N° 5874 … BULLE» | «TIN OFFICIEL 1647»); the
    # third printed across, its folio read alone on its line. The law starts under the last article of the text
    # before it, its heading read with two spaces.
    monkeypatch.setattr(subprocess, 'run', Tesseract([
        'Article premier\nLe texte.',
        '1646 BULLE\nArticle unique\nLe présent arrêté sera publié au Bulletin officiel.\n'
        'Loi n°  52-05 portant code de la route\nArticle premier\n'
        'Au sens de la présente loi, on entend par véhicule\ntout engin.',
        'TIN OFFICIEL N° 5874 – 7 chaoual 1431 (16-9-2010)\nArticle 2\nLe permis de conduire est obligatoire',
        'N° 5874 – 7 chaoual 1431 (16-9-2010) BULLE\npour conduire un véhicule.',
        'TIN OFFICIEL 1647\nArticle 3\nLe permis est délivré',
        '1648\nBULLETIN OFFICIEL N° 5874 – 7 chaoual 1431 (16-9-2010)\npar le ministre chargé du transport.\n'
        'Article 4\nLe permis est valable dix ans.']))
    Text.objects.create(akn_uri='/akn/ma/act/loi/52-05', type='law', number='52-05')
    opts = {'url': 'u', 'text': '/akn/ma/act/loi/52-05', 'title': 'Loi n° 52-05 portant code de la route',
            'start': 'loi n° 52-05 portant', 'stdout': StringIO()}
    with pytest.raises(CommandError, match='no folio read'):
        call_command('load_bo_french', 'issues/bo_fr/BO_7000_fr.pdf', pages='1-1', issue='7000', issue_date='2021-06-03',
                     **opts)
    assert not FrenchText.objects.exists()
    call_command('load_bo_french', 'issues/bo_fr/BO_5874_fr.pdf', pages='1646-1648', issue='5874',
                 issue_date='2010-09-16', **opts)
    # The running heads, cut or alone, are in no article's words.
    assert [(a.number, a.body, a.printed_page) for a in FrenchArticle.objects.all()] == [
        ('1', 'Au sens de la présente loi, on entend par véhicule tout engin.', 1646),
        ('2', 'Le permis de conduire est obligatoire pour conduire un véhicule.', 1646),
        ('3', 'Le permis est délivré par le ministre chargé du transport.', 1647),
        ('4', 'Le permis est valable dix ans.', 1648)]
    assert (FrenchText.objects.get().issue_suffix, FrenchText.objects.get().pages) == ('', '1646-1648')
