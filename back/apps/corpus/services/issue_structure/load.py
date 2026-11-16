"""The texts cut and described into the corpus (`load_texts`): a promulgating dahir filed as its law, the rubric the
contents print above a text, the text's address settled, a code first printed before 1956 known by its day, its
version and articles written."""
import re
from datetime import date

from django.db import transaction

from apps.corpus.models import Alias, Article, Consolidation, Status, Text, Version
from apps.corpus.services import works
from apps.corpus.services.issue_structure.articles import _DIVISION, one_piece, split_articles, whole_text
from apps.corpus.services.issue_structure.printed import _date, _days, article_number, cited_day, normalize_number
from apps.corpus.services.issue_structure.segment import issue_lines
from apps.corpus.services.issue_structure.toc import TYPES
from apps.corpus.services.titles import full_title
from apps.sources.models import Issue
from apps.sources.services import remarks
from apps.sources.services.compare import fold


SUBTYPES = works.SUBTYPES

_AFTER_TITLE = re.compile(r'^(?:بيان الأسباب|مادة فريدة|مادة وحيدة|المادة\s|ديباجة|تصدير|الحمد لله)')
_PROMULGATES = re.compile(r'بتنفيذ (القانون التنظيمي|القانون|قانون[^ ]*)(?: [^ ]+)?? رقم ([\d.]+\d)')
_OWN = re.compile(r'^\s*(?:ال)?قانون(\s+(?:ال)?تنظيمي)?\s+رقم\s+(\d+\.\d+)(?![.\d])')


def own_name(title: str) -> tuple[str, str] | None:
    """(kind, number as printed) a law's heading gives itself: «قانون تنظيمي رقم 48.22 …» is organic law 48.22,
    whatever the contents or the model said (BO 7180 filed it as law 14.22, BO 7213 law 83.21 as 01.23). A number
    of three parts is a dahir's: a heading that starts with one is another text's, quoted."""
    m = _OWN.match(title or '')
    return ('organic_law' if m.group(1) else 'law', m.group(2)) if m else None


def as_law(data: dict, front: str) -> dict:
    """A dahir promulgating a law is filed as the law (the model sometimes describes the dahir): its type, number
    and printed title, the dahir's number kept as promulgating_dahir. The title is the law's heading as printed
    (the front's last lines from «قانون …»), whatever the model wrote."""
    data = dict(data)
    m = _PROMULGATES.search(data['title'])
    if data['type'] == 'dahir' and m:
        data.update(type='organic_law' if 'التنظيمي' in m.group(1) else 'law', number_as_printed=m.group(2),
                    promulgating_dahir=data['promulgating_dahir'] or data['number_as_printed'])
    if data['type'] in ('law', 'organic_law'):
        lines = front.splitlines()
        heads = [n for n, line in enumerate(lines) if line.startswith(('قانون', 'القانون')) and 'رقم' in line]
        if heads:
            title = []
            for line in lines[heads[-1]:]:
                # The heading ends where the law's own parts begin: «I. - الضرائب…», «الجزء الأول», its statement
                # of reasons (law 58.25's «بيان الأسباب» ran on for 4,000 letters) or its single article.
                if title and (re.match(r'^[IVX]+\s*[.\-–]', line) or _DIVISION.match(line) or _AFTER_TITLE.match(line)):
                    break
                title.append(line)
            data['title'] = ' '.join(title)
            own = own_name(data['title'])
            if own:
                data['type'], data['number_as_printed'] = own
    return data


def own_heading_at(item: dict) -> int:
    """Where a cut text's own heading stands in its front: the first «رقم N» of its number (as its heading names it,
    BO 7383's 02.24 being listed as 55.24) or of its promulgating dahir; 0 when none is printed there."""
    front, data = item.get('front') or '', item.get('data') or {}
    own = as_law(data, front).get('number_as_printed') if data else ''
    # A heading that names another number than the entry's is the text's: the entry's number and dahir are another
    # text's, earlier in the same front.
    numbers = (own,) if own and own != data.get('number_as_printed') else \
        (own, data.get('promulgating_dahir'), item['toc'].get('number_as_printed')) if data else ()
    at = [m.start() for p in numbers if p and p.split()
          and (m := re.search(rf'رقم\s+{re.escape(p.split()[0])}(?![\d.]*\d)', front))]
    return min(at, default=0)


# The codes the site holds from Adala whose first print is in the Bulletin before 1956, where its dahirs have no number:
# known by their day and their title's words (H7 of the Bulletin-from-No.-1 review).
FIRST_PRINTS = {('dahir', date(1913, 8, 12), 'الالتزامات والعقود'): '/akn/ma/act/code/doc',
                ('dahir', date(1913, 8, 12), 'التحفيظ العقاري'): '/akn/ma/act/code/land-registration'}


def first_print_of(kind: str, number: str, signed: date | None, title: str) -> str:
    """The address of a code the site holds that this unnumbered text first printed, or ''."""
    if number or not signed:
        return ''
    words = fold(title or '')
    return next((uri for (k, day, name), uri in FIRST_PRINTS.items()
                 if k == kind and day == signed and fold(name) in words), '')


# A line of the contents that is a text's own, never its rubric.
_NOT_RUBRIC = re.compile(r'^(?:ظهير|شريف|مرسوم|قرار|مقرر|قانون|منشور|دورية|صفحة|فهرست|نصوص|\||\d)')


def contents_rubric(lines: list[tuple[int, str]], first_page: int, printed: str, dahir: str) -> str:
    """The rubric the contents print above a text's line («الشركات الجهوية متعددة الخدمات.» above «ظهير شريف رقم
    1.23.53 … بتنفيذ القانون رقم 83.21 …»): for a text the model's reading of the contents missed (BO 7213 read
    four lines before «فهرست» and dropped them) or took for another; '' when the contents do not show it."""
    names = []
    if dahir:
        names.append(re.compile(rf'رقم\s+{re.escape(dahir)}(?![\d.]*\d)'))
    if printed:
        names.append(re.compile(rf'^\S+(?:\s+\S+){{0,8}}?\s+رقم\s+{re.escape(printed)}(?![\d.]*\d)\s+صادر'
                                rf'|بتنفيذ\s+\S+(?:\s+\S+)?\s+رقم\s+{re.escape(printed)}(?![\d.]*\d)'))
    for n, (page, line) in enumerate(lines):
        if page is not None and page >= first_page:
            break
        if n and any(p.search(line) for p in names):
            above = lines[n - 1][1].strip()
            if not _NOT_RUBRIC.match(above) and 2 <= len(above.split()) and len(above) < 200:
                return above
            return ''
    return ''


@transaction.atomic
def load_texts(issue: Issue, texts: list[dict], written: set | None = None, only: set[int] | None = None) -> dict:
    """The issue's texts into the corpus; `written` collects the versions it wrote (reload_issues sweeps the rest).
    `only`: the positions in `texts` to load, the others left as they are. A text with no number takes its address
    from its position among all the issue's texts, so a list of only some would give it another text's (
    the Bulletin-from-No.-1 review, 1 Nov 2026: the archive's MISSING loads had written 35 decisions over orders loaded before them)."""
    counts = {'texts': 0, 'articles': 0, 'skipped': 0, 'in_doubt': 0, 'held': 0}
    rubrics = {(item['toc'].get('rubric') or '').strip(' .') for item in texts} - {''}
    first_page = min((item['toc'].get('page') or 0 for item in texts), default=0)
    contents = None      # the contents pages' lines, read when a text needs its rubric from them
    for i, item in enumerate(texts):
        if only is not None and i not in only:
            continue
        data, toc = item.get('data'), item['toc']
        if not data or not data.get('found'):
            counts['skipped'] += 1
            continue
        if not item['articles']:
            # A text cut before single articles were known, or whose articles a recut gave back to the text they
            # were: its own still sit in its front, from its own heading on (BO 7180's front holds organic law
            # 14.22 before 48.22, each with its «مادة فريدة»).
            lines = item.get('front', '').splitlines()
            lines = lines[item.get('front', '').count('\n', 0, own_heading_at(item)):]
            item = {**item, 'front': '\n'.join(lines)}
            cut = split_articles([(item['pages'][0], line) for line in lines])
            if cut['articles']:
                item = {**item, 'front': cut['front'], 'articles': cut['articles'],
                        'tail': '\n'.join(x for x in (cut['tail'], item.get('tail', '')) if x)}
        data = as_law(data, item.get('front', ''))
        kind = data['type'] if data['type'] in TYPES else toc['type']
        heading = toc['title'] or (item.get('front') or '').split('\n')[0]
        if kind == 'decision' and works.ministers_order(heading, data['number_as_printed'] or toc['number_as_printed']):
            kind = 'order'      # «قرار لوزير … رقم 1234.20»: an order, wherever the model filed it (R18 of the road plan)
        signed = _date(data['signed_on_gregorian']) or _date(toc['signed_on_gregorian'])
        if issue.date.year < 1956 and cited_day(toc['title'] or data['title'], signed, data.get('closing') or ''):
            signed = _date((_days(data.get('closing') or '') or [''])[0])
        # An old scan's number may be read backwards: put back by its shape, weighed by its year, or in doubt (no
        # address of its own, never another text's).
        number, doubt = works.oriented(kind, normalize_number(data['number_as_printed']),
                                       normalize_number(toc['number_as_printed']), signed or issue.date)
        counts['in_doubt'] += doubt
        if not item['articles'] or one_piece(data['title'] or toc['title'], data['number_as_printed']):
            whole = whole_text(item, data, rubrics)
            if whole is not item:
                item, data = whole, {**data, 'preamble': []}     # its visas are in its words
        # A law whose own heading names another number than its contents entry (BO 7213: 01.23's entry held 83.21)
        # is not that entry's text: the entry's rubric, page and promulgating dahir belong to the other one.
        entry = {works.orient(normalize_number(toc['number_as_printed'])).lstrip('0')} | \
            {works.orient(normalize_number(m.group(2))).lstrip('0') for m in _PROMULGATES.finditer(toc['title'])}
        rubric, page = toc['rubric'], toc['page']
        if kind in ('law', 'organic_law') and number and entry - {''} and number.lstrip('0') not in entry:
            data, rubric = {**data, 'promulgating_dahir': ''}, ''
            page = item['articles'][0]['page'] if item['articles'] else page
        if not rubric:
            if contents is None:
                contents = [(p, line) for p, line in issue_lines(issue) if p is not None and p < first_page] \
                    if issue.document_id else []
            rubric = contents_rubric(contents, first_page, data['number_as_printed'], data['promulgating_dahir'])
        year = (signed or issue.date).year
        fallback = (f'/akn/ma/act/{SUBTYPES[kind]}/{year}/{number}' if number
                    else f'/akn/ma/act/{SUBTYPES[kind]}/{issue.date}/bo{issue.number}-{i + 1}')
        uri = settle(works.uri_for(kind, number, data['number_as_printed'] or toc['number_as_printed'], fallback),
                     fallback, issue, kind, number)
        if Alias.objects.filter(alias=uri, reason__in=(Alias.Reason.COPY, Alias.Reason.TWIN)).exists():
            counts['folded'] = counts.get('folded', 0) + 1
            continue        # folded into the fuller cut of the same printed text (FX3, FX7): never loaded again
        first = first_print_of(kind, number, signed, data['title'] or toc['title'])
        uri = first or uri
        held = Text.objects.filter(akn_uri=uri).exclude(first_published_in=issue).first()
        if held is not None and held.versions.exists():
            # A text the site already holds (Adala's or the SGG's consolidation, a topic's reading) is never written over
            # by an issue read later: its title, its versions and their words stay (28 Oct 2026, the archive's load had
            # replaced 27 of Adala's texts, 130.13 and 88.13 among them, with its own reading of their first print).
            # One of the 1913 codes: its first print, when the site did not know it, is this issue's page (H7).
            if first and held.first_published_in_id is None:
                Text.objects.filter(pk=held.pk).update(first_published_in=issue, first_published_page=page,
                                                       signed_on=held.signed_on or signed)
            counts['held'] += 1
            continue
        text, _ = Text.objects.update_or_create(akn_uri=uri, defaults={
            'type': kind, 'number': number,
            'number_as_printed': (number.replace('-', '.') if number and number != normalize_number(
                data['number_as_printed']) else data['number_as_printed'])[:60],     # a number put back reads put back
            'title_ar': full_title(data['title'] or toc['title'], toc['title'], item.get('front', ''),
                                   data['number_as_printed'] or toc['number_as_printed']), 'signed_on': signed,
            'signed_on_hijri': (data['signed_on_hijri'] or toc['signed_on_hijri'])[:80],
            'authority': data['authority'][:200], 'promulgating_dahir': data['promulgating_dahir'][:40],
            'rubric': rubric[:300], 'bo_section': toc['section'], 'status': Status.UNKNOWN, 'first_published_in': issue,
            # Where its own pages begin when the contents give a page well outside them (the contents page itself, the
            # issue's first page) or none (FX4 of the mended-Bulletin review); a page either side is the contents' word.
            'first_published_page': item['pages'][0] if item.get('pages') and (
                not page or page < item['pages'][0] - 1 or page > item['pages'][1] + 1) else page,
        })
        version, _ = Version.objects.update_or_create(text=text, language='ar', valid_from=issue.date, defaults={
            'consolidation': Consolidation.AS_PUBLISHED, 'source_document': issue.document,
            'source_pages': f'{item["pages"][0]}-{item["pages"][1]}',
            'preamble': remarks.strip('\n'.join(data['preamble'])),
            'closing': remarks.strip('\n'.join([data['closing'], *data['signatories']]).strip()),
        })
        if written is not None:
            written.add(version.pk)
        version.articles.all().delete()
        articles, eids = [], set()
        for n, a in enumerate(item['articles']):
            eid = f'art_{article_number(a["label"]) or n + 1}'
            eid = eid if eid not in eids else f'{eid}_{n + 1}'  # the same label twice keeps both anchors apart
            eids.add(eid)
            articles.append(Article(version=version, order=n + 1, label=a['label'][:80],
                                    number=article_number(a['label']), heading_path=a['heading_path'],
                                    body=remarks.strip(a['body']), eid=eid, printed_page=a['page']))
        tail = item['tail'].split('\n')
        at = next((k for k, line in enumerate(tail) if line.startswith(('ملحق', 'الملحق', 'جدول', 'الجدول'))), None)
        if at is not None:
            articles.append(Article(version=version, order=len(articles) + 1, label=tail[at][:80], number='annex',
                                    body='\n'.join(tail[at:]), eid='annex'))
        Article.objects.bulk_create(articles)
        if data['promulgating_dahir'] and kind in ('law', 'organic_law'):
            # Only a law is promulgated by a dahir: a decree's «dahir» is the one it applies (28 Oct 2026: decree
            # 2.72.513 had swallowed the SGG's dahir 1.72.255 on hydrocarbons, which the 2027 bill cites).
            dahir = works.address('dahir', works.orient(normalize_number(data['promulgating_dahir'])))
            if dahir != uri:
                twin = Text.objects.filter(akn_uri=dahir).first()
                if twin is not None:
                    works.merge(twin, text)
                Alias.objects.update_or_create(alias=dahir, defaults={'uri': uri, 'reason': Alias.Reason.DAHIR})
        counts['texts'] += 1
        counts['articles'] += len(articles)
    return counts


def settle(uri: str, fallback: str, issue: Issue, kind: str, number: str) -> str:
    """The address a text read from `issue` takes. A waiting row at it (the text cited before it was read) is filled;
    so is one waiting under a neighbouring kind (an organic law cited as a law). An address another issue's text
    already holds is a clash, a reprint or a misread number: this text keeps its year-based address instead."""
    held = Text.objects.filter(akn_uri=uri).first()
    if held is not None and held.versions.exists() and held.first_published_in_id not in (None, issue.pk):
        uri = fallback
        held = Text.objects.filter(akn_uri=uri).first()
        if held is not None and held.versions.exists() and held.first_published_in_id not in (None, issue.pk):
            uri = f'{fallback}-bo{issue.key}'
    if works.numbered(kind, number):
        for neighbour in works.FAMILY.get(kind, ())[1:]:
            twin = Text.objects.filter(akn_uri=works.address(neighbour, number)).first()
            if twin is not None and not twin.versions.exists():
                text = Text.objects.filter(akn_uri=uri).first()
                if text is None:
                    twin.akn_uri, twin.type = uri, kind
                    twin.save(update_fields=['akn_uri', 'type', 'updated_at'])
                    works.move(works.address(neighbour, number), uri, Alias.Reason.MERGED)
                else:
                    works.merge(twin, text)
    return uri
