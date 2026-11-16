"""The consolidation engine's pieces on wordings taken from the BO and the SGG (row 19)."""
import pytest

from apps.consolidation.services import fill, layer, sgg
from apps.consolidation.services.instructions.amending import read, strays
from apps.consolidation.services.instructions.labels import label_key

OLD_1 = """يحدد هذا المرسوم، تطبيقا لأحكام الفصل 54 من الظهير الشريف
الصادر في 28 من جمادى الآخرة 1337 (31 مارس 1919) المشار إليه
أعلاه، لائحة الإجازات اللازمة وكذا الشروط المطلوبة لممارسة مهام
القيادة ومهام ضابط على متن سفن الصيد البحري."""


def test_a_modifying_article_is_read_into_its_articles_wordings():
    body = ('تغير وتتمم مقتضيات المادة الأولى والمواد 2 و3 من المرسوم السالف الذكر رقم 2.17.556، كما يلي :\n'
            '« المادة الأولى.- يحدد هذا المرسوم، ................................................\n'
            '« مهام ضابط على متن سفن الصيد البحري، وسفن مساعدة تربية «الأحياء المائية البحرية.»\n'
            '«المادة 2. - يقصد بالسلطة الحكومية المختصة «السلطة الحكومية المكلفة بالصيد البحري.»')
    ins = read(body)
    assert ins.action == 'modify' and ins.target == {'kind': 'decree', 'number': '2-17-556'}
    assert [(u.number, u.dotted) for u in ins.units] == [('1', True), ('2', False)]
    assert ins.units[0].lines[1] == 'مهام ضابط على متن سفن الصيد البحري، وسفن مساعدة تربية الأحياء المائية البحرية.'


def test_the_other_ways_an_amendment_is_worded():
    add = read('يتمم القانون السالف الذكر رقم 2.00 بالمادة 1.7 التالية :\n«المادة 1.7 . - يخضع استغلال المصنفات.»')
    assert add.action == 'add' and add.units[0].number == '1-7'
    words = read('تحل عبارتا «منتج تسجيل صوتي» و«منتج التسجيلات الصوتية»، على التوالي، محل عبارتي «منتج مسجل صوتي» '
                 'و«منتج المسجلات الصوتية» في المواد 38 و51 و65 من القانون السالف الذكر رقم 2.00.')
    assert words.action == 'words' and words.words[0] == ('منتج مسجل صوتي', 'منتج تسجيل صوتي')
    assert [a['number'] for a in words.articles] == ['38', '51', '65']
    repeal = read('تنسخ مقتضيات المواد 39 و40 و41 من القانون سالف الذكر رقم 15.02.')
    assert repeal.action == 'repeal' and [a['number'] for a in repeal.articles] == ['39', '40', '41']
    assert read('تلغى اعتمادات الأداء المفتوحة بموجب قانون المالية') is None
    annex = read('تنسخ الجداول الملحقة بالمرسوم رقم 2.17.556 وتعوض بالجداول الملحقة بهذا المرسوم.')
    assert (annex.action, annex.reason) == ('unclear', 'annex')
    assert label_key('المادة 5 المكررة مرتين') == '5-ter' and label_key('المادة الأولى') == '1'
    assert strays('16 - يقصد بمصطلح «البث الإذاعي»، تبليغ الجمهور، «بشكل مباشر') == \
        '16 - يقصد بمصطلح «البث الإذاعي»، تبليغ الجمهور، بشكل مباشر'


def test_a_dotted_wording_keeps_the_old_words_where_the_dots_stand():
    new, dropped = fill.fill(['يحدد هذا المرسوم، ................................................',
                              'مهام ضابط على متن سفن الصيد البحري، وسفن مساعدة تربية الأحياء المائية البحرية.'], OLD_1)
    assert dropped == 0
    assert new == ('يحدد هذا المرسوم، تطبيقا لأحكام الفصل 54 من الظهير الشريف الصادر في 28 من جمادى الآخرة 1337 '
                   '(31 مارس 1919) المشار إليه أعلاه، لائحة الإجازات اللازمة وكذا الشروط المطلوبة لممارسة مهام '
                   'القيادة ومهام ضابط على متن سفن الصيد البحري، وسفن مساعدة تربية الأحياء المائية البحرية.')


def test_numbered_paragraphs_lines_of_dots_and_the_rest_unchanged():
    old = 'يراد بما يلي :\n1 - الربان : الشخص الذي يتولى القيادة ؛\n2 - المساعد : ضابط السطح الذي يلي الربان في ممارسة مهامه ؛\n3 - الملازم : الضابط المكلف.'
    new, dropped = fill.fill(['يراد بما يلي :', '..............................', '2 - مساعد الربان : ضابط ..........مهامه ؛',
                              '(الباقي لا تغيير فيه.)'], old)
    assert new.splitlines() == ['يراد بما يلي :', '1 - الربان : الشخص الذي يتولى القيادة ؛',
                                '2 - مساعد الربان : ضابط السطح الذي يلي الربان في ممارسة مهامه ؛', '3 - الملازم : الضابط المكلف.']
    assert dropped == 0


def test_a_wording_whose_anchor_is_not_there_is_not_placed():
    with pytest.raises(fill.Unplaced, match=r'^anchor$'):
        fill.fill(['تحدد اللائحة .......... في الجريدة الرسمية.'], OLD_1)


def test_the_sgg_layer_is_put_right_from_the_corpus_words():
    words = {'الأمانة': 50, 'المنتج': 40, 'لإنجاز': 10, 'ولا': 900, 'وال': 2, 'الظهير': 80, 'بموجب': 70, 'على': 999,
             'في': 999, 'موافقة': 30, 'الشخص': 60, 'المزمع': 5, 'مشاركته': 4, 'بحث': 20}
    text, _stats = layer.repair('األمانة املنتج إلنجاز وال الظهري مبوجب عىل يف القا�ضي »المنتج«', words)
    assert text.split()[:8] == ['الأمانة', 'المنتج', 'لإنجاز', 'ولا', 'الظهير', 'بموجب', 'على', 'في']
    assert '«المنتج»' in text
    assert layer.repair('علىموافقةالشخصاملزمعمشاركتهفي', words)[0] == 'على موافقة الشخص المزمع مشاركته في'


def test_an_sgg_text_is_read_into_articles_and_their_notes():
    page0 = 'تم إعداد هذه النسخة\nالقانون رقم 2.00\nصيغة موطدة بتاريخ\nسبتمبر 2026'
    page1 = ('1\nالأمانة العامة للحكومة\nالقانون رقم 2.00 المتعلق بحقوق المؤلف\n)ج.ر عدد 4796 بتاريخ 14 من صفر 1421 )18 ماي 2000(، ص : 1112(\n'
             'الباب الأول\nتعاريف\nالمادة 1\n)غيرت وتممت بموجب المادة الأولى من القانون رقم 013.26 الصادر بتنفيذه الظهير الشريف '
             'رقم 1.26.68؛ ج.ر عدد 7533 بتاريخ 26 من صفر 1448 )10 أغسطس 2026(، ص: 5141(\nيقصد بالمصطلحات المعاني التالية :\n'
             'المادة 2\nيسري هذا القانون على المصنفات.')
    t = sgg.read([page0, page1])
    assert t.as_of.isoformat() == '2026-09-01' and t.first_issue == 4796 and t.first_page == 1112
    assert [a.number for a in t.articles] == ['1', '2']
    # A title printed bare, its name on the next line, is one title on every article under it (25 Oct 2026; it was two
    # headings on the first article only, and a bare «الباب الأول» on the others).
    assert t.articles[0].heading_path == t.articles[1].heading_path == ['الباب الأول: تعاريف']
    note = t.articles[0].notes[0]
    assert (note.verb, note.kind, note.number, note.issue, note.page, note.on.isoformat()) == \
        ('modified', 'law', '013-26', 7533, 5141, '2026-08-10')
    assert t.articles[0].body == 'يقصد بالمصطلحات المعاني التالية :'


def test_a_note_naming_only_the_promulgating_dahir_is_the_dahir_and_a_numbered_bis_is_an_article():
    # 47.06's art. 1 (H5 of the housing plan): «… من القانون … الظهير الشريف رقم 1.20.91» is no law 1.20.91.
    note = sgg.notes('(نسخت بموجب المادة الثانية من القانون الصادر بتنفيذه الظهير الشريف رقم 1.20.91؛ '
                     'ج.ر عدد 6948 بتاريخ 4 يناير 2021، ص: 8642)')[0]
    assert (note.verb, note.kind, note.number) == ('repealed', 'dahir', '1-20-91')
    # 18.00's «المادة 16 مكرر 4» heads an article of its own.
    page = ('القانون رقم 18.00 المتعلق بنظام الملكية المشتركة للعقارات المبنية\nالمادة 16 مكرر 3\nإذا لم يقم الوكيل.\n'
            'المادة 16 مكرر 4\nيوجه الوكيل الاستدعاء.')
    t = sgg.read(['صيغة محينة بتاريخ 16 يوليو 2026', page])
    assert [a.label for a in t.articles] == ['المادة 16 مكرر 3', 'المادة 16 مكرر 4']


def test_an_adala_division_named_on_its_line_holds_until_the_next_and_a_marked_stop_ends_an_article():
    # The rent law from Adala (P12 of the polish review): «الباب الأول: نطاق التطبيق» heads every article under it, the
    # title's last line is no heading, and «و 39 من قانون المسطرة المدنية.⟦3⟧» is article 4's last line.
    page0 = 'صيغة محينة بتاريخ 21 فبراير 2019'
    page1 = ('القانون رقم 67.12 المتعلق بتنظيم العلاقات التعاقدية بين المكري والمكتري\n'
             'للمحلات المعدة للسكنى أو للاستعمال المهني\nالباب الأول: نطاق التطبيق\nالمادة الأولى\n'
             'تطبق مقتضيات هذا القانون على أكرية المحلات المعدة للسكنى أو للاستعمال المهني.\n'
             'المادة 2\nتحدد بتراضي الأطراف شروط ووجيبة الكراء.\nالمادة 4\nيجب إشعار المكتري بانتقال الملكية حسب الكيفيات المشار '
             'إليها في الفصول 37 و 38\nو 39 من قانون المسطرة المدنية.⟦3⟧\nالباب الثاني: عقد الكراء\nالفرع الأول: التزامات المكري\n'
             'المادة 5\nيلتزم المكري بتسليم المحل للمكتري في حالة جيدة.')
    t = sgg.read([page0, page1])
    assert [a.heading_path for a in t.articles] == [
        ['الباب الأول: نطاق التطبيق'], ['الباب الأول: نطاق التطبيق'], ['الباب الأول: نطاق التطبيق'],
        ['الباب الثاني: عقد الكراء', 'الفرع الأول: التزامات المكري']]
    assert t.articles[2].lines[-1] == 'و 39 من قانون المسطرة المدنية.⟦3⟧'
    # A stray dash after the division's word (the social security dahir, T1 of the work plan) does not hide it.
    t = sgg.read([page0, page1.replace('الباب الثاني: عقد الكراء', 'الباب- الثاني: عقد الكراء')])
    assert t.articles[3].heading_path[0] == 'الباب الثاني: عقد الكراء'


def test_a_long_division_name_goes_on_to_its_next_line_and_may_hold_commas():
    # The labour code (T1 of the work plan): a division's name that fills the line ends on the next; law 19.12's
    # «الباب الثالث» lists with commas. A short heading's next line stays a heading of its own.
    page0 = 'صيغة محينة بتاريخ 16 يوليو 2026'
    page1 = ('القانون رقم 65.99 المتعلق بمدونة الشغل\n'
             'الباب الخامس: الإجازات الخاصة ببعض المناسبات ورخص التغيب\nالممنوحة لأسباب شخصية\n'
             'الفرع الأول: الإجازة بمناسبة الولادة\nالمادة 269\nيستفيد كل أجير من إجازة مدتها ثلاثة أيام.\n'
             'الباب الثالث: مدة العمل، الراحة الأسبوعية، والعطلة السنوية وأيام\nالعطل\nالمادة 270\nنص.\n'
             'الباب الرابع: أحكام عامة\nتعاريف\nالمادة 271\nنص.')
    t = sgg.read([page0, page1])
    assert [a.heading_path for a in t.articles] == [
        ['الباب الخامس: الإجازات الخاصة ببعض المناسبات ورخص التغيب الممنوحة لأسباب شخصية', 'الفرع الأول: الإجازة بمناسبة الولادة'],
        ['الباب الثالث: مدة العمل، الراحة الأسبوعية، والعطلة السنوية وأيام العطل'],
        ['الباب الرابع: أحكام عامة', 'تعاريف']]


def test_a_reading_is_checked_against_the_sggs_spacing():
    assert fill.fragments_found(['يحق للمؤلفين ........ والفيديوغرامات وناشري الكتب وناشري الصحف'],
                                'يحق للمؤلفين وفناني الأداء ولا فيديو غرامات وناشري الكتب وناشري الصحف') == 1.0


def test_the_text_page_gives_the_version_on_a_date_and_each_articles_history(api, db):
    import datetime

    from apps.consolidation.models import Change
    from apps.corpus.models import Article, Consolidation, Text, Version
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/39-08', type='law', number='39-08', title_ar='مدونة الحقوق العينية')
    old = Version.objects.create(text=text, language='ar', valid_from=datetime.date(2013, 11, 28),
                                 valid_to=datetime.date(2026, 7, 16), consolidation=Consolidation.SGG)
    new = Version.objects.create(text=text, language='ar', valid_from=datetime.date(2026, 7, 16),
                                 consolidation=Consolidation.MACHINE)
    Article.objects.create(version=old, order=1, label='المادة 4', number='4', eid='art_4', body='بموجب محرر رسمي أو بمحرر ثابت التاريخ.')
    Article.objects.create(version=new, order=1, label='المادة 4', number='4', eid='art_4', body='بموجب محرر رسمي.')
    Change.objects.create(text_uri=text.akn_uri, number='4', verb='modified', source='reading', by_kind='law',
                          by_number='041-25', issue=7526, page=4426, published_on=datetime.date(2026, 7, 16),
                          verdict='agrees', score=1.0)
    d = api.get('/api/corpus/at/ma/loi/39-08/').json()
    assert d['version']['consolidation'] == 'machine' and [v['current'] for v in d['versions']] == [False, True]
    a = d['articles'][0]
    assert a['diff'] == [['=', 'بموجب محرر'], ['-', 'رسمي أو بمحرر ثابت التاريخ.'], ['+', 'رسمي.']]
    assert a['changes'][0]['by']['number'] == '041-25' and a['changes'][0]['issue']['number'] == 7526
    earlier = api.get('/api/corpus/at/ma/loi/39-08/', {'on': '2020-01-01'}).json()
    assert earlier['version']['consolidation'] == 'sgg' and earlier['articles'][0]['diff'] is None
    assert api.get('/api/corpus/at/ma/loi/39-08/', {'on': 'yesterday'}).status_code == 400


def test_what_changed_shows_only_a_change_of_the_law(api, db):
    # HM38 of the hard-moment review: the road code's 218 diffs were Adala's copy and the SGG's, both from 11
    # August 2016, and most of the rest a colon's space, «.1» for «1 -», a hamza's seat or a digit's script.
    import datetime

    from apps.corpus.models import Article, Consolidation, Text, Version
    text = Text.objects.create(akn_uri='/akn/ma/act/loi/52-05', type='law', number='52-05', title_ar='مدونة السير')
    day = datetime.date(2016, 8, 11)
    adala = Version.objects.create(text=text, language='ar', valid_from=day, consolidation=Consolidation.ADALA)
    sgg = Version.objects.create(text=text, language='ar', valid_from=day, consolidation=Consolidation.SGG)
    Article.objects.create(version=adala, order=1, label='المادة 184', number='184', eid='art_184', body='المخالفات التالية:\n.1 السرعة')
    Article.objects.create(version=sgg, order=1, label='المادة 184', number='184', eid='art_184', body='المخالفات التالية :\n1 - السرعة')
    assert api.get('/api/corpus/at/ma/loi/52-05/').json()['articles'][0]['diff'] is None
    later = Version.objects.create(text=text, language='ar', valid_from=datetime.date(2024, 7, 10), consolidation=Consolidation.MACHINE)
    a = Article.objects.create(version=later, order=1, label='المادة 184', number='184', eid='art_184',
                               body='المخالفات التالية:\n1- السرعة ومسئولية الهيأة')
    Article.objects.filter(version=sgg).update(body='المخالفات التالية :\n1 - السرعة ومسؤولية الهيئة')
    assert api.get('/api/corpus/at/ma/loi/52-05/').json()['articles'][0]['diff'] is None
    a.body = 'المخالفات التالية:\n1- السرعة ومسؤولية السائق'
    a.save()
    assert ['+', 'السائق'] in api.get('/api/corpus/at/ma/loi/52-05/').json()['articles'][0]['diff']


def test_a_finance_law_is_the_target_not_the_dahir_that_promulgated_it():
    from apps.consolidation.services.instructions.amending import _target
    assert _target('أحكام المادة 22 من قانون المالية رقم 110.13 للسنة المالية 2014، الصادر بتنفيذه الظهير الشريف '
                   'رقم 1.13.115') == {'kind': 'law', 'number': '110-13'}
    assert _target('من القانون رقم 2.00 الصادر بتنفيذه الظهير الشريف رقم 1.00.20') == {'kind': 'law', 'number': '2-00'}


def test_anchors_hold_across_a_layers_spacing_and_enumerators_either_way():
    old = 'يراد بما يلي:\n-1 «حافلة»: مركبة تضم أكثر من تسعة مقاعد يتم تخصيصها، حسب صنع هاو تهيئتها، للنقل الجماعي.\n-2 «حافلة كبيرة»: حافلة.'
    new, dropped = fill.fill(['يراد بما يلي :', '1 - «حافلة».................. للنقل الجماعي للأشخاص وأمتعتهم ؛',
                              '(الباقي لا تغيير فيه.)'], old)
    assert new.splitlines() == ['يراد بما يلي :',
                                '1 - «حافلة» مركبة تضم أكثر من تسعة مقاعد يتم تخصيصها، حسب صنع هاو تهيئتها، للنقل الجماعي للأشخاص وأمتعتهم ؛',
                                '-2 «حافلة كبيرة»: حافلة.']
    assert dropped == 0


def _run(words: str, size: float = 16.0, base: float = 700.0) -> list[tuple[str, float, float]]:
    return [(ch, size, base) for ch in words]


def test_an_adala_page_loses_its_page_number_its_footnotes_and_their_marks():
    from apps.consolidation.services import adala
    page = [
        _run('- 29 -', 14.0, 800),
        _run('ظـهـير شـريـف رقـم 1.59.413', base=760),               # Word justifies with tatweel
        _run('1 - مطبوع خاص بطلب الإذن يحدد بقرار من وزير', base=700),
        _run('4', 10.6, 684) + _run(' العدل', base=680),          # the layer cuts a printed line at its mark
        _run('؛', base=680),
        _run('2', 10.6, 664) + _run(' المادة 15', base=660),      # a heading marked
        _run('5 الفصل 14', base=640),                             # a mark set full size
        _run('يجب على المغاربة أن يودعوا نسخة منه.', base=620),
        _run('-4 قرار لوزير العدل رقم 269.04 بتحديد شكل المطبوع، الجريدة الرسمية عدد 5186', 13.0, 100),
        _run('فبراير 2004، ص .520', 13.0, 85),
    ]
    body, foot = adala.split_page(page, 16.0)
    assert body == ['ظهير شريف رقم 1.59.413', '1 - مطبوع خاص بطلب الإذن يحدد بقرار من وزير', 'العدل؛⟦4⟧', 'المادة 15', '⟦2⟧.', 'الفصل 14', '⟦5⟧.',
                    'يجب على المغاربة أن يودعوا نسخة منه.']
    assert foot[0].startswith('-4 قرار') and foot[1] == 'فبراير 2004، ص .520'


def test_adala_footnotes_run_on_across_pages_and_their_numbers_may_skip_one():
    from apps.consolidation.services import adala
    notes = adala.footnotes([
        ['-1 الجريدة الرسمية عدد 5184، ص .418'],
        ['2 - تم تغيير الفقرة الأولى من المادة 15 أعلاه'],
        ['- بمقتضى المادة الفريدة من القانون رقم 102.15', '1 - قائمة في الحاشية'],
        ['-4 قرار لوزير العدل رقم 269.04'],
    ])
    assert [(n.number, n.page) for n in notes] == [(1, 0), (2, 1), (4, 3)]
    assert notes[1].text.endswith('رقم 102.15\n1 - قائمة في الحاشية')


def test_an_adala_version_points_to_its_own_file_and_names_it(api, db):
    import datetime

    from django.utils import timezone

    from apps.consolidation.services.sgg import SggArticle
    from apps.consolidation.services.versions import save_version, text_for
    from apps.corpus.models import Consolidation
    from apps.sources.models import Document
    doc = Document.objects.create(source='adala', kind='text', sha256='a6d5' * 16, path='samples/adala/adala_118.pdf',
                                  url='https://adala.justice.gov.ma/api/uploads/2024/07/22/x.pdf', mime='application/pdf',
                                  language='ar', bytes=1, page_count=107, fetched_at=timezone.now(),
                                  meta={'as_of': '2021-07-29', 'first_issue': 5184, 'first_page': 418})
    text, created = text_for('70-03', 'القانون رقم 70.03 بمثابة مدونة الأسرة', Consolidation.ADALA)
    save_version(text, Consolidation.ADALA, doc, datetime.date(2021, 7, 29),
                 [SggArticle(label='المادة 15', number='15', heading_path=[], page=12, lines=['يجب على المغاربة.'])])
    assert created and text.akn_uri == '/akn/ma/act/loi/70-03'
    d = api.get('/api/corpus/at/ma/loi/70-03/').json()
    assert d['version']['consolidation'] == 'adala' and d['version']['source']['first_issue'] == 5184
    a = d['articles'][0]
    assert (a['document_id'], a['page'], a['page_index'], a['reading']) == (doc.pk, 13, 12, 'layer')


def test_an_sgg_title_cut_short_or_missing_gives_way_to_the_sggs_list():
    from apps.consolidation.management.commands.load_sgg_consolidated import title_of
    listed = 'القانون رقم 17.04 بمثابة مدونة الأدوية والصيدلة'
    assert title_of('القانون رقم 17.0 بمثابة مدونة الأدوية والصيدلة الصادر بتنفيذه', listed, '17-04') == listed
    assert title_of('', 'القانون رقم 131.13 المتعلق بمزاولة مهنة الطب', '131-13').startswith('القانون رقم 131.13')
    whole = 'القانون رقم 01.09 المتعلق بالمراكز السجلية الصادر بتنفيذه الظهير الشريف'
    assert title_of(whole, 'Loi 1.09', '01-09') == whole


def test_a_law_headed_by_the_dahir_that_promulgates_it_is_filed_as_the_law():
    from apps.consolidation.services.adala import PROMULGATES
    title = ('ظهير شريف رقم 1.13.111 صادر في 15 من محرم 1435 (19 نوفمبر 2013) بتنفيذ القانون رقم 67.12 المتعلق '
             'بتنظيم العلاقات التعاقدية بين المكري والمكتري.')
    assert PROMULGATES.search(title).group(1).rstrip(' .') == 'القانون رقم 67.12 المتعلق بتنظيم العلاقات التعاقدية بين المكري والمكتري'
    assert PROMULGATES.search('ظهير شريف رقم 1.59.413 بالمصادقة على مجموعة القانون الجنائي') is None


def test_an_adala_page_is_shown_as_its_articles_read_it(api, db, monkeypatch):
    # P14 of the polish review: a reader opening the page to check an article sees «العلاقات», not the raw «العالقات».
    from django.utils import timezone

    from apps.consolidation.services import layer
    from apps.sources.models import Document, Page

    monkeypatch.setattr(layer, 'lexicon', lambda: {'العلاقات': 40, 'الأول': 90, 'الباب': 60})
    doc = Document.objects.create(source='adala', kind='text', sha256='b7e6' * 16, path='samples/adala/x.pdf',
                                  url='https://adala.justice.gov.ma/x.pdf', mime='application/pdf', language='ar', page_count=1,
                                  bytes=1, fetched_at=timezone.now())
    Page.objects.create(document=doc, index=0, kind='text', text='الباب األول العالقات', text_source='layer')
    r = api.get(f'/api/sources/documents/{doc.pk}/pages/0/').json()
    assert r['text'] == 'الباب الأول العلاقات' and r['repaired'] and r['source'] == 'adala'


def test_a_law_that_quotes_another_keeps_its_own_articles_when_told_their_word():
    # Law 103.13 (F2 of the family plan): its «المادة 2» quotes the penal code's «الفصل 404»; more «الفصل» than
    # «المادة» once made the quoted articles the law's own.
    page = ('القانون رقم 103.13 المتعلق بمحاربة العنف ضد النساء\nباب تمهيدي: أحكام عامة\nالمادة الأولى\nيراد بما يلي العنف ضد المرأة.\n'
            'المادة 2\nتغير على النحو التالي أحكام الفصلين 404 و431:\nالفصل 404\nيعاقب كل من ارتكب عمدا ضربا.\n'
            'الفصل 431\nمن أمسك عمدا عن تقديم مساعدة.\nالمادة 3\nيدخل هذا القانون حيز التنفيذ.')
    t = sgg.read(['صيغة محينة بتاريخ 12 مارس 2018', page], 'المادة')
    assert [a.number for a in t.articles] == ['1', '2', '3']
    assert 'الفصل 404' in t.articles[1].lines and t.articles[0].heading_path == ['باب تمهيدي: أحكام عامة']


def test_a_file_never_cuts_a_title_nor_revives_a_repealed_text(db):
    from apps.consolidation.services.versions import text_for
    from apps.corpus.models import Consolidation, Status, Text
    Text.objects.create(akn_uri='/akn/ma/act/loi/41-10', type='law', number='41-10', status=Status.REPEALED,
                        title_ar='القانون رقم 41.10 المتعلق بتحديد شروط ومساطر الاستفادة من صندوق التكافل العائلي')
    text, created = text_for('41-10', 'القانون رقم 41.10 المتعلق بتحديد', Consolidation.ADALA)
    assert not created and text.status == Status.REPEALED and text.title_ar.endswith('صندوق التكافل العائلي')


def test_articles_numbered_in_compound_words_and_a_repealed_one_are_read_and_nothing_is_swallowed():
    """T1–T2 of the work plan: the civil service statute numbers its «فصول» in words («الفصل الحادي عشر»), and AMO
    law 65.00 prints a repealed article as «(نسخت).», which opened a note that took articles 79 to 149."""
    page = '\n'.join(['النظام الأساسي العام للوظيفة العمومية', 'الفصل العاشر', 'يؤسس مجلس أعلى للوظيفة العمومية.',
                      'الفصل الحادي عشر', 'يحدد بمرسوم ما يلي.', 'الفصل الثاني والعشرون', 'للموظف الحق في رخص.',
                      'الفصل في النزاعات من اختصاص المحاكم الإدارية، كما هو مبين.'])
    t = sgg.read(['صيغة محينة بتاريخ 12 مارس 2018', page], 'الفصل')
    assert [(a.label, a.number) for a in t.articles] == [('الفصل العاشر', '10'), ('الفصل الحادي عشر', '11'),
                                                         ('الفصل الثاني والعشرون', '22')]
    assert t.articles[-1].body.endswith('كما هو مبين.')
    # Adala's text layer prints the brackets turned, «)نسخت(.»; the layer turns them back.
    t = sgg.read(['صيغة محينة بتاريخ 12 مارس 2018', 'القانون رقم 65.00\nالمادة 78\n)نسخت(.\nالمادة 79\nتطبق أحكام الظهير الشريف.'])
    assert [(a.label, a.body) for a in t.articles] == [('المادة 78', '(نسخت).'), ('المادة 79', 'تطبق أحكام الظهير الشريف.')]


def test_the_constitutions_numbers_in_words_past_forty_and_past_a_hundred_are_read():
    """Adala's constitutions of 1992 and 1996: «الحادي والأر بعون» (a word the layer split), «السابع والعشرين», «الثاني
    السبعون» (its «و» left out), «المائة», «الثاني بعد المائة». Articles 41–49 sat inside 40, and 101–108 inside 100."""
    page = '\n'.join(['دستور المملكة المغربية', 'الفصل السابع والعشرين', 'للملك حق حل مجلس النواب.',
                      'الفصل الأربعون', 'للوزراء أن يحضروا الجلسات.', 'الفصل الحادي والأر بعون', 'جلسات مجلس النواب عمومية.',
                      'الفصل الثاني السبعون', 'لا يمكن حل المجلس الذي يليه.', 'الفصل المائة', 'لا يمكن أن تتناول المراجعة النظام الملكي.',
                      'الفصل الثاني بعد المائة', 'تبقى المحاكم مختصة.', 'الفصل الثاني من هذا الباب ينظم ما يلي.'])
    t = sgg.read(['صيغة محينة بتاريخ 7 أكتوبر 1996', page], 'الفصل')
    assert [(a.label, a.number) for a in t.articles] == [
        ('الفصل السابع والعشرين', '27'), ('الفصل الأربعون', '40'), ('الفصل الحادي والأربعون', '41'),
        ('الفصل الثاني السبعون', '72'), ('الفصل المائة', '100'), ('الفصل الثاني بعد المائة', '102')]
    assert t.articles[-1].body.endswith('ينظم ما يلي.')       # a sentence that opens with «الفصل الثاني» is no heading
    assert label_key('الفصل الثاني بعد المائة') == '102' and label_key('الفصل الثاني من هذا الظهير') == '2'


def test_a_constitutions_preamble_is_a_part_of_it_first_even_after_the_dahirs_own_articles():
    """The 2011 constitution's «تصدير» says «يشكل هذا التصدير جزءا لا يتجزأ من هذا الدستور»; the reader used to drop it
    with the title's lines. 1970's dahir prints its own articles first, and the preamble after them."""
    page = '\n'.join(['ظهير شريف رقم 1.11.91 بتنفيذ نص الدستور', 'تصدير',
                      'إن المملكة المغربية، وفاء لاختيارها الذي لا رجعة فيه، في بناء دولة ديمقراطية.',
                      'يشكل هذا التصدير جزءا لا يتجزأ من هذا الدستور.', 'الباب الأول: أحكام عامة', 'الفصل 1',
                      'نظام الحكم بالمغرب نظام ملكية دستورية.'])
    t = sgg.read(['صيغة محينة بتاريخ 30 يوليو 2011', page], 'الفصل')
    assert [(a.label, a.number) for a in t.articles] == [('تصدير', 'preamble'), ('الفصل 1', '1')]
    assert t.articles[0].body.endswith('جزءا لا يتجزأ من هذا الدستور.') and t.articles[1].heading_path == ['الباب الأول: أحكام عامة']
    page = '\n'.join(['ظهير شريف رقم 1.70.177 بإصدار الأمر بتنفيذ الدستور', 'الفصل الأول',
                      'يصدر جنابنا الشريف الأمر بتنفيذ الدستور المضاف نصه إلى ظهيرنا هذا.', 'الفصل الثاني',
                      'يلغى الدستور الصادر الأمر بتنفيذه يوم 14 دجنبر 1962.', 'الدستور', 'تصدير',
                      'المملكة المغربية دولة إسلامية ذات سيادة كاملة، لغتها الرسمية هي اللغة العربية.',
                      'الباب الأول: أحكام عامة', 'الفصل 1', 'نظام الحكم بالمغرب نظام ملكية دستورية.'])
    t = sgg.read(['صيغة محينة بتاريخ 1 غشت 1970', page], 'الفصل')
    assert [a.number for a in t.articles] == ['preamble', '1', '2', '1']     # adala.read sends the dahir's 1 and 2 away


def test_titles_in_two_words_one_line_articles_and_a_number_ending_a_sentence_are_read_right():
    """The 2011 constitution: «الباب الحادي عشر: …» is a title (it was the last line of art. 150), art. 112 is one short
    line with no full stop (it was a heading of art. 113); 1962's art. 33 ends «في الفصل .84», the layer's «84.»."""
    page = '\n'.join(['الدستور', 'الباب العاشر: المجلس الأعلى للحسابات', 'الفصل 150',
                      'يحدد قانون تنظيمي اختصاصات المجالس الجهوية للحسابات.', 'الباب الحادي عشر: المجلس الاقتصادي والاجتماعي والبيئي',
                      'الفصل 151', 'يحدث مجلس اقتصادي واجتماعي وبيئي.', 'الفصل 112', 'يحدد النظام الأساسي للقضاة بقانون تنظيمي',
                      'المجلس الأعلى للسلطة القضائية', 'الفصل 113', 'يسهر المجلس الأعلى للسلطة القضائية على تطبيق الضمانات.',
                      'الفصل 33', 'يعين القضاة طبق الشروط المنصوص عليها في', 'الفصل .84', 'الفصل 34', 'القضاء مستقل.'])
    t = sgg.read(['صيغة محينة بتاريخ 30 يوليو 2011', page], 'الفصل')
    got = {a.number: a for a in t.articles}
    assert got['150'].body.endswith('الجهوية للحسابات.')
    assert got['151'].heading_path == ['الباب الحادي عشر: المجلس الاقتصادي والاجتماعي والبيئي']
    assert got['112'].body == 'يحدد النظام الأساسي للقضاة بقانون تنظيمي'
    assert got['113'].heading_path[-1] == 'المجلس الأعلى للسلطة القضائية'
    assert got['33'].body.endswith('الفصل .84') and 'الفصل .84' not in got['34'].heading_path


def test_the_stretching_stroke_is_never_the_first_letter_nor_after_the_last():
    """Adala prints a stretched word with «م» in its stroke («الرسممم», «اسمترجاع»); the rule cut real letters too:
    «ممنوع» became «نوع» (the 1962 constitution's art. 3, the road code, decree 2.10.420) and «مجموعتهم» «مجموعته»."""
    from apps.consolidation.services.layer import _unstretched
    assert 'نوع' not in set(_unstretched('ممنوع')) and 'مجموعته' not in set(_unstretched('مجموعتهم'))
    assert 'الرسم' in set(_unstretched('الرسممم')) and 'استرجاع' in set(_unstretched('اسمترجاع'))


def test_words_the_layer_cut_with_spaces_are_joined_when_the_whole_is_a_word_the_bo_prints():
    """T1 of the work plan: the labour code's file prints «الطر ف», «ي م كن», «لأل ج ي ر»."""
    from apps.consolidation.services.layer import join_split
    words = {'الطرف': 40, 'يمكن': 900, 'للأجير': 300, 'في': 5000, 'الأجير': 400, 'حق': 80, 'ما': 900, 'يحق': 60}
    assert join_split('يحق للطر ف', words) == 'يحق للطر ف'           # «للطرف» unknown here: left as it came
    assert join_split('يحق الطر ف في', words) == 'يحق الطرف في'
    assert join_split('ي م كن لأل ج ي ر', words) == 'يمكن للأجير'
    assert join_split('في ما حق', words) == 'في ما حق'               # known words stay apart
    assert join_split('فائدة لأل ج ي ر.', words) == 'فائدة للأجير.'


def test_a_code_that_repeals_the_old_one_from_its_own_entry_into_force_takes_effect_after_six_months():
    """T2 of the work plan: law 58.25 (civil procedure) read as «in force on a condition» from its art. 644, and its
    repeal of the 1974 code went unread («ينسخ،» then a numbered list)."""
    from apps.consolidation.services.instructions.dates import in_force
    from apps.consolidation.services.instructions.provisions import clauses
    art643 = 'يدخل هذا القانون حيز التنفيذ، بعد ستة (6) أشهر من تاريخ نشره بالجريدة الرسمية.'
    art644 = ('ينسخ، ابتداء من تاريخ دخول هذا القانون حيز التنفيذ :\n'
              '1 - الظهير الشريف بمثابة قانون رقم 1.74.447 بتاريخ 11 من رمضان 1394 (28 شتنبر 1974) بالمصادقة على نص قانون '
              'المسطرة المدنية، كما وقع تغييره وتتميمه ؛\n'
              '2 - المواد 4 و5 ومن 7 إلى 13 من القانون رقم 42.10 المتعلق بتنظيم قضاء القرب ؛\n'
              '3 - القانون رقم 53.95 القاضي بإحداث المحاكم التجارية، كما وقع تغييره وتتميمه.')
    assert in_force(art644) is None
    assert (in_force(art643).rule, in_force(art643).months) == ('after', 6)
    [repeal] = clauses(art644)
    named = {c.get('text_number') for c in repeal.citations}
    assert named == {'1-74-447', '53-95'}         # only articles of 42.10: never the whole law
    assert repeal.same_date


def test_a_numbered_bis_keeps_its_number():
    # 18.00 numbers its added articles «16 مكرر 2 … 16 مكرر 9» and «59 مكرر 1 … 59 مكرر 11» (H2 of the housing plan).
    assert label_key('المادة 16 مكرر 4') == '16-bis-4'
    assert label_key('المادة 59 مكرر 11') == '59-bis-11'
    assert label_key('المادة 16 مكرر مرتين') == '16-ter'
    assert label_key('المادة 16 مكرر') == '16-bis'
    assert label_key('المادة 16 مكرر1') == '16-bis-1'


def test_a_turned_sub_article_heading_is_read_and_its_mark_goes_to_the_body():
    # Adala's DOC (H1 of the housing plan): «الفصل -3 618 مكرر⟦173⟧» heads 618-3 مكرر, «الفصل 106 1-» 106-1.
    assert sgg.turned('الفصل -3 618 مكرر⟦173⟧') == 'الفصل 618-3 مكرر⟦173⟧'
    assert sgg.turned('الفصل 106 1-') == 'الفصل 106-1'
    assert sgg.turned('الفصل 3-106') == 'الفصل 106-3'
    assert sgg.turned('الفصل 618-3') == 'الفصل 618-3'
    page = ('ظهير بمثابة قانون الالتزامات والعقود\nالفصل 618-3\nيجب أن يرد عقد البيع الابتدائي في محرر رسمي.\n'
            'الفصل -3 618 مكرر⟦173⟧\nيجب أن يتضمن عقد البيع الابتدائي على الخصوص البيانات التالية:')
    t = sgg.read(['صيغة محينة بتاريخ 16 يوليو 2026', page], 'الفصل')
    assert [a.number for a in t.articles] == ['618-3', '618-3-bis']
    assert t.articles[1].lines[-1] == '⟦173⟧'


def test_a_lam_alif_printed_backwards_is_turned_when_its_stem_is_known():
    words = {'يتحمل': 9, 'خلاف': 74, 'خالف': 19, 'إبطال': 3}
    assert layer.repair_word('يتحمالن', words)[0] == 'يتحملان'
    assert layer.repair_word('بخالفه', words)[0] == 'بخلافه'
    assert layer.repair_word('لإلبطال', words)[0] == 'للإبطال'
    assert layer.repair_word('احتيال', words)[0] == 'احتيال'     # no known stem either way: left as printed


def test_a_numbered_bis_run_into_its_text_is_cut_and_the_owners_are_plural():
    # Adala's 18.00 (H2 of the housing plan).
    page = ('القانون رقم 18.00 المتعلق بنظام الملكية المشتركة للعقارات المبنية\nالمادة 16\nيدعو مالك أو أكثر إلى الجمع العام.\n'
            'المادة 16 مكرر1 يتولى الجمع العام في أول اجتماع يعقده تعيين وكيل الاتحاد.\n'
            'ويمكن الرجوع إلى المادة 40 مكرر1 من هذا القانون.')
    t = sgg.read(['صيغة محينة بتاريخ 16 يوليو 2026', page])
    assert [a.number for a in t.articles] == ['16', '16-bis-1']
    assert t.articles[1].lines[0].startswith('يتولى الجمع العام')
    words = {'المالك': 50, 'المشتركين': 40, 'جميع': 90}
    assert layer.repair('يستدعى إليهما جميع المالك المشتركين', words)[0] == 'يستدعى إليهما جميع الملاك المشتركين'
    assert layer.repair('يمكن للمالك أن يطلب', words)[0] == 'يمكن للمالك أن يطلب'
    assert layer.repair('يعتبر محتال بدون حق ولا سند', words)[0] == 'يعتبر محتلا بدون حق ولا سند'


def test_a_kashida_printed_as_mim_is_taken_out_when_the_word_is_known():
    # Adala's DOC, 618-3 مكرر: «مراجع ضممانة اسمترجاع الأقسماط» (H1 of the housing plan).
    words = {'ضمانة': 30, 'استرجاع': 20, 'الأقساط': 12, 'الرهون': 5}
    assert layer.repair('مراجع ضممانة اسمترجاع الأقسماط', words)[0] == 'مراجع ضمانة استرجاع الأقساط'
    assert layer.repair_word('المرهون', words)[0] == 'المرهون'     # a word's own «م» stays
    words |= {'ممثل': 40, 'بالمثل': 30, 'توقيع': 50, 'توقيعها': 20}
    assert layer.repair_word('بالممثل', words)[0] == 'بالممثل'     # a known stem: the «مم» is the word's
    assert layer.repair_word('توقيعهما', words)[0] == 'توقيعهما'
    words |= {'تاريخ': 90, 'هما': 30}
    assert layer.repair_word('لتاريخهما', words)[0] == 'لتاريخهما'     # nor cut into «لتاريخ هما»


def test_an_adala_heading_run_into_its_line_or_set_on_the_line_before_is_a_heading():
    # The 1984 dahir on accident victims (road topic, R3): «المادة األولى مكررة . - يراد …» opens the article, and a
    # heading law 70.24 rewrote, marked, is set at the end of the line before («… ولكنه 10 المادة الثامنة»).
    from apps.consolidation.services.adala import _run_in
    assert _run_in(['المادة األولى مكررة . - يراد بما يلي في مدلول ظهيرنا الشريف']) == [
        'المادة الأولى مكررة', 'يراد بما يلي في مدلول ظهيرنا الشريف']
    assert _run_in(['عيشهم من المادة الحادية عشرة⟦11⟧', 'جراء وفاته يقسم عليهم']) == [
        'عيشهم من', 'المادة الحادية عشرة', '⟦11⟧.', 'جراء وفاته يقسم عليهم']
    assert _run_in(['المحددة في المادة الخامسة']) == ['المحددة في المادة الخامسة']      # a reference, unmarked


def test_the_road_decrees_ligature_and_an_image_readings_headings_are_put_right(monkeypatch):
    from apps.consolidation.services import adala
    words = {'تقاطعا': 40, 'التقاطعات': 12}
    assert layer.repair_word('تقاصا', words) == ('تقاطعا', True)
    pages = [(['المادة الأولى 2', 'نص.', 'المادة 2 3', 'نص.', 'المادة ©', 'نص.', 'المادة 4', 'نص.'], [])]
    assert [line for line in adala._headings(pages)[0][0] if line.startswith('المادة')] == [
        'المادة الأولى', 'المادة 2', 'المادة 3', 'المادة 4']


def test_sgg_headings_with_their_note_glued_or_spaced_open_their_articles(monkeypatch):
    # Law 52.05 as the SGG consolidated it (R1 of the road plan): 16 articles stood inside their neighbours.
    # The words the corpus prints, which the note's turned «مبوجب» is put right by: the test's own (the corpus's list is
    # built from the database into CORPUS_DIR, which a test does not share).
    monkeypatch.setattr(layer, 'lexicon', lambda: {'بموجب': 900, 'المادة': 900, 'الثانية': 300, 'القانون': 900})
    page = ('صيغة محينة بتاريخ 10 يوليو 2024\nالقانون رقم 52.05 المتعلق بمدونة السير على الطرق\n'
            'المادة 54\nتتضمن شهادة التسجيل البيانات التالية :\n- استعمال المركبة ؛\n'
            'المادة ￾55مدة صلاحية الحامل المحررة فيه شهادة التسجيل.\nتخضع أيضا للتسجيل المركبات الفلاحية.\n'
            'المادة 112\nيمكن الأمر بإيداع المركبة في المحجز.\nالمادة 112 - 1\nيتحمل المالك صوائر الإيداع.\n'
            'المادة220 \nيجوز للمخالف أن يطلب أداء الغرامة.\n'
            'املادة221 )نسخت وعوضت مبوجب املادة الثانية من القانون رقم 116.14، ج.ر عدد 6490، ص: 5869(\n'
            'يمكن أداء مبلغ الغرامات داخل أجل ثلاثين يوما.')
    t = sgg.read([page])
    assert [a.number for a in t.articles] == ['54', '55', '112', '112-1', '220', '221']
    assert t.articles[0].lines[-1] == '- استعمال المركبة ؛ مدة صلاحية الحامل المحررة فيه شهادة التسجيل.' or \
        t.articles[0].body.endswith('مدة صلاحية الحامل المحررة فيه شهادة التسجيل.')
    assert t.articles[1].body == 'تخضع أيضا للتسجيل المركبات الفلاحية.'
    assert t.articles[-1].body == 'يمكن أداء مبلغ الغرامات داخل أجل ثلاثين يوما.' and t.articles[-1].notes


def test_a_table_read_on_the_page_takes_the_place_of_the_flattened_one_and_its_rows_stay_rows(monkeypatch, tmp_path):
    from apps.consolidation.services import fill
    tables = tmp_path / 'page_tables.yaml'
    tables.write_text("- {file: '52_05', article: '99', from: 'الجنح الرقم الترتيبي', table: \"الجنح\\n| 01 | القتل | 14 |\\n| 02 | الجروح | 6 |\"}\n")
    monkeypatch.setattr(sgg, 'PAGE_TABLES', tables)
    a = sgg.SggArticle(label='المادة 99', number='99', heading_path=[],
                       lines=['وفقا لما يلي :', 'الجنح', 'الرقم', 'الترتيبي', 'القتل غير العمدي 01 14'])
    assert sgg.page_tables('52_05', [a]) == 1
    assert fill.paragraphs(a.body) == ['وفقا لما يلي :', 'الجنح', '| 01 | القتل | 14 |', '| 02 | الجروح | 6 |']


@pytest.mark.django_db
def test_a_scanned_annex_read_on_the_page_is_added_as_the_texts_annex(monkeypatch, tmp_path):
    from datetime import date

    from django.utils import timezone

    from apps.consolidation.services.versions import save_version
    from apps.corpus.models import Consolidation, Text
    from apps.sources.models import Document, Source
    tables = tmp_path / 'page_tables.yaml'
    tables.write_text("- {file: order_ar, article: annex, label: ملحق, page: 4, table: \"| البلد |\\n|---|\\n| مصر |\"}\n")
    monkeypatch.setattr(sgg, 'PAGE_TABLES', tables)
    articles = [sgg.SggArticle(label='المادة الأولى', number='1', heading_path=[], lines=['نص.'])]
    assert sgg.page_tables('order_ar', articles) == 1 and sgg.page_tables('other', articles) == 0
    text = Text.objects.create(akn_uri='/akn/ma/act/arrete/2-11', type='order', number='2-11')
    doc = Document.objects.create(source=Source.ADALA, kind='consolidated_text', path='order_ar.pdf', sha256='0' * 64,
                                  mime='application/pdf', bytes=1, page_count=4, fetched_at=timezone.now())
    rows = save_version(text, Consolidation.ADALA, doc, date(2011, 2, 7), articles)
    assert [(r.eid, r.printed_page) for r in rows] == [('art_1', 1), ('annex', 4)]


def test_heads_the_ocr_lost_are_restored_from_the_page_reading(monkeypatch, tmp_path):
    tables = tmp_path / 'page_tables.yaml'
    tables.write_text("""
- {file: d311, article: '22', label: المادة 22, after: '21', from: توجه النيابة العامة, page: 12, table: توجه النيابة العامة المختصة.}
- {file: d311, article: '28', label: المادة 28, after: '27', was: '20'}
- {file: d311, article: '3', table: يجوز للمترشح اجتياز الاختبار النظري.}
""")
    monkeypatch.setattr(sgg, 'PAGE_TABLES', tables)
    arts = [sgg.SggArticle(label=f'المادة {n}', number=n, heading_path=[], lines=[body]) for n, body in (
        ('3', 'يجوز للمترشح اجتياز ال اختبار'), ('21', 'تحدد بقرار مشترك ما يلي. توجه النيابة العامة المختصة.'),
        ('27', 'لا يترتب استرجاع النقط.'), ('20', 'لا يمكن السائق.'))]
    assert sgg.page_tables('d311', arts) == 3
    assert [a.number for a in arts] == ['3', '21', '22', '27', '28']
    assert arts[1].body == 'تحدد بقرار مشترك ما يلي.' and arts[2].body == 'توجه النيابة العامة المختصة.'
    assert arts[2].page == 11 and arts[4].label == 'المادة 28'
    assert arts[0].body == 'يجوز للمترشح اجتياز الاختبار النظري.'


def test_a_run_in_heading_with_a_two_digit_mark_given_words_first_keeps_its_first_line():
    from apps.consolidation.services.adala import _run_in
    lines = ['. - يجب على مقاولة التأمين أن تقوم، خلال الستين يوما التالية  المادة التاسعة عشرة⟦16⟧',
             'لتسلم مستندات الإثبات المشار إليها في المادة السابقة،',
             '-. لا يحول الصلح أو المقرر القضائي النهائي الذي تم بموجبه  المادة العشرون مكررة⟦18⟧']
    assert _run_in(lines) == ['المادة التاسعة عشرة', '⟦16⟧.', 'يجب على مقاولة التأمين أن تقوم، خلال الستين يوما التالية',
                              'لتسلم مستندات الإثبات المشار إليها في المادة السابقة،',
                              'المادة العشرون مكررة', '⟦18⟧.', 'لا يحول الصلح أو المقرر القضائي النهائي الذي تم بموجبه']


# The health review, S3: law 65.00 as the BO's chain (27.22 of 2022, 37.25 of 2025), its wordings as printed.
ART_21 = ('تحدد آجال وكيفيات إبرام الاتفاقيات الوطنية بنص تنظيمي.\n'
          'ويتعين أن تصادق الإدارة على هذه الاتفاقيات قبل الشروع في تطبيقها.\n'
          'وفي حالة عدم الاتفاق على مضمون الاتفاقيات الوطنية، فإن الإدارة تقرر الاستمرار في العمل تلقائيا بالإتفاقية '
          'السابقة المبرمة بموجب هذا القانون إن وجدت، أو تقرر، عند الاقتضاء، نظاما للتعريفة بعد استشارة الوكالة الوطنية '
          'للتأمين الصحي.')


def _change(number, wording, verb='modified', **detail):
    from apps.consolidation.models import Change
    return Change(text_uri='/akn/ma/act/loi/65-00', number=number, verb=verb, wording=wording,
                  by_uri='/akn/ma/act/loi/27-22', detail=detail)


def _row(number, body):
    return {'key': number, 'label': f'المادة {number}', 'eid': f'art_{number}', 'body': body, 'heading_path': [], 'page': 1}


def test_a_dotted_paragraph_changes_that_paragraph_only():
    from apps.consolidation.services.engine.rebuild import apply
    rows = [_row('21', ART_21)]
    apply(rows, _change('21', ['وفي حالة عدم الاتفاق على ............... بموجب هذا القانون، أو تقرر ............... '
                               'للتأمين الصحي.'], part=['الفقرة', [3]], dotted=True))
    lines = rows[0]['body'].splitlines()
    assert lines[:2] == ART_21.splitlines()[:2]          # the two paragraphs before it stay
    assert 'إن وجدت' not in lines[2] and lines[2].endswith('بعد استشارة الوكالة الوطنية للتأمين الصحي.')


def test_a_paragraph_that_opens_a_list_is_counted_with_its_items():
    from apps.consolidation.services.engine.rebuild import apply
    body = 'يضمن التأمين.\nيخول التأمين ما يلي :\n- العلاجات ؛\n- الأدوية.\nتحدد الكيفيات بمرسوم.'
    rows = [_row('7', body)]
    apply(rows, _change('7', ['تحدد الكيفيات والآجال بمرسوم.'], part=['الفقرة', [3]]))
    assert rows[0]['body'].splitlines() == ['يضمن التأمين.', 'يخول التأمين ما يلي :', '- العلاجات ؛', '- الأدوية.',
                                            'تحدد الكيفيات والآجال بمرسوم.']


def test_the_rest_unchanged_under_a_wording_without_dots_keeps_the_rest():
    from apps.consolidation.services.engine.rebuild import apply
    rows = [_row('6', 'إذا كان الزوج والزوجة مؤمنين، وجب التصريح بالأولاد لدى هيئة الأب.\nوفي حالة انحلال ميثاق الزوجية، يتعين التصريح.')]
    apply(rows, _change('6', ['إذا كان الزوج والزوجة مؤمنين، وجب التصريح بالأولاد لدى هيئة الأب أو الأم.', '(الباقي بدون تغيير.)'],
                        verb='replaced'))
    assert rows[0]['body'].splitlines() == ['إذا كان الزوج والزوجة مؤمنين، وجب التصريح بالأولاد لدى هيئة الأب أو الأم.',
                                            'وفي حالة انحلال ميثاق الزوجية، يتعين التصريح.']


def test_a_paragraph_quoted_with_the_rest_unchanged_after_it():
    # Law 01.05 on 65.00 art. 147 (BO 5294): its heading's dash is a tatweel, its date is the quoted article's, not its
    # own, and «(الباقي بدون تغيير.)» follows a line that closes the quote.
    from apps.consolidation.services.instructions.dates import in_force
    body = ('تغير أحكام الفقرة الأولى من المادة 147 من القانون رقم 65.00 كالتالي :\n'
            '« المادة 147 (الفقرة الأولى). ـ تدخل أحكام هذا القانون حيز التنفيذ، ابتداء من تاريخ «النشر للنصوص التطبيقية.\n'
            '«وتدخل أحكام نظام المساعدة الطبية حيز التنفيذ ابتداء من تاريخ نشر النصوص «بهذا النظام.»\n'
            '(الباقي بدون تغيير.)')
    ins = read(body)
    assert [u.number for u in ins.units] == ['147'] and ins.units[0].lines[1].endswith('بهذا النظام.')
    assert in_force(body) is None
    new, _dropped = fill.fill(ins.units[0].lines, 'تدخل أحكام هذا القانون حيز التنفيذ في فاتح يناير.\nويجب على المشغلين الانخراط.')
    assert new.splitlines()[-1] == 'ويجب على المشغلين الانخراط.' and 'الباقي' not in new


def test_a_quoted_heading_names_the_paragraph_it_changes():
    # Law 116.12 art. 29 on 65.00 art. 5 (BO 6384, 2015): the lead says «الفقرة الثالثة من المادة 5», the heading
    # «المادة 5 (الفقرة الثالثة)»; only that paragraph changes.
    from apps.consolidation.services.engine.rebuild import apply
    ins = read('تغير، على النحو التالي، أحكام الفقرة الثالثة من المادة 5 من القانون رقم 65.00 السالف الذكر:\n'
               '«المادة 5 (الفقرة الثالثة). - غير أن حد السن يمكن تمديده إلى 26 «سنة بالنسبة للأولاد الذين يتابعون '
               'دراسات عليا، شريطة الإدلاء «بما يثبت ذلك.»')
    assert ins.action == 'modify' and ins.units[0].part == ('الفقرة', [3])
    rows = [_row('5', 'يشمل التأمين الإجباري ما يلي :\n- زوج المؤمن ؛\n- الأولاد.\nيحدد حد السن في 21 سنة.\n'
                      'غير أن حد السن يمكن تمديده إلى 25 سنة.\nيعفى من حد السن الأولاد المعاقون.')]
    apply(rows, _change('5', ins.units[0].lines, part=list(ins.units[0].part)))
    assert rows[0]['body'].splitlines()[4:] == ['غير أن حد السن يمكن تمديده إلى 26 سنة بالنسبة للأولاد الذين يتابعون '
                                                'دراسات عليا، شريطة الإدلاء بما يثبت ذلك.', 'يعفى من حد السن الأولاد المعاقون.']


def test_a_date_of_force_the_scan_broke_over_two_lines():
    from apps.consolidation.services.instructions.dates import in_force
    when = in_force('يدخل هذا القانون حيز التنفيذ ابتداء من فاتح الشهر الموالي لتاريخ\nنشره بالجريدة الرسمية.')
    assert when.rule == 'after' and when.next_month


def test_a_repeal_and_replace_with_its_wording_quoted_is_a_replacement():
    # 64.12 art. 139 on 65.00 (BO 6240, 2014): «تنسخ أحكام المواد 50 (الفقرتان الثانية والثالثة) و52 … وتعوض على النحو التالي».
    ins = read('تنسخ أحكام المواد 50 (الفقرتان الثانية والثالثة) و55 من القانون رقم 65.00، وتعوض على النحو التالي :\n'
               '«المادة 50 (الفقرتان الثانية والثالثة). ـ وتحدد كيفيات تكوين هذه «الاحتياطيات.\n«ويتعين أن تودع الأموال.»\n'
               '«المادة 55. - تباشر المراقبة التقنية.»')
    assert ins.action == 'replace' and [(u.number, u.part) for u in ins.units] == [('50', ('الفقرة', [2, 3])), ('55', None)]


def test_an_article_headed_with_its_title_is_an_article_and_its_title_goes_over_it():
    # The shelf, 27 Oct 2026: Adala's nationality code (dahir 1.58.250) titles every «فصل», and the reader kept 15 of 46.
    from apps.consolidation.services import sgg
    from apps.consolidation.services.adala import _run_in
    lines = _run_in(['الفصل :1 المصادر القانونية بشأن الجنسية', 'تحدد المقتضيات المتعلقة بالجنسية المغربية بموجب القانون.',
                     'ترجح على أحكام القانون الداخلي',
                     'الفصل الثالث: الجنسية ومدونة الأسرة⟦2⟧', 'يحدد مجال تطبيق مدونة الأسرة.',
                     'المحلي : الاختصاص', 'الفصل الثامن والثلاثون', '⟦23⟧.', 'إن الدعوى ترفع لدى المحكمة.',
                     'القسم الثالث: في استرجاع الجنسية المغربية', 'الفصل 15', 'تطبق المقتضيات المقررة في الفصل الرابع عشر من هذا',
                     'القانون', 'القسم الرابع: في آثار اكتساب الجنسية', 'الفصل الواحد والأربعون: الدعوى الاعتراضية',
                     'إذا أثيرت مسألة الجنسية.'])
    text = sgg.read(['\n'.join(lines)], 'الفصل')
    assert [(a.number, a.heading_path[-1]) for a in text.articles] == [
        ('1', 'المصادر القانونية بشأن الجنسية'), ('3', 'الجنسية ومدونة الأسرة'), ('38', 'الاختصاص المحلي'),
        ('15', 'القسم الثالث: في استرجاع الجنسية المغربية'), ('41', 'الدعوى الاعتراضية')]
    assert text.articles[0].body.endswith('ترجح على أحكام القانون الداخلي')
    assert text.articles[3].body.endswith('من هذا\nالقانون')
    # A division's own «X: Y» over a heading is never taken for the article's title.
    assert _run_in(['الفرع 1: في الجرائم', 'الفصل 219', '⟦4⟧.'])[0] == 'الفرع 1: في الجرائم'
