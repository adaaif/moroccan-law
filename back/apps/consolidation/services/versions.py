"""A consolidation read from someone else's file (the SGG's, Adala's) into the corpus: the text it belongs to,
found by its number or created, and the version with its articles. Run again, a file replaces its own version."""
from datetime import date

from apps.consolidation.services.fill import paragraphs
from apps.consolidation.services.instructions.labels import label_key
from apps.consolidation.services.sgg import SggArticle
from apps.corpus.models import Article, Consolidation, Status, Text, Version
from apps.corpus.services import works
from apps.sources.models import Document

KIND_BY_TITLE = (('القانون التنظيمي', 'organic_law'), ('الظهير الشريف بمثابة قانون', 'dahir'), ('القانون', 'law'),
                 ('المرسوم', 'decree'), ('مرسوم', 'decree'), ('الظهير', 'dahir'), ('ظهير', 'dahir'),
                 ('القرار', 'order'), ('قرار', 'order'))


def text_for(number: str, title: str, consolidation: str) -> tuple[Text, bool]:
    """The text a consolidation belongs to, at the address its kind and number give, created when the corpus does not
    hold it yet. A text the corpus has not read from the BO itself (one waiting, or known from consolidations) takes
    this consolidation's title."""
    kind = next((k for words, k in KIND_BY_TITLE if title.startswith(words)), 'law')
    uri = works.follow(works.address(kind, number))
    text = Text.objects.filter(akn_uri=uri).first()
    if text is None:
        return Text.objects.create(akn_uri=uri, type=kind, number=works.fold(number),
                                   number_as_printed=works.fold(number).replace('-', '.'), title_ar=title,
                                   status=Status.IN_FORCE), True
    if not text.versions.filter(consolidation=Consolidation.AS_PUBLISHED).exists():
        # A file's title cut at a line («القانون رقم 15.01 المتعلق بكفالة») never replaces the whole one.
        whole = text.title_ar if text.title_ar.startswith(title) else title
        # A text the links found repealed («41.10», by 58.23) stays repealed whatever file is loaded for it.
        status = text.status if text.status == Status.REPEALED else Status.IN_FORCE
        text.title_ar, text.type, text.status = whole, kind, status
        text.save(update_fields=['title_ar', 'type', 'status', 'updated_at'])
    return text, False


def text_at(uri: str, title: str) -> tuple[Text, bool]:
    """A text known by its address alone (the DOC of 12 August 1913 has no number): found, or created there."""
    text = Text.objects.filter(akn_uri=works.follow(uri)).first()
    if text is not None:
        return text, False
    kind = next((k for words, k in KIND_BY_TITLE if title.startswith(words)), 'dahir')
    return Text.objects.create(akn_uri=uri, type=kind, number='', number_as_printed='', title_ar=title,
                               status=Status.IN_FORCE), True


def save_version(text: Text, consolidation: str, doc: Document, valid_from: date | None,
                 articles: list[SggArticle], preamble: str = '') -> list[Article]:
    """The file's version of the text, replacing the one it gave before, with its articles."""
    text.versions.filter(consolidation=consolidation).delete()
    version = Version.objects.create(text=text, language='ar', valid_from=valid_from, consolidation=consolidation,
                                     source_document=doc, source_pages=f'1-{doc.page_count}', preamble=preamble)
    rows, seen = [], set()
    for order, a in enumerate(articles, 1):
        key = label_key(a.label) or a.number or str(order)
        eid = a.number if a.number in ('annex', 'preamble') else f'art_{key}' if f'art_{key}' not in seen else f'art_{key}_{order}'
        seen.add(eid)
        rows.append(Article(version=version, order=order, label=a.label, number=key, heading_path=a.heading_path,
                            body='\n'.join(paragraphs(a.body)) or a.note_text.strip(), eid=eid,
                            printed_page=a.page + 1))
    rows = Article.objects.bulk_create(rows)
    # What a person put right in the version before (R7), put right again.
    from apps.quality.services.corrections import reapply
    reapply(rows, text.akn_uri)
    return rows
