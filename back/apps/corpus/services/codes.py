"""The codes people cite by name (ma_cite's `code` keys), with their names and where they live in the corpus.

A code that is not loaded yet still has a name, so a citation to it is told as «not in the corpus yet»
rather than as an unknown reference. The address is the one corpus `_find_or_stub` gives a named code.
"""
import json
import re
from functools import lru_cache
from pathlib import Path

import ma_law

CODES = {
    'doc': ('قانون الالتزامات والعقود', 'Dahir des obligations et des contrats'),
    'family': ('مدونة الأسرة', 'Code de la famille'),
    'penal': ('مجموعة القانون الجنائي', 'Code pénal'),
    'civil_procedure': ('قانون المسطرة المدنية', 'Code de procédure civile'),
    'criminal_procedure': ('قانون المسطرة الجنائية', 'Code de procédure pénale'),
    'labour': ('مدونة الشغل', 'Code du travail'),
    'tax': ('المدونة العامة للضرائب', 'Code général des impôts'),
    'commerce': ('مدونة التجارة', 'Code de commerce'),
    'road': ('مدونة السير على الطرق', 'Code de la route'),
    'constitution': ('دستور المملكة المغربية', 'Constitution du Royaume du Maroc'),
    'housing_lease': ('قانون كراء المحلات المعدة للسكنى', "Loi sur les baux d'habitation"),
    'land_registration': ('ظهير التحفيظ العقاري', "Dahir sur l'immatriculation foncière"),
}

# The corpus's address for a code it holds, by ma_cite key (corpus.services.issue_structure.NAMED_CODES).
CODE_URIS = {'tax': '/akn/ma/act/code/cgi', 'doc': '/akn/ma/act/code/doc', 'land_registration': '/akn/ma/act/code/land-registration',
             # Typed «constitution» since 25 Oct 2026 (load_constitutions): known by its address, at its dahir's.
             'constitution': '/akn/ma/act/dahir/1-11-91'}

# A code replaced by a new one: cited by its name before the new one was published, it is the old one, era by era
# (until each date, oldest first). The civil procedure was dahir 1.74.447 until law 58.25 (BO of 23 Feb 2026); the
# constitution of a year is the one in force then (data/constitutions.json, their BO dates).
CODE_BEFORE = {
    'civil_procedure': [('2026-02-23', ('dahir', '1-74-447'))],
    'constitution': [('1970-08-01', ('dahir', 'constitution-1962')), ('1972-03-15', ('dahir', '1-70-177')),
                     ('1992-10-14', ('dahir', '1-72-061')), ('1996-10-10', ('dahir', '1-92-155')),
                     ('2011-07-30', ('dahir', '1-96-157'))],
}

# The numbered text that IS a code, as (corpus type, number): «مدونة السير» is law 52.05, the civil procedure is
# law 58.25 since 2026. Found like any numbered text; a code whose text is not loaded is told as not held here yet.
CODE_TEXTS = {
    'road': ('law', '52-05'), 'family': ('law', '70-03'), 'labour': ('law', '65-99'), 'commerce': ('law', '15-95'),
    'civil_procedure': ('law', '58-25'), 'criminal_procedure': ('law', '22-01'), 'penal': ('dahir', '1-59-413'),
    'constitution': ('dahir', '1-11-91'), 'housing_lease': ('law', '67-12'),
}

# What people call each code (row 2 of the reader-experience review): the official name, the everyday one, the French. A
# query holding one of these is a question about that code, even when ma_cite does not read it as a citation.
NAMES = {
    'doc': ['قانون الالتزامات والعقود', 'dahir des obligations et des contrats'],
    'family': ['مدونة الأسرة', 'قانون الأسرة', 'code de la famille', 'moudawana'],
    'penal': ['القانون الجنائي', 'مجموعة القانون الجنائي', 'code pénal'],
    'civil_procedure': ['المسطرة المدنية', 'code de procédure civile'],
    'criminal_procedure': ['المسطرة الجنائية', 'code de procédure pénale'],
    'labour': ['مدونة الشغل', 'قانون الشغل', 'code du travail'],
    'tax': ['المدونة العامة للضرائب', 'code général des impôts'],
    'commerce': ['مدونة التجارة', 'code de commerce'],
    'road': ['مدونة السير', 'قانون السير', 'مدونة السير على الطرق', 'code de la route'],
    'constitution': ['الدستور', 'دستور المملكة المغربية', 'constitution du maroc', 'constitution marocaine'],
    'housing_lease': ['كراء المحلات المعدة للسكنى', 'الكراء السكني', 'كراء السكن', "bail d'habitation", "baux d'habitation"],
    'land_registration': ['ظهير التحفيظ العقاري', 'المتعلق بالتحفيظ العقاري', "immatriculation foncière"],
}
# A dahir cited by its date has no number: ma_cite reads «ظهير 9 رمضان 1331» as dahir «9» (H1 of the housing plan).
HIJRI_MONTH = re.compile(r'^\s*(?:من\s+)?(?:محرم|صفر|ربيع|جمادى|رجب|شعبان|رمضان|شوال|ذو|ذي)')


def dated(body: str, c: dict) -> dict:
    """The citation, as the code its words name when it cites a dahir by its date («الفصل 573 من ظهير 9 رمضان 1331
    (12 أغسطس 1913) بمثابة قانون الالتزامات والعقود» is the DOC's, «… المتعلق بالتحفيظ العقاري» the land
    registration's, both dahirs of that day); as read otherwise."""
    number = c.get('text_number') or ''
    # Read whole since H9 of the Bulletin-from-No.-1 review («… الصادر في 9 رمضان 1331 (12 أغسطس 1913)», its day kept),
    # or, before, its Hijri day read as its number («ظهير 9»).
    whole = c.get('date') and not number
    if c.get('text_kind') != 'dahir' or not (whole or (number.isdigit() and HIJRI_MONTH.match(body[c['end']:c['end'] + 20]))):
        return c
    rest = body[c['end']:c['end'] + 220]
    key = next((k for k, names in NAMES.items() for name in names if name in rest), None)
    return {**c, 'text_kind': None, 'text_number': None, 'code': key} if key else c


# Names that are a code only when they are the whole query («constitution», never «constitution d'une société»;
# «عقد الكراء» is a home's lease, never «عقد الكراء التجاري»).
ALONE = {'constitution': ['constitution', 'la constitution'], 'housing_lease': ['عقد الكراء', 'قانون الكراء']}

# Where to read a code the site does not hold yet: its file on Adala, the Ministry of Justice's portal, when we know
# one (data/samples/manifest.json), else the portal itself.
ADALA = 'https://adala.justice.gov.ma'
OFFICIAL = {
    'family': f'{ADALA}/api/uploads/2024/07/22/مدونة الأسرة-1721646687560.pdf',
    'penal': f'{ADALA}/api/uploads/2025/03/14/ظـهير شـريف رقم 1.59.413 بالمصادقة على مجموعة القانون الجنائي-1741952873602.pdf',
    'constitution': f'{ADALA}/api/uploads/2024/01/30/الدستور-1706626006826.pdf',
    'labour': f'{ADALA}/api/uploads/2024/04/30/code du travail-1714463246806.pdf',
    'housing_lease': f'{ADALA}/api/uploads/2026/04/15/ظهير شريف رقم 1.13.111 صادر في-1776242288111.pdf',
}


# The name a text is known by, said first on its page above its formal title (R4 of the for-everyone review): shorter
# than the code's official name where people say it shorter.
EVERYDAY = {'housing_lease': ('قانون الكراء', 'Loi sur les baux d\'habitation'), 'road': ('مدونة السير', 'Code de la route'),
            'constitution': ('الدستور', 'La Constitution'), 'penal': ('القانون الجنائي', 'Code pénal')}


def eras(text) -> list[dict] | None:
    """The texts a code has been, oldest first, when `text` is one of them (CODE_BEFORE): each constitution since 1962,
    the civil procedure's dahir of 1974 then law 58.25. Each with its address, year, everyday name, whether it is
    today's, when it stood (from, until) and how long it is (characters); None for a text that is not one. Four
    queries."""
    from django.db.models import Min, Sum
    from django.db.models.functions import Length

    from apps.corpus.models import Article, Text, Version
    from apps.corpus.services.addresses import text_path
    from apps.corpus.services.works import address, code_target, follow_many

    for code, before in CODE_BEFORE.items():
        # The series' own addresses first, without a query: a text outside every series costs nothing.
        named = [address(*older) for _, older in before] + [code_target(code)[0]]
        followed = follow_many(named) if text.akn_uri in named or code_of(text) == code else {}
        uris = [followed.get(uri, uri) for uri in named]
        if text.akn_uri not in uris:
            continue
        held = {t.akn_uri: t for t in Text.objects.filter(akn_uri__in=uris)}
        # How long each text is (its latest version's characters) and since when it stood: the drawing's two scales.
        size = dict(Article.objects.filter(version__text__akn_uri__in=held).values_list('version__text__akn_uri')
                    .annotate(n=Sum(Length('body'))).values_list('version__text__akn_uri', 'n'))
        starts = dict(Version.objects.filter(text__akn_uri__in=held).values_list('text__akn_uri').annotate(
            first=Min('valid_from')).values_list('text__akn_uri', 'first'))
        out = [{'path': text_path(uri), 'year': held[uri].signed_on.year if held[uri].signed_on else None,
                'name': display_name(held[uri]), 'current': k == len(uris) - 1, 'here': uri == text.akn_uri,
                'from': starts.get(uri), 'size': size.get(uri) or 0}
               for k, uri in enumerate(uris) if uri in held]
        for e, after in zip(out, out[1:] + [None]):
            e['until'] = after['from'] if after else None
        return out
    return None


def everyday_name(text) -> dict | None:
    """{ar, fr}: what people call the text, when it is a code or one of the shelf's texts; None for any other."""
    key = code_of(text)
    if key:
        ar, fr = EVERYDAY.get(key) or CODES.get(key) or (None, None)
        return {'ar': ar, 'fr': fr} if ar else None
    for key, numbered in SHELF:
        if numbered and (text.type, text.number) == (numbered[0], numbered[1]):
            ar, fr = EVERYDAY.get(key) or (numbered[2], numbered[3])
            return {'ar': ar, 'fr': fr}
    if text.type == 'constitution' and (popular := _popular().get(text.akn_uri)):
        return {'ar': popular[1], 'fr': popular[0]}       # «دستور المملكة المغربية لسنة 1996», over its dahir's title
    return None


# A text's title said short: the words before its dahir («الصادر بتنفيذه…»), its date or its memorandum.
_TAIL = re.compile(r'\s+(?:الصادرة?\s+بتنفيذه|الصادرة?\s+في|بتاريخ|بيان\s+الأسباب)')
# A decree's date sits before its subject: «مرسوم رقم 2.25.983 صادر في 8 رجب 1447 (29 ديسمبر 2025) بتحديد…».
_DATED = re.compile(r'\s+(?:ال)?صادرة?\s+في\s+[^()]{0,40}\([^)]*\)')
_FINANCE = re.compile(r'^قانون\s+المالية(?:\s+رقم\s+[\d.]+)?\s+(?:للسنة\s+المالية|لسنة)\s+(\d{4})')


def short_title(title: str, most: int = 60) -> str:
    """A title cut by words, never mid-word or mid-number: the API's names are never left to CSS to clip (P1, P6 of
    the polish review: «…7.12» for 67.12)."""
    name = _TAIL.split(_DATED.sub('', title or ''))[0].strip().rstrip('.،, ')
    if len(name) <= most:
        return name
    cut = name[:most]
    return cut[:cut.rfind(' ')].rstrip('،, ') + '…' if ' ' in cut else cut + '…'


@lru_cache(maxsize=1)
def _popular() -> dict:
    path = Path(__file__).resolve().parents[2] / 'search' / 'data' / 'popular_names.json'
    return json.loads(path.read_text())['texts'] if path.exists() else {}


def display_name(text) -> dict:
    """{ar, fr}: the name to show wherever the text is named (P6 of the polish review), in this order: the everyday
    name of a code or a shelf text; the popular name readers search with (search/data/popular_names.json, kept for a
    person's review); a finance law by its year; else its title cut by words. `fr` only where a French name exists."""
    named = everyday_name(text)
    if named:
        return named
    french = short_title(text.title_fr) if getattr(text, 'title_fr', '') else None
    popular = _popular().get(text.akn_uri)
    if popular:
        return {'ar': popular[1], 'fr': french}
    if getattr(text, 'type', '') == 'bill':     # «مشروع قانون المالية 2027» (the finance-bill review, P1)
        from apps.consolidation.services.history import bill_name
        n = bill_name(text)
        return {'ar': n['ar'], 'fr': n['fr'][:1].upper() + n['fr'][1:]}
    finance = _FINANCE.match(text.title_ar or '')
    if finance:
        year = finance.group(1)
        return {'ar': f'قانون المالية {year}', 'fr': f'Loi de finances {year}'}
    return {'ar': short_title(text.title_ar), 'fr': french}


def official_link(text) -> str | None:
    """Where a reader finds a shelf text the site has not loaded yet: its file on Adala, the Ministry of Justice's portal
    (P7 of the polish review: the labour code's page said «لا مادة» and offered no way to its text)."""
    key = code_of(text)
    if key is None:
        key = next((k for k, numbered in SHELF if numbered and text.type == numbered[0] and text.number in spellings(numbered[1])), None)
    return OFFICIAL.get(key) if key else None


def code_named(query: str) -> tuple[str, str] | None:
    """(code key, the name as found) for the longest code name the query holds as whole words."""
    folded = f' {ma_law.fold(query)} '
    found = [(len(name), key, name) for key, names in NAMES.items() for name in names
             if f' {ma_law.fold(name)} ' in folded]
    found += [(len(name), key, name) for key, names in ALONE.items() for name in names
              if f' {ma_law.fold(name)} ' == folded]
    return (max(found)[1], max(found)[2]) if found else None


def code_of(text) -> str | None:
    """The code a text is, if any."""
    for key, (kind, number) in CODE_TEXTS.items():
        if text.number == number and text.type == kind:
            return key
    return next((key for key, uri in CODE_URIS.items() if uri == text.akn_uri), None)

# ma_cite's text kinds → corpus TextType values.
TEXT_KINDS = {
    'law': ['law'], 'organic_law': ['organic_law', 'law'], 'dahir': ['dahir'], 'decree_law': ['decree_law', 'decree'],
    'decree': ['decree'], 'order': ['order', 'decision'], 'decision': ['decision', 'order'],
}

# How much a text's kind weighs in ranking: people mostly look for laws and codes.
TYPE_WEIGHT = {
    'constitution': 1.6, 'organic_law': 1.5, 'law': 1.5, 'dahir': 1.3, 'decree_law': 1.3, 'decree': 1.1,
    'order': 0.9, 'decision': 0.8, 'circular': 0.9, 'convention': 0.8, 'other': 1.0,
    # A bill filed in Parliament (the finance-bill review, P19): found, said as a bill, never above the law in force.
    'bill': 1.0,
}


# The shelf (row 3 of the reader-experience review): the twenty texts Moroccans look for most, in the order a reader
# meets them — by a code key (its names and text above) or by (type, number) with its name. Each is shown as
# held here, known by title only, or not yet (with where to read it).
SHELF = [
    ('constitution', None), ('family', None), ('doc', None), ('penal', None), ('criminal_procedure', None),
    ('civil_procedure', None), ('labour', None), ('commerce', None), ('road', None), ('tax', None),
    ('real_rights', ('law', '39-08', 'مدونة الحقوق العينية', 'Code des droits réels')),
    ('nationality', ('dahir', '1-58-250', 'قانون الجنسية المغربية', 'Code de la nationalité marocaine')),
    ('civil_status', ('law', '36-21', 'قانون الحالة المدنية', "Loi relative à l'état civil")),
    ('consumer', ('law', '31-08', 'قانون حماية المستهلك', 'Loi sur la protection du consommateur')),
    ('co_ownership', ('law', '18-00', 'قانون الملكية المشتركة للعقارات المبنية', 'Loi sur la copropriété des immeubles bâtis')),
    ('housing_lease', None),
    ('urbanism', ('law', '12-90', 'قانون التعمير', "Loi relative à l'urbanisme")),
    ('personal_data', ('law', '09-08', 'قانون حماية المعطيات الشخصية', 'Loi sur la protection des données personnelles')),
    ('access_information', ('law', '31-13', 'قانون الحق في الحصول على المعلومات', "Loi sur le droit d'accès à l'information")),
    ('copyright', ('law', '2-00', 'قانون حقوق المؤلف والحقوق المجاورة', "Loi sur les droits d'auteur et droits voisins")),
]


# Named texts a topic lists beside the shelf's (H17 of the housing plan), each found, shown and said «not held here
# yet» with its official file as the shelf's are; never on the shelf itself.
MORE = [
    ('commercial_lease', ('law', '49-16', 'قانون كراء العقارات أو المحلات المخصصة للاستعمال التجاري أو الصناعي أو الحرفي',
                          'Loi sur les baux commerciaux, industriels ou artisanaux')),
    ('rent_to_own', ('law', '51-00', 'قانون الإيجار المفضي إلى تملك العقار', 'Loi sur la location-accession à la propriété immobilière')),
    ('buildings_risk', ('law', '94-12', 'قانون المباني الآيلة للسقوط وتنظيم عمليات التجديد الحضري',
                        'Loi sur les bâtiments menaçant ruine et les opérations de rénovation urbaine')),
    ('local_taxes', ('law', '47-06', 'قانون جبايات الجماعات الترابية', 'Loi sur la fiscalité des collectivités territoriales')),
    ('housing_aid', ('decree', '2-23-350', 'مرسوم الدعم المباشر للسكن', "Décret sur l'aide directe au logement")),
    ('land_registration', None),
    ('urbanism_control', ('law', '66-12', 'قانون مراقبة وزجر المخالفات في مجال التعمير والبناء',
                          "Loi sur le contrôle et la répression des infractions en matière d'urbanisme et de construction")),
    # The texts the road lives by (A16 of the road-signposted review): the doors cite them; «القانون كامل» listed one.
    ('road_rules', ('decree', '2-10-420', 'قواعد السير على الطرق', 'Les règles de la circulation routière')),
    ('road_licence', ('decree', '2-10-311', 'رخصة السياقة', 'Le permis de conduire')),
    ('road_signs', ('order', '2805-14', 'علامات الطريق', 'La signalisation routière')),
    ('road_victims', ('dahir', '1-84-177', 'تعويض ضحايا حوادث السير', 'L’indemnisation des victimes des accidents de la circulation')),
    ('insurance', ('law', '17-99', 'مدونة التأمينات', 'Le code des assurances')),
    ('road_pro', ('decree', '2-10-314', 'السياقة المهنية', 'La conduite professionnelle')),
    ('road_school', ('decree', '2-10-432', 'تعليم السياقة', 'L’enseignement de la conduite')),
    # The texts the family's journeys cite (G5 of the family-papers review): «القانون كامل» listed the code alone.
    ('civil_status_decree', ('decree', '2-22-04', 'مرسوم الحالة المدنية', 'Le décret sur l’état civil')),
    ('kafala', ('law', '15-01', 'كفالة الأطفال المهملين', 'La kafala des enfants abandonnés')),
    ('women_violence', ('law', '103-13', 'محاربة العنف ضد النساء', 'La lutte contre les violences faites aux femmes')),
    ('direct_support', ('law', '58-23', 'الدعم الاجتماعي المباشر', 'L’aide sociale directe')),
    ('direct_support_decree', ('decree', '2-23-1067', 'مرسوم الدعم الاجتماعي المباشر', 'Le décret sur l’aide sociale directe')),
    # The texts the work topic stands on (E7 of the work-counted review): its folder cites 29; «القانون كامل» listed the code alone.
    ('social_security', ('dahir', '1-72-184', 'نظام الضمان الاجتماعي', 'Le régime de sécurité sociale')),
    ('work_accidents', ('law', '18-12', 'التعويض عن حوادث الشغل', 'La réparation des accidents du travail')),
    ('domestic_work', ('law', '19-12', 'العاملات والعمال المنزليون', 'Les travailleuses et travailleurs domestiques')),
    ('strike', ('organic_law', '97-15', 'ممارسة حق الإضراب', 'L’exercice du droit de grève')),
    ('minimum_wage', ('decree', '2-25-983', 'الحد الأدنى القانوني للأجر', 'Le salaire minimum légal')),
    ('old_age_pension', ('decree', '2-25-265', 'معاش الشيخوخة والزمانة', 'Les pensions d’invalidité et de vieillesse')),
    ('civil_service', ('dahir', '1-58-008', 'النظام الأساسي العام للوظيفة العمومية', 'Le statut général de la fonction publique')),
    # The texts the consumer topic stands on (the consumer-receipt review): «القانون كامل» listed two.
    ('consumer_decree', ('decree', '2-12-503', 'مرسوم تطبيق قانون حماية المستهلك', 'Le décret d’application de la loi sur la protection du consommateur')),
    ('product_safety', ('law', '24-09', 'سلامة المنتوجات والخدمات', 'La sécurité des produits et des services')),
    ('food_safety', ('law', '28-07', 'السلامة الصحية للمنتجات الغذائية', 'La sécurité sanitaire des produits alimentaires')),
    ('fraud', ('law', '13-83', 'الزجر عن الغش في البضائع', 'La répression des fraudes sur les marchandises')),
    ('competition', ('law', '104-12', 'حرية الأسعار والمنافسة', 'La liberté des prix et de la concurrence')),
    # The texts the land topic stands on (the land review, M16): «القانون كامل» listed two.
    ('subdivisions', ('law', '25-90', 'قانون التجزئات العقارية وتقسيم العقارات', 'Loi sur les lotissements, groupes d’habitations et morcellements')),
    ('building_rules', ('decree', '2-18-577', 'ضابط البناء العام: تسليم الرخص', 'Le règlement général de construction : la délivrance des autorisations')),
    ('expropriation', ('law', '7-81', 'نزع الملكية لأجل المنفعة العامة', 'L’expropriation pour cause d’utilité publique')),
    ('collective_lands', ('law', '62-17', 'الجماعات السلالية وتدبير أملاكها', 'La tutelle des collectivités ethniques et la gestion de leurs biens')),
    ('collective_delimitation', ('law', '63-17', 'التحديد الإداري لأراضي الجماعات السلالية', 'La délimitation administrative des terres collectives')),
    # The texts the tax topic stands on beside the code (the tax review, T5): the communes' taxes, the two
    # finance laws its figures come from, the auto-entrepreneur's status.
    ('finance_2026', ('law', '50-25', 'قانون المالية لسنة 2026', 'La loi de finances 2026')),
    ('finance_2025', ('law', '60-24', 'قانون المالية لسنة 2025', 'La loi de finances 2025')),
    ('auto_entrepreneur', ('law', '114-13', 'نظام المقاول الذاتي', 'Le statut de l’auto-entrepreneur')),
    # The texts the health topic stands on (the health review, S6): the AMO and its regimes, medicines, the
    # practice of medicine and its ethics, organ donation, disability.
    ('amo', ('law', '65-00', 'قانون التأمين الإجباري الأساسي عن المرض', 'La loi sur l’assurance maladie obligatoire')),
    ('amo_self', ('law', '98-15', 'التأمين الإجباري الأساسي عن المرض للمهنيين والمستقلين', 'L’AMO des indépendants')),
    ('amo_achamil', ('law', '60-22', 'أمو الشامل: التأمين لمن يستطيع الأداء', 'L’AMO Achamil')),
    ('amo_tadamon', ('decree', '2-22-797', 'مرسوم أمو تضامن', 'Le décret de l’AMO Tadamon')),
    ('medicines', ('law', '17-04', 'مدونة الأدوية والصيدلة', 'Le code du médicament et de la pharmacie')),
    ('medicine_practice', ('law', '131-13', 'قانون مزاولة مهنة الطب', 'La loi sur l’exercice de la médecine')),
    ('medical_ethics', ('decree', '2-21-225', 'مدونة أخلاقيات مهنة الطب', 'Le code de déontologie médicale')),
    ('organ_donation', ('law', '16-98', 'قانون التبرع بالأعضاء البشرية', 'La loi sur le don d’organes')),
    ('disability', ('law', '97-13', 'القانون الإطار لحقوق الأشخاص في وضعية إعاقة', 'La loi-cadre sur les personnes en situation de handicap')),
    ('hospital_rules', ('order', '456-11', 'النظام الداخلي للمستشفيات', 'Le règlement intérieur des hôpitaux')),
    # The texts the papers topic stands on (the papers review): the card, the passport, the administration's duties,
    # legalisation and certified copies, the foreigners' titles («القانون كامل» listed two).
    ('cnie', ('law', '4-20', 'قانون البطاقة الوطنية للتعريف الإلكترونية', 'La loi sur la carte nationale d’identité électronique')),
    ('cnie_decree', ('decree', '2-20-521', 'مرسوم البطاقة الوطنية للتعريف الإلكترونية', 'Le décret sur la carte nationale d’identité électronique')),
    ('passport', ('decree', '2-08-310', 'مرسوم جواز السفر البيومتري', 'Le décret sur le passeport biométrique')),
    ('simplification', ('law', '55-19', 'قانون تبسيط المساطر والإجراءات الإدارية', 'La loi sur la simplification des procédures administratives')),
    ('signatures', ('decree', '2-22-047', 'الإشهاد على صحة الإمضاء', 'La légalisation des signatures')),
    ('certified_copies', ('decree', '2-22-048', 'الإشهاد على مطابقة النسخ لأصولها', 'La certification des copies conformes')),
    ('foreigners', ('law', '2-03', 'قانون دخول وإقامة الأجانب', 'La loi sur l’entrée et le séjour des étrangers')),
    # The texts the business topic stands on (the business review): the company forms, cooperatives, the
    # auto-entrepreneur's register and excluded trades, public procurement, the investment charter.
    ('companies', ('law', '5-96', 'الشركة ذات المسؤولية المحدودة وشركات الأشخاص', 'La SARL et les sociétés de personnes')),
    ('cooperatives', ('law', '112-12', 'قانون التعاونيات', 'La loi sur les coopératives')),
    ('auto_register', ('decree', '2-15-258', 'مرسوم السجل الوطني للمقاول الذاتي', 'Le décret du registre national de l’auto-entrepreneur')),
    ('auto_excluded', ('decree', '2-15-263', 'المهن المستثناة من نظام المقاول الذاتي', 'Les professions exclues du régime de l’auto-entrepreneur')),
    ('public_markets', ('decree', '2-22-431', 'مرسوم الصفقات العمومية', 'Le décret des marchés publics')),
    ('investment_charter', ('law', '3-22', 'ميثاق الاستثمار', 'La charte de l’investissement')),
    # The texts the justice topic stands on (the justice review) beside the two procedures and the penal code: the
    # courts, lawyers, legal aid, the alternative sentences' decree, prisons, commissaires de justice.
    ('judicial_organisation', ('law', '38-15', 'قانون التنظيم القضائي', 'La loi sur l’organisation judiciaire')),
    ('lawyers', ('law', '66-23', 'قانون مهنة المحاماة', 'La loi sur la profession d’avocat')),
    ('legal_aid', ('decree_law', '514-65', 'المساعدة القضائية', 'L’assistance judiciaire')),
    ('alternatives_decree', ('decree', '2-25-386', 'مرسوم العقوبات البديلة', 'Le décret sur les peines alternatives')),
    ('prisons', ('law', '10-23', 'قانون المؤسسات السجنية', 'La loi sur les établissements pénitentiaires')),
    ('bailiffs', ('law', '46-21', 'قانون المفوضين القضائيين', 'La loi sur les commissaires de justice')),
    # The texts the digital topic stands on (the digital review) beside the shelf's 09.08, 31.13 and 2.00: the press
    # code, cybersecurity, trust services and the data law's decree.
    ('press', ('law', '88-13', 'قانون الصحافة والنشر', 'Le code de la presse et de l’édition')),
    ('cybersecurity', ('law', '05-20', 'قانون الأمن السيبراني', 'La loi sur la cybersécurité')),
    ('trust_services', ('law', '43-20', 'خدمات الثقة والتوقيع الإلكتروني', 'Les services de confiance et la signature électronique')),
    ('personal_data_decree', ('decree', '2-09-165', 'مرسوم حماية المعطيات الشخصية', 'Le décret sur la protection des données personnelles')),
]


def text_of(key: str):
    """The text a shelf key names, the one the site holds first: by its address, else by its kind and number."""
    return texts_of([key])[key]


def spellings(number: str) -> set[str]:
    """A number as the corpus may hold it, with or without its leading zero: law 09.08 is «09-08» (BO 5711's reading),
    law 08.12 «8-12» (Adala's); the shelf showed 09.08 missing for it."""
    first, _, rest = number.partition('-')
    return {number, f"{first.lstrip('0') or '0'}-{rest}" if rest else number}


def texts_of(keys, extra: dict | None = None) -> dict:
    """The text each key names (the shelf's, MORE's, a code's or `extra`'s: key → (kind, number, …) or ('uri', address,
    …)), the one the site holds first, with its versions and first issue fetched with it: one query for all of them (S5 and
    S7 of the performance audit)."""
    from django.db.models import Prefetch, Q

    from apps.corpus.models import Text, Version

    named = dict(SHELF + MORE)
    named.update(extra or {})

    def wanted(key):
        if key in CODE_URIS:
            return ('uri', CODE_URIS[key])
        if named.get(key) is not None and named[key][0] == 'uri':
            return ('uri', named[key][1])
        kind_number = CODE_TEXTS.get(key) if named.get(key) is None else named[key][:2]
        return ('kind', tuple(kind_number)) if kind_number else None

    keys = {key: wanted(key) for key in keys}
    found = Q()
    for want in filter(None, keys.values()):
        found |= Q(akn_uri=want[1]) if want[0] == 'uri' else Q(type=want[1][0], number__in=spellings(want[1][1]))
    texts = list(Text.objects.filter(found).order_by('id').select_related('first_published_in').prefetch_related(
        Prefetch('versions', queryset=Version.objects.select_related('source_document')))) if found else []
    out = {}
    for key, want in keys.items():
        held = [t for t in texts if want and (t.akn_uri == want[1] if want[0] == 'uri'
                                              else t.type == want[1][0] and t.number in spellings(want[1][1]))]
        out[key] = min(held, key=lambda t: not t.versions.all(), default=None)
    return out


def shelf() -> list[dict]:
    """The shelf as the API sends it: each text's names, where it stands on the site and how many articles it has
    (a spine's width)."""
    return books_of(SHELF)


def books(keys: list[str]) -> list[dict]:
    """The named texts a topic lists, the shelf's and the others (MORE), in its order."""
    named = dict(SHELF + MORE)
    return books_of([(k, named[k]) for k in keys if k in named])


def books_of(pairs: list[tuple]) -> list[dict]:
    """Named texts as the shelf and the topics show them: their names, where each stands on the site, its articles. Three
    queries for all of them (S5 of the performance audit: four a book before, the first a scan of every text)."""
    from django.db.models import Count

    from apps.consolidation.services.history import pick
    from apps.corpus.models import Article
    from apps.corpus.services.addresses import text_path

    texts = texts_of([key for key, _ in pairs])
    chosen = {key: (texts[key], pick(texts[key].versions.all(), None)[0] if texts[key] else None) for key, _ in pairs}
    counts = dict(Article.objects.filter(version_id__in=[v.pk for _, v in chosen.values() if v]).values('version_id')
                  .annotate(n=Count('id')).values_list('version_id', 'n'))
    out = []
    for key, numbered in pairs:
        text, latest = chosen[key]
        name = {'ar': CODES[key][0], 'fr': CODES[key][1]} if numbered is None else {'ar': numbered[2], 'fr': numbered[3]}
        out.append({'key': key, 'name': name, 'articles': counts.get(latest.pk, 0) if latest else 0,
                    'state': 'in_corpus' if latest else 'title_only' if text else 'not_in_corpus',
                    'path': text_path(text.akn_uri) if text else None,
                    'number_as_printed': text.number_as_printed if text else '', 'type': text.type if text else None,
                    'status': text.status if text else None,
                    'official': None if latest else OFFICIAL.get(key, ADALA)})
    return out

