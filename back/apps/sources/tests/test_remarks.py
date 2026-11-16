"""The reading model's remarks out of what readers see (FX5 of the mended-Bulletin review). Cases from the Bulletin."""
from apps.sources.services import remarks
from apps.sources.services.issue import clean_reading

NOTICE = ('وصرح طالب التسجيل بان ليس فى علمه على الملك المذكور ادنى تحمل\nاو حق عقاري حالي او طاري.\n\n'
          'وانه يملكه بمقتضى خمسة رسوم منها اربعة مثبتة الاول بتاريخ اوائل شعبان 1320 موافق 28 يوليو 1911 '
          'والثاني في 14 رمضان 1328 باعوا له الملك المذكور\n\n'
          'المحافظ على الاملاك العقارية بمكناس بالنيابة صاليل')


def test_a_note_on_method_goes():
    text = 'ظهير شريف\n\nNote: the table below is transcribed as printed, columns from right to left.\n\n| 1 | 2 |'
    assert remarks.strip(text) == 'ظهير شريف\n\n| 1 | 2 |'


def test_a_note_that_words_are_missing_leaves_a_mark():
    text = 'الفصل الأول\n\n*Note: the remaining rows of this page are not legible at this resolution.*'
    assert remarks.strip(text) == 'الفصل الأول\n\n[…]'
    assert remarks.strip('السطر\n\nملاحظة: بعض الكلمات غير واضحة في الصورة.') == 'السطر\n\n[…]'
    assert remarks.strip('مساحتها (غير مقروء) هكتار') == 'مساحتها […] هكتار'


def test_what_stands_for_something_printed_stays():
    chart = '[Chart: 60%, 50%, 40% axis. Categories from right to left: مرضية جدا; مرضية]'
    assert remarks.strip(chart) == chart
    assert remarks.strip('وحرر بالرباط\n\n[signature]') == 'وحرر بالرباط\n\n[signature]'


def test_french_law_keeps_its_own_notes():
    text = 'Article 3. — Le présent arrêté entre en vigueur.\n\nNote : le texte est publié au Bulletin officiel.'
    assert remarks.strip(text) == text


def test_the_masthead_keeps_its_words():
    assert remarks.strip('[Logo: الجريدة الرسمية للدولة المغربية]\n\nعدد 1002') == 'الجريدة الرسمية للدولة المغربية\n\nعدد 1002'
    assert remarks.strip('البلاغ الرسمي (title logo rendered as stylized calligraphy)\nللدولة المغربية') == \
        'البلاغ الرسمي\nللدولة المغربية'


def test_a_retry_takes_the_failed_attempt_with_it():
    text = ('مطلب عدد 36\n\n' + NOTICE + '\n\nوانه يملكه بقتضى خمسة رسوم منها اربعة مبتة الاول بتاريخ\n'
            'اوائل شعباeffective...\n\nLet me redo this carefully.\n\n'
            'وانه يملكه بمقتضى خمسة رسوم منها اربعة مثبتة الاول بتاريخ اوائل شعبان 1320 موافق 28 يوليو 1911\n\nمطلب عدد 37')
    out = remarks.strip(text)
    assert 'effective' not in out and 'Let me' not in out
    assert out.startswith('مطلب عدد 36\n\n' + NOTICE)       # the notice above, repeated only by formula, stays
    assert out.endswith('مطلب عدد 37')


def test_a_header_put_right_by_a_retry():
    text = ('الجريدة الرسمية عدد 4440 - 8 شعبان 1417 (19 दिसمبر 1996) 2808\n\n'
            'Correction: the header reads "19 ديسمبر 1996".\n\n'
            'الجريدة الرسمية عدد 4440 - 8 شعبان 1417 (19 ديسمبر 1996) 2808\n\nم. 23 - الصيد البحري')
    assert remarks.strip(text) == 'الجريدة الرسمية عدد 4440 - 8 شعبان 1417 (19 ديسمبر 1996) 2808\n\nم. 23 - الصيد البحري'


def test_a_retry_that_repeats_nothing_takes_only_its_own_line():
    text = 'الفصل الأول\n\nيأذن جنابنا الشريف\n\nLet me transcribe carefully.\n\nالفصل الثاني\n\nيحرر رسم المعاوضة'
    counts = remarks.found(text)
    assert remarks.strip(text) == 'الفصل الأول\n\nيأذن جنابنا الشريف\n\nالفصل الثاني\n\nيحرر رسم المعاوضة'
    assert counts['retry-line'] == 1 and counts['retry-unsure'] == 1 and not counts['retry']


def test_cleaning_twice_changes_nothing_more():
    text = ('عدد 610\n\n(title in decorative calligraphy: الجريدة الرسمية — rendered as displayed)\n\n'
            'Note: the table is reproduced below in full.\n\n| 1 | 2 |')
    once = remarks.strip(text)
    assert once == 'عدد 610\n\n| 1 | 2 |'
    assert remarks.strip(once) == once


def test_clean_reading_takes_remarks_out():
    assert clean_reading('ظهير شريف\n\nLet me transcribe carefully.\n\nالحمد لله وحده') == 'ظهير شريف\n\nالحمد لله وحده'


def test_found_names_what_would_go():
    counts = remarks.found('نص\n\nNote: the table above has columns from right to left.\n\n[Logo: الجريدة الرسمية]')
    assert counts['note'] == 1 and counts['logo'] == 1
    assert not remarks.found('ظهير شريف يتعلق بالكيف')


def test_a_correction_line_without_its_colon_goes_too():
    text = '| 1 | 2 |\n\nCorrection to the full table below.\n\n| 1 | 2 |\n| 3 | 4 |'
    assert remarks.strip(text) == '| 1 | 2 |\n| 3 | 4 |'
