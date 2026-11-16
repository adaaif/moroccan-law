"""A text as Akoma Ntoso 3.0 XML (OASIS LegalDocML): its FRBR identity (work, expression, manifestation), its
publication in the BO, its title and its articles. The open-data dump writes one file a text.

The expression is the version the file holds, in its language, authoritative only when it is the text as the Bulletin
printed it; the meta's proprietary block (OWN) gives its kind, its days and, for a translation, the language it was
translated from."""
from xml.etree import ElementTree as ET

from django.conf import settings

from apps.corpus.models import Text, Version

NS = 'http://docs.oasis-open.org/legaldocml/ns/akn/3.0'
OWN = 'urn:x-law:akn:version'      # the proprietary block's own names
LANGUAGES = {'ar': 'ara', 'fr': 'fra'}
TYPE_NAMES = {'law': 'act', 'organic_law': 'act', 'dahir': 'act', 'decree_law': 'act', 'decree': 'act',
              'order': 'act', 'decision': 'act', 'circular': 'doc', 'convention': 'act', 'constitution': 'act',
              'other': 'doc'}


def _sub(parent, tag, text=None, **attrs):
    el = ET.SubElement(parent, f'{{{NS}}}{tag}', {k: str(v) for k, v in attrs.items() if v is not None})
    if text is not None:
        el.text = text
    return el


def akn_xml(text: Text, version: Version) -> bytes:
    ET.register_namespace('', NS)
    ET.register_namespace('law', OWN)
    language = LANGUAGES.get(version.language, 'ara')
    root = ET.Element(f'{{{NS}}}akomaNtoso')
    doc = _sub(root, TYPE_NAMES.get(text.type, 'act'), name=text.type)
    meta = _sub(doc, 'meta')
    ident = _sub(meta, 'identification', source='#site')
    work_date = (text.signed_on or version.valid_from).isoformat()
    expr = f'{text.akn_uri}/{language}@{version.valid_from.isoformat()}'
    for frbr, this, uri, date_ in (
        ('FRBRWork', f'{text.akn_uri}/!main', text.akn_uri, work_date),
        ('FRBRExpression', f'{expr}/!main', expr, version.valid_from.isoformat()),
        ('FRBRManifestation', f'{expr}/!main.xml', f'{expr}.akn', version.valid_from.isoformat()),
    ):
        part = _sub(ident, frbr)
        _sub(part, 'FRBRthis', value=this)
        _sub(part, 'FRBRuri', value=uri)
        _sub(part, 'FRBRdate', date=date_, name='signature' if frbr == 'FRBRWork' else 'publication')
        _sub(part, 'FRBRauthor', href='#author')
        if frbr == 'FRBRWork':
            _sub(part, 'FRBRcountry', value='ma')
            if text.number:
                _sub(part, 'FRBRnumber', value=text.number_as_printed or text.number)
        if frbr == 'FRBRExpression':
            _sub(part, 'FRBRauthoritative', value='true' if version.consolidation == 'as_published' else 'false')
            _sub(part, 'FRBRlanguage', language=language)
    issue = text.first_published_in
    if issue:
        _sub(meta, 'publication', date=issue.date.isoformat(), name='الجريدة الرسمية',
             showAs=f'الجريدة الرسمية عدد {issue.number}{" مكرر" if issue.suffix == "bis" else ""}',
             number=issue.key)
    references = _sub(meta, 'references', source='#site')
    _sub(references, 'TLCOrganization', eId='site', href=settings.SITE_URL, showAs='قانون')
    _sub(references, 'TLCOrganization', eId='author', href='/ontology/organization/ma/author',
         showAs=text.authority or 'المملكة المغربية')
    own = _sub(meta, 'proprietary', source='#site')
    ET.SubElement(own, f'{{{OWN}}}version', {k: v for k, v in (
        ('kind', version.consolidation), ('validFrom', version.valid_from.isoformat()),
        ('validTo', version.valid_to and version.valid_to.isoformat()), ('translatedFrom', version.translated_from))
        if v})
    preface = _sub(doc, 'preface')
    long_title = _sub(preface, 'longTitle')
    _sub(long_title, 'p', text.title_ar)
    body = _sub(doc, 'body')
    for a in version.articles.all():
        art = _sub(body, 'article', eId=a.eid)
        _sub(art, 'num', a.label)
        content = _sub(art, 'content')
        for line in a.body.splitlines():
            if line.strip():
                _sub(content, 'p', line.strip().replace('**', ''))
    return ET.tostring(root, encoding='utf-8', xml_declaration=True)
