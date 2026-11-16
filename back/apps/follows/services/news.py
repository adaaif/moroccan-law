"""What changed in what someone follows (R13 of the for-everyone review): a law, an article or a life topic. The site knows
a text changed from the links pipeline (apps.consolidation): the article, the text that changed it, the BO issue and
page that printed the change. A change the pipeline could not settle is said to be unsettled, never told as fact.

Each item has a key that outlives a reload of the changes (the amending text and its issue), so the device and the
letters tell only what is new to the reader: what they had not seen, not what is recent."""
import re

from apps.accounts.services.refusals import Refused
from apps.consolidation.services import history
from apps.consolidation.services.instructions import label_key
from apps.corpus.models import Text
from apps.corpus.services import works
from apps.topics.services import kit, topics
from apps.corpus.services.addresses import split_path, text_path
from apps.corpus.services.codes import display_name
from apps.discussion.services import anchors

PATHS_MAX = 60
ITEMS_MAX = 20
PATH_MAX = 300          # a follow's row (apps.follows.models.Follow.path)
UNSETTLED = {'unclear', 'conflict'}


def kind_of(path: str) -> str:
    if path.startswith('/topics/'):
        return 'topic'
    if path.startswith('/places/'):
        # A state or a Moroccan place of «البلدان والمدن» has a Latin slug (apps/places, 1 Nov 2026); a commune followed
        # from the land's finder kept its Arabic name.
        return 'where' if re.fullmatch(r'/places/[a-z0-9-]+', path) else 'place'
    if not path.startswith('/ma/'):
        return ''
    return 'article' if split_path(path)[1] else 'text'


def name(text: Text) -> dict:
    """What people call the text, else its title said short (P6 of the polish review)."""
    n = display_name(text)
    return {'ar': n['ar'], 'fr': n['fr'] or n['ar']}


def describe(path: str, known: dict | None = None) -> dict:
    """What a followed address is, named in both languages. Refused when the site does not hold it. `known` holds the
    texts, articles and places a list of addresses was read with (`known_of`)."""
    path = str(path or '').strip()
    kind = kind_of(path)
    if kind == 'topic':
        slug, _, rest = path.removeprefix('/topics/').partition('/')
        topic = topics.find(slug)
        key = rest.removeprefix('reform/') if rest.startswith('reform/') else 'reform' if rest == 'reform' else ''
        reform = kit.page(slug, 'reform', key) if topic and key else None
        if reform:     # a topic's reform (F12 of the family plan): its record grows, the reader is told
            return {'path': path, 'kind': 'reform', 'name': reform['title']}
        if topic and not rest:
            return {'path': path, 'kind': kind, 'name': topic['name']}
    elif kind == 'where':
        from apps.places.models import Place
        slug = path.removeprefix('/places/')
        p = known['places'].get(slug) if known else (
            Place.objects.filter(slug=slug).values('name_ar', 'name_fr', 'name_en').first())
        if p:
            return {'path': path, 'kind': kind, 'name': {'ar': p['name_ar'], 'fr': p['name_fr'] or p['name_en'] or p['name_ar']}}
    elif kind == 'place':
        # A commune followed from «أرضي فالجريدة الرسمية» (M10 of the land review): its land texts are its news.
        from urllib.parse import unquote
        place = unquote(path.removeprefix('/places/')).strip()
        # A commune's name as printed, never longer than a follow's row holds.
        if place and len(path) <= PATH_MAX:
            return {'path': path, 'kind': kind, 'name': {'ar': place, 'fr': place}}
    elif kind == 'text':
        uri = split_path(path)[0]
        text = known['texts'].get(uri) if known else Text.objects.filter(akn_uri=uri).first()
        if text:
            return {'path': text_path(text.akn_uri), 'kind': kind, 'name': name(text)}
    elif kind == 'article':
        a = known['anchors'].get(path) if known else anchors.find_many([path]).get(path)
        if a is not None:
            return {'path': a.path, 'kind': kind, 'name': name(a.text), 'article': a.article.label}
    raise Refused('path', 'not_found', 404)


def known_of(paths: list[str], recent: bool = False) -> dict:
    """The texts, articles, places and changes a list of addresses names, read once for all of them (three queries an
    address before: 130 for a device following 40). `recent`: with what `items` lists for the states and communes among
    them, read the same way (two queries an address before), and room for each topic's recent texts, read once a
    topic."""
    texts = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in={split_path(p)[0] for p in paths
                                                                  if kind_of(p) in ('text', 'article')})}
    found = anchors.find_many([p for p in paths if kind_of(p) == 'article'])
    # A bill's stages (P16 of the finance-bill review), and what bills propose for the articles followed.
    from apps.corpus.models import Consolidation, Version
    bills = [uri for uri, t in texts.items() if t.type == 'bill']
    stages = list(Version.objects.filter(text__akn_uri__in=bills, consolidation=Consolidation.BILL)
                  .select_related('source_document', 'text')) if bills else []
    from apps.places.models import Place
    slugs = [p.removeprefix('/places/') for p in paths if kind_of(p) == 'where']
    places = {p.pop('slug'): p for p in Place.objects.filter(slug__in=slugs).values('slug', 'name_ar', 'name_fr', 'name_en')} \
        if slugs else {}
    out = {'texts': texts, 'anchors': found, 'changes': history.changes_of(texts),
           'proposals': history.proposals_many(texts), 'stages': stages, 'places': places}
    if recent:
        from urllib.parse import unquote

        from apps.places.services import finder
        from apps.topics.services import places as land
        communes = [unquote(p.removeprefix('/places/')).strip() for p in paths if kind_of(p) == 'place']
        out['recent'] = {'where': finder.recent_many(slugs) if slugs else {},
                         'place': land.of_places(communes) if communes else {}, 'topics': {}}
    return out


def items(what: dict, known: dict | None = None) -> list[dict]:
    """Everything the site holds that changed the address, newest first."""
    if what['kind'] == 'reform':
        slug, _, rest = what['path'].removeprefix('/topics/').partition('/')
        reform = kit.page(slug, 'reform', rest.removeprefix('reform/') if rest.startswith('reform/') else 'reform') or {}
        return [{'key': f"reform:{e['date']}", 'kind': 'reform', 'on': e['date'], 'text': e['text'], 'source': e['source']}
                for e in sorted(reform.get('timeline') or [], key=lambda e: e['date'], reverse=True)]
    read = (known or {}).get('recent')
    if what['kind'] == 'where':
        # A state or a Moroccan place (PL22 of the places review): the newest texts that name it.
        from apps.places.services import finder
        slug = what['path'].removeprefix('/places/')
        return [{'key': f"where:{t['path']}", 'kind': 'new_text', 'on': t['date'].isoformat(),
                 'text': {'path': t['path'], 'title': t['title'], 'name': {'ar': t['title'], 'fr': None}, 'date': t['date'].isoformat(),
                          'issue': t['issue'], 'kind': t['kind']}}
                for t in (read['where'].get(slug, []) if read else finder.recent(slug))]
    if what['kind'] == 'place':
        from apps.topics.services import places
        commune = what['name']['ar']
        return [{'key': f"place:{t['path']}", 'kind': 'new_text', 'on': t['date'],
                 'text': {'path': t['path'], 'title': t['title'], 'name': {'ar': t['title'], 'fr': None}, 'date': t['date'],
                          'issue': t['issue'], 'kind': t['kind']}}
                for t in (read['place'].get(commune, []) if read else places.of_place(commune))]
    if what['kind'] == 'topic':
        # Read once a topic for all who follow it (the topics are a fixed few).
        kept = read['topics'] if read else {}
        if what['path'] not in kept:
            topic = topics.find(what['path'].removeprefix('/topics/'))
            kept[what['path']] = [{'key': f"text:{t['path']}", 'kind': 'new_text', 'on': t['date'], 'text': t}
                                  for t in topics.recent(topic)]
        return list(kept[what['path']])
    uri, eid = split_path(what['path'])
    if not known:
        known = known_of([what['path']])
    text = known['texts'].get(uri)
    if text is not None and text.type == 'bill':
        return bill_stages(text, known['stages'])
    table = known['changes'][uri]
    proposed = []
    if eid:
        a = known['anchors'][what['path']].article
        rows = [(label_key(a.label) or a.number, e) for e in history.changes_for(table, a.label, a.number)]
        p = known['proposals'].get(uri, {}).get(label_key(a.label) or a.number)
        if p and p['filed_on']:
            # A bill proposes to change the article followed: said as a bill's, never as a change.
            bill = (p['name'] or {}).get('ar') or ''
            proposed.append({'key': f"proposed:{p['bill']}", 'kind': 'reform', 'on': p['filed_on'],
                             'text': {'ar': f'{bill} يقترح تغيير هذه المادة (مشروع، ماشي قانون)',
                                      'fr': f"Le {(p['name'] or {}).get('fr') or bill} propose de modifier cet article (un projet, pas une loi)"},
                             'source': {'name': p['name'] or {'ar': bill, 'fr': bill}, 'url': p['bill']}})
    else:
        rows = [(number, e) for number, entries in table.items() for e in entries]
    out: dict[str, dict] = {}
    for number, e in rows:
        if not e['on']:
            continue
        key = f"{e['by']['kind']}:{works.fold(e['by']['number'])}:{e['issue']['number'] or ''}"
        item = out.setdefault(key, {'key': key, 'kind': 'changed', 'on': e['on'], 'by': e['by'], 'issue': e['issue'],
                                    'articles': [], 'verbs': [], 'settled': True, 'effective_on': e['effective_on']})
        if number and number not in item['articles']:
            item['articles'].append(number)
        if e['verb'] not in item['verbs']:
            item['verbs'].append(e['verb'])
        item['settled'] = item['settled'] and e['state'] not in UNSETTLED
    return sorted([*out.values(), *proposed], key=lambda i: (str(i['on']), i['key']), reverse=True)


STAGE_WORDS = {
    'filed': ('أودعته الحكومة في البرلمان', 'Déposé par le gouvernement au Parlement'),
    'representatives': ('صوّت عليه مجلس النواب', 'Voté par la Chambre des représentants'),
    'councillors': ('صوّت عليه مجلس المستشارين', 'Voté par la Chambre des conseillers'),
    'second_reading': ('صوّت عليه مجلس النواب في قراءة ثانية', 'Voté en seconde lecture par la Chambre des représentants'),
}


def bill_stages(text: Text, stages) -> list[dict]:
    """A bill followed (P16): each stage the site holds, as the chamber's vote or the filing, with its file."""
    out = []
    for v in (v for v in stages if v.text_id == text.pk):
        meta = v.source_document.meta if v.source_document_id else {}
        ar, fr = STAGE_WORDS.get(meta.get('stage') or 'filed', STAGE_WORDS['filed'])
        out.append({'key': f'bill:{v.valid_from}', 'kind': 'reform', 'on': v.valid_from, 'text': {'ar': ar, 'fr': fr},
                    'source': {'name': name(text), 'url': (v.source_document.url if v.source_document_id else '') or text_path(text.akn_uri)}})
    return sorted(out, key=lambda i: i['on'], reverse=True)


def news(paths: list[str], most: int = ITEMS_MAX) -> list[dict]:
    """Each address the site holds, with what changed it, newest first. The reader's device knows which it has seen."""
    out = []
    paths = list(dict.fromkeys(str(p).strip() for p in paths))[:PATHS_MAX]
    known = known_of(paths, recent=True)
    for path in paths:
        try:
            what = describe(path, known)
        except Refused:
            continue
        found = items(what, known)
        out.append({**what, 'items': found[:most], 'total': len(found)})
    return out


def keys(path: str) -> list[str]:
    return [i['key'] for i in items(describe(path))]
