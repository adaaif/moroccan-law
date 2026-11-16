"""A page's reading as the page viewer is sent it: who read it says «ai» or «tesseract», never a model's name, and no
run's price."""
import pytest
from django.utils import timezone

from apps.sources.models import Document, OcrRun, Page

pytestmark = pytest.mark.django_db


def test_a_page_reading_names_no_model_and_no_price(api):
    doc = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='r' * 64, path='BO_9_ar.pdf',
                                  mime='application/pdf', bytes=1, language='ar', page_count=1, fetched_at=timezone.now())
    page = Page.objects.create(document=doc, index=0, kind='scan', text='الفصل الأول', text_source='ocr')
    OcrRun.objects.create(page=page, engine='tesseract-5', variant='page-1596', text='الفصل الاول', cost_usd=0)
    OcrRun.objects.create(page=page, engine='a-model-2026', variant='page-1596', text='الفصل الأول', cost_usd='0.004100')
    r = api.get(f'/api/sources/documents/{doc.pk}/pages/0/')
    body = r.content.decode()
    assert r.status_code == 200 and 'a-model' not in body and 'cost' not in body
    got = r.json()
    assert got['read_by'] == {'engine': 'ai', 'variant': 'page'}
    assert sorted(run['engine'] for run in got['ocr_runs']) == ['ai', 'tesseract']
