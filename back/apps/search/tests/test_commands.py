"""The search's smaller commands and refusals, on any database: the lemma table drafted (B4) and the everyday words drafted
(C2) by Haiku (a stand-in for the API), the index rebuilt for some issues' texts, the words of old searches blanked, and an
event refused in the one error shape."""
import json
from datetime import date, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.corpus.tests import claude
from apps.search.management.commands import draft_lemmas, draft_vocab
from apps.search.models import SearchEntry, SearchEvent, SearchLog
from apps.sources.models import Edition, Issue
from apps.sources.services.ocr import SpendingNotAllowed

pytestmark = pytest.mark.django_db


def run(*args) -> str:
    out = StringIO()
    call_command(*args, stdout=out)
    return out.getvalue()


def lemmatizing(cid, params):
    """Haiku's lemmas by number: right ones, one of two words, one not Arabic, one sharing no letter, and two that name
    no word sent."""
    return {'lemmas': [{'n': 1, 'lemma': 'عقد'}, {'n': 2, 'lemma': 'العقد'}, {'n': 3, 'lemma': 'حق حقوق'},
                       {'n': 4, 'lemma': 'shart'}, {'n': 5, 'lemma': 'كتب'}, {'n': 6, 'lemma': 'محكمه'},
                       {'n': 0, 'lemma': 'عقد'}, {'n': '2', 'lemma': 'عقد'}]}


def test_the_lemma_table_maps_each_common_stem_to_its_lemmas_stem(settings, monkeypatch):
    with pytest.raises(CommandError, match=r'stem_words\.json is missing'):
        run('draft_lemmas')
    sent = claude.install(monkeypatch, settings, settings.CORPUS_DIR, lemmatizing)
    derived = settings.CORPUS_DIR / 'derived'
    derived.mkdir()
    # {stem: [its commonest written word, how often]}, read most common first: «عقد» 80, «عقود» 50, …
    (derived / 'stem_words.json').write_text(json.dumps({
        'حقوق': ['الحقوق', 30], 'عقود': ['العقود', 50], 'عقد': ['العقد', 80], 'شروط': ['الشروط', 20], 'حكم': ['الحكم', 10],
        'محاكم': ['المحاكم', 6], 'نادر': ['النادر', 4], 'ق': ['ق', 900]}, ensure_ascii=False))
    said = run('draft_lemmas', '--min', '5')
    assert said.startswith('6 stems seen 5 times or more, 1 requests; worst case $') and sent.requests() == []
    said = run('draft_lemmas', '--min', '5', '--write')
    params = sent.requests()[0]['params']
    assert params['messages'][0]['content'] == '1 العقد\n2 العقود\n3 الحقوق\n4 الشروط\n5 الحكم\n6 المحاكم'
    assert (params['model'], params['max_tokens'], params['system']) == (draft_lemmas.MODEL, 12000, draft_lemmas.SYSTEM)
    assert params['output_config']['format']['schema'] == draft_lemmas.SCHEMA
    data = json.loads((derived / 'lemmas.json').read_text())
    # «عقود» → «عقد» and «محاكم» → «محكم»; «عقد» is its own lemma; three answers refused.
    assert data['lemmas'] == {'عقود': 'عقد', 'محاكم': 'محكم'} and (data['model'], data['min']) == ('claude-haiku-5-5', 5)
    assert said.strip().splitlines()[-1] == '3 stems lemmatized, 2 of them to another stem, 3 answers refused by the rules'


def test_the_everyday_words_are_drafted_for_review_and_nothing_is_paid_without_write(settings, monkeypatch):
    seeds = json.loads(draft_vocab.SEEDS.read_text())
    groups = {k: v for k, v in seeds.items() if isinstance(v, list)}

    def answer(cid, params):
        terms = params['messages'][0]['content'].splitlines()[1:]
        return {'entries': [{'typed': terms[0], 'means': ['أ', 'ب', 'ج', 'د'], 'sure': True},
                            {'typed': terms[1], 'means': [], 'sure': False},
                            {'typed': 'not a seed', 'means': ['هـ'], 'sure': True}]}

    sent = claude.install(monkeypatch, settings, settings.CORPUS_DIR, answer)
    with pytest.raises(SpendingNotAllowed):
        run('draft_vocab')
    assert sent.requests() == []                    # refused before anything reached the API
    said = run('draft_vocab', '--write')
    assert [r['custom_id'] for r in sent.requests()] == [f'vocab-{k}' for k in groups]
    params = sent.requests()[0]['params']
    assert (params['model'], params['max_tokens'], params['system']) == (draft_vocab.MODEL, 8000, draft_vocab.SYSTEM)
    assert params['messages'][0]['content'] == 'Typed terms, one a line:\n' + '\n'.join(next(iter(groups.values())))
    assert params['output_config']['format']['schema'] == draft_vocab.SCHEMA
    drafts = json.loads((settings.CORPUS_DIR / 'reports' / 'vocab' / 'drafts.json').read_text())
    assert drafts['model'] == draft_vocab.MODEL
    assert drafts['drafts'] == [{'typed': terms[0], 'kind': kind, 'means': ['أ', 'ب', 'ج'], 'sure': True}
                                for kind, terms in groups.items()]
    assert f'{len(groups)} drafts of {sum(map(len, groups.values()))} seed terms' in said


def test_the_index_is_rebuilt_for_the_texts_of_the_issues_named():
    for number, suffix, akn in ((7533, '', '/akn/ma/act/loi/91-97'), (7465, 'bis', '/akn/ma/act/loi/92-97'),
                                (7465, '', '/akn/ma/act/loi/93-97')):            # 7465 and its «bis» are two issues
        issue = Issue.objects.create(edition=Edition.GENERAL_AR, number=number, suffix=suffix, date=date(2026, 1, 1))
        text = Text.objects.create(akn_uri=akn, type='law', number=akn[-5:], title_ar='قانون', first_published_in=issue)
        v = Version.objects.create(text=text, language='ar', valid_from=date(2026, 1, 1), consolidation=Consolidation.AS_PUBLISHED)
        Article.objects.create(version=v, order=1, label='المادة 1', number='1', eid='art_1', body='نص.')
    assert run('build_search_index', '7533', '7465-bis').strip().splitlines()[-1] == 'search index: 4 entries for 2 texts'
    assert sorted(set(SearchEntry.objects.values_list('text_path', flat=True))) == ['/ma/loi/91-97', '/ma/loi/92-97']
    assert run('build_search_index').strip().splitlines()[-1] == 'search index: 6 entries for 3 texts'


def test_the_words_of_old_searches_are_blanked_and_their_counts_stay():
    old = SearchLog.objects.create(query='عقد الكراء', folded='عقد الكراء', results=3)
    SearchLog.objects.filter(pk=old.pk).update(at=timezone.now() - timedelta(days=40))
    SearchLog.objects.create(query='الطلاق', folded='الطلاق', results=2)
    assert run('prune_search_logs').strip() == '0 searches older than 90 days kept as counts only'
    assert run('prune_search_logs', '--days', '30').strip() == '1 searches older than 30 days kept as counts only'
    assert list(SearchLog.objects.order_by('pk').values_list('query', 'folded', 'results')) == [
        ('', '', 3), ('الطلاق', 'الطلاق', 2)]


def test_an_event_names_its_search_by_number_and_a_rank_from_0_to_500(api):
    log = SearchLog.objects.create(query='x', folded='x', results=1)
    for body, field in (({'log': str(log.pk), 'kind': 'saved'}, 'log'), ({'log': log.pk, 'kind': 'saved', 'rank': 501}, 'rank'),
                        ({'log': log.pk, 'kind': 'saved', 'rank': '1'}, 'rank')):
        r = api.post('/api/search/event/', body, format='json')
        assert (r.status_code, r.json()) == (400, {'errors': [{'field': field, 'code': 'invalid'}]}), body
    assert api.post('/api/search/event/', {'log': log.pk, 'kind': 'shared', 'rank': 500}, format='json').status_code == 204
    assert list(SearchEvent.objects.values_list('kind', 'rank')) == [('shared', 500)]
