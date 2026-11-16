"""The test set (B1 of the search plan, 24 Oct 2026): new questions, written by Haiku from articles drawn at random from
the whole corpus, one question an article, in six registers taken in turn. A person checks each one before it counts;
until lawyers join, a provisional check by the editors stands (24 Oct 2026), and each question says so.

Half the articles come from laws, codes and dahirs, three in ten from decrees, two in ten from orders and decisions:
what people look for, without leaving the rest out. Articles that only publish, repeal or start a text are skipped."""
import random
import re

from django.db.models.functions import Length

from apps.consolidation.services.instructions import label_key
from apps.corpus.services.addresses import article_path, text_path
from apps.corpus.services.codes import display_name
from apps.search.models import SearchEntry
from apps.search.services.judge import anchors
from apps.translations.models import FrenchArticle

MODEL = 'claude-haiku-5-5'
PROMPT = 't1'
STRATA = (('laws', ('law', 'organic_law', 'dahir', 'decree_law', 'code', 'constitution', 'other'), 0.5),
          ('decrees', ('decree',), 0.3),
          ('orders', ('order', 'decision'), 0.2))
REGISTERS = {
    'msa': ('Modern Standard Arabic, as an educated Moroccan types it: no vowel marks, plain words',
            'ما هي مدة الإشعار قبل إفراغ المكتري؟'),
    'darija': ('Moroccan Darija in Arabic letters, as typed on a phone, spelling as people write it',
               'واش مول الدار يقدر يخرجني بلا إنذار؟'),
    'darija_latin': ('Moroccan Darija in Latin letters, digits for Arabic letters (3 for ع, 7 for ح, 9 for ق, 2 for ء, '
                     '5 or kh for خ, gh for غ, ch for ش)',
                     'wach mol dar y9der ykhrjni bla indar?'),
    'french': ('French as a Moroccan types it, accents sometimes missing',
               'delai de preavis pour quitter un logement loue'),
    'english': ('English, as a foreigner living in Morocco or an AI assistant would ask',
                'how much notice must a landlord give before evicting a tenant in Morocco'),
    'professional': ('a lawyer\'s or a law student\'s query in Arabic: legal terms, may name the code or the law and its '
                     'number, often no full sentence',
                     'أجل الإنذار بالإفراغ في القانون 67.12'),
}
INTENTS = ('name', 'number', 'procedure', 'definition', 'question', 'words')
SYSTEM = (
    'You write test questions for a free search engine of Moroccan law. You get one article of a Moroccan legal text '
    'and a register. Write ONE search that a real person in Morocco would type, in that register, whose answer is in '
    'this article: the article must be a right answer, ideally the best one.\n'
    'Rules:\n'
    '- Write as people type: their own words for the situation, not the article\'s wording. Never copy a phrase of '
    'four words or more from the article.\n'
    '- Never give the article\'s number. Only the professional register may name the text (by its name or number).\n'
    '- One search only, at most 20 words.\n'
    '- Set usable to false, with an empty question, when nobody would search for this article: it only publishes, '
    'starts, repeals or lists texts, names people, approves a deal, or is a table with no context.\n'
    '- intent: name (asks for a text by its name), number (a duration, amount, rate or age), procedure (how to do '
    'something), definition (what a term means), question (any other question), words (a few words, no question).\n'
    '- why: at most 15 words, in English, on what in the article answers the search.')
SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['usable', 'question', 'intent', 'why'],
    'properties': {
        'usable': {'type': 'boolean'},
        'question': {'type': 'string'},
        'intent': {'type': 'string', 'enum': list(INTENTS)},
        'why': {'type': 'string'},
    },
}
# Articles that only publish, start or repeal a text, or are too short to ask about.
FORMAL = re.compile(r'ينشر (?:هذا|هذه)|بالجريدة الرسمية|يعهد بتنفيذ|يدخل هذا .{0,40}حيز التنفيذ|تنسخ (?:جميع )?(?:المقتضيات|أحكام)|'
                    r'sera publié|est abrogé|entre en vigueur')
MIN_CHARS = 150
BODY_MAX, FRENCH_MAX = 4000, 1500


def sample(n: int, seed: int) -> list[dict]:
    """`n` articles of the index (each text's latest version, texts not known repealed), drawn by stratum with `seed`,
    each given its register in turn. Five queries whatever `n`."""
    rng = random.Random(seed)
    rows = list(SearchEntry.objects.filter(kind=SearchEntry.Kind.ARTICLE, in_force=True)
                .annotate(chars=Length('body')).filter(chars__gte=MIN_CHARS)
                .order_by('id').values_list('text_path', 'eid', 'text_type'))
    chosen: list[tuple] = []
    for _, kinds, share in STRATA:
        pool = [(p, e) for p, e, t in rows if t in kinds]
        rng.shuffle(pool)
        chosen += pool[:round(n * share * 1.25)]     # a quarter more: the formal ones fall out below
    found = anchors([f'{p}/{e}' for p, e in chosen])
    keep = [found[f'{p}/{e}'].article for p, e in chosen if f'{p}/{e}' in found]
    keep = [a for a in keep if not (len(a.body) < 400 and FORMAL.search(a.body))]
    rng.shuffle(keep)
    keep = keep[:n]
    uris = {a.version.text.akn_uri for a in keep}
    french = {(u, num): body for u, num, body in
              FrenchArticle.objects.filter(text_uri__in=uris).values_list('text_uri', 'number', 'body')}
    names = list(REGISTERS)
    out = []
    for i, a in enumerate(keep):
        text = a.version.text
        out.append({'id': f'q{i:04d}', 'article': a, 'text': text, 'register': names[i % len(names)],
                    'path': article_path(text.akn_uri, a.eid), 'text_path': text_path(text.akn_uri),
                    'french': french.get((text.akn_uri, label_key(a.label) or a.number), '')})
    return out


def content(item: dict) -> str:
    text, a = item['text'], item['article']
    description, example = REGISTERS[item['register']]
    parts = [f"Register: {item['register']}: {description}. For example: {example}",
             f"Text: {display_name(text)['ar']} ({text.title_ar[:300]})",
             f"Headings: {' › '.join(a.heading_path or []) or '-'}",
             f"Article: {a.label}\n{a.body[:BODY_MAX]}"]
    if item['french']:
        parts.append(f"Official French: {item['french'][:FRENCH_MAX]}")
    return '\n\n'.join(parts)


def requests(items: list[dict]) -> list[dict]:
    from apps.corpus.services.llm import request

    return [request(item['id'], model=MODEL, system=SYSTEM, content=content(item), schema=SCHEMA, max_tokens=1500)
            for item in items]


def questions(items: list[dict], results: dict) -> tuple[list[dict], dict]:
    """The usable questions, as goldset items, and what fell out ({reason: count})."""
    out, dropped = [], {'not usable': 0, 'no answer': 0, 'too long': 0}
    for item in items:
        got = (results.get(item['id']) or {}).get('data')
        if not got:
            dropped['no answer'] += 1
            continue
        q = ' '.join((got.get('question') or '').split())
        if not got.get('usable') or not q:
            dropped['not usable'] += 1
            continue
        if len(q.split()) > 25:
            dropped['too long'] += 1
            continue
        out.append({'q': q, 'expect': [item['path']], 'register': item['register'], 'intent': got['intent'],
                    'why': got.get('why', ''), 'text_type': item['text'].type, 'checked': 'owner-provisional',
                    'drafted_by': MODEL, 'prompt': PROMPT})
    return out, dropped
