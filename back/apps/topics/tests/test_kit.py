"""The topic kit (F16 of the family plan): a topic's folder of YAML, shown to readers once a person checked it, marked
when an article it cites has changed since."""
from datetime import date

import pytest
from django.core.management import call_command

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.topics.models import Helped
from apps.topics.services import kit
from apps.topics.services.kit import folders

pytestmark = pytest.mark.django_db

HUB = """
events:
  - {key: marry, title: {ar: غادي نتزوج, fr: Je vais me marier}, to: journeys/marry}
  - {key: birth, title: {ar: تزاد عندي مولود, fr: Un enfant est né}, to: journeys/birth}
tools:
  - {key: inheritance, tool: true, title: {ar: حاسبة الإرث, fr: Héritage}}
  - {key: dates, tool: true, open: true, title: {ar: تواريخ, fr: Dates}}
"""
JOURNEYS = """
- key: marry
  title: {ar: الزواج, fr: Le mariage}
  steps:
    - {title: {ar: الملف, fr: Le dossier}, cites: [/ma/loi/70-03/art_65]}
- key: birth
  title: {ar: الولادة, fr: La naissance}
  steps: []
"""


@pytest.fixture
def family(tmp_path, monkeypatch, settings):
    settings.SHOW_DRAFTS = False
    monkeypatch.setattr(folders, 'BASE', tmp_path)
    kit.load.cache_clear()
    (tmp_path / 'family').mkdir()
    (tmp_path / 'family' / 'hub.yaml').write_text(HUB, encoding='utf-8')
    (tmp_path / 'family' / 'journeys.yaml').write_text(JOURNEYS, encoding='utf-8')
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/70-03', type='law', number='70-03', title_ar='مدونة الأسرة')
    v = Version.objects.create(text=text, language='ar', valid_from=date(2021, 7, 29), consolidation=Consolidation.ADALA)
    Article.objects.create(version=v, order=65, label='المادة 65', number='65', eid='art_65', body='يحدث ملف لعقد الزواج.')
    yield tmp_path / 'family'
    kit.load.cache_clear()


def test_nothing_reaches_a_reader_before_a_person_checks_it(family, api):
    assert api.get('/api/topics/family/journeys/marry/').status_code == 404
    assert kit.hub('family') == {'events': [], 'tools': [kit.load('family')['hub']['tools'][1]], 'reform': None,
                                 'changes': [], 'profile': None, 'urgent': None, 'learn': [], 'doors_title': None, 'beliefs': [],
                                 'next': [], 'last': None, 'marks': None, 'stages': None}
    call_command('approve_topic', 'family', 'journeys/marry', 'tools/inheritance', '--by', 'a reviewer')
    out = api.get('/api/topics/family/journeys/marry/').json()
    assert out['state'] == 'checked' and out['checked']['by'] == 'a reviewer'
    assert out['steps'][0]['cites'] == [{'path': '/ma/loi/70-03/art_65', 'label': 'المادة 65', 'number': '65',
                                         'text': out['steps'][0]['cites'][0]['text']}]
    # The door to the birth journey stays shut; the checked tool opens.
    hub = api.get('/api/topics/family/').json()['module']
    assert [e['key'] for e in hub['events']] == ['marry'] and [t['key'] for t in hub['tools']] == ['inheritance', 'dates']


def test_an_open_tool_shows_before_its_check_and_says_so(family, api):
    tools = api.get('/api/topics/family/').json()['module']['tools']
    assert [(t['key'], t['open'], t.get('checked')) for t in tools] == [('dates', True, None)]


def test_drafts_show_while_developing(family, settings):
    settings.SHOW_DRAFTS = True
    assert kit.page('family', 'journeys', 'birth')['state'] == 'draft'
    assert [e['key'] for e in kit.hub('family')['events']] == ['marry', 'birth']


def test_a_checked_page_whose_article_changed_asks_for_a_check_again(family):
    call_command('approve_topic', 'family', 'journeys/marry', '--by', 'a reviewer')
    Article.objects.filter(eid='art_65').update(body='يحدث ملف إلكتروني لعقد الزواج.')
    assert kit.page('family', 'journeys', 'marry')['state'] == 'stale'
    assert kit.problems('family') == ['journeys/marry: an article it cites changed since its check']


def test_check_topic_names_what_the_corpus_lacks(family):
    (family / 'journeys.yaml').write_text(JOURNEYS.replace('art_65', 'art_650'), encoding='utf-8')
    kit.load.cache_clear()
    assert kit.problems('family') == ['cites a missing article: /ma/loi/70-03/art_650']


def test_helped_counts_an_answer_and_keeps_nothing_about_the_reader(api):
    assert api.post('/api/topics/helped/', {'path': '/topics/family/journeys/marry#2', 'helped': False,
                                            'reason': 'unclear'}, format='json').status_code == 201
    assert Helped.objects.get().reason == 'unclear'
    bad = api.post('/api/topics/helped/', {'path': '/somewhere', 'helped': True}, format='json')
    assert bad.json() == {'errors': [{'field': 'path', 'code': 'invalid'}]}


def test_helped_takes_only_a_reason_it_knows(api):
    bad = api.post('/api/topics/helped/', {'path': '/topics/family/journeys/marry', 'helped': False, 'reason': 'boring'},
                   format='json')
    assert bad.status_code == 400 and bad.json() == {'errors': [{'field': 'reason', 'code': 'invalid'}]}
    assert not Helped.objects.exists()


def test_every_dated_line_of_a_change_names_where_it_comes_from():
    """A change's dated line names its official page, or, for a date the law itself sets (an entry into force, a last
    day), the articles that set it: never neither. The page shows whichever it has: read without the check, a line
    with no page broke seven changes' pages (17 Nov 2026)."""
    kit.load.cache_clear()
    bare = [(slug, key, line['date']) for slug in folders._folders() for key, change in kit.load(slug)['reform'].items()
            for line in change.get('timeline') or [] if not line.get('source') and not line.get('cites')]
    assert not bare, bare
    assert any(not line.get('source') for slug in folders._folders() for change in kit.load(slug)['reform'].values()
               for line in change.get('timeline') or []), 'no line without a page is left: the test below reads none'


@pytest.mark.parametrize('slug', ['family', 'work'])
def test_a_topic_folder_is_whole_in_both_languages(slug):
    """Every page it leads to exists, every citation is an article address, every sentence is in Arabic and French, and
    nothing else: a comma left unquoted in a YAML flow mapping («fr: CNSS, centre d’appel») splits it silently."""
    import re
    kit.load.cache_clear()
    content = kit.load(slug)
    keys = {f'{kind}/{key}' for kind in kit.KINDS for key in content[kind]} | {
        f'tools/{t["key"]}' for t in content['hub']['tools']}
    for kind in kit.KINDS:
        for key, item in content[kind].items():
            assert kit.links(item) <= keys, (kind, key, kit.links(item) - keys)
    assert all(re.fullmatch(r'/ma/(loi|decret|dahir|loi-organique|code|projet-loi)/[\w-]+/art_[\w-]+', p) for p in kit.cited(content))

    def bilingual(obj, where):
        if isinstance(obj, dict):
            if set(obj) & {'ar', 'fr'}:
                assert isinstance(obj.get('ar'), str) and isinstance(obj.get('fr'), str), where
                assert set(obj) <= {'ar', 'fr', 'cites'}, (where, set(obj))
            for k, v in obj.items():
                bilingual(v, f'{where}.{k}')
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                bilingual(v, f'{where}[{i}]')
    bilingual(content, slug)
    # The series add up as printed: each year read from a kept file.
    for s in content['series'].values():
        assert {y['from'] for y in s['years']} <= set(s['files']) and len({y['year'] for y in s['years']}) == len(s['years'])


def test_search_suggests_a_topics_tool_once_shown_and_keeps_violence_searches_as_counts(settings):
    kit.load.cache_clear()
    settings.SHOW_DRAFTS = False
    assert [m['path'] for m in kit.matching('كيفاش نقسمو الورث')] == ['/topics/family/tools/inheritance']   # open
    assert kit.matching('شنو هي الآجال') == []          # the dates wait for a person's check
    settings.SHOW_DRAFTS = True
    # A bare «الآجال» names no family moment since HM10 of the hard-moment review: the family's own deadlines do.
    assert next(m['path'] for m in kit.matching('شنو هي آجال مدونة الأسرة')) == '/topics/family/tools/dates'
    assert kit.private('راجلي كيضربني شنو ندير') and kit.private('violences conjugales')
    assert not kit.private('الكراء ديال الدار')


def test_a_doors_articles_come_in_the_order_its_item_names_them():
    # U17 of the Moroccan-design review: search answers under the door with the articles its first steps cite.
    from apps.topics.services.kit.items import cited_in_order
    item = {'steps': [{'cites': ['/ma/loi/65-99/art_35', '/ma/loi/65-99/art_39']},
                      {'answer': 'x', 'more': [{'cites': ['/ma/loi/65-99/art_63', '/ma/loi/65-99/art_35']}]}]}
    assert cited_in_order(item) == ['/ma/loi/65-99/art_35', '/ma/loi/65-99/art_39', '/ma/loi/65-99/art_63']


def test_a_topics_situations_are_named_from_the_files_drafts_only_when_shown():
    from apps.corpus.services import situations
    first = situations.load(situations.SITUATIONS)[0]['slug']
    with_drafts = situations.titles([first, 'no-such-situation'], include_drafts=True)
    assert [s['slug'] for s in with_drafts] == [first] and with_drafts[0]['title']['ar']
    approved = {s['slug'] for s in situations.load(situations.APPROVED)}
    assert situations.titles([first]) == ([] if first not in approved else situations.titles([first], True))


@pytest.mark.django_db
@pytest.mark.needs('fribidi')
def test_a_topic_has_its_link_picture(api, settings, tmp_path):
    # U15 of the Moroccan-design review: a link to a topic's page shows its name, line and doors on the paper.
    settings.CORPUS_DIR = tmp_path
    r = api.get('/api/topics/family/card/')
    assert r.status_code == 200 and r['Content-Type'] == 'image/png'
    assert api.get('/api/topics/no-such-topic/card/').status_code == 404


@pytest.mark.django_db
@pytest.mark.needs('fribidi')
def test_a_journey_a_tool_and_a_post_have_their_own_link_picture(api, settings, tmp_path):
    # HM5 of the hard-moment review: shared, they previewed as the bare site.
    settings.CORPUS_DIR = tmp_path
    settings.SHOW_DRAFTS = True
    kit.load.cache_clear()
    from apps.topics.services.cards import content
    journey = content('work', 'journeys/dismissed')
    assert journey['name'] == kit.page('work', 'journeys', 'dismissed')['title']['ar'] and journey['doors'] == ['الشغل']
    assert content('road', 'tools/points')['name'].startswith('شحال')
    assert content('work', 'journeys/no-such') is None
    r = api.get('/api/topics/work/card/', {'item': 'journeys/dismissed'})
    assert r.status_code == 200 and r['Content-Type'] == 'image/png'
    assert api.get('/api/topics/work/card/', {'item': '../x'}).status_code == 404
    post = api.get('/api/blog/').json()['posts'][0]['slug']
    assert api.get(f'/api/blog/{post}/card/')['Content-Type'] == 'image/png'
    assert api.get('/api/blog/no-such-post/card/').status_code == 404


@pytest.mark.needs('fribidi')
def test_a_cards_words_stop_at_a_sentences_end_when_cut():
    from PIL import Image, ImageDraw
    from apps.corpus.services.cards import _font, _lines
    d = ImageDraw.Draw(Image.new('RGB', (10, 10)))
    words = 'لكل واحد من الزوجين ذمة مالية مستقلة عن ذمة الآخر. ' + 'غير أنه يجوز لهما الاتفاق على تدبير الأموال ' * 6
    lines = _lines(d, words, _font('MarkaziText.ttf', 40, 500), 420, 4)
    assert len(lines) >= 2
    assert lines[-1].endswith('الآخر.')


def test_the_calendar_says_what_changes_next_and_what_changed_lately_never_a_bill(settings, api):
    settings.SHOW_DRAFTS = True
    c = kit.calendar('2026-10-30')
    assert c['ahead'] and all(e['date'] > '2026-10-30' for e in c['ahead'])
    assert [e['date'] for e in c['ahead']] == sorted(e['date'] for e in c['ahead'])
    assert c['behind'] and all(e['date'] <= '2026-10-30' for e in c['behind'])
    assert all(e['stage'] not in ('bill', 'announced') for e in c['ahead'] + c['behind'])
    cnops = next(e for e in c['ahead'] if e['change'] == 'cnops-2027')
    assert cnops['date'] == '2027-02-01' and cnops['path'] == '/topics/health/reform/cnops-2027' and cnops['text'] == '/ma/loi/54-23'
    pairs = [(e['topic']['slug'], e['change']) for e in c['ahead']]
    assert len(pairs) == len(set(pairs))
    settings.SHOW_DRAFTS = False
    assert api.get('/api/topics/calendar/').status_code == 200


def test_the_topics_page_gives_each_topic_its_moments_with_their_answer_and_its_next_change(settings, api):
    # The topics page (30 Oct 2026): what happens to people, as they say it, with the line that answers it.
    settings.SHOW_DRAFTS = True
    m = {t['slug']: t for t in kit.moments('2026-10-30')}
    work = m['work']
    assert work['doors'][0] == {'key': 'dismissed', 'title': {'ar': 'طردوني', 'fr': 'J’ai été licencié'},
                                'lead': work['doors'][0]['lead'], 'path': '/topics/work/journeys/dismissed'}
    assert work['doors'][0]['lead']['ar'].startswith('90 يوم') and work['count'] == len([e for e in kit.hub('work')['events'] if e.get('moment', True)])
    assert all(len(t['doors']) <= 6 for t in m.values()) and len(m) == 12
    assert m['health']['next']['date'] == '2027-02-01' and m['health']['next']['path'] == '/topics/health/reform/cnops-2027'
    assert m['family']['next'] is None
    # Only what may be shown: without the drafts, a door whose answer waits for its review is not a moment yet.
    settings.SHOW_DRAFTS = False
    assert api.get('/api/topics/moments/').status_code == 200
    assert sum(t['count'] for t in kit.moments('2026-10-30')) < sum(t['count'] for t in m.values())
