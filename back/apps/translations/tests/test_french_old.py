"""A of the Bulletin-from-No.-1 review (1 Nov 2026): the texts only the French Bulletin printed before 1926, found, cut
and given addresses of their own, the Arabic edition's issues of the same weeks asked first."""
import json
from datetime import date

import pytest
from django.utils import timezone

from apps.corpus.services import french
from apps.sources.models import Document, Edition, Issue, Page
from apps.translations.models import FrenchArticle, FrenchText

pytestmark = pytest.mark.django_db

LINES = [(560, 'DAHIR DU 12 AOUT 1913 (9 ramadan 1331) relatif à l\'organisation judiciaire ........ 560'),
         (561, 'DAHIR DU 12 AOUT 1913 (9 ramadan 1331)'), (561, 'formant code des obligations et des contrats.'),
         (561, 'Article premier. – Les obligations dérivent des conventions.'),
         (562, 'DAHIR DU 12 AOUT 1913 (9 ramadan 1331)'), (562, 'relatif à l\'organisation judiciaire du Protectorat.'),
         (562, 'Article premier. – Il est institué des tribunaux.'), (562, 'Art. 2. – Ils jugent.')]


def test_an_old_text_with_no_number_is_found_by_its_kind_its_day_and_its_words():
    judicial = {'title': "Dahir du 12 août 1913 (9 ramadan 1331) relatif à l'organisation judiciaire du Protectorat",
                'number_as_printed': '', 'page': 560, 'signed_on_gregorian': '1913-08-12'}
    assert french._start_of(LINES, judicial, 0) == 4
    alone = {**judicial, 'title': 'Dahir du 1er août 1913 sur les forêts'}
    assert french._start_of(LINES, {**alone, 'signed_on_gregorian': '1913-08-01'}, 0) is None


def test_a_heading_of_the_same_day_pages_on_is_not_taken_for_a_text_whose_heading_names_no_kind():
    """BO 190 of 1916: the Council's minutes of 7 June (p. 585) had taken the order of that day on p. 589, «juin» and
    «chaabane» counted as the title's words, and the order itself was then lost."""
    lines = [(585, 'COMPTE RENDU'), (585, 'DE LA SÉANCE DU CONSEIL DES VIZIRS'), (585, 'du 7 Juin 1916 (5 Chaabane 1334)'),
             (585, 'Le Conseil des Vizirs s\'est réuni le mercredi 7 juin 1916.'),
             (589, 'ARRÊTÉ VIZIRIEL DU 7 JUIN 1916'), (589, '(5 CHAABANE 1334)'),
             (589, 'portant déclassement d\'une parcelle du Domaine Public sise à Mazagan'),
             (589, 'ARTICLE PREMIER. — La parcelle de l\'immeuble 214 cesse de faire partie du Domaine public.')]
    minutes = {'title': 'Compte rendu de la séance du Conseil des Vizirs du 7 Juin 1916 (5 Chaabane 1334)',
               'number_as_printed': '', 'page': 585, 'signed_on_gregorian': '1916-06-07'}
    order = {'title': "Arrêté Viziriel du 7 Juin 1916 (5 Chaabane 1334) portant déclassement d'une parcelle du Domaine "
                      'Public sise à Mazagan', 'number_as_printed': '', 'page': 588, 'signed_on_gregorian': '1916-06-07'}
    assert french._dated_start(lines, minutes, 0) is None
    assert french._start_of(lines, minutes, 0) == 0     # its own heading, by its words
    assert french._start_of(lines, order, 1) == 4
    assert french._title_words(minutes['title']) == ['compte', 'rendu', 'seance', 'conseil', 'vizirs']


def test_an_old_entry_with_no_kind_nor_day_is_found_by_its_title_never_in_the_contents_nor_at_its_formula():
    """BO 18 and 59 of 1913: «Nominations et mutations …» opens with no kind; a contents line with spaced dots and the
    «ARRÊTE :» before the articles are never a heading."""
    lines = [(77, 'SOMMAIRE'), (77, 'IV. — Arrêté portant constitution du cercle des Beni-Mtir . . . 78'),
             (77, 'V. — Nominations et mutations dans les services des commandements territoriaux . . . . 79'),
             (78, 'ARRÊTÉ'), (78, 'portant constitution du cercle des Beni-Mtir'), (78, 'ARRÊTE :'),
             (78, 'ARTICLE PREMIER. — Il est constitué un Cercle Beni Mtir.'),
             (79, 'NOMINATIONS ET MUTATIONS DANS LES SERVICES DES COMMANDEMENTS TERRITORIAUX'),
             (79, 'Par arrêté du 2 avril 1913, M. X est nommé.')]
    assert french._contents_end(lines) == 3
    beni = {'title': 'Arrêté portant constitution du cercle des Beni-Mtir', 'number_as_printed': '', 'page': 78,
            'signed_on_gregorian': ''}
    staff = {'title': 'Nominations et mutations dans les services des commandements territoriaux', 'number_as_printed': '',
             'page': 79, 'signed_on_gregorian': ''}
    assert french._start_of(lines, beni, 3) == 3
    assert french._start_of(lines, staff, 4) == 7
    assert french._start_of(lines, staff, 0) == 7      # the contents line names it too, but its dots give it away


def test_an_old_french_only_text_gets_an_address_of_its_own_beside_its_issue():
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='f' * 64, path='issues/bo_fr/BO_46_fr.pdf',
                                  mime='application/pdf', language='fr', bytes=1, fetched_at=timezone.now(), page_count=2)
    Page.objects.create(document=doc, index=0, printed_number=561, text='\n'.join(t for p, t in LINES[1:4]))
    Page.objects.create(document=doc, index=1, printed_number=562, text='\n'.join(t for p, t in LINES[4:]))
    issue = Issue.objects.create(edition=Edition.TRANSLATION_FR, number=46, date=date(1913, 9, 12), document=doc)
    toc = [{'type': 'dahir', 'number_as_printed': '', 'page': 561, 'signed_on_gregorian': '1913-08-12', 'section': 'general',
            'title': 'Dahir du 12 août 1913 (9 ramadan 1331) formant code des obligations et des contrats'},
           {'type': 'dahir', 'number_as_printed': '', 'page': 562, 'signed_on_gregorian': '1913-08-12', 'section': 'general',
            'title': "Dahir du 12 août 1913 (9 ramadan 1331) relatif à l'organisation judiciaire du Protectorat"}]
    counts = french.load(issue, toc, only={1})          # the Arabic edition printed the first: only the second is loaded
    assert counts['texts'] == 1
    (text,) = FrenchText.objects.all()
    assert text.text_uri == '/akn/ma/act/dahir/1913-09-12/bofr46-2' and text.signed_on == date(1913, 8, 12)
    assert [(a.label, a.body) for a in FrenchArticle.objects.filter(text_uri=text.text_uri).order_by('order')] == \
        [('Article premier', 'Il est institué des tribunaux.'), ('Art. 2', 'Ils jugent.')]


def test_the_old_contents_prompt_knows_the_two_parts():
    assert 'PARTIE NON OFFICIELLE' in french.toc_system(Issue(number=46, date=date(1913, 9, 12)))
    assert 'PARTIE NON OFFICIELLE' not in french.toc_system(Issue(number=7410, date=date(2025, 6, 5)))


def test_the_match_keeps_only_what_the_arabic_never_printed(tmp_path, settings, monkeypatch):
    from django.core.management import call_command
    from apps.translations.management.commands import archive_french
    settings.CORPUS_DIR = tmp_path
    folder = tmp_path / 'archive'
    folder.mkdir()
    (folder / 'plan_fr.json').write_text(json.dumps({'issues': [{'key': '46', 'date': '1913-09-12', 'url': '', 'path': 'BO_46_fr.pdf'}]}))
    (folder / 'plan.json').write_text(json.dumps({'pilot': [], 'issues': [{'key': '19', 'date': '1913-09-13', 'url': '', 'path': '1913/BO_19_Ar.pdf'}]}))
    (tmp_path / 'reports' / 'issues' / '19').mkdir(parents=True)
    (tmp_path / 'reports' / 'issues' / '19' / 'toc.json').write_text(json.dumps(
        [{'section': 'general', 'type': 'dahir', 'title': 'ظهير شريف بشان تنظيم العدلية بالايالة الشريفة', 'page': 1}]))
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='e' * 64, path='issues/bo_fr/BO_46_fr.pdf',
                                  mime='application/pdf', language='fr', bytes=1, fetched_at=timezone.now(), page_count=1)
    Issue.objects.create(edition=Edition.TRANSLATION_FR, number=46, date=date(1913, 9, 12), document=doc)
    work = tmp_path / 'reports' / 'issues' / 'fr-46'
    work.mkdir(parents=True)
    (work / 'toc.json').write_text(json.dumps([
        {'section': 'general', 'type': 'dahir', 'title': "Dahir relatif à l'organisation judiciaire", 'page': 560,
         'signed_on_gregorian': '1913-08-12', 'number_as_printed': ''},
        {'section': 'general', 'type': 'dahir', 'title': 'Dahir formant code des obligations et des contrats', 'page': 561,
         'signed_on_gregorian': '1913-08-12', 'number_as_printed': ''},
        {'section': 'other', 'type': 'other', 'title': 'Annonces', 'page': 600, 'signed_on_gregorian': '', 'number_as_printed': ''}]))
    (folder / 'state' / 'fr-toc').mkdir(parents=True)
    (folder / 'state' / 'fr-toc' / '46.done').write_text('{}')
    sent = {}

    def batch(kind, reqs, log=print):
        sent['content'] = json.loads(reqs[0]['params']['messages'][0]['content'])
        return {reqs[0]['custom_id']: {'data': {'pairs': [{'fr': 0, 'ar': '19:0'}, {'fr': 1, 'ar': ''}]}, 'stop': 'end_turn', 'error': ''}}
    monkeypatch.setattr(archive_french, 'run_batch', batch)
    call_command('archive_french', 'work', 'match', stdout=open('/dev/null', 'w'))
    assert [e['id'] for e in sent['content']['arabic_entries']] == ['19:0']
    assert len(sent['content']['french_issue']['entries']) == 2              # the notices are not asked about
    assert json.loads((work / 'match.json').read_text())['alone'] == [1]


def test_a_code_held_from_adala_is_never_translated_again(tmp_path, settings, monkeypatch):
    """The DOC of 1913, which the Arabic edition never printed but the site holds from Adala, is not cut nor translated."""
    from django.core.management import call_command
    from apps.translations.management.commands import archive_french
    settings.CORPUS_DIR = tmp_path
    folder = tmp_path / 'archive'
    (folder / 'state' / 'fr-match').mkdir(parents=True)
    (folder / 'plan_fr.json').write_text(json.dumps({'issues': [{'key': '46', 'date': '1913-09-12', 'url': '', 'path': 'BO_46_fr.pdf'}]}))
    (folder / 'state' / 'fr-match' / '46.done').write_text('{}')
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='d' * 64, path='issues/bo_fr/BO_46_fr.pdf',
                                  mime='application/pdf', language='fr', bytes=1, fetched_at=timezone.now(), page_count=2)
    Page.objects.create(document=doc, index=0, printed_number=561, text='\n'.join(t for p, t in LINES[1:4]))
    Page.objects.create(document=doc, index=1, printed_number=562, text='\n'.join(t for p, t in LINES[4:]))
    Issue.objects.create(edition=Edition.TRANSLATION_FR, number=46, date=date(1913, 9, 12), document=doc)
    work = tmp_path / 'reports' / 'issues' / 'fr-46'
    work.mkdir(parents=True)
    (work / 'toc.json').write_text(json.dumps([
        {'type': 'dahir', 'number_as_printed': '', 'page': 561, 'signed_on_gregorian': '1913-08-12', 'section': 'general',
         'title': 'Dahir du 12 août 1913 (9 ramadan 1331) formant code des obligations et des contrats'},
        {'type': 'dahir', 'number_as_printed': '', 'page': 562, 'signed_on_gregorian': '1913-08-12', 'section': 'general',
         'title': "Dahir du 12 août 1913 (9 ramadan 1331) relatif à l'organisation judiciaire du Protectorat"}]))
    (work / 'match.json').write_text(json.dumps({'pairs': {'0': '', '1': ''}, 'alone': [0, 1]}))
    asked = []
    monkeypatch.setattr(archive_french, 'call_command', lambda *a, **k: asked.append(a))
    call_command('archive_french', 'work', 'texts', stdout=open('/dev/null', 'w'))
    assert list(FrenchText.objects.values_list('text_uri', flat=True)) == ['/akn/ma/act/dahir/1913-09-12/bofr46-2']
    assert asked == [('translate_french', '46')]
