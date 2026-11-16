"""The library's catalogue (LB3–LB7 of the every-code review, 9 Nov 2026): the 67 codes and core laws
Moroccans ask for by name, in nine branches of the law. Each branch is drawn as a pile: its general text at the base,
the special laws on it, the texts it replaced dashed under it. Each book says how current the text a reader opens is:
the day of its version, who brought it up to date, and whether a change shown as fact is on record after it (LB5). A
book's card (LB6) says how to cite it, where it was printed, its parts, its last change and its French.

Every text named here is on the site; one that is not shows as such (its state), never as a gap."""
from datetime import date

from django.db.models import Count, Max
from django.db.models.functions import Coalesce

# key: (how to find it, its everyday name in Arabic and French, the other names people give it, which the library's box
# reads). How to find it: None for a code codes.py already names (CODES, CODE_URIS, CODE_TEXTS); else (kind, number) or
# ('uri', address). The customs code is the 1977 dahir's code by its address: two texts carry dahir 1.77.339's number.
BOOKS: dict[str, tuple] = {
    # The Constitution and the institutions
    'constitution': (None, 'الدستور', 'La Constitution', ['دستور 2011', 'الدستور المغربي', 'constitution', 'constitution du maroc']),
    'organic_finance': (('organic_law', '130-13'), 'القانون التنظيمي لقانون المالية', 'La loi organique relative à la loi de finances',
                        ['القانون التنظيمي للمالية', 'lolf', 'loi organique des finances']),
    'communes': (('organic_law', '113-14'), 'القانون التنظيمي للجماعات', 'La loi organique relative aux communes', ['الجماعات', 'الجماعة', 'communes']),
    'regions': (('organic_law', '111-14'), 'القانون التنظيمي للجهات', 'La loi organique relative aux régions', ['الجهات', 'الجهة', 'régions']),
    'house': (('organic_law', '27-11'), 'القانون التنظيمي لمجلس النواب', 'La loi organique relative à la Chambre des représentants',
              ['مجلس النواب', 'البرلمان', 'chambre des représentants', 'parlement']),
    'government': (('organic_law', '065-13'), 'القانون التنظيمي للحكومة', 'La loi organique relative au gouvernement', ['الحكومة', 'gouvernement']),
    'parties': (('organic_law', '29-11'), 'القانون التنظيمي للأحزاب', 'La loi organique relative aux partis politiques', ['الأحزاب', 'حزب', 'partis politiques']),
    'elections': (('law', '9-97'), 'مدونة الانتخابات', 'Le code électoral', ['الانتخابات', 'اللوائح الانتخابية', 'code électoral', 'élections']),
    # The family and persons
    'family': (None, 'مدونة الأسرة', 'Le Code de la famille', ['المدونة', 'قانون الأسرة', 'الزواج', 'الطلاق', 'النفقة', 'الحضانة', 'moudawana', 'code de la famille']),
    'nationality': (None, 'قانون الجنسية', 'Le Code de la nationalité', ['الجنسية', 'nationalité']),
    'civil_status': (None, 'قانون الحالة المدنية', "La loi relative à l'état civil", ['الحالة المدنية', 'كناش الحالة المدنية', 'état civil']),
    'kafala': (None, 'كفالة الأطفال المهملين', 'La kafala des enfants abandonnés', ['الكفالة', 'kafala']),
    'women_violence': (None, 'محاربة العنف ضد النساء', 'La lutte contre les violences faites aux femmes', ['العنف ضد النساء', 'violences faites aux femmes']),
    'direct_support': (None, 'الدعم الاجتماعي المباشر', "L'aide sociale directe", ['الدعم المباشر', 'الدعم الاجتماعي', 'aide sociale directe']),
    # Civil law and property
    'doc': (None, 'قانون الالتزامات والعقود', 'Le Dahir des obligations et des contrats',
            ['ق ل ع', 'الالتزامات والعقود', 'العقود', 'القانون المدني', 'doc', 'code civil', 'obligations et contrats']),
    'real_rights': (None, 'مدونة الحقوق العينية', 'Le Code des droits réels', ['الحقوق العينية', 'الشفعة', 'droits réels']),
    'land_registration': (None, 'ظهير التحفيظ العقاري', "Le dahir sur l'immatriculation foncière",
                          ['التحفيظ', 'التحفيظ العقاري', 'الرسم العقاري', 'المحافظة العقارية', 'immatriculation foncière', 'titre foncier']),
    'co_ownership': (None, 'الملكية المشتركة', 'La copropriété des immeubles bâtis', ['الملكية المشتركة', 'السانديك', 'copropriété', 'syndic']),
    'housing_lease': (None, 'قانون الكراء', "La loi sur les baux d'habitation", ['الكراء', 'الكرا', 'الكراء السكني', 'bail', "bail d'habitation", 'loyer']),
    'commercial_lease': (None, 'الكراء التجاري', 'Le bail commercial', ['الكراء التجاري', 'الأصل التجاري', 'bail commercial']),
    'urbanism': (None, 'قانون التعمير', "La loi relative à l'urbanisme", ['التعمير', 'رخصة البناء', 'urbanisme', 'permis de construire']),
    'expropriation': (None, 'نزع الملكية', "L'expropriation", ['نزع الملكية', 'expropriation']),
    'habous': (('dahir', '1-09-236'), 'مدونة الأوقاف', 'Le Code des Habous', ['الأوقاف', 'الحبوس', 'الوقف', 'habous']),
    # Criminal law
    'penal': (None, 'القانون الجنائي', 'Le Code pénal', ['الجنائي', 'مجموعة القانون الجنائي', 'code pénal']),
    'criminal_procedure': (None, 'قانون المسطرة الجنائية', 'Le Code de procédure pénale', ['المسطرة الجنائية', 'الحراسة النظرية', 'procédure pénale']),
    'military_justice': (('law', '108-13'), 'قانون العدل العسكري', 'La loi relative à la justice militaire', ['العدل العسكري', 'المحكمة العسكرية', 'justice militaire']),
    'prisons': (None, 'المؤسسات السجنية', 'Les établissements pénitentiaires', ['السجون', 'السجن', 'prisons']),
    # Courts and procedure
    'civil_procedure': (None, 'قانون المسطرة المدنية', 'Le Code de procédure civile', ['المسطرة المدنية', 'procédure civile', 'cpc']),
    'judicial_organisation': (None, 'التنظيم القضائي', "L'organisation judiciaire", ['التنظيم القضائي', 'المحاكم', 'organisation judiciaire']),
    'judges': (('organic_law', '106-13'), 'النظام الأساسي للقضاة', 'Le statut des magistrats', ['القضاة', 'magistrats']),
    'judicial_council': (('organic_law', '100-13'), 'المجلس الأعلى للسلطة القضائية', 'Le Conseil supérieur du pouvoir judiciaire',
                         ['المجلس الأعلى للسلطة القضائية', 'cspj']),
    'lawyers': (None, 'مهنة المحاماة', "La profession d'avocat", ['المحاماة', 'المحامي', 'avocat']),
    'notaries': (('law', '32-09'), 'التوثيق', 'Le notariat', ['التوثيق', 'الموثق', 'notaire', 'notariat']),
    'bailiffs': (None, 'المفوضون القضائيون', 'Les commissaires de justice', ['المفوض القضائي', 'huissier', 'commissaire de justice']),
    'legal_aid': (None, 'المساعدة القضائية', "L'assistance judiciaire", ['المساعدة القضائية', 'assistance judiciaire']),
    # Commerce and business
    'commerce': (None, 'مدونة التجارة', 'Le Code de commerce', ['التجارة', 'الشيك', 'الكمبيالة', 'صعوبات المقاولة', 'code de commerce', 'chèque']),
    'public_companies': (('law', '17-95'), 'شركات المساهمة', 'Les sociétés anonymes', ['شركة المساهمة', 'société anonyme']),
    'companies': (None, 'الشركات الأخرى', 'La SARL et les autres sociétés', ['الشركة ذات المسؤولية المحدودة', 'الشركات', 'sarl']),
    'insurance': (None, 'مدونة التأمينات', 'Le Code des assurances', ['التأمين', 'التأمينات', 'assurance', 'assurances']),
    'consumer': (None, 'حماية المستهلك', 'La protection du consommateur', ['المستهلك', 'consommateur']),
    'competition': (None, 'حرية الأسعار والمنافسة', 'La liberté des prix et de la concurrence', ['المنافسة', 'الأسعار', 'concurrence']),
    'cooperatives': (None, 'التعاونيات', 'Les coopératives', ['التعاونية', 'coopérative']),
    'auto_entrepreneur': (None, 'المقاول الذاتي', "L'auto-entrepreneur", ['auto-entrepreneur', 'autoentrepreneur']),
    'copyright': (None, 'حقوق المؤلف', "Les droits d'auteur", ['حقوق المؤلف', "droit d'auteur", 'copyright']),
    # Work and social protection
    'labour': (None, 'مدونة الشغل', 'Le Code du travail', ['الشغل', 'قانون الشغل', 'الخدمة', 'الطرد', 'code du travail', 'travail']),
    'social_security': (None, 'الضمان الاجتماعي', 'La sécurité sociale', ['الضمان الاجتماعي', 'cnss', 'sécurité sociale']),
    'amo': (None, 'التغطية الصحية الأساسية', 'La couverture médicale de base', ['التغطية الصحية', 'amo', 'التأمين الإجباري عن المرض', 'couverture médicale']),
    'work_accidents': (None, 'حوادث الشغل', 'Les accidents du travail', ['حوادث الشغل', 'accident du travail']),
    'domestic_work': (None, 'العمال المنزليون', 'Le travail domestique', ['العمال المنزليون', 'الخادمة', 'travail domestique']),
    'strike': (None, 'ممارسة حق الإضراب', "L'exercice du droit de grève", ['الإضراب', 'grève']),
    'civil_service': (('dahir', '1-58-008'), 'الوظيفة العمومية', 'La fonction publique', ['الوظيفة العمومية', 'الموظف', 'الفونكسيون', 'fonction publique']),
    # Taxes and public finance
    'tax': (None, 'المدونة العامة للضرائب', 'Le Code général des impôts', ['الضرائب', 'الضريبة', 'الضريبة على الدخل', 'cgi', 'impôts', 'tva']),
    'customs': (('uri', '/akn/ma/act/dahir/1977/1-77-339'), 'مدونة الجمارك', 'Le Code des douanes', ['الجمارك', 'الديوانة', 'douane', 'douanes']),
    'debt_collection': (('law', '15-97'), 'تحصيل الديون العمومية', 'Le recouvrement des créances publiques', ['تحصيل الديون العمومية', 'الخزينة', 'recouvrement']),
    'local_taxes': (None, 'جبايات الجماعات الترابية', 'La fiscalité des collectivités territoriales', ['الجبايات المحلية', 'ضريبة السكن', 'fiscalité locale']),
    'financial_courts': (('law', '62-99'), 'المحاكم المالية', 'Les juridictions financières', ['المحاكم المالية', 'المجلس الأعلى للحسابات', 'cour des comptes']),
    'public_markets': (None, 'الصفقات العمومية', 'Les marchés publics', ['الصفقات العمومية', 'الصفقات', 'marchés publics']),
    'finance_2026': (None, 'قانون المالية 2026', 'La loi de finances 2026', ['قانون المالية', 'الميزانية', 'loi de finances', 'budget']),
    # Rights and public life
    'road': (None, 'مدونة السير', 'Le Code de la route', ['السير', 'قانون السير', 'رخصة السياقة', 'البيرمي', 'code de la route']),
    'access_information': (None, 'الحق في الحصول على المعلومات', "Le droit d'accès à l'information", ['الحق في المعلومة', "accès à l'information"]),
    'personal_data': (None, 'حماية المعطيات الشخصية', 'La protection des données personnelles', ['المعطيات الشخصية', 'cndp', 'données personnelles']),
    'press': (None, 'الصحافة والنشر', "La presse et l'édition", ['الصحافة', 'الصحفي', 'presse']),
    'associations': (('dahir', '1-58-376'), 'تأسيس الجمعيات', 'Les associations', ['الجمعيات', 'الجمعية', 'associations']),
    'gatherings': (('dahir', '1-58-377'), 'التجمعات العمومية', 'Les rassemblements publics', ['التجمعات العمومية', 'المظاهرات', 'الوقفة', 'manifestations']),
    'water': (('law', '36-15'), 'قانون الماء', "La loi sur l'eau", ['الماء', 'eau']),
    'medicines': (None, 'الأدوية والصيدلة', 'Le médicament et la pharmacie', ['الصيدلة', 'الدواء', 'الأدوية', 'pharmacie', 'médicament']),
    'foreigners': (None, 'دخول الأجانب وإقامتهم', "L'entrée et le séjour des étrangers", ['الأجانب', 'الإقامة', 'الهجرة', 'étrangers', 'séjour']),
}

# The branches in the order a faculty teaches them: (key, Arabic, French, the general text at the pile's base or None,
# the other books, the texts it replaced: (Arabic, French, address on the site, the years it stood)).
BRANCHES: list[tuple] = [
    ('institutions', 'الدستور والمؤسسات', 'La Constitution et les institutions', 'constitution',
     ['organic_finance', 'communes', 'regions', 'house', 'government', 'parties', 'elections'],
     [('دساتير 1962 و1970 و1972 و1992 و1996', 'Les constitutions de 1962, 1970, 1972, 1992 et 1996', '/constitution', '1962–2011')]),
    ('family', 'الأسرة والأشخاص', 'La famille et les personnes', 'family',
     ['nationality', 'civil_status', 'kafala', 'women_violence', 'direct_support'],
     [('مدونة الأحوال الشخصية', 'Le Code du statut personnel', '/ma/dahir/1-57-343', '1957–2004')]),
    ('civil', 'المدني والعقار', 'Le droit civil et les biens', 'doc',
     ['real_rights', 'land_registration', 'co_ownership', 'housing_lease', 'commercial_lease', 'urbanism', 'expropriation', 'habous'], []),
    ('criminal', 'القانون الجنائي', 'Le droit pénal', 'penal', ['criminal_procedure', 'military_justice', 'prisons'], []),
    ('courts', 'القضاء والمساطر', 'La justice et les procédures', 'civil_procedure',
     ['judicial_organisation', 'judges', 'judicial_council', 'lawyers', 'notaries', 'bailiffs', 'legal_aid'],
     [('قانون المسطرة المدنية لسنة 1974', 'Le Code de procédure civile de 1974', '/ma/loi/1-74-447', '1974–2026')]),
    ('business', 'التجارة والأعمال', 'Le commerce et les affaires', 'commerce',
     ['public_companies', 'companies', 'insurance', 'consumer', 'competition', 'cooperatives', 'auto_entrepreneur', 'copyright'], []),
    ('work', 'الشغل والحماية الاجتماعية', 'Le travail et la protection sociale', 'labour',
     ['social_security', 'amo', 'work_accidents', 'domestic_work', 'strike', 'civil_service'], []),
    ('finance', 'الضرائب والمالية العامة', 'Les impôts et les finances publiques', 'tax',
     ['customs', 'debt_collection', 'local_taxes', 'financial_courts', 'public_markets', 'finance_2026'], []),
    ('public', 'الحقوق والحياة العامة', 'Les droits et la vie publique', None,
     ['road', 'access_information', 'personal_data', 'press', 'associations', 'gatherings', 'water', 'medicines', 'foreigners'], []),
]

# What jurists and students write for a code (W6 of the library-search review, 10 Nov 2026): the letters of the short form,
# folded and joined, → a book's key, or (kind, number) for a text outside the 67. A first list (owner-provisional): a
# jurist checks it before the lawyers join.
SHORT: dict[str, str | tuple] = {
    'قلع': 'doc', 'ظلع': 'doc', 'قمم': 'civil_procedure', 'قمج': 'criminal_procedure', 'قج': 'penal', 'مقج': 'penal',
    'مش': 'labour', 'ما': 'family', 'مت': 'commerce', 'محع': 'real_rights', 'قتع': 'land_registration',
    'ظتع': 'land_registration', 'معض': 'tax', 'مس': 'road', 'مج': 'customs', 'قما': ('law', '41-90'),
    'doc': 'doc', 'coc': 'doc', 'cpc': 'civil_procedure', 'cpp': 'criminal_procedure', 'cp': 'penal', 'ct': 'labour',
    'cf': 'family', 'cgi': 'tax', 'cdr': 'real_rights', 'ccom': 'commerce',
}
# Arabic short forms a reader may type without dots or spaces.
SHORT_JOINED = {'قلع', 'قمم', 'قمج'}

# Names a text had, has elsewhere in the Arab world, or shares with the text that replaced it: the words that must all
# be there (folded, without the letters Arabic writes on a word's front) → the texts, the first the likeliest, and why.
FORMER: list[tuple] = [
    (('احوال', 'شخصيه'), [('dahir', '1-57-343'), 'family'], 'replaced'),
    (('قانون', 'عقوبات'), ['penal'], 'elsewhere'),
    (('قانون', 'تجاري'), ['commerce'], 'elsewhere'),
    (('حريات', 'عامه'), ['associations', 'gatherings', 'press'], 'freedoms'),
    (('نظام', 'اساسي', 'عام', 'وظيفه', 'عموميه'), ['civil_service'], ''),
    (('محاكم', 'اداريه'), [('law', '41-90'), 'judicial_organisation'], 'courts'),
    (('محاكم', 'تجاريه'), [('law', '53-95'), 'judicial_organisation'], 'courts'),
    (('قانون', 'بنكي'), [('law', '103-12')], ''),
]

# The dozen under the box (C5): a first list, chosen by hand.
MOST = ['family', 'labour', 'penal', 'doc', 'civil_procedure', 'criminal_procedure', 'commerce', 'road', 'constitution',
        'real_rights', 'housing_lease', 'tax']

# Where a text's changes are also recorded: the customs code's 300 articles are the 1977 dahir's code (its own address),
# while the finance laws' changes to it were read against dahir 1.77.339's other entry.
TWINS = {'customs': ['/akn/ma/act/dahir/1-77-339']}

# A book with a page of its own beside the law: the finance law's figures, checked (/budget/2026).
EXTRA = {'finance_2026': '/budget/2026'}


def _issue(issue) -> dict | None:
    return None if issue is None else {'number': issue.number, 'suffix': issue.suffix, 'key': issue.key, 'date': issue.date}


def _changes(uris_by_key: dict[str, list[str]]) -> dict[str, tuple[date | None, int]]:
    """Each book's newest change shown as fact that has taken effect (a repeal of the whole text aside: the status says
    it), and how many texts changed it: one query for all of them."""
    from apps.consolidation.models import Change, Verb
    from apps.consolidation.services.engine import SHOWN

    today = date.today()
    every = {uri for uris in uris_by_key.values() for uri in uris}
    rows = (Change.objects.filter(text_uri__in=every, source=Change.Source.READING, state__in=SHOWN)
            .exclude(verb=Verb.REPEALED, number='')
            .annotate(on=Coalesce('effective_on', 'published_on')).filter(on__lte=today)
            .values('text_uri').annotate(last=Max('on'), n=Count('by_uri', distinct=True)))
    per_uri = {r['text_uri']: (r['last'], r['n']) for r in rows}
    out = {}
    for key, uris in uris_by_key.items():
        found = [per_uri[u] for u in uris if u in per_uri]
        out[key] = (max((f[0] for f in found), default=None), sum(f[1] for f in found))
    return out


def catalogue() -> dict:
    """The library's catalogue as the API sends it (GET /api/corpus/library/): each book's names, the names the box
    reads, its address, articles, the version a reader opens and whether a change is on record after it, where it was
    first printed; each branch's base and the texts it replaced; the dozen people ask for, the two newest issues as
    they are and when the SGG was last asked (W9, C5 of the library-search review). Seven queries whatever it holds."""
    from apps.consolidation.services.history import pick
    from apps.corpus.models import Article
    from apps.corpus.services import codes
    from apps.corpus.services.addresses import text_path
    from apps.sources.models import Edition, Issue

    keys = [k for b in BRANCHES for k in ([b[3]] if b[3] else []) + b[4]]
    extra = {k: BOOKS[k][0] + (BOOKS[k][1], BOOKS[k][2]) for k in keys if BOOKS[k][0] is not None}
    texts = codes.texts_of(keys, extra=extra)
    chosen = {k: pick(t.versions.all(), None)[0] if t else None for k, t in texts.items()}
    counts = dict(Article.objects.filter(version_id__in=[v.pk for v in chosen.values() if v]).values('version_id')
                  .annotate(n=Count('id')).values_list('version_id', 'n'))
    changed = _changes({k: [t.akn_uri] + TWINS.get(k, []) for k, t in texts.items() if t})
    # Where a compiled copy says the text was first printed, when the text itself names no issue (citing.citer's rule).
    wanted = {k: v.source_document.meta['first_issue'] for k, v in chosen.items()
              if v and texts[k].first_published_in_id is None and v.source_document_id and v.source_document.meta.get('first_issue')}
    first = {i.number: i for i in Issue.objects.filter(edition=Edition.GENERAL_AR, number__in=set(wanted.values()))
             .order_by('number', 'suffix')} if wanted else {}
    on_shelf = {k for k, _ in codes.SHELF}

    def book(key: str, base: bool) -> dict:
        _how, ar, fr, names = BOOKS[key]
        text, version = texts.get(key), chosen.get(key)
        last, n = changed.get(key, (None, 0))
        issue, page = (text.first_published_in, text.first_published_page) if text else (None, None)
        if text and issue is None and key in wanted:
            issue, page = first.get(wanted[key]), version.source_document.meta.get('first_page')
        return {'key': key, 'name': {'ar': ar, 'fr': fr}, 'aliases': names, 'base': base, 'shelf': key in on_shelf,
                'path': text_path(text.akn_uri) if text else None,
                'state': 'in_corpus' if version else 'title_only' if text else 'not_in_corpus',
                'type': text.type if text else None, 'number': text.number_as_printed if text else '',
                'status': text.status if text else None, 'articles': counts.get(version.pk, 0) if version else 0,
                'version': None if version is None else {'from': version.valid_from, 'kind': version.consolidation},
                'changes': n, 'last_change': last,
                # A change shown as fact, in force, after the version a reader opens: that version may not hold it yet.
                'stale': bool(version and last and last > version.valid_from),
                'issue': _issue(issue), 'page': page, 'extra': EXTRA.get(key)}

    return {'most': [k for k in MOST if texts.get(k)], 'newest': newest(), 'asked': asked(), 'branches': [{
        'key': key, 'name': {'ar': ar, 'fr': fr}, 'base': base,
        'books': ([book(base, True)] if base else []) + [book(k, False) for k in others],
        'replaced': [{'name': {'ar': g_ar, 'fr': g_fr}, 'path': path, 'years': years} for g_ar, g_fr, path, years in gone],
    } for key, ar, fr, base, others, gone in BRANCHES]}


def newest(n: int = 2) -> list[dict]:
    """The newest issues of the general edition as they are (W9): number, day, how many texts and pages, and for one
    kept by its pages alone the line its own contents table prints. Two queries."""
    from apps.sources.models import Edition, Issue, Page
    from apps.sources.services.contents import about

    rows = list(Issue.objects.filter(edition=Edition.GENERAL_AR, copy_of__isnull=True).annotate(n=Count('texts_first_published'))
                .order_by('-date', '-number', '-suffix').values('number', 'suffix', 'date', 'hijri_date', 'n', 'document_id',
                                                                 'document__page_count')[:n])
    bare = [r['document_id'] for r in rows if not r['n'] and r['document_id']]
    first = dict(Page.objects.filter(document_id__in=bare, index=0).values_list('document_id', 'text')) if bare else {}
    return [{'number': r['number'], 'suffix': r['suffix'], 'key': f"{r['number']}-{r['suffix']}" if r['suffix'] else str(r['number']),
             'date': r['date'], 'hijri': r['hijri_date'], 'texts': r['n'], 'pages': r['document__page_count'] or 0,
             'about': about(first.get(r['document_id'], '')) if not r['n'] else ''} for r in rows]


def asked() -> dict | None:
    """When the nightly fetch last asked the SGG's list, and the newest issue the list named (`fetch_new_issues` keeps
    it): {'at', 'newest', 'newest_date'}, or None before its first night."""
    import json
    from pathlib import Path

    from django.conf import settings
    try:
        state = json.loads((Path(settings.CORPUS_DIR) / 'reports' / 'fetch_new_issues.json').read_text())
    except (OSError, ValueError):
        return None
    found = state.get('asked') or {}
    return {'at': found['at'], 'newest': found.get('newest', ''), 'newest_date': found.get('newest_date', '')} if found.get('at') else None


def card(text) -> dict:
    """A book's card (GET /api/corpus/library/card/?path=…, LB6): the reference to cite, where it was first printed, the
    version a reader opens, its parts with their first article and count, its newest change shown as fact with its issue,
    and its French. Fixed queries whatever the text."""
    from apps.consolidation.models import Change, Verb
    from apps.consolidation.services.engine import SHOWN
    from apps.consolidation.services.history import pick_version
    from apps.corpus.models import Article, Text
    from apps.corpus.services.addresses import text_path
    from apps.corpus.services.citing import citer
    from apps.sources.models import Edition, Issue
    from apps.translations.models import FrenchText

    version, _ = pick_version(text, None)
    issue, page = text.first_published_in, text.first_published_page
    meta = version.source_document.meta if version and version.source_document_id else {}
    if issue is None and meta.get('first_issue'):
        issue = Issue.objects.filter(edition=Edition.GENERAL_AR, number=meta['first_issue']).order_by('suffix').first()
        page = meta.get('first_page')
    parts: list[dict] = []
    total = 0
    if version is not None:
        for eid, number, heading in Article.objects.filter(version=version).order_by('order').values_list('eid', 'number', 'heading_path'):
            total += 1
            head = (heading or [''])[0].strip()
            # A «heading» of a sentence's length is words the reading took for one (the tax code's arts 226–248, «الكتاب
            # مقررو هذه اللجان…»): those articles stay in the part before.
            if parts and (parts[-1]['heading'] == head or len(head) > 90):
                parts[-1]['articles'] += 1
            else:
                parts.append({'heading': head, 'eid': eid, 'number': number, 'articles': 1})
    # A part is a heading the text gives; the articles before its first heading are no part of their own.
    parts = [p for p in parts if p['heading']] if len([p for p in parts if p['heading']]) > 1 else []
    today = date.today()
    uris = [text.akn_uri] + [u for k, (how, *_) in BOOKS.items() if how and how[0] == 'uri' and how[1] == text.akn_uri
                             for u in TWINS.get(k, [])]
    changes = (Change.objects.filter(text_uri__in=uris, source=Change.Source.READING, state__in=SHOWN)
               .exclude(verb=Verb.REPEALED, number='')
               .annotate(on=Coalesce('effective_on', 'published_on')).filter(on__lte=today))
    newest = changes.order_by('-on', '-id').first()
    by = Text.objects.filter(akn_uri=newest.by_uri).first() if newest else None
    french = FrenchText.objects.filter(text_uri=text.akn_uri).first()
    return {
        'path': text_path(text.akn_uri), 'citation': citer(text, version)(None),
        'issue': _issue(issue), 'page': page, 'articles': total, 'parts': parts,
        'version': None if version is None else {'from': version.valid_from, 'kind': version.consolidation,
                                                 'as_of': meta.get('as_of')},
        'changes': changes.values('by_uri').distinct().count(),
        'last': None if newest is None else {
            'on': newest.on, 'path': text_path(newest.by_uri) if by else None,
            'type': by.type if by else None, 'number': by.number_as_printed if by else newest.by_number.replace('-', '.'),
            'title': by.title_ar if by else '',
            'issue': {'number': newest.issue, 'bis': newest.issue_bis, 'page': newest.page} if newest.issue else None},
        'french': None if french is None else {'issue': french.issue_number, 'suffix': french.issue_suffix,
                                               'date': french.issue_date, 'to': french.consolidated_to},
    }


def issue_map() -> dict:
    """Every issue the site holds, compact (LB13 and LB10): the general edition's, those with no text cut from them too (their
    pages are held), and the French edition's that carry texts the Arabic never printed. In columns, oldest first, so it
    compresses: `n` each number less the one before, `d` the days since the issue before (the first since `epoch`), `t`
    texts, `p` pages, `f` the first page's printed number less the one the issue before leads to (its first page and
    pages, when both are known; else the number itself), `s` [row, 1 bis | 2 ter], `l` [row, the cover's last number],
    `z` the rows held without texts. 22 KB gzipped where the issue list is 188 KB. Two queries."""
    from apps.sources.models import Edition, Issue

    epoch = date(1912, 1, 1)
    suffix = {'bis': 1, 'ter': 2}
    last = dict(Issue.objects.filter(copy_of__isnull=False).values('copy_of').annotate(last=Max('number'))
                .values_list('copy_of', 'last'))
    rows = (Issue.objects.filter(copy_of__isnull=True, edition__in=[Edition.GENERAL_AR, Edition.TRANSLATION_FR])
            .annotate(n=Count('texts_first_published')).order_by('date', 'number', 'suffix')
            .values_list('pk', 'edition', 'number', 'suffix', 'date', 'n', 'document__page_count', 'first_page_number', 'document_id'))
    out = {key: {'n': [], 'd': [], 't': [], 'p': [], 'f': [], 's': [], 'l': [], 'z': []} for key in ('ar', 'fr')}
    prev = {key: {'number': 0, 'day': 0, 'first': 0, 'pages': 0} for key in out}
    for pk, edition, number, suf, day, n, pages, first, document in rows:
        if edition == Edition.GENERAL_AR and (n or document):
            key = 'ar'
        elif edition == Edition.TRANSLATION_FR and n:
            key = 'fr'
        else:
            continue
        col, was = out[key], prev[key]
        row = len(col['n'])
        days = (day - epoch).days
        col['n'].append(number - was['number'])
        col['d'].append(days - was['day'])
        col['t'].append(n)
        col['p'].append(pages or 0)
        first = first or 0
        col['f'].append(first - (was['first'] + was['pages']) if was['first'] and was['pages'] else first)
        if suf in suffix:
            col['s'].append([row, suffix[suf]])
        if pk in last:
            col['l'].append([row, last[pk]])
        if not n:
            col['z'].append(row)
        prev[key] = {'number': number, 'day': days, 'first': first, 'pages': pages or 0}
    return {'epoch': epoch, **out}
