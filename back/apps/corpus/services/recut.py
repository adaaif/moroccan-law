"""Laws read into the text before them (T3 of the work plan). When an issue's table of contents is misread (BO 7383
lists «73.24» and «55.24» where it prints 02.24 and 27.23), a law's span runs on into the next one: its promulgating
dahir ends up in the last article of the text before it (55.19 in art. 10 of 22.19, an «article» of 199,078
letters), or its articles are dropped. The issue's pages were read right; only the cut was wrong. So each promulgating
dahir in an issue whose law has no text from that issue is cut again from the page readings, by code (no model), and
loaded as the pipeline loads a text; the article that held it gives it back.

Since the housing plan (H5), any text's own heading counts too: a decree, an order, a decision (BO 7051: decree
2.21.604 held decree 2.21.605, order 3484.21 with the insurance regulator's circular, and order 3707.21 in its art. 3
onwards). The host text ends where the first heading it swallowed begins: the article that holds it keeps what comes
before, and the host's later articles go to the texts cut again."""
import json
import re
from datetime import date
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import Q

from apps.consolidation.services.instructions import date_in
from apps.corpus.models import Article, Version
from apps.corpus.services import works
from apps.corpus.services.issue_structure import (
    as_law, issue_lines, load_texts, normalize_number, own_heading_at, own_name, segment_issue, split_articles)
from apps.sources.models import Issue

# «ظهير شريف رقم 1.25.03 صادر في 21 من شعبان 1446 (20 فبراير 2025) بتنفيذ القانون رقم 27.23 …» at a line's start:
# a promulgation's own heading, never a citation of one (those read «الصادر بتنفيذه الظهير الشريف …»).
HEAD = re.compile(r'^ظهير\s+شريف\s+رقم\s+([\d.]+\d)\s+صادر\s+في\s+([^(]{0,60}?)\s*\(([^)]*)\)\s*'
                  r'بتنفيذ\s+(القانون التنظيمي|القانون)\s+رقم\s+([\d.]+\d)')
# Any text's heading as the BO prints it: «مرسوم رقم 2.20.512 صادر في …», «قرار لوزير … رقم 1704.20 صادر في …».
# A citation reads «الصادر في»; a heading never does. Where the contents missed the next text (BO 6904), the cut
# still ends at its heading.
HEADING = re.compile(r'^(?:ظهير شريف|مرسوم|قرار|مقرر|منشور|دورية)\b.{0,200}?\bرقم\s+[\d.]+\d\s+صادر\s+في')
# The same heading with its parts, for a decree, an order or a decision («ظهير» headings are HEAD's).
# The date may be lost where the page's columns cut the heading («… رقم 3484.21 صادر في 1», BO 7051).
TEXT_HEAD = re.compile(r'^(ظهير شريف|مرسوم|قرار|مقرر)\b(.{0,200}?)\bرقم\s+([\d.]+\d)\s+صادر\s+في'
                       r'(?:\s+([^(]{0,60}?)\s*\(([^)]*)\))?')
TEXT_KIND = {'ظهير شريف': 'dahir', 'مرسوم': 'decree', 'قرار': 'order', 'مقرر': 'decision'}
# A dahir's heading the scan broke: its words glued («ظهيرشريف رقم 1.23.70 صادرفي 23 من محرم 1445 (10 أ», BO 7228)
# and the law it promulgates cut off. That law is named by its own heading a few lines on («قانون التصفية رقم 11.23»).
BROKEN = re.compile(r'^ظهير\s*شريف\s+رقم\s+([\d.]+\d)\s+صادر\s*في\b')
LAW_HEAD = re.compile(r'^(?:ال)?قانون(?:\s+(?:ال)?تنظيمي|\s+التصفية|\s+المالية(?:\s+المعدل)?)?\s+رقم\s+(\d+\.\d+)\s*\.?$')


def workdir(issue: Issue) -> Path:
    return Path(settings.CORPUS_DIR) / 'reports' / 'issues' / issue.key


def _toc(issue: Issue) -> list[dict]:
    path = workdir(issue) / 'toc.json'
    return json.loads(path.read_text()) if path.exists() else []


def _held(issue: Issue, kind: str, number: str, printed: str) -> bool:
    """A text from this issue already holds the law: at its address, or with its number in its title (a law filed
    under a fallback address)."""
    # A row with no article and almost no words holds nothing: its words were swallowed by the text before it (BO
    # 7535's orders 2876.25 to 2879.25, title-only; FX6 of the mended-Bulletin review).
    here = Version.objects.filter(source_document=issue.document).filter(
        Q(articles__isnull=False) | Q(preamble__regex=r'.{200}')).distinct()
    kinds = ('order', 'decision') if kind in ('order', 'decision') else (kind,)
    return (any(here.filter(text__akn_uri=works.address(k, number)).exists() for k in kinds)
            or here.filter(text__title_ar__contains=f'رقم {printed} ').exists()
            or (kind not in ('law', 'organic_law') and here.filter(text__number_as_printed=printed).exists())
            or (kind == 'dahir' and here.filter(text__promulgating_dahir__in=(printed, number)).exists()))


def heads(issue: Issue, lines: list[tuple[int, str]] | None = None) -> list[dict]:
    """Every promulgating dahir in the issue's texts (its contents pages left out), in page order."""
    lines = issue_lines(issue) if lines is None else lines
    toc = _toc(issue)
    first = min((e['page'] for e in toc), default=(issue.first_page_number or 0) + 2)
    out = []
    for n, (page, line) in enumerate(lines):
        if page is None or page < first:
            continue
        joined = line + ' ' + (lines[n + 1][1] if n + 1 < len(lines) else '')
        m = HEAD.match(joined)
        if m:
            on = date_in(m.group(3))
            out.append({'line': n, 'page': page, 'dahir': m.group(1), 'hijri': m.group(2).strip(' ،,'),
                        'gregorian': on.isoformat() if on else '',
                        'kind': 'organic_law' if 'التنظيمي' in m.group(4) else 'law', 'printed': m.group(5),
                        'number': normalize_number(m.group(5)), 'words': line})
            continue
        t = TEXT_HEAD.match(joined)
        b = BROKEN.match(line) if not t else None
        if b:
            # The law it promulgates: the first law heading before any other text's heading.
            for k in range(n + 1, min(n + 40, len(lines))):
                if HEADING.match(lines[k][1]) or BROKEN.match(lines[k][1]):
                    break
                if law := LAW_HEAD.match(lines[k][1]):
                    out.append({'line': n, 'page': page, 'dahir': b.group(1), 'hijri': '', 'gregorian': '',
                                'kind': 'organic_law' if 'تنظيمي' in lines[k][1] else 'law', 'printed': law.group(1),
                                'number': normalize_number(law.group(1)), 'words': line})
                    break
            continue
        if t and t.group(1) == 'ظهير شريف' and 'بتنفيذ' in joined:
            continue      # a promulgating dahir: its law is HEAD's, or a finance or framework law held by its own number
        if t:
            printed = t.group(3)
            if TEXT_KIND[t.group(1)] in ('order', 'decision') and re.fullmatch(r'\d{2}\.\d{3,}', printed):
                printed = '.'.join(reversed(printed.split('.')))      # read in reverse: «19.2001» is 2001.19
            on = date_in(t.group(5)) if t.group(5) else None
            out.append({'line': n, 'page': page, 'dahir': '', 'hijri': (t.group(4) or '').strip(' ،,'),
                        'gregorian': on.isoformat() if on else '', 'kind': TEXT_KIND[t.group(1)],
                        'printed': printed, 'number': normalize_number(printed), 'words': line})
    return out


def missing(issue: Issue) -> list[dict]:
    """The promulgated laws of an issue that no text from it holds."""
    return [h for h in heads(issue) if not _held(issue, h['kind'], h['number'], h['printed'])]


def _item(issue: Issue, head: dict, part: list[tuple[int, str]]) -> dict | None:
    """A cut text in the shape `load_texts` reads (the one `extract_texts` writes), its description read by code."""
    cut = split_articles(part)
    if not cut['articles']:
        return None
    lines = cut['front'].splitlines() + cut['tail'].splitlines()
    data = {'found': True, 'type': head['kind'], 'number_as_printed': head['printed'], 'title': '',
            'signed_on_gregorian': head['gregorian'], 'signed_on_hijri': head['hijri'], 'authority': '',
            'promulgating_dahir': head['dahir'],
            'preamble': [line for line in cut['front'].splitlines() if line.startswith('بناء على')],
            'closing': next((line for line in lines if line.startswith('وحرر')), ''),
            'signatories': [], 'cites': [], 'amends': []}
    title = as_law(data, cut['front'])['title']
    if head['kind'] not in ('law', 'organic_law'):
        # A decree's or an order's title is its heading as printed, up to its author («رئيس الحكومة،») or its visas.
        heading = []
        for line in cut['front'].splitlines():
            if heading and (line.startswith(('بناء على', 'بعد الاطلاع', 'باقتراح')) or re.match(r'^[^\s]+(?:\s+[^\s]+){0,8}،$', line)):
                break
            heading.append(line)
        title = re.sub(r'[\s.]+$', '', ' '.join(heading))
        if not re.search(r'\(\s*\d{1,2}\s+\S+\s+\d{4}\s*\)', title):
            # No date where a heading prints one: the page's columns broke it. Its first words are sure.
            short = re.match(r'^.*?\bرقم\s+[\d.]+\d', title)
            title = short.group(0) if short else title
    toc = {'section': 'general', 'rubric': '', 'type': head['kind'], 'number_as_printed': head['printed'],
           'title': title or head['words'], 'signed_on_gregorian': head['gregorian'], 'signed_on_hijri': head['hijri'],
           'page': head['page']}
    return {'toc': toc, 'pages': [part[0][0], part[-1][0]], 'front': cut['front'], 'articles': cut['articles'],
            'tail': cut['tail'], 'data': data, 'stop': 'recut', 'error': ''}


def plan(issue: Issue) -> list[dict]:
    """For each law missing from the issue: its cut (from its dahir to the next text's start), the article that
    holds its dahir now, if one does, and why it is left alone when it is."""
    lines = issue_lines(issue)
    found = heads(issue, lines)
    toc = _toc(issue)
    starts = sorted({s[0] for s in segment_issue(issue, toc) if s} | {h['line'] for h in found}) if toc else \
        sorted(h['line'] for h in found)
    out = []
    for head in found:
        if _held(issue, head['kind'], head['number'], head['printed']):
            continue
        if any(lines[k][1].lstrip().startswith('استدراك') for k in range(max(0, head['line'] - 3), head['line'])):
            # A corrigendum quotes the heading of the text it puts right (BO 6753: «استدراك خطإ …» then «قرار لوزير
            # الفلاحة … رقم 3770.18 …»): that text was published before.
            out.append({**head, 'item': None, 'why': 'quoted by a corrigendum'})
            continue
        if head['gregorian'] and (issue.date - date.fromisoformat(head['gregorian'])).days > 730:
            # A dahir signed years before the issue is reprinted or quoted there (BO 7305 bis, 48.15 of 2016).
            out.append({**head, 'item': None, 'why': 'signed long before the issue: a reprint, not its publication'})
            continue
        if head['kind'] in ('order', 'decision') and not re.fullmatch(r'\d+\.\d{2}', head['printed']):
            out.append({**head, 'item': None, 'why': 'a misread number (an order is numbered N.YY)'})
            continue
        if head['kind'] not in ('law', 'organic_law'):
            # Its subject already titles a text printed on the same page: that text, under a misread number.
            joined = head['words'] + ' ' + (lines[head['line'] + 1][1] if head['line'] + 1 < len(lines) else '')
            subject = re.sub(r'^.*?\)\s*', '', joined, count=1)[:45].strip()
            if len(subject) >= 25 and Version.objects.filter(
                    source_document=issue.document, text__title_ar__contains=subject,
                    text__first_published_page__gte=head['page'] - 1, text__first_published_page__lte=head['page'] + 1).exists():
                out.append({**head, 'item': None, 'why': 'its subject titles a text on the same page'})
                continue
        end = min((s for s in starts if s > head['line']), default=len(lines))
        end = next((n for n in range(head['line'] + 1, end) if HEADING.match(lines[n][1])), end)
        item = _item(issue, head, lines[head['line']:end])
        if item is None:
            out.append({**head, 'item': None, 'why': 'no article found in its pages'})
            continue
        if not any(a['body'] for a in item['articles']):
            out.append({**head, 'item': None, 'why': 'its articles came out empty: read the pages again'})
            continue
        own = own_name(item['data']['title'] or '') or own_name(item['toc']['title'])
        if own and own != (head['kind'], head['printed']) and _held(issue, own[0], normalize_number(own[1]), own[1]):
            # The dahir's number was misread and its law is there under its own (BO 7180: «14.22» for 48.22).
            out.append({**head, 'item': None, 'why': f'held as {own[1]}'})
            continue
        host = Article.objects.filter(version__source_document=issue.document, version__language='ar',
                                      body__contains=head['words'][:60]).first()
        out.append({**head, 'item': item, 'host': host, 'why': ''})
    return out


def _trim(body: str, words: str) -> str:
    """An article's body up to the dahir it swallowed, without the separators («*», «* *») before it."""
    at = body.find(words[:60])
    if at < 0:
        return body
    lines = body[:at].rstrip().splitlines()
    while lines and not re.sub(r'[*\s]', '', lines[-1]):
        lines.pop()
    return '\n'.join(lines).rstrip()


@transaction.atomic
def repair(issue: Issue, log=print, files: bool = True) -> dict:
    """Load each missing law, give the host article back its own words, and record both in the issue's texts.json,
    so a reload of the issue keeps the repair. `files=False` repairs the database only (a copy of it, for a trial:
    the files are shared, and a second repair would record the texts twice)."""
    from apps.consolidation.services import engine
    from apps.corpus.models import Text

    steps = [p for p in plan(issue) if p['item']]
    if not steps:
        return {'texts': 0, 'articles': 0, 'hosts': 0}
    items = [p['item'] for p in steps]
    before = set(Version.objects.filter(source_document=issue.document).values_list('text_id', flat=True))
    counts = load_texts(issue, items)
    hosts = dropped = 0
    for p in sorted(steps, key=lambda p: p['line']):
        # Read the host again: an earlier cut in the same text may already have ended it.
        host = Article.objects.filter(pk=p['host'].pk).first() if p['host'] is not None else None
        if host is not None and p['words'][:60] in host.body:
            host.body = _trim(host.body, p['words'])
            host.save(update_fields=['body'])
            later = Article.objects.filter(version=host.version, order__gt=host.order)
            dropped += later.count()
            later.delete()
            hosts += 1
        log(f'  {issue.key}: {p["kind"]} {p["printed"]} ({len(p["item"]["articles"])} articles)'
            + (f', given back by {host.version.text.akn_uri} {host.label}' if host else ''))
    path = workdir(issue) / 'texts.json'
    if files and path.exists():
        saved = json.loads(path.read_text())
        kept = path.with_name('texts.before-recut.json')
        if not kept.exists():
            kept.write_text(json.dumps(saved, ensure_ascii=False, indent=1))
        for p in steps:
            for item in saved:
                arts = item.get('articles') or []
                for k, a in enumerate(arts):
                    if p['words'][:60] in a['body']:
                        a['body'] = _trim(a['body'], p['words'])
                        del arts[k + 1:]
                        # Its tail came after the text it swallowed: that text's annexes (BO 7228: the 2021
                        # settlement law's tables on 58.22), which a reload would make the host's again.
                        item['tail'] = ''
                        break
                else:
                    # Swallowed after the host's last article, into the tail its annex is made from.
                    if p['words'][:60] in (item.get('tail') or ''):
                        item['tail'] = _trim(item['tail'], p['words'])
                    # Or before its first, after its own heading: every article after it was the swallowed text's
                    # (BO 6754: law 96.18's «مادة فريدة» stayed in its front, and order 40.19's two articles stood as
                    # the law's). Before its own heading, it is only the cut starting early, and the articles stay.
                    elif (item.get('front') or '').find(p['words'][:60]) > own_heading_at(item):
                        item.update(front=_trim(item['front'], p['words']), articles=[], tail='')
        path.write_text(json.dumps(saved + items, ensure_ascii=False, indent=1))
    new = list(Text.objects.filter(versions__source_document=issue.document).exclude(pk__in=before).distinct())
    engine.run(new, log=lambda *a: None)
    return {**counts, 'hosts': hosts, 'articles_moved': dropped}
