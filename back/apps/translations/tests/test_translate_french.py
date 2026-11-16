"""`translate_french` (31 Oct 2026): the texts of an issue held only in its official French given Arabic by the model,
once, to a file `load_translated` reads anywhere. The model's answers come from a stand-in for the API, in its shapes."""
import json
from datetime import date, datetime
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.corpus.models import Consolidation, Text, Version
from apps.corpus.tests import claude
from apps.sources.models import Document, Edition, Issue
from apps.sources.services.ocr import SpendingNotAllowed
from apps.translations.management.commands import translate_french
from apps.translations.models import FrenchArticle, FrenchText

pytestmark = pytest.mark.django_db

DECREE = '/akn/ma/act/decret/2-25-366'
HELD = '/akn/ma/act/decret/2-25-269'
TRANSLATED = '/akn/ma/act/decret/2-25-400'


def french_issue():
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='f' * 64, path='issues/bo_fr/BO_7410_fr.pdf',
                                  mime='application/pdf', language='fr', bytes=1, fetched_at=timezone.now(),
                                  page_count=40, url='https://example.org/BO_7410_fr.pdf')
    return Issue.objects.create(edition=Edition.TRANSLATION_FR, number=7410, date=date(2025, 6, 5), document=doc)


def french_text(uri, number, bodies, pages='2040-2041'):
    FrenchText.objects.create(text_uri=uri, type='decree', number=number, signed_on=date(2025, 5, 22),
                              title=f'Décret n° {number} relatif à la navigation aérienne militaire', issue_number=7410,
                              issue_date=date(2025, 6, 5), document_sha='f' * 64, pages=pages)
    for k, body in enumerate(bodies):
        FrenchArticle.objects.create(text_uri=uri, order=k + 1, label='Article premier' if k == 0 else f'Art. {k + 1}',
                                     number=str(k + 1), body=body, printed_page=int(pages[:4]))


def run(*args, **opts) -> str:
    out = StringIO()
    call_command('translate_french', '7410', *args, stdout=out, **opts)
    return out.getvalue()


def test_an_issue_not_registered_is_refused(tmp_path):
    with pytest.raises(CommandError, match=r'BO 7410 \(French\) is not registered'):
        run(out=str(tmp_path))


class Clock(datetime):
    """The clock standing still at the moment the file is written."""

    @classmethod
    def now(cls, tz=None):
        return datetime(2026, 10, 31, 22, 5, 17, 482000, tzinfo=tz)


def test_a_text_held_in_arabic_is_never_sent_and_one_well_translated_is_asked_once(tmp_path, settings, monkeypatch):
    """BO 7410: one decree held as printed in Arabic, one held only as an earlier machine translation (translated again),
    one held in French alone."""
    monkeypatch.setattr(translate_french, 'datetime', Clock)
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: {
        't0': {'title': 'مرسوم رقم 2-25-400 بتحديد المناطق', 'articles': [
            {'key': 'a0', 'label': 'المادة الفريدة', 'body': 'تحدد المناطق.'}]},
        't1': {'title': 'مرسوم رقم 2-25-366 يتعلق بالملاحة الجوية العسكرية', 'articles': [
            {'key': 'a0', 'label': 'المادة الأولى', 'body': 'يحدد هذا المرسوم الارتفاقات المنصوص عليها في المادة 3.'},
            {'key': 'a1', 'label': 'المادة 2', 'body': 'تطبق أحكام المرسوم رقم 2-20-1 على الطائرات.'}]}}[cid])
    french_issue()
    french_text(DECREE, '2-25-366', ["Le présent décret fixe les servitudes prévues à l'article 3.",
                                     "Les dispositions du décret n° 2-20-1 s'appliquent aux aéronefs."])
    french_text(HELD, '2-25-269', ['Le texte imprimé en arabe.'])
    french_text(TRANSLATED, '2-25-400', ['Les zones sont fixées.'], pages='2030-2030')     # printed first: asked first
    for uri, held_as in ((HELD, Consolidation.AS_PUBLISHED), (TRANSLATED, Consolidation.TRANSLATION)):
        text = Text.objects.create(akn_uri=uri, type='decree', number=uri.rsplit('/', 1)[1])
        Version.objects.create(text=text, language='ar', valid_from=date(2025, 5, 22), consolidation=held_as)
    with pytest.raises(SpendingNotAllowed):
        run(out=str(tmp_path))                                    # nothing is paid unasked
    said = run('--write', out=str(tmp_path), max_tokens=8000)
    assert said.startswith('BO 7410 fr: 3 texts, 1 held in Arabic, 2 to translate\n')
    assert said.rstrip().endswith(f'{tmp_path}/bo_7410_fr.json: 2 texts translated, 0 refused')
    assert [r['custom_id'] for r in sent.requests()] == ['t0', 't1']      # one asking: nothing to ask again
    params = sent.requests()[1]['params']
    assert (params['model'], params['max_tokens'], params['thinking'], params['system']) == (
        'claude-haiku-5-5', 8000, {'type': 'disabled'}, translate_french.SYSTEM)
    assert json.loads(params['messages'][0]['content']) == {
        'title': 'Décret n° 2-25-366 relatif à la navigation aérienne militaire', 'articles': [
            {'key': 'a0', 'label': 'Article premier', 'body': "Le présent décret fixe les servitudes prévues à l'article 3."},
            {'key': 'a1', 'label': 'Art. 2', 'body': "Les dispositions du décret n° 2-20-1 s'appliquent aux aéronefs."}]}
    data = json.loads((tmp_path / 'bo_7410_fr.json').read_text())
    assert {k: data[k] for k in ('issue', 'date', 'arabic', 'translated_from', 'translated_by', 'prompt_version',
                                 'translated_at')} == {
        'issue': '7410', 'date': '2025-06-05', 'arabic': 'not online (the SGG answers 404)', 'translated_from': 'fr',
        'translated_by': 'claude-haiku-5-5', 'prompt_version': 'tr2', 'translated_at': '2026-10-31T22:05:17+00:00'}
    assert data['french'] == {'number': 7410, 'suffix': '', 'date': '2025-06-05', 'sha256': 'f' * 64,
                              'url': 'https://example.org/BO_7410_fr.pdf'}
    assert [t['text_uri'] for t in data['texts']] == [TRANSLATED, DECREE]
    text = data['texts'][1]
    assert {k: text[k] for k in ('type', 'number', 'signed_on', 'title_fr', 'pages_fr')} == {
        'type': 'decree', 'number': '2-25-366', 'signed_on': '2025-05-22',
        'title_fr': 'Décret n° 2-25-366 relatif à la navigation aérienne militaire', 'pages_fr': '2040-2041'}
    # A text's number written as the Arabic Bulletin prints it.
    assert text['title_ar'] == 'مرسوم رقم 2.25.366 يتعلق بالملاحة الجوية العسكرية'
    assert text['articles'] == [
        {'order': 1, 'number': '1', 'label_fr': 'Article premier', 'page_fr': 2040,
         'body_fr': "Le présent décret fixe les servitudes prévues à l'article 3.",
         'label_ar': 'المادة الأولى', 'body_ar': 'يحدد هذا المرسوم الارتفاقات المنصوص عليها في المادة 3.'},
        {'order': 2, 'number': '2', 'label_fr': 'Art. 2', 'page_fr': 2040,
         'body_fr': "Les dispositions du décret n° 2-20-1 s'appliquent aux aéronefs.",
         'label_ar': 'المادة 2', 'body_ar': 'تطبق أحكام المرسوم رقم 2.20.1 على الطائرات.'}]
    assert data['refused'] == []


def test_a_translation_that_loses_a_number_is_asked_again_with_it_named_and_kept_out_when_it_loses_it_again(
        tmp_path, settings, monkeypatch):
    """BO 16 of 1913: the tirailleur's number 4882 left out of the Arabic twice; another text whose answer keys an
    article that was not sent is asked again as it was, nothing to name."""
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: {
        't0': {'title': 'قرار', 'articles': [{'key': 'a0', 'label': '', 'body': 'جرح الرامي في 30 غشت 1912.'}]},
        't1': {'title': 'قرار', 'articles': [{'key': 'a0', 'label': '', 'body': 'يعين.'},
                                             {'key': 'a7', 'label': '', 'body': 'ينقل.'}]}}[cid])
    french_issue()
    french_text(DECREE, '2-25-366', ['Le tirailleur, matricule 4882, blessé le 30 août 1912.'], pages='2040-2040')
    french_text(TRANSLATED, '2-25-400', ['Est nommé.', 'Est muté.'], pages='2041-2041')
    said = run('--write', out=str(tmp_path))
    first, second = sent.requests()[:2], sent.requests()[2:]
    assert [r['custom_id'] for r in first] == [r['custom_id'] for r in second] == ['t0', 't1']
    assert [json.loads(r['params']['messages'][0]['content']).get('note') for r in first] == [None, None]
    assert [json.loads(r['params']['messages'][0]['content']).get('note') for r in second] == [
        'Each of these numbers of the French must appear in the Arabic in Western digits: 4882', None]
    data = json.loads((tmp_path / 'bo_7410_fr.json').read_text())
    assert data['texts'] == [] and data['refused'] == [{'text_uri': DECREE, 'why': "numbers lost: ['4882']"},
                                                       {'text_uri': TRANSLATED, 'why': 'an article missing'}]
    assert said.rstrip().endswith(
        f"0 texts translated, 2 refused: {DECREE} (numbers lost: ['4882']); {TRANSLATED} (an article missing)")


def test_a_translation_cut_short_twice_is_kept_out_of_the_file_and_named(tmp_path, settings, monkeypatch):
    cut = ('{"title": "مرسوم", "articles": [{"key": "a0", "label": "المادة الأولى", "body": "يحدد', 'max_tokens')
    sent = claude.install(monkeypatch, settings, tmp_path, lambda cid, params: cut)
    french_issue()
    french_text(DECREE, '2-25-366', ['Le présent décret fixe les servitudes.'])
    said = run('--write', out=str(tmp_path), arabic='not printed in the Arabic edition')
    assert len(sent.requests()) == 2                                  # asked once more, then given up
    data = json.loads((tmp_path / 'bo_7410_fr.json').read_text())
    assert data['texts'] == [] and data['arabic'] == 'not printed in the Arabic edition'
    [(uri, why)] = [(r['text_uri'], r['why']) for r in data['refused']]
    assert uri == DECREE and why.startswith('not JSON: ')
    assert '1 to translate\n' in said and f'0 texts translated, 1 refused: {DECREE} (not JSON: ' in said
