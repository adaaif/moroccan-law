"""Pictures made to be forwarded (R14 of the for-everyone review): an article, a text an editor told under a headline, or a
question and its answer, as a post (1080×1350, 4:5) or a story (1080×1920, 9:16). Most of the site will travel through
WhatsApp, Facebook and Instagram; a true card beats a screenshot of a rumour. Every card names its text, its BO issue
and page (or says the version is assembled after the amendments), keeps the people's words apart from the law's, and
ends with the address. Drawn by Pillow with raqm, like the link cards, kept by their content under CORPUS_DIR."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlparse

from django.conf import settings
from PIL import Image, ImageDraw

from apps.accounts.services.refusals import Refused
from apps.corpus.models import Consolidation, Text
from apps.corpus.services.addresses import split_path, text_path
from apps.corpus.services.cards import SPACES, STYLE, _font, _plain, mark, pill
from apps.corpus.services.codes import display_name
from apps.discussion.models import Contribution, Kind
from apps.discussion.services import anchors, counters
from apps.explain.models import Explanation
from apps.explain.services.explanations import checked

SHAPES = {'post': (1080, 1350), 'story': (1080, 1920)}
PAPER, SHEET, INK, SOFT, RULE = '#f4f2ee', '#ffffff', '#1e1b2c', '#5d586e', '#e4e0da'
STAMP, WASH, AMBER, AMBER_WASH = '#5b3a9e', '#efe9f8', '#a15c07', '#fdf3e6'
PEOPLE, PEOPLE_WASH, TALK, TALK_WASH = '#a35a00', '#fff1d9', '#126b60', '#e1f2ee'
TOPICS = {'family': '#c2417a', 'work': '#2f6fdb', 'housing': '#11806a', 'road': '#b86e00', 'consumer': '#a6338f',
          'land': '#5e7f1f', 'tax': '#8d6e00', 'health': '#c8463d', 'papers': '#0e7490', 'business': '#a0522d',
          'justice': '#3f51b5', 'digital': '#455a64'}
MONTHS = ['يناير', 'فبراير', 'مارس', 'أبريل', 'ماي', 'يونيو', 'يوليوز', 'غشت', 'شتنبر', 'أكتوبر', 'نونبر', 'دجنبر']
OUTER, PAD = 44, 64
# Letters of any words a card wraps, at most: the largest card holds about a thousand at its smallest size, and a long
# article (a table of megabytes) was wrapped whole, at six sizes, before it was cut.
FIT_MOST = 3000


# ── what a card says ───────────────────────────────────────────────────────

def _source(text: Text, page: int | None, consolidated: bool) -> dict:
    issue = text.first_published_in
    if consolidated or issue is None:
        return {'consolidated': True, 'words': 'نص بعد التعديلات · غير رسمي'}
    number = f'{issue.number} مكرر' if issue.suffix == 'bis' else str(issue.number)
    return {'consolidated': False,
            'words': f'الجريدة الرسمية {number}' + (f' · الصفحة {page}' if page else '')}


def _name(text: Text) -> str:
    return display_name(text)['ar']


def _checked(path: str, register: str) -> Explanation | None:
    return checked().filter(path=path, register=register).first()


def content(path: str = '', register: str = 'ar', answer: int | None = None) -> dict:
    """What the card holds, from an article's address, a text's, or an answer's id. Refused when the site holds none."""
    if answer:
        a = (Contribution.objects.filter(counters.published(), pk=answer, parent__isnull=False,
                                         parent__kind=Kind.QUESTION).select_related('parent', 'discussion').first())
        if a is None or not Contribution.objects.filter(counters.published(), pk=a.parent_id).exists():
            raise Refused('answer', 'not_found', 404)
        from apps.discussion.services import places

        if places.is_place(a.discussion.path):
            # A question in a topic (29 Oct 2026): its topic's name, its title and words, and the article it started
            # from when it did.
            place = places.find(a.discussion.path)
            source = {'consolidated': True, 'words': f'النقاش · {place.name["ar"]}'}
            if a.parent.about:
                try:
                    at = anchors.find(a.parent.about)
                    source = _source(at.text, at.article.printed_page,
                                     at.version.consolidation != Consolidation.AS_PUBLISHED)
                except Refused:
                    pass
            asked = ' — '.join(x for x in (a.parent.title, _plain(a.parent.body)) if x)
            return {'kind': 'answer', 'question': asked, 'answer': _plain(a.body), 'label': 'سؤال',
                    'name': place.name['ar'], 'source': source, 'link': f'{a.discussion.path}/{a.parent_id}'}
        at = anchors.find(a.discussion.path)
        return {'kind': 'answer', 'question': _plain(a.parent.body), 'answer': _plain(a.body),
                'label': at.article.label, 'name': _name(at.text),
                'source': _source(at.text, at.article.printed_page,
                                  at.version.consolidation != Consolidation.AS_PUBLISHED),
                'link': f'/discussion{a.discussion.path}'}
    uri, eid = split_path(str(path or ''))
    if eid:
        at = anchors.find(path)
        e = _checked(at.path, register)
        if e and e.article_digest and e.article_digest != anchors.digest(at.article.body):
            e = None  # the article changed since: its explanation waits for a person
        # Paragraph by paragraph (HM14): art. 53's four tiers ran into one paragraph.
        body = '\n'.join(filter(None, map(_plain, at.article.body[:FIT_MOST].split('\n'))))
        return {'kind': 'article', 'label': at.article.label, 'body': body, 'name': _name(at.text),
                'explained': {'body': e.body, 'register': e.register} if e else None,
                'source': _source(at.text, at.article.printed_page,
                                  at.version.consolidation != Consolidation.AS_PUBLISHED),
                'link': at.path}
    text = Text.objects.filter(akn_uri=uri).select_related('first_published_in').first() if path.startswith('/ma/') else None
    if text is None:
        raise Refused('path', 'not_found', 404)
    from apps.topics.services import topics
    e = _checked(text_path(text.akn_uri), register)
    issue = text.first_published_in
    version = text.latest_version()
    return {'kind': 'text', 'name': _name(text), 'title': _plain(text.title_ar),
            'headline': e.headline if e else '', 'body': e.body if e else '', 'register': e.register if e else register,
            'topic': topics.of_title(text.title_ar),
            'date': f'{issue.date.day} {MONTHS[issue.date.month - 1]} {issue.date.year}' if issue else '',
            'source': _source(text, text.first_published_page,
                              bool(version) and version.consolidation != Consolidation.AS_PUBLISHED),
            'link': text_path(text.akn_uri)}


# ── drawing ────────────────────────────────────────────────────────────────

class Pen:
    """Lines set right to left from the right edge of the sheet's column; `y` goes down as it writes."""

    def __init__(self, img: Image.Image, left: int, right: int, y: int):
        self.d, self.left, self.right, self.y = ImageDraw.Draw(img), left, right, y

    @property
    def width(self) -> int:
        return self.right - self.left

    def wrap(self, text: str, font, most: int, width: int | None = None, rtl: bool = True) -> list[str]:
        """Each paragraph (a line of `text`) from a new line, its words into lines that fit; past `most` lines, cut with «…»."""
        lines: list[str] = []
        width = width or self.width
        for paragraph in text.split('\n'):
            line = ''
            for word in SPACES.split(paragraph.strip()):
                candidate = f'{line} {word}'.strip()
                if self.d.textlength(candidate, font=font, direction='rtl' if rtl else 'ltr',
                                     language='ar' if rtl else 'fr') <= width:
                    line = candidate
                    continue
                if line:
                    lines.append(line)
                line = word
            if line:
                lines.append(line)
            if len(lines) > most:
                lines = lines[:most]
                lines[-1] += ' …'
                return lines
        return lines

    def lines(self, lines: list[str], font, fill: str, step: int, right: int | None = None, rtl: bool = True) -> None:
        for line in lines:
            if rtl:
                self.d.text((right or self.right, self.y), line, font=font, fill=fill, direction='rtl', language='ar',
                            anchor='ra')
            else:
                self.d.text((self.left, self.y), line, font=font, fill=fill, direction='ltr', language='fr',
                            anchor='la')
            self.y += step

    def pill(self, words: str, consolidated: bool) -> None:
        """The source mark, drawn as the link cards draw it (apps/corpus/services/cards.py)."""
        self.y += pill(self.d, self.right, self.y, words, consolidated)


def _frame(shape: str) -> tuple[Image.Image, Pen, int]:
    w, h = SHAPES[shape]
    img = Image.new('RGB', (w, h), PAPER)
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([OUTER, OUTER, w - OUTER, h - OUTER], radius=48, fill=SHEET)
    pen = Pen(img, OUTER + PAD, w - OUTER - PAD, OUTER + PAD)
    return img, pen, h - OUTER - PAD


def _head(pen: Pen, name: str) -> None:
    """The mark (the arch and «قانون», U15 of the Moroccan-design review: the violet tile's letters ran past it), what
    the card is about across from it."""
    y = pen.y
    left = mark(pen.d, pen.right, y, 84)
    small = _font('ReadexPro.ttf', 32, 500)
    line = pen.wrap(name, small, 1, width=left - pen.left - 40)[0]
    pen.d.text((pen.left, y + 52), line, font=small, fill=SOFT, direction='rtl', language='ar', anchor='lm')
    pen.y += 84 + 64


def _foot_top(bottom: int, note: str) -> int:
    return bottom - 34 - 44 - (56 if note else 0) - 64 - 48


def _foot(pen: Pen, c: dict, bottom: int, note: str = '') -> None:
    """The source mark, what the people's words are, the address: from the bottom up."""
    link = urlparse(settings.SITE_URL).netloc + c['link']
    pen.d.text((pen.left, bottom - 34), link, font=_font('ReadexPro.ttf', 28, 500), fill=STAMP, anchor='ls')
    pen.y = bottom - 34 - 44 - (56 if note else 0) - 64
    s = c['source']
    pen.pill(s['words'], s['consolidated'])
    if note:
        pen.y += 18
        pen.lines([note], _font('ReadexPro.ttf', 26, 400), SOFT, 40)


def _fit(pen: Pen, text: str, face: str, weight: int, sizes: list[int], lead: float, room: int, width: int,
         rtl: bool = True, most: int = 99) -> tuple:
    """The largest size at which the words fit `room` whole; else the smallest, cut with «…»."""
    text = text[:FIT_MOST]
    for size in sizes:
        font = _font(face, size, weight)
        step = int(size * lead)
        lines = pen.wrap(text, font, 999, width=width, rtl=rtl)
        if len(lines) * step <= room and len(lines) <= most:
            return font, lines, step
    font = _font(face, sizes[-1], weight)
    step = int(sizes[-1] * lead)
    return font, pen.wrap(text, font, max(1, min(most, room // step)), width=width, rtl=rtl), step


class Box:
    """People's words in their own wash, apart from the law's: «باختصار» in saffron, an answer in teal."""
    LABEL, PAD = 56, 36

    def __init__(self, pen: Pen, label: str, body: str, colour: str, wash: str, room: int, rtl: bool = True):
        self.pen, self.label, self.colour, self.wash, self.rtl = pen, label, colour, wash, rtl
        self.font, self.lines, self.step = _fit(pen, body, 'ReadexPro.ttf', 400, [40, 37, 34], 1.6,
                                                room - self.LABEL - 2 * self.PAD, pen.width - 2 * self.PAD, rtl)
        self.height = 2 * self.PAD + self.LABEL + len(self.lines) * self.step

    def draw(self) -> None:
        pen = self.pen
        top = pen.y
        pen.d.rounded_rectangle([pen.left, top, pen.right, top + self.height], radius=32, fill=self.wash)
        pen.y = top + self.PAD
        pen.lines([self.label], _font('ReadexPro.ttf', 30, 700), self.colour, self.LABEL, right=pen.right - self.PAD)
        if self.rtl:
            pen.lines(self.lines, self.font, INK, self.step, right=pen.right - self.PAD)
        else:
            left, pen.left = pen.left, pen.left + self.PAD
            pen.lines(self.lines, self.font, INK, self.step, rtl=False)
            pen.left = left
        pen.y = top + self.height


def _centre(pen: Pen, room: int, height: int) -> None:
    """What is short sits a little above the middle of the room it has, not at its top."""
    pen.y += max(0, int((room - height) * 0.4))


def draw(c: dict, shape: str) -> Image.Image:
    img, pen, bottom = _frame(shape)
    story = shape == 'story'
    told = 'الشرح كتبه الناس وراجعه مراجع، وليس نص القانون'
    if c['kind'] == 'article':
        note = told if c['explained'] else ''
        _head(pen, c['name'])
        room = _foot_top(bottom, note) - pen.y
        box = None
        if c['explained']:
            e = c['explained']
            box = Box(pen, 'باختصار', e['body'], PEOPLE, PEOPLE_WASH, int(room * (0.5 if story else 0.45)),
                      rtl=e['register'] != 'fr')
        label = 104
        law_room = room - label - (box.height + 32 if box else 0)
        law, lines, step = _fit(pen, c['body'], 'MarkaziText.ttf', 500, [72, 64, 58, 52, 48, 44], 1.62, law_room,
                                pen.width - 36)
        _centre(pen, room, label + len(lines) * step + (box.height + 32 if box else 0))
        pen.lines([c['label']], _font('MarkaziText.ttf', 72, 700), STAMP, label)
        top = pen.y
        pen.lines(lines, law, INK, step, right=pen.right - 36)
        pen.d.rounded_rectangle([pen.right - 6, top + 8, pen.right, pen.y - step // 3], radius=3, fill='#c9b8ec')
        if box:
            pen.y += 32
            box.draw()
        _foot(pen, c, bottom, note)
    elif c['kind'] == 'text':
        note = told if c['body'] else ''
        _head(pen, c['topic']['name']['ar'] if c.get('topic') else 'من الجريدة الرسمية')
        if c['topic']:
            pen.d.rectangle([pen.right - 120, pen.y - 30, pen.right, pen.y - 22], fill=TOPICS.get(c['topic']['slug'], STAMP))
        room = _foot_top(bottom, note) - pen.y
        rtl = c['register'] != 'fr'
        # Its headline, else what people call it; the title as printed under it, unless that is what heads it.
        heading = c['headline'] or c['name']
        big, heads, hstep = _fit(pen, heading, 'ReadexPro.ttf', 700, [72, 64, 58, 52], 1.36, int(room * 0.42),
                                 pen.width, most=6)
        title = _font('MarkaziText.ttf', 36, 500)
        titles = pen.wrap(c['title'], title, 2 if c['body'] else 4) if heading != c['title'] else []
        date = 48 if c['date'] else 0
        body_room = room - len(heads) * hstep - 28 - len(titles) * 52 - date - 28
        body, lines, bstep = (_fit(pen, c['body'], 'ReadexPro.ttf', 400, [46, 42, 38, 35], 1.62, body_room, pen.width, rtl)
                              if c['body'] else (None, [], 0))
        _centre(pen, room, len(heads) * hstep + 28 + len(lines) * bstep + 28 + len(titles) * 52 + date)
        pen.lines(heads, big, INK, hstep)
        pen.y += 28
        pen.lines(lines, body, INK, bstep, rtl=rtl)
        pen.y += 28
        pen.lines(titles, title, SOFT, 52)
        if c['date']:
            pen.lines([f"نُشر في {c['date']}"], _font('ReadexPro.ttf', 30, 400), SOFT, 48)
        _foot(pen, c, bottom, note)
    else:
        note = 'جواب من أحد القراء، وليس استشارة قانونية'
        _head(pen, f"{c['name']} · {c['label']}")
        room = _foot_top(bottom, note) - pen.y
        q, lines, qstep = _fit(pen, c['question'], 'ReadexPro.ttf', 600, [56, 50, 46, 42], 1.45, int(room * 0.36),
                               pen.width, most=6)
        ask = 56 + len(lines) * qstep + 32
        box = Box(pen, 'جواب', c['answer'], TALK, TALK_WASH, room - ask)
        _centre(pen, room, ask + box.height)
        pen.lines(['سؤال'], _font('ReadexPro.ttf', 32, 700), TALK, 56)
        pen.lines(lines, q, INK, qstep)
        pen.y += 32
        box.draw()
        _foot(pen, c, bottom, note)
    return img


def picture(shape: str, c: dict, request=None) -> Path:
    """The card's file for what `content` found, drawn the first time and again whenever what it holds changes, under
    the drawing limits (config/drawing.py: raises Busy), in a folder whose size is kept."""
    from config import drawing

    key = hashlib.sha1(json.dumps([STYLE, shape, c, settings.SITE_URL], ensure_ascii=False, sort_keys=True).encode(), usedforsecurity=False).hexdigest()
    out = Path(settings.CORPUS_DIR) / 'cards' / 'share' / f'{key}.png'
    return drawing.picture(out, lambda part: draw(c, shape).save(part, optimize=True), request)
