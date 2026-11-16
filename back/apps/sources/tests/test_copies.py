"""FX3 of the mended-Bulletin review: one issue for each printed cover."""
from datetime import UTC, date, datetime

import pytest

from apps.corpus.models import Alias, Article, Consolidation, Text, Version
from apps.sources.models import Document, Issue, OcrRun, Page
from apps.sources.services import copies

pytestmark = pytest.mark.django_db


def issue(number, size, cover='', pages=2, texts=('ظهير شريف في ضبط زرع الكيف', 'قرار وزيري')):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256=f'h{number}', path=f'BO_{number}.pdf',
                                  mime='application/pdf', bytes=size, language='ar', page_count=pages,
                                  fetched_at=datetime(2026, 11, 1, tzinfo=UTC))
    bo = Issue.objects.create(edition='general_ar', number=number, date=date(1923, 8, 14), document=doc,
                              first_page_number=777)
    for k in range(pages):
        p = Page.objects.create(document=doc, index=k, printed_number=777 + k, kind='scan',
                                text=(cover + '\n' if k == 0 else '') + texts[k % len(texts)])
        OcrRun.objects.create(page=p, engine='claude-haiku-5-5', text=p.text)
    return bo


def text(bo, k, title, articles=0, page=777):
    t = Text.objects.create(akn_uri=f'/akn/ma/act/arrete/1923-08-14/bo{bo.number}-{k}', type='order', title_ar=title,
                            first_published_in=bo, first_published_page=page)
    v = Version.objects.create(text=t, language='ar', valid_from=bo.date, consolidation=Consolidation.AS_PUBLISHED)
    for n in range(1, articles + 1):
        Article.objects.create(version=v, order=n, label=f'الفصل {n}', number=str(n), eid=f'art_{n}', body='يعمل به')
    return t


def test_most_readings_win_word_by_word():
    readings = ['ظهير شريف في ضبط زرع الكيف', 'ظهير شريف في ضبط درع الكيف', 'ظهير شريف في ضبط زرع الكيف']
    assert copies.vote(readings) == 'ظهير شريف في ضبط زرع الكيف'
    assert copies.vote(['قرار وزيرى', 'قرار وزيري شعباeffective']) == 'قرار وزيرى'     # of two, the cleaner


def test_covers_are_found_by_what_they_print_or_by_their_bytes():
    issue(537, 1514091, cover='عدد 537 – و538 – و539')
    issue(538, 1514013)                         # its metadata 78 bytes shorter
    issue(539, 1514091)
    issue(134, 50000, cover='عدد 134 ثمن النسخة')
    issue(135, 50300)                           # a neighbour of the same length, printed under its own cover
    issue(87, 245854, cover='عددى ٨٧')
    issue(88, 245854)                           # the same file to the byte
    found = {cover.number: [c.number for c in rest] for cover, rest in copies.groups(log=lambda *a: None)}
    assert found == {87: [88], 537: [538, 539]}


def test_folding_keeps_the_fullest_cut_under_the_cover_and_every_address():
    cover = issue(537, 1514091, cover='عدد 537 – و538')
    copy = issue(538, 1514091)
    mine = text(cover, 1, 'قرار وزيري في تعيين كاتب', articles=0)
    fuller = text(copy, 1, 'قرار وزيرى فى تعيين كاتب', articles=2)
    missed = text(copy, 2, 'ظهير شريف في احداث جماعة لقبيلة بني ورياجل', articles=1)
    done = copies.fold(cover, [copy], log=lambda *a: None)
    assert done['fuller cut taken from a copy'] == 1 and done['texts the cover lacked'] == 1
    mine.refresh_from_db()
    assert mine.versions.get().articles.count() == 2                  # the copy's fuller cut, under the cover's address
    assert Alias.objects.get(alias=fuller.akn_uri).uri == mine.akn_uri
    kept = Text.objects.get(title_ar=missed.title_ar)
    assert kept.first_published_in == cover and kept.akn_uri.endswith(f'/bo{cover.key}-2')
    assert Alias.objects.get(alias=missed.akn_uri).uri == kept.akn_uri
    copy.refresh_from_db()
    assert copy.copy_of == cover and not Page.objects.filter(document=copy.document).exists()
    page = Page.objects.get(document=cover.document, index=0)
    assert page.ocr_runs.filter(variant='copy 538').count() == 1      # the copy's reading kept on the cover's page
    assert page.ocr_runs.filter(engine='vote').exists()
