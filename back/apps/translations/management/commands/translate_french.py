"""Arabic for the texts of an issue whose Arabic edition the SGG never put online, from its official French translation
(31 Oct 2026: translated by a model and said clearly to be a translation from the French; BO 7410 of 5 Jun 2025 answers
404 in Arabic, its French edition is held). A model translates each text once; the result is a file, read and loaded by
`load_translated` anywhere with no API, so every database shows the same words. Never a text whose Arabic the site holds.

    process_issue 7410 --edition translation_fr --date 2025-06-05 --steps ingest,ocr,number,toc,load   # the French
    translate_french 7410                     # → apps/translations/data/translated/bo_7410_fr.json
    load_translated apps/translations/data/translated/bo_7410_fr.json

Each text is checked: as many articles back as sent, and every number of the French found in the Arabic (dates,
amounts, references); a text that fails is kept out of the file and named."""
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from apps.corpus.models import Version
from apps.corpus.services import llm
from apps.sources.models import Edition, Issue
from apps.translations.models import FrenchArticle, FrenchText
from apps.sources.services.ocr import allow_spending

MODEL = 'claude-haiku-5-5'
PROMPT_VERSION = 'tr2'
OUT = Path(__file__).resolve().parents[2] / 'data' / 'translated'
SYSTEM = (
    'You translate the official French translation of a Moroccan legal text from the Bulletin officiel back into the '
    'Arabic the Bulletin itself prints. Use its register and set phrases: «ظهير شريف»، «مرسوم»، «قرار»، «المادة»، '
    '«الحمد لله وحده»، «الطابع الشريف»، «يعلم من ظهيرنا الشريف هذا»، «أصدرنا أمرنا الشريف بما يلي»، «وحرر بالرباط في»، '
    '«وقعه بالعطف»، «يسند تنفيذ هذا المرسوم إلى»، «ينشر بالجريدة الرسمية». Dates as the Bulletin writes them: «12 من شوال '
    '1446 (11 أبريل 2025)», Moroccan month names (يناير، فبراير، مارس، أبريل، ماي، يونيو، يوليو، غشت، شتنبر، أكتوبر، '
    'نونبر، دجنبر). Digits stay Western. Every number, reference, amount and date is kept exactly; a text number '
    '«1-25-39» is written «1.25.39». Names of people and places as Moroccan official Arabic writes them. Translate '
    'faithfully: add nothing, leave nothing out, keep each article\'s paragraphs and lists; a table stays a Markdown table.'
)
SCHEMA = {
    'type': 'object', 'additionalProperties': False, 'required': ['title', 'articles'],
    'properties': {
        'title': {'type': 'string'},
        'articles': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False, 'required': ['key', 'label', 'body'],
            'properties': {'key': {'type': 'string'}, 'label': {'type': 'string'}, 'body': {'type': 'string'}}}},
    },
}
NUMBERS = re.compile(r'\d+')
# An ordinal is a word in Arabic («Bureau de 1re Classe» is «من الدرجة الأولى», «2e alinéa» «الفقرة الثانية»): not a
# number the Arabic must print.
ORDINAL = re.compile(r'\d+\s*(?:ers?|res?|ères?|èmes?|emes?|mes?|e|[\u1d49\u02b3\u1d48\u1d50\u02e2]+)(?!\w)')


def printed_numbers(arabic: str) -> str:
    """A text's number after «رقم» as the Arabic Bulletin prints it: «2-25-366» is «2.25.366», «1346-25» «1346.25»."""
    return re.sub(r'(رقم\s+)(\d[\d\-]*\d)', lambda m: m.group(1) + m.group(2).replace('-', '.'), arabic)


def numbers_kept(french: str, arabic: str, folios: set[str] = frozenset()) -> list[str]:
    """The French's numbers the Arabic lacks («1-25-39» may be written «1.25.39»: the digits are compared alone),
    its ordinals and the text's own page numbers aside (a folio the scan left inside a line: «directi- 78 ves»)."""
    have = set(NUMBERS.findall(arabic))
    return sorted({n for n in NUMBERS.findall(ORDINAL.sub(' ', french)) if n not in have and n not in folios})


def folios(pages: str) -> set[str]:
    """«79-81» → {'79', '80', '81'}."""
    m = re.fullmatch(r'(\d+)-(\d+)', pages or '')
    return {str(n) for n in range(int(m.group(1)), int(m.group(2)) + 1)} if m and int(m.group(2)) - int(m.group(1)) < 40 else set()


class Command(BaseCommand):
    help = 'Translate into Arabic the texts of an issue held only in its official French edition (once, to a file).'

    def add_arguments(self, parser):
        parser.add_argument('--write', action='store_true', help='send the paid requests (without it, nothing is paid)')
        parser.add_argument('issue', help='The issue key, «7410».')
        parser.add_argument('--max-tokens', type=int, default=16000)
        parser.add_argument('--out', help='the folder the file goes to (default: the app\'s data/translated)')
        parser.add_argument('--arabic', default='not online (the SGG answers 404)',
                            help='why the Arabic is missing, said in the file')

    def handle(self, *args, issue, max_tokens, **opts):
        allow_spending(opts['write'], log=self.stdout.write)
        number, suffix = Issue.parse_key(issue)
        french_issue = Issue.objects.filter(edition=Edition.TRANSLATION_FR, number=number, suffix=suffix).first()
        if french_issue is None:
            raise CommandError(f'BO {issue} (French) is not registered: process_issue {issue} --edition translation_fr first.')
        texts = list(FrenchText.objects.filter(issue_number=number, issue_suffix=suffix).order_by('pages', 'text_uri'))
        held = set(Version.objects.filter(text__akn_uri__in=[t.text_uri for t in texts], language='ar')
                   .exclude(consolidation='translation').values_list('text__akn_uri', flat=True))
        todo = [t for t in texts if t.text_uri not in held]
        self.stdout.write(f'BO {issue} fr: {len(texts)} texts, {len(held)} held in Arabic, {len(todo)} to translate')
        articles = {t.text_uri: [] for t in todo}
        for a in FrenchArticle.objects.filter(text_uri__in=list(articles)).order_by('text_uri', 'order'):
            articles[a.text_uri].append(a)

        def ask(i: int, t, keep: list[str] = ()):
            keyed = [{'key': f'a{k}', 'label': a.label, 'body': a.body} for k, a in enumerate(articles[t.text_uri])]
            body = {'title': t.title, 'articles': keyed}
            if keep:        # a second asking: the numbers the first Arabic lacked, named
                body = {'note': 'Each of these numbers of the French must appear in the Arabic in Western digits: '
                                + ', '.join(keep), **body}
            return llm.request(f't{i}', model=MODEL, system=SYSTEM, content=json.dumps(body, ensure_ascii=False),
                               schema=SCHEMA, max_tokens=max_tokens, think=False)

        def check(t, answer: dict):
            """(the Arabic's pairs, None) or (None, why, the numbers lost)."""
            data, french = answer.get('data'), articles[t.text_uri]
            if not data or len(data.get('articles', [])) != len(french) or answer.get('stop') == 'max_tokens':
                stop = answer.get('stop') if answer.get('stop') != 'end_turn' else ''     # an answer that ended as asked
                return None, answer.get('error') or stop or 'articles differ', []
            by_key = {a['key']: a for a in data['articles']}
            pairs = [(a, by_key.get(f'a{k}')) for k, a in enumerate(french)]
            pages = folios(t.pages)
            lost = sorted({n for a, ar in pairs for n in numbers_kept(a.body, (ar or {}).get('body', ''), pages)})
            if any(ar is None for _, ar in pairs) or lost:
                return None, f'numbers lost: {lost[:6]}' if lost else 'an article missing', lost
            return (data, pairs), None, []

        answers = llm.run_batch('translate-french', [ask(i, t) for i, t in enumerate(todo)],
                                log=self.stdout.write) if todo else {}
        results = {i: check(t, answers.get(f't{i}') or {}) for i, t in enumerate(todo)}
        again = {i: lost for i, (good, why, lost) in results.items() if good is None}
        if again:       # once more, the numbers named; what still fails is kept out of the file and named
            answers = llm.run_batch('translate-french', [ask(i, todo[i], lost) for i, lost in again.items()],
                                    log=self.stdout.write)
            for i in again:
                results[i] = check(todo[i], answers.get(f't{i}') or {})
        out, refused = [], []
        for i, t in enumerate(todo):
            good, why, _ = results[i]
            if good is None:
                refused.append((t.text_uri, why))
                continue
            data, pairs = good
            out.append({
                'text_uri': t.text_uri, 'type': t.type, 'number': t.number, 'signed_on': t.signed_on and t.signed_on.isoformat(),
                'title_fr': t.title, 'title_ar': printed_numbers(data['title']), 'pages_fr': t.pages,
                'articles': [{'order': k + 1, 'number': a.number, 'label_fr': a.label, 'body_fr': a.body,
                              'page_fr': a.printed_page, 'label_ar': ar['label'], 'body_ar': printed_numbers(ar['body'])}
                             for k, (a, ar) in enumerate(pairs)],
            })
        out_dir = Path(opts['out']) if opts.get('out') else OUT
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / f'bo_{issue}_fr.json'
        path.write_text(json.dumps({
            'issue': issue, 'date': french_issue.date.isoformat(), 'arabic': opts.get('arabic') or 'not online (the SGG answers 404)',
            'french': {'number': number, 'suffix': suffix, 'date': french_issue.date.isoformat(),
                       'sha256': french_issue.document.sha256, 'url': french_issue.document.url},
            'translated_from': 'fr', 'translated_by': MODEL, 'prompt_version': PROMPT_VERSION,
            'translated_at': datetime.now(UTC).isoformat(timespec='seconds'),
            'texts': out, 'refused': [{'text_uri': u, 'why': w} for u, w in refused],
        }, ensure_ascii=False, indent=1) + '\n')
        self.stdout.write(f'{path}: {len(out)} texts translated, {len(refused)} refused' +
                          (': ' + '; '.join(f'{u} ({w})' for u, w in refused) if refused else ''))
