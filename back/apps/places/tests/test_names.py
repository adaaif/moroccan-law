"""The matcher (PL2): every trap the pilot met, in the words the Bulletin prints them."""
import pytest

from apps.places.services.build import gazetteer
from apps.places.services.names import Matcher, kind_of


@pytest.fixture(scope='module')
def m():
    return Matcher(gazetteer())


def found(m, text, title=False):
    return [(f.slug, text[f.start:f.end]) for f in m.find(text, title)]


@pytest.mark.parametrize('text, places', [
    # a state, written with و، ب or ل, and the longest name first
    ('الاتفاقية بين المملكة المغربية والجمهورية الفرنسية', [('france', 'والجمهورية الفرنسية')]),
    ('للصين ولجمهورية الصين الشعبية', [('china', 'للصين'), ('china', 'ولجمهورية الصين الشعبية')]),
    ('الصادرات وللسنغال', [('senegal', 'وللسنغال')]),
    ('غينيا الاستوائية وغينيا', [('equatorial-guinea', 'غينيا الاستوائية'), ('guinea', 'وغينيا')]),
    # a word that is not a state
    ('باللغة الفرنسية والفرنك الفرنسي', []),
    ('قطر الأنبوب 20 مم ودعم مالي', []),
    ('مع دولة قطر', [('qatar', 'دولة قطر')]),
    ('سيلان المياه', []),
    # a first name is not Israel; the state is
    ('مارك بن اسرائيل', []),
    ('شلوم اسرائيل بريز', []),
    ('مكتب الاتصال بإسرائيل', [('israel', 'بإسرائيل')]),
    # a street, a hotel, a thing named after a place
    ('محمد فنجاوي 37 زنقة اليمن مكتب رقم 2', []),
    ('فندق السويد الصغيرة', []),
    ('لمجرفة بحرية معروفة باسم «تطوان»', []),
    ('زقاق بليز باسكال', []),
    # a city that is also a word
    ('الداخلة في نطاق اختصاص', []),
    ('الإصلاحات الجديدة', []),
    ('بمدينة الداخلة', [('dakhla', 'الداخلة')]),
    ('المحكمة الابتدائية بالجديدة', [('el-jadida', 'بالجديدة')]),
    # what the word before a name says
    ('إقليم تازة وجماعة تازة ومدينة طنجة', [('province-taza', 'تازة'), ('taza', 'تازة'), ('tanger', 'طنجة')]),
    ('الجماعة القروية سبت الزينات', [('sebt-azzinate', 'سبت الزينات')]),
    ('جهة فاس-مكناس', [('region-fes-meknes', 'فاس-مكناس')]),
    # where a text was signed, a person's address, a property's name
    ('وحرر بالرباط في 5 ذي الحجة', []),
    ('الساكن بالعيون ببولو', []),
    ('الملك المسمى «السمارة I» بإقليم الرحامنة', [('province-rehamna', 'الرحامنة')]),
    # without quotes, the two words after «المسمى» are the property's name
    ('الملك المسمى سطات', []),
    ('الملك المسمى روض سطات بإقليم سطات', [('province-settat', 'سطات')]),
    # an amendment opens each of its lines with «: nothing is hidden
    ('أو ما يعادلها :\n«........\n« - أوكرانيا :\n«.......', [('ukraine', 'أوكرانيا')]),
    # a town named like a man: «محمد بن أحمد» is a man, «مدينة بن أحمد» the town
    ('السيد محمد بن أحمد', []),
    ('بجماعة بن أحمد', [('ben-ahmed', 'بن أحمد')]),
    # an old name counts for the city it became
    ('بور ليوطي', [('kenitra', 'بور ليوطي')]),
    ('بالدار البيضاء', [('casablanca', 'بالدار البيضاء')]),
    ('بإقليم خريبكة', [('province-khouribga', 'خريبكة')]),
    # the Bulletin before 1956, read on every state it names (BH12 of the posts-from-No.-1 review)
    ('جعل على مركز اليمن والسعادة مداره', []),
    ('الذي مساحته ايران اثنان والمحدود جوفا', []),
    ('زيتون قرب المكتب (البيرو) لسي عبد الكبير', []),
    ('مع جمهورية بيرو', [('peru', 'بيرو')]),
    ('قبائل وزكيطة وكدميوة وكنداڤة', []),
    ('الجهة اليمنی', []),
    ('ينبغي للعامل ان يقدمها للولاة البحرين', []),
    ('من حمى مالطة', []),
    ('بقشلة السنغال وبزنقتي الجابون', []),
    ('الجمعية الوطنية للهند الصيني', []),
    ('من البرازيل وايطاليا', [('brazil', 'البرازيل'), ('italy', 'وايطاليا')]),
    # a held spelling in a list of states counts; alone, beside a man's name, it does not
    ('الكاميرون، الرأس الأخضر، الشيلي، كولومبيا', [('cameroon', 'الكاميرون'), ('cape-verde', 'الرأس الأخضر'), ('chile', 'الشيلي'),
                                                ('colombia', 'كولومبيا')]),
    ('| سيشل | 150 | 193 | | شيلي | 150 | 402 |', [('seychelles', 'سيشل'), ('chile', 'شيلي')]),
    ('على ربان الصيد كوريا ماركوس من الجنسية البرتغالية', []),
    ('محمد بن علي بيرو والتهامي بيرو', []),
    ('المتزوج بالدار البيضاء مع كوريا اوڤيست', [('casablanca', 'بالدار البيضاء')]),
    ('ترقية يحفها اليمن والاسعاد', []),
])
def test_found(m, text, places):
    assert found(m, text) == places


def test_a_title_names_a_state_without_a_state_word(m):
    assert found(m, 'اتفاق بين المملكة المغربية واسرائيل', title=True) == [('israel', 'واسرائيل')]


def test_an_empty_form_names_nothing():
    m = Matcher([{'slug': 'france', 'kind': 'country', 'forms': ['', 'فرنسا']}])
    assert found(m, 'مع فرنسا') == [('france', 'فرنسا')]


def test_the_old_name_is_marked(m):
    (f,) = m.find('فضالة')
    assert (f.slug, f.old) == ('mohammadia', True)


@pytest.mark.parametrize('title, foreign, kind', [
    ('قرار بتحديد قائمة الشهادات التي تعادل دبلوم دكتور في الطب', True, 'studies'),
    ('ظهير شريف بنشر الاتفاقية الموقعة بالرباط', True, 'treaty'),
    ('مرسوم بإعلان أن المنفعة العامة تقضي بنزع ملكية', False, 'land'),
    ('قرار بشأن شيء آخر', False, 'other'),
])
def test_kind(title, foreign, kind):
    assert kind_of(title, foreign) == kind
