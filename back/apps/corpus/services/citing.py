"""An article's reference the way Moroccan lawyers write it: «المادة 8 من القانون رقم 2.00 المتعلق بحقوق
المؤلف…، الجريدة الرسمية عدد … بتاريخ …، ص. …». The text API sends it with every article (the web's «نسخ مع
المرجع») and the Word export prints it under each one."""
from collections.abc import Callable
from datetime import date

from apps.corpus.models import Article, Text, Version

# Gregorian months as Morocco writes them in Arabic.
MONTHS_AR = ['يناير', 'فبراير', 'مارس', 'أبريل', 'ماي', 'يونيو', 'يوليوز', 'غشت', 'شتنبر', 'أكتوبر', 'نونبر', 'دجنبر']

# «قانون رقم 31.13» is cited «القانون رقم 31.13»; a title that does not name its number right after its kind
# («قانون المالية رقم 50.25», «قرار لوزير …») is cited as printed.
DEFINITE = [('قانون تنظيمي رقم', 'القانون التنظيمي رقم'), ('قانون رقم', 'القانون رقم'),
            ('ظهير شريف رقم', 'الظهير الشريف رقم'), ('ظهير شريف بمثابة قانون رقم', 'الظهير الشريف بمثابة قانون رقم'),
            ('مرسوم بقانون رقم', 'المرسوم بقانون رقم'), ('مرسوم رقم', 'المرسوم رقم'),
            ('قرار مشترك رقم', 'القرار المشترك رقم'), ('قرار رقم', 'القرار رقم'), ('مقرر رقم', 'المقرر رقم')]


def definite_title(title: str) -> str:
    for bare, with_al in DEFINITE:
        if title.startswith(bare + ' '):
            return with_al + title[len(bare):]
    return title


def citation_ar(text: Text, article: Article | None = None, version: Version | None = None) -> str:
    """The reference of `text` (or of its `article`), as `citer` writes it."""
    return citer(text, version)(article)


# Who assembled a version from its amendments, as a reference names them (HM37 of the hard-moment review).
COMPILERS = {'adala': 'بوابة عدالة', 'sgg': 'الأمانة العامة للحكومة', 'dgi': 'المديرية العامة للضرائب',
             'machine': '«قانون»', 'checked': '«قانون»'}


def _day(d: date) -> str:
    return f'{d.day} {MONTHS_AR[d.month - 1]} {d.year}'


def citer(text: Text, version: Version | None = None, issues: dict | None = None) -> Callable[[Article | None], str]:
    """Writes the text's references, one call an article, the text's own parts read once (a page of articles makes no
    query of its own). The Bulletin is cited, never a compiler's file: an article of Adala's, the SGG's or the DGI's
    copy names the issue the text first appeared in (the file's own note of it when the text holds none) and its first
    page, then «(نص بعد التعديلات، بوابة عدالة، 16 يوليوز 2026)»; «ص. 27» of a ministry's PDF is no reference
    (HM37 of the hard-moment review). `issues`: the issues by number, read once for many texts (the Word
    export), where a file's note names the first issue."""
    from apps.corpus.services import constitutions
    from apps.sources.models import Edition, Issue

    if (c := constitutions.by_uri().get(text.akn_uri)):
        # A constitution as people cite it: «الفصل 19 من الدستور، الجريدة الرسمية عدد 5964 مكرر بتاريخ 30 يوليوز 2011».
        d = date.fromisoformat(c['published'])
        bo = f"الجريدة الرسمية عدد {c['issue']} بتاريخ {_day(d)}"
        whole = 'دستور المملكة المغربية' if c['cited_as'] == 'الدستور' else c['cited_as']
        return lambda article: '، '.join([f"{article.label} من {c['cited_as']}" if article else whole, bo])
    title = definite_title(' '.join(text.title_ar.split())[:300])
    compiled = version is not None and version.consolidation in COMPILERS
    meta = version.source_document.meta if compiled and version.source_document_id else {}
    issue, first_page = text.first_published_in, text.first_published_page
    if issue is None and meta.get('first_issue'):
        issue = issues.get(str(meta['first_issue'])) if issues is not None else \
            Issue.objects.filter(edition=Edition.GENERAL_AR, number=meta['first_issue']).order_by('suffix').first()
        first_page = meta.get('first_page')
    bo = ''
    if issue:
        number = f'{issue.number} مكرر' if issue.suffix == 'bis' else str(issue.number)
        bo = f'الجريدة الرسمية عدد {number} بتاريخ {_day(issue.date)}'
    note = ''
    if compiled:
        as_of = meta.get('as_of')
        day = date.fromisoformat(as_of) if as_of else version.valid_from
        note = f' (نص بعد التعديلات، {COMPILERS[version.consolidation]}، {_day(day)})'

    def cite(article: Article | None) -> str:
        parts = [f'{article.label} من {title}' if article else title]
        if bo:
            parts.append(bo)
        # An article of a copy as printed stands on its own page of the Bulletin; an assembled one on no page at all.
        page = first_page if compiled or article is None else article.printed_page
        if page and (bo or not compiled):
            parts.append(f'ص. {page}')
        return '، '.join(parts) + note
    return cite
