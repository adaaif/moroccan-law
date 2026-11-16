"""Finding places in the law's words (PL2 of the places review, 1 Nov 2026), by code, $0.

A text is cut into words, each folded as search folds them (أ إ آ ٱ → ا, ى → ي, ة → ه, no harakat or tatweel) and kept
with where it is printed; «» " and | stay as marks. A place's name may carry و ب ل ف ك or لل in front («وبفرنسا»,
«للمغرب»), and the longest name wins («غينيا الاستوائية» before «غينيا»).

What a word next to a name says decides what the name is:
- after إقليم or عمالة it is a province or prefecture, after جهة a region, after جماعة (or «الجماعة القروية») a commune;
- a commune's name that is also a word of the language (curated.yaml: «الداخلة في» is «included in», «الجديدة» is «new»)
  counts only after a place word (مدينة، جماعة، باشوية…) or written with «بـ», and never before «في», «ضمن»;
- a state whose name is also a first name (Israel) counts only after a state word (دولة، حكومة، مع…), written with
  و، ب or ل, or in a title;
- never a street, a building or a thing named after a place («زنقة لبنان», «فندق السويد»), a person's name («مارك بن اسرائيل»), a property's name («الملك المسمى «السمارة I»», in quotes after
  المسمى، المدعو، الملك…; an amendment's quotes open its lines and hide nothing),
  a person's address («الساكن بالعيون») or where a text was signed («وحرر بالرباط»)."""
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

_DIACRITICS = re.compile('[ؐ-ًؚ-ٰٟۖ-ۭ]')
# The letters a reading prints from Persian or Maghribi keyboards («ڤ» in «كنداڤة», «ی» in «اليمنی»): inside a word, so
# that a word is never cut short into a place's name («كندا», «اليمن»), and folded to their Arabic letters.
_LETTERS = str.maketrans({'ی': 'ي', 'ې': 'ي', 'ک': 'ك', 'گ': 'ك', 'ڤ': 'ف', 'ڥ': 'ف', 'ڨ': 'ق', 'پ': 'ب', 'چ': 'ج'})
_WORD = re.compile(r'[ء-ْٰـٱیېکگڤڥڨپچ]+|[A-Za-z]+|\d+|[«»"|]')


def fold(text: str) -> str:
    """A name or a word, folded; words joined by one space, everything else dropped."""
    t = unicodedata.normalize('NFKC', text)
    t = _DIACRITICS.sub('', t).replace('ـ', '').translate(_LETTERS)
    t = re.sub('[أإآٱ]', 'ا', t).replace('ى', 'ي').replace('ة', 'ه').lower()
    return ' '.join(re.findall(r'[ء-ي]+|[a-z0-9]+', t))


@lru_cache(maxsize=500_000)
def _word(w: str) -> str:
    return w if w in '«»"|' else fold(w)


def words(text: str) -> list[tuple[str, int, int]]:
    """Each word of `text` folded, with its start and end in `text`; a mark stays as itself."""
    return [(_word(m.group(0)), m.start(), m.end()) for m in _WORD.finditer(text)]


def _f(*xs: str) -> set[str]:
    return {fold(x) for x in xs}


PROVINCE = _f('إقليم', 'عمالة')
REGION = _f('جهة')
COMMUNE = _f('جماعة', 'الجماعة', 'جماعتي', 'الحضرية', 'القروية', 'الترابية', 'البلدية', 'بلدية')
CITY = COMMUNE | PROVINCE | REGION | _f('مدينة', 'المدينة', 'مدينتي', 'باشوية', 'دائرة', 'قيادة', 'مركز', 'ميناء', 'مطار',
                                       'محكمة', 'الابتدائية', 'الاستئناف', 'التجارية', 'الإدارية', 'ولاية', 'مدن')
STATE = _f('دولة', 'حكومة', 'جمهورية', 'مملكة', 'سفارة', 'قنصلية', 'مع', 'بين', 'دولتي', 'حكومتي', 'المملكة', 'الجمهورية')
# Before 1956 the land requisitions name settlers «المسيو …», «المراة …» (BH4 of the posts-from-No.-1 review: «المسيو إيران»).
PERSON = _f('بن', 'بنت', 'ابن', 'ابنة', 'ولد', 'السيد', 'السيدة', 'ذ', 'الأستاذ', 'المسيو', 'مسيو', 'السيو', 'المستر',
            'مستر', 'مدام', 'المدام', 'المراة', 'المرأة', 'الفتاة', 'الآنسة', 'سي')
ADDRESS = _f('الساكن', 'الساكنة', 'القاطن', 'القاطنة', 'المقيم', 'المقيمة', 'الساكنين', 'القاطنين')
# Where a text was signed, and, before 1956, the Resident General's visa under every dahir and vizirial order: «اطلع عليه
# واذن بنشره الرباط في …» (8 of 100 old Moroccan mentions drawn on 6 Nov 2026 were this line, none a text about Rabat).
SIGNED = _f('حرر', 'وحرر', 'صدر', 'وصدر', 'بنشره', 'بتنشره', 'بتنفيذه', 'وجرر', 'وحرد')
VISA = _f('اذن', 'واذن', 'وأذن', 'أذن')      # «واذن بنشره الرباط في»: a misread «بنشره» («بشمره») still follows «اذن»
NAMED = _f('المسمى', 'المسماة', 'المدعو', 'المدعوة', 'المدعوين', 'المسميين', 'المعروف', 'المعروفة', 'يسميه', 'يسميها', 'يسموه')
# A property's name in quotes follows one of these; anywhere else «» are the quotes an amendment opens each line with.
PROPERTY = NAMED | _f('الملك', 'العقار', 'الملكين', 'الأملاك', 'الضيعة', 'الأرض', 'القطعة', 'باسم')
NOT_AFTER = _f('في', 'ضمن', 'تحت', 'على', 'بين', 'من')
# A street, a building or a thing named after a place is not the place («زنقة لبنان», «فندق السويد», «باسم «تطوان»»).
STREET = _f('زنقة', 'شارع', 'زقاق', 'نهج', 'درب', 'ممر', 'ساحة', 'فندق', 'إقامة', 'عمارة', 'مقهى', 'مطعم', 'باسم', 'تجزئة', 'مركب',
           'زاوية', 'ضريح', 'مسجد', 'محج', 'بطحاء', 'فناء', 'فسحة', 'أزقة', 'الأزقة', 'باب', 'حومة',
           # BH12: «بزنقتي الجابون والولايات المتحدة», «ببطحة ايطاليا», «فيلا اطاليا», «بقشلة السنغال», «بمحجة بريطانيا»
           'زنقتي', 'زنقتا', 'زقاقي', 'بطحة', 'فيلا', 'قشلة', 'محجة')
# A douar, a tribe's fraction or a tribe named after a place is not the place («بدوار وزان», «بنى عامر», «اهل افران»,
# «فرقة اولاد صالح»: the old land requisitions, BH4).
TRIBE = _f('دوار', 'الدوار', 'بني', 'بنى', 'اهل', 'أهل', 'فرقة', 'الفرقة', 'فخذة', 'فخدة', 'ايت', 'آيت', 'سيدي', 'مولاي', 'نهر')
# A name the word before makes a common phrase: «المدينة الجديدة» is the new town, not El Jadida.
# «حمى مالطة» is brucellosis; «الجناح اليمن» the right wing.
NOT_AFTER_WORD = {'الجديده': {'المدينه'}, 'مالطه': {'حمي'}, 'مالطا': {'حمي'}, 'اليمن': {'الجناح', 'الجانب', 'الضفه', 'الجهه'}}
# A name the next word makes another place: «الهند الصينية» is Indochina, not India.
# «جعل على مركز اليمن والسعادة مداره»: the old dahirs' good fortune, not Yemen (BH12).
NOT_THEN = {('الهند',): {'الصينيه', 'الصيني'}, ('اليمن',): {'والسعاده', 'والاسعاد'}}
WITH = _f('مع', 'بين')
QUOTES = {'«': '»', '"': '"'}


@lru_cache(maxsize=300_000)
def bare(word: str) -> tuple[tuple[str, str], ...]:
    """A word and what it would be without the letters that cling to its front: [(word, clitic)]."""
    out = [(word, '')]
    if word.startswith('ولل') and len(word) > 4:
        out.append(('ال' + word[3:], 'ل'))
    if word.startswith('لل') and len(word) > 3:
        out.append(('ال' + word[2:], 'ل'))
    if word[:2] in ('وب', 'ول', 'فب', 'فل', 'وك') and len(word) > 4:
        out.append((word[2:], word[1]))
    if word[:1] in ('و', 'ب', 'ل', 'ف', 'ك') and len(word) > 3:
        out.append((word[1:], word[0]))
    return tuple(out)


@lru_cache(maxsize=300_000)
def plain(word: str) -> str:
    """A word without its clinging letters, when that leaves a context word («بإقليم» → «اقليم»)."""
    for w, _ in bare(word):
        if w in CITY or w in STATE or w in PERSON or w in ADDRESS or w in NAMED or w in STREET or w in PROPERTY or w in TRIBE:
            return w
    return word


@dataclass(frozen=True)
class Found:
    slug: str
    family: str      # country, city, commune, province, region
    start: int       # where the name is printed (characters)
    end: int
    old: bool = False
    clitic: str = ''  # the letter that clings to its front («ب» in «بفرنسا»)


class Matcher:
    """Built once from places.json's rows: each family's names by their first folded word, longest first."""

    FAMILIES = ('country', 'city', 'commune', 'province', 'region')

    def __init__(self, places):
        self.index = {f: {} for f in self.FAMILIES}       # family → first word → {rest of the name: (slug, old)}
        self.size = {f: {} for f in self.FAMILIES}        # family → first word → its longest name, in words
        self.ctx = set()
        for p in places:
            kind, slug = p['kind'], p['slug']
            family = 'country' if kind == 'gone' else kind
            if p.get('ctx'):
                self.ctx.add(slug)
            needs = set(p.get('needs', ()))
            for form, old in [(f, False) for f in p['forms']] + [(f, True) for f in p.get('old', [])]:
                key = tuple(form.split())
                if not key:
                    continue
                for fam in (family, 'commune') if kind == 'city' else (family,):   # a city is also a commune after «جماعة»
                    self.index[fam].setdefault(key[0], {}).setdefault(key[1:], (slug, old, form in needs))
                    self.size[fam][key[0]] = max(self.size[fam].get(key[0], 1), len(key))
        self.starts = set().union(*(self.index[f] for f in self.FAMILIES))
        self.may = {}
        self.named_words = {v for w in NAMED for v in (w, 'و' + w, 'ب' + w)}

    def _name(self, family, ws, i):
        """The longest name of `family` starting at word i: (slug, old, size, clitic) or None."""
        n = len(ws)
        for first, clitic in bare(ws[i]):
            names = self.index[family].get(first)
            if not names:
                continue
            for size in range(min(self.size[family][first], n - i), 0, -1):
                hit = names.get(tuple(ws[i + 1:i + size]))
                if hit:
                    return hit[0], hit[1], size, clitic, hit[2]
        return None

    def _may_start(self, w: str) -> bool:
        known = self.may.get(w)
        if known is None:
            known = self.may[w] = any(v in self.starts for v, _ in bare(w))
        return known

    def find(self, text: str, title: bool = False) -> list[Found]:
        """The places `text` names, where each is printed. Words are folded first and their places in `text` read
        only when a name is found (most articles name none)."""
        ws = [_word(t) for t in _WORD.findall(text)]
        hits = self.scan(ws, title)
        if not hits:
            return []
        spans = [m.span() for m in _WORD.finditer(text)]
        return [Found(slug, family, spans[i][0], spans[i + size - 1][1], old, clitic) for i, size, slug, family, old, clitic in hits]

    # A state's spelling that needs a state word (`needs`, `ctx`) still counts in a list of states: another state named
    # with at most this many words between, numbers and table bars aside («الرأس الأخضر، الشيلي، كولومبيا», «| شيلي | 150 | … | الصومال»).
    LIST = 1

    def scan(self, ws: list[str], title: bool = False) -> list[tuple]:
        out, pending, i, n = [], [], 0, len(ws)
        quoted, quote_left, named_left = None, 0, 0
        while i < n:
            w = ws[i]
            if quoted:
                quote_left -= 1
                if w == quoted or quote_left <= 0:
                    quoted = None
                i += 1
                continue
            if w in QUOTES:
                if i and plain(ws[i - 1]) in PROPERTY:
                    quoted, quote_left = QUOTES[w], 8
                i += 1
                continue
            if w == '|':
                named_left = 0
                i += 1
                continue
            if named_left:
                named_left -= 1
                i += 1
                continue
            if not self._may_start(w):
                if w in self.named_words and i + 1 < n and ws[i + 1] not in QUOTES:   # a property's name: «المسمى …»
                    named_left = 2
                i += 1
                continue
            prev = plain(ws[i - 1]) if i else ''
            if prev in PERSON or prev in ADDRESS or prev in STREET or prev in TRIBE or (i and ws[i - 1] in SIGNED) \
                    or (i > 1 and ws[i - 2] in VISA and ws[i - 1].startswith('ب')) or prev in NOT_AFTER_WORD.get(bare(w)[-1][0], ()):
                i += 1
                continue
            if prev in PROVINCE:
                order = ('province', 'city')
            elif prev in REGION:
                order = ('region',)
            elif prev in COMMUNE:
                order = ('commune', 'city')
            else:
                order = ('country', 'city')
            hit = None
            for family in order:
                got = self._name(family, ws, i)
                if not got:
                    continue
                slug, old, size, clitic, needs = got
                if not old and not self._fits(family, slug, prev, clitic, ws, i, size, title, needs):
                    if family == 'country':
                        pending.append((i, size, slug, family, old, clitic))
                    continue
                if hit is None or size > hit[3]:
                    hit = (family, slug, old, size, clitic)
            if hit and i + hit[3] < n and any(ws[i + hit[3]] in NOT_THEN.get((b, *ws[i + 1:i + hit[3]]), ()) for b, _ in bare(ws[i])):
                hit = None
            if hit:
                family, slug, old, size, clitic = hit
                out.append((i, size, slug, family, old, clitic))
                i += size
            else:
                i += 1
        if pending:
            out = self._lists(ws, out, pending)
        return out

    def _lists(self, ws, out, pending):
        """The held states that stand in a list of states (LIST), each counted once where it is printed."""
        at, k = [], 0                                     # each token's place among the words
        for w in ws:
            at.append(k)
            k += bool(w) and w not in '«»"|' and not w.isdigit() and not w.isascii()
        taken = {j for h in out for j in range(h[0], h[0] + h[1])}
        held = [p for p in pending if not any(j in taken for j in range(p[0], p[0] + p[1]))]
        states = [h for h in out if h[3] == 'country'] + held

        def near(a, b):
            if a is b:
                return False
            first, second = (a, b) if a[0] < b[0] else (b, a)
            return at[second[0]] - at[first[0] + first[1] - 1] - 1 <= self.LIST

        # A held name beside itself is a family («محمد بن علي بيرو والتهامي بيرو»), not a list.
        kept = [p for p in held if any(near(p, h) and h[2] != p[2] for h in states)]
        return sorted(out + kept) if kept else out

    def _fits(self, family, slug, prev, clitic, ws, i, size, title, needs=False) -> bool:
        if family in ('province', 'region', 'commune') and prev in (PROVINCE | REGION | COMMUNE):
            return True
        if slug not in self.ctx and not needs:
            return True
        after = ws[i + size] if i + size < len(ws) else ''
        if family == 'country':
            # A spelling that is also a word or a man's name (`needs`) is not proved by و، ب or ل either: «باكل وبيرو» are
            # two men, «شمالا باسرائيل كياي» a neighbour; only a list of states (LIST) or a state word.
            # «مع» and «بين» prove a treaty's state, not a word's: «المتزوج … مع كوريا اوڤيست» is a wife.
            return title or (prev in STATE - WITH if needs else prev in STATE or clitic in ('و', 'ب', 'ل'))
        return (prev in CITY or clitic == 'ب') and after not in NOT_AFTER


# What a text is, read from its own title (PL5, PL17): the first rule that matches, in this order.
FOREIGN_KINDS = [
    ('studies', r'معادله|الشهادات|الدبلومات|دبلوم|تعادل'),
    ('missions', r'مساعدين بالصرف|الامرين المساعدين|البعثات|السفارات|القنصليات|سفاره|سفير|التمثيليات'),
    ('finance', r'قانون الماليه|بقانون الماليه'),
    ('loan', r'قرض|القرض|اقتراض|عقد الضمان|عقد ضمان'),
    ('treaty', r'اتفاق|معاهده|بروتوكول|مذكره تفاهم|ميثاق'),
    ('customs', r'الجمرك|جمركي|الاستيراد|التصدير|المنشا|التعريفه|الرسوم'),
    ('people', r'الجنسيه|الاجانب|الاقامه|الهجره'),
    ('transport', r'الجوي|الطيران|الملاحه|البحري|الطرقي|النقل'),
]
HOME_KINDS = [
    ('land', r'نزع|المنفعه العامه|تصميم التهيئه|تصاميم التهيئه|التحديد الاداري|التحفيظ|الغابوي|تخطيط حدود|تجزئه|الاحتلال المؤقت|'
             r'الملك العمومي|الملك الخاص'),
    ('territory', r'احداث|التقسيم|الدوائر|القيادات|الجماعات|العمالات|الاقاليم|حدود|المراكز المحدده|تغيير اسم|تسميه'),
    ('courts', r'محكمه|المحاكم|القضائي'),
    ('water', r'الماء|المياه|السقي|التطهير|الكهرباء'),
    ('schools', r'التعليم|المدارس|مدرسه|معهد|جامعه|كليه'),
    ('health', r'مستشفي|الصحه|الاستشفائي'),
    ('economy', r'الضريبه|الرسم|الميزانيه|السوق|المنطقه الحره|مناطق التسريع|الاستثمار|الموانئ|ميناء'),
]
_FOREIGN = [(k, re.compile(p)) for k, p in FOREIGN_KINDS]
_HOME = [(k, re.compile(p)) for k, p in HOME_KINDS]


def kind_of(title: str, foreign: bool) -> str:
    t = fold(title)
    return next((k for k, p in (_FOREIGN if foreign else _HOME) if p.search(t)), 'other')
