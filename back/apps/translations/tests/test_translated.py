"""A text the site holds only in its official French (BO 7410: the SGG answers 404 for its Arabic) gets Arabic a model
translated, marked as such everywhere (31 Oct 2026): a version of its own that the Bulletin's Arabic always outranks,
never touching a text held in Arabic, never read for the changes it would make."""
import json
from datetime import date

import pytest
from django.core.management import call_command

from apps.corpus.models import Consolidation, Text, Version
from apps.corpus.services import french
from apps.translations.models import FrenchArticle, FrenchText

pytestmark = pytest.mark.django_db


def _file(tmp_path, texts):
    path = tmp_path / 'bo_7410_fr.json'
    path.write_text(json.dumps({
        'issue': '7410', 'date': '2025-06-05', 'arabic': 'not online',
        'french': {'number': 7410, 'suffix': '', 'date': '2025-06-05', 'sha256': 'f' * 64, 'url': 'https://x/fr.pdf'},
        'translated_from': 'fr', 'translated_by': 'claude-haiku-5-5', 'prompt_version': 'tr1',
        'translated_at': '2026-10-31T22:05:17+00:00', 'texts': texts, 'refused': []}, ensure_ascii=False))
    return path


def _text(uri, number, kind='decree'):
    return {'text_uri': uri, 'type': kind, 'number': number, 'signed_on': '2025-05-22', 'pages_fr': '2040-2041',
            'title_fr': f'Décret n° {number} relatif à la navigation aérienne militaire',
            'title_ar': f'مرسوم رقم {number.replace("-", ".")} بشأن الملاحة الجوية العسكرية',
            'articles': [{'order': 1, 'number': '1', 'label_fr': 'Article premier', 'body_fr': 'Le présent décret fixe…',
                          'page_fr': 2040, 'label_ar': 'المادة الأولى', 'body_ar': 'يحدد هذا المرسوم…'}]}


def test_a_translated_text_is_marked_and_a_text_held_in_arabic_is_never_touched(tmp_path):
    held = Text.objects.create(akn_uri='/akn/ma/act/decret/2-25-269', type='decree', number='2-25-269', title_ar='مرسوم مطبوع')
    Version.objects.create(text=held, language='ar', valid_from=date(2025, 5, 22), consolidation=Consolidation.AS_PUBLISHED)
    path = _file(tmp_path, [_text('/akn/ma/act/decret/2-25-366', '2-25-366'), _text('/akn/ma/act/decret/2-25-269', '2-25-269')])
    call_command('load_translated', str(path))
    v = Version.objects.get(text__akn_uri='/akn/ma/act/decret/2-25-366', language='ar')
    assert (v.consolidation, v.translated_from, v.translated_by) == (Consolidation.TRANSLATION, 'fr', 'claude-haiku-5-5')
    assert v.articles.get().body == 'يحدد هذا المرسوم…' and v.text.title_fr.startswith('Décret n° 2-25-366')
    assert FrenchArticle.objects.get(text_uri='/akn/ma/act/decret/2-25-366').body == 'Le présent décret fixe…'
    # The Bulletin's Arabic stands: no translation beside it; its French is kept all the same.
    assert list(held.versions.values_list('consolidation', flat=True)) == [Consolidation.AS_PUBLISHED]
    assert FrenchText.objects.filter(text_uri='/akn/ma/act/decret/2-25-269').exists()
    # A reload replaces the translation, never doubles it.
    call_command('load_translated', str(path))
    assert Version.objects.filter(text__akn_uri='/akn/ma/act/decret/2-25-366').count() == 1


def test_the_bulletins_arabic_outranks_a_translation_of_the_same_day():
    t = Text.objects.create(akn_uri='/akn/ma/act/decret/2-25-366', type='decree', number='2-25-366')
    Version.objects.create(text=t, language='ar', valid_from=date(2025, 6, 5), consolidation=Consolidation.TRANSLATION,
                           translated_from='fr')
    printed = Version.objects.create(text=t, language='ar', valid_from=date(2025, 6, 5), consolidation=Consolidation.AS_PUBLISHED)
    assert t.latest_version() == printed


def test_a_text_held_only_as_a_translation_changes_nothing():
    from apps.consolidation.services import engine
    t = Text.objects.create(akn_uri='/akn/ma/act/decret/2-25-366', type='decree', number='2-25-366')
    v = Version.objects.create(text=t, language='ar', valid_from=date(2025, 6, 5), consolidation=Consolidation.TRANSLATION,
                               translated_from='fr')
    v.articles.create(order=1, label='المادة 1', number='1', eid='art_1', body='تنسخ المادة 3 من المرسوم رقم 2.20.1.')
    stats = engine.run([t], log=lambda *a: None)
    assert not stats.get('changes')


def test_a_decrees_art_headings_and_a_dahir_with_no_article_are_cut():
    lines = [(2040, 'Décret n° 2-25-366 du 24 kaada 1446 relatif à la navigation aérienne militaire'),
             (2040, 'ARTICLE PREMIER. – Le présent décret fixe les servitudes.'),
             (2040, 'ART. 2. – .Les servitudes aéronautiques militaires sont établies.'), (2041, 'ART. 3. – Sous réserve.')]
    articles = french.split_articles(lines)
    assert [a['number'] for a in articles] == ['1', '2', '3']
    assert articles[1]['body'] == 'Les servitudes aéronautiques militaires sont établies.'


def test_an_ordinal_is_a_word_in_arabic_but_every_other_number_is_kept():
    """BO 16 of 1913: «Bureau de 1re Classe», «la 2e compagnie du 1er Tirailleurs» are words in the Bulletin's Arabic."""
    from apps.translations.management.commands.translate_french import numbers_kept
    french = 'le tirailleur de 2e classe, matricule 4882, de la 2e compagnie du 1er Tirailleurs, blessé le 30 août 1912'
    assert numbers_kept(french, 'الرامي من الدرجة الثانية، رقم 4882، من السرية الثانية، جرح في 30 غشت 1912') == []
    assert numbers_kept(french, 'الرامي من الدرجة الثانية، من السرية الثانية، جرح في 30 غشت 1912') == ['4882']
    assert numbers_kept('les articles 3 et 4', 'الفصلان 3 و') == ['4']


def test_old_ordinals_and_the_texts_own_folios_are_not_numbers_the_arabic_lost():
    """BO 9 and 18 of 1913: «10me Compagnie», «1ᵉʳ août», and the folio «78» the scan left inside a line."""
    from apps.translations.management.commands.translate_french import folios, numbers_kept
    assert numbers_kept('Sergent, 10me Compagnie du 3me Tirailleurs, nommé du 1ᵉʳ août 1913', 'رقيب، 1913') == []
    assert numbers_kept('aux commandants des directi- 78 ves d\'ensemble', 'للقادة توجيهات عامة', folios('77-78')) == []
    assert numbers_kept('puni de 30 jours', 'عوقب بثلاثين يوما', folios('77-78')) == ['30']


def test_a_translation_that_lost_a_number_is_asked_once_more_with_the_number_named(tmp_path, monkeypatch):
    from django.utils import timezone
    from apps.corpus.services import llm
    from apps.sources.models import Document, Edition, Issue
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='e' * 64, path='issues/bo_fr/BO_18_fr.pdf',
                                  mime='application/pdf', language='fr', bytes=1, fetched_at=timezone.now(), page_count=1)
    Issue.objects.create(edition=Edition.TRANSLATION_FR, number=18, date=date(1913, 3, 21), document=doc)
    uri = '/akn/ma/act/decision/1913-03-21/bofr18-9'
    FrenchText.objects.create(text_uri=uri, type='decision', title='Décision portant punition', issue_number=18,
                              issue_date=date(1913, 3, 21), document_sha='e' * 64, pages='79-79')
    FrenchArticle.objects.create(text_uri=uri, order=1, label='', number='', body='Ce sous-officier a été puni de 30 jours.',
                                 printed_page=79)
    asked = []

    def run_batch(name, requests, log=None):
        asked.append(requests)
        body = 'عوقب هذا الضابط الصف بثلاثين يوما.' if len(asked) == 1 else 'عوقب هذا الضابط الصف ب 30 يوما.'
        return {r['custom_id']: {'data': {'title': 'قرار بعقوبة', 'articles': [{'key': 'a0', 'label': '', 'body': body}]}}
                for r in requests}
    monkeypatch.setattr(llm, 'run_batch', run_batch)
    call_command('translate_french', '18', out=str(tmp_path), stdout=open('/dev/null', 'w'))
    data = json.loads((tmp_path / 'bo_18_fr.json').read_text())
    assert [t['text_uri'] for t in data['texts']] == [uri] and data['refused'] == []
    assert len(asked) == 2 and '30' in json.dumps(asked[1][0], ensure_ascii=False)


def test_a_text_only_the_french_edition_printed_before_1956_belongs_to_its_french_issue(tmp_path):
    """2 Nov 2026: the 4,712 translated texts of 1912–1925 had no issue, so their French issues had no text and /bo left
    them out. BO 7410's (an Arabic issue only not online) keep none."""
    from django.utils import timezone
    from apps.sources.models import Document, Edition, Issue
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='a' * 64, path='issues/bo_fr/BO_190_fr.pdf',
                                  mime='application/pdf', language='fr', bytes=1, fetched_at=timezone.now(), page_count=18)
    french = Issue.objects.create(edition=Edition.TRANSLATION_FR, number=190, date=date(1916, 6, 12), document=doc)
    path = tmp_path / 'bo_190_fr.json'
    old = {**_text('/akn/ma/act/arrete/1916-06-12/bofr190-4', '', kind='order'), 'pages_fr': '589-589', 'signed_on': '1916-06-02'}
    path.write_text(json.dumps({
        'issue': '190', 'date': '1916-06-12', 'arabic': 'not printed in the Arabic edition (the French Bulletin alone holds it)',
        'french': {'number': 190, 'suffix': '', 'date': '1916-06-12', 'sha256': 'a' * 64, 'url': ''},
        'translated_from': 'fr', 'translated_by': 'claude-haiku-5-5', 'prompt_version': 'tr2',
        'translated_at': '2026-11-01T22:05:17+00:00', 'texts': [old], 'refused': []}, ensure_ascii=False))
    call_command('load_translated', str(path))
    text = Text.objects.get(akn_uri='/akn/ma/act/arrete/1916-06-12/bofr190-4')
    assert (text.first_published_in, text.first_published_page) == (french, 589)
    call_command('load_translated', str(_file(tmp_path, [_text('/akn/ma/act/decret/2-25-366', '2-25-366')])))
    assert Text.objects.get(akn_uri='/akn/ma/act/decret/2-25-366').first_published_in is None
