from datetime import date

import pytest
from django.utils import timezone

from apps.corpus.models import Article, Consolidation, Text, Version
from apps.sources.models import Document, Issue
from apps.translations.models import FrenchArticle, FrenchText

ART_51_NOW = ('يترتب عن إنهاء عقد الشغل غير محدد المدة، دون إعطاء أجل الإخطار، أو قبل انصرام مدته، أداء الطرف المسؤول '
              'عن الإنهاء، تعويضا عن الإخطار للطرف الآخر.')
ART_51_THEN = 'نص المادة 51 كما نشر سنة 2003.'


@pytest.fixture
def labour():
    """Law 65.99 as the site holds it: published in BO 5167, Adala's consolidation of 16 July 2026, its 2003 text before
    it, the official French of BO 5210."""
    scan = Document.objects.create(source='sgg_bo', kind='bo_issue', sha256='5' * 64, path='bo/5167.pdf',
                                   mime='application/pdf', bytes=1, language='ar', fetched_at=timezone.now())
    issue = Issue.objects.create(edition='general_ar', number=5167, date=date(2003, 12, 8), document=scan)
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/65-99', type='law', number='65-99', number_as_printed='65.99',
                               title_ar='القانون رقم 65.99 المتعلق بمدونة الشغل', status='in_force',
                               first_published_in=issue, first_published_page=3969)
    then = Version.objects.create(text=text, language='ar', valid_from=date(2004, 6, 8),
                                  consolidation=Consolidation.AS_PUBLISHED)
    now = Version.objects.create(text=text, language='ar', valid_from=date(2026, 7, 16), consolidation=Consolidation.ADALA)
    heading = ['الكتاب الأول: الاتفاقيات المتعلقة بالشغل', 'الفرع الثالث: أجل الإخطار']
    for version, body51 in ((then, ART_51_THEN), (now, ART_51_NOW)):
        for order, n in enumerate(range(49, 55), start=1):
            Article.objects.create(version=version, order=order, label=f'المادة {n}', number=str(n), eid=f'art_{n}',
                                   body=body51 if n == 51 else f'نص المادة {n}.', heading_path=heading, printed_page=26)
    FrenchText.objects.create(text_uri=text.akn_uri, type='law', title='Loi n° 65-99 relative au Code du travail',
                              issue_number=5210, issue_date=date(2004, 5, 6), document_sha='x' * 64)
    FrenchArticle.objects.create(text_uri=text.akn_uri, order=3, label='Article 51', number='51',
                                 body='Toute rupture sans préavis du contrat de travail à durée indéterminée…')
    return text
