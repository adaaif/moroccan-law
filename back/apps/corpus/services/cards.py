"""A link's picture (WhatsApp, Facebook, X): 1200×630 on the app's paper, the mark (the arch and «قانون»), the
article's label and its words in Markazi Text cut at a sentence's end, the text's name, and the source as the app
shows it: the BO issue and page, or «نص بعد التعديلات · غير رسمي» (U15 of the Moroccan-design review). Drawn by
Pillow with raqm (Arabic shaped and set right to left), kept under CORPUS_DIR/cards, redrawn when the text changes.
The mark and the source pill are shared with the pictures made to be forwarded (apps/explain/services/cards.py)."""
import hashlib
import math
import re
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

from apps.corpus.models import Article, Consolidation, Text

W, H = 1200, 630
MARGIN = 72
FONTS = Path(__file__).resolve().parent.parent / 'fonts'
# The web's tokens (web/src/shared/design/app.css): the paper, the ink, the violet, the amber of a consolidation.
PAPER, INK, INK_SOFT, STAMP, WASH, RULE = '#f4f2ee', '#1e1b2c', '#5d586e', '#5b3a9e', '#efe9f8', '#e4e0da'
AMBER, AMBER_WASH = '#a15c07', '#fdf3e6'
BODY_MOST = 3000   # letters of an article a link's picture reads at most
# Version of the drawing, in every card's key: a change here draws the cards again.
# 9 Nov 2026: the wordmark; 'logo1-site' (8 Nov: the address), 'logo1' (4 Nov: the arch), 'u15' before.
STYLE = 'wordmark1'


def _font(name: str, size: int, weight: int) -> ImageFont.FreeTypeFont:
    font = ImageFont.truetype(str(FONTS / name), size, layout_engine=ImageFont.Layout.RAQM)
    # Every axis at its default but the weight (Readex Pro also has HEXP, its letter spacing).
    axes = [weight if b'eight' in bytes(a['name']) else a['default'] for a in font.get_variation_axes()]
    font.set_variation_by_axes(axes)
    return font


def arch_points(right: float, top: float, height: float, foot: float = 132) -> list[tuple[float, float]]:
    """The horseshoe arch of web/src/features/topics/Arch.tsx (120 × 132 grid: jambs at 16 and 104, the circle's centre
    at (60, 58), radius 48), `height` tall, its right edge at `right`; `foot` lengthens the jambs (a solid arch stands
    taller, as the app icon's does, or it reads as a keyhole)."""
    k = height / (foot - 10)
    left = right - 88 * k
    at = lambda gx, gy: (left + (gx - 16) * k, top + (gy - 10) * k)
    start, end = math.atan2(19.2, -44), math.atan2(19.2, 44) + 2 * math.pi   # over the top, in screen angles
    arc = [at(60 + 48 * math.cos(a), 58 + 48 * math.sin(a))
           for a in (start + (end - start) * i / 48 for i in range(49))]
    return [at(16, foot), *arc, at(104, foot)]


def smooth_polygon(d: ImageDraw.ImageDraw, points: list[tuple[float, float]], fill: str, scale: int = 4) -> None:
    """A polygon with smooth edges (Pillow's own has none): drawn four times as large on a mask, then reduced."""
    x0, y0 = math.floor(min(x for x, _ in points)), math.floor(min(y for _, y in points))
    x1, y1 = math.ceil(max(x for x, _ in points)), math.ceil(max(y for _, y in points))
    mask = Image.new('L', ((x1 - x0) * scale, (y1 - y0) * scale), 0)
    ImageDraw.Draw(mask).polygon([((x - x0) * scale, (y - y0) * scale) for x, y in points], fill=255)
    d.bitmap((x0, y0), mask.resize((x1 - x0, y1 - y0), Image.LANCZOS), fill=fill)


def mark(d: ImageDraw.ImageDraw, right: int, top: int, height: int, words: bool = True) -> int:
    """The logo: the wordmark «قانون المغرب» in violet, `height` tall from `top`, its right edge at `right` (9 Nov
    2026, apps/corpus/services/wordmark.py; the arch and «ق» with «قانون» before), and the address people type beside it,
    on its foot (8 Nov 2026: a forwarded preview says where «قانون» is). Gives its left edge."""
    from apps.corpus.services import wordmark
    drawn = wordmark.mask(height)
    left = right - drawn.width
    d.bitmap((left, top), drawn, fill=STAMP)
    if not words:
        return left
    from apps.accounts.services.mail import site
    gap, font = round(height * 0.3), _font('ReadexPro.ttf', round(height * 0.36), 500)
    d.text((left - gap, top + height), site(), font=font, fill=INK_SOFT, anchor='rd')
    return int(left - gap - d.textlength(site(), font=font))


def pill(d: ImageDraw.ImageDraw, right: int, y: int, words: str, consolidated: bool, size: int = 29) -> int:
    """The source mark as the app draws it: a tick in violet for the BO as printed, an amber ↻ for a text assembled
    after its amendments, in a rounded pill. Gives its height."""
    font = _font('ReadexPro.ttf', size, 500)
    fill, wash = (AMBER, AMBER_WASH) if consolidated else (STAMP, WASH)
    w = int(d.textlength(words, font=font, direction='rtl', language='ar'))
    h, icon = round(size * 2.2), round(size * 1.03)
    d.rounded_rectangle([right - w - icon - 64, y, right, y + h], radius=h // 2, fill=wash)
    cx, cy = right - 26 - icon // 2, y + h // 2
    if consolidated:
        d.arc([cx - 12, cy - 12, cx + 12, cy + 12], start=40, end=330, fill=fill, width=4)
        d.polygon([(cx + 13, cy - 16), (cx + 13, cy - 3), (cx + 2, cy - 7)], fill=fill)
    else:
        d.line([(cx - 11, cy + 1), (cx - 3, cy + 9), (cx + 12, cy - 9)], fill=fill, width=5, joint='curve')
    d.text((right - 26 - icon - 12, cy), words, font=font, fill=fill, direction='rtl', language='ar', anchor='rm')
    return h


def source_words(text: Text, page: int | None, consolidated: bool) -> tuple[str, bool]:
    """What the pill says, as the app's source mark says it."""
    issue = text.first_published_in
    if consolidated or issue is None:
        return 'نص بعد التعديلات · غير رسمي', True
    number = f'{issue.number} مكرر' if issue.suffix == 'bis' else str(issue.number)
    return f'الجريدة الرسمية {number}' + (f' · الصفحة {page}' if page else ''), False


def _lines(draw: ImageDraw.ImageDraw, text: str, font, width: int, most: int) -> list[str]:
    """Words into lines that fit `width`, at most `most` of them. Cut, it ends at the last sentence's end it holds
    (a full stop, «؛» or «:») when that keeps two lines; else at a word, with «…»."""
    words, lines, line = SPACES.split(text.strip()), [], ''
    for word in words:
        candidate = f'{line} {word}'.strip()
        if draw.textlength(candidate, font=font, direction='rtl', language='ar') <= width:
            line = candidate
            continue
        lines.append(line)
        line = word
        if len(lines) == most:
            break
    else:
        if line:
            lines.append(line)
        return lines[:most]
    for i in range(len(lines) - 1, 0, -1):
        end = max(lines[i].rfind(c) for c in '.؛:')
        if end > 0:
            return lines[:i] + [lines[i][:end + 1]]
    lines[-1] = lines[-1] + ' …'
    return lines


def articles_ar(n: int) -> str:
    """«مادة واحدة», «مادتان», «3 مواد», «11 مادة»."""
    return {1: 'مادة واحدة', 2: 'مادتان'}.get(n) or (f'{n} مواد' if 3 <= n <= 10 else f'{n} مادة')


# A number whose groups a space parts («40 000») is drawn right to left group by group, «000 40» (HM14 of
# the hard-moment review); a no-break space is a number's own separator and keeps it whole. Drawn so, never stored so.
GROUPS = re.compile(r'(?<![\d.,])\d{1,3}(?: \d{3})+(?!\d)')
SPACES = re.compile(r'[^\S\u00a0]+')      # a line's spaces, not a number's


def held(text: str) -> str:
    return GROUPS.sub(lambda m: m.group(0).replace(' ', '\u00a0'), text)


def _plain(body: str) -> str:
    return held(re.sub(r'\s+', ' ', re.sub(r'\*\*|\||-{3,}', ' ', body)).strip())


def draw_card(text: Text, article: Article | None) -> Image.Image:
    from apps.corpus.services.codes import display_name

    img = Image.new('RGB', (W, H), PAPER)
    d = ImageDraw.Draw(img)
    right = W - MARGIN
    rtl = {'direction': 'rtl', 'language': 'ar', 'anchor': 'ra'}
    left_of_mark = mark(d, right, 48, 66)
    if article:  # an article's card names its text across from the mark; a text's card is its own title
        small = _font('ReadexPro.ttf', 28, 500)
        named = _lines(d, display_name(text)['ar'], small, left_of_mark - MARGIN - 40, 1)[0]
        d.text((MARGIN, 82), named, font=small, fill=INK_SOFT, direction='rtl', language='ar', anchor='lm')
    y = 158
    version = text.latest_version()
    consolidated = bool(version) and version.consolidation != Consolidation.AS_PUBLISHED
    if article:
        d.text((right, y), article.label, font=_font('MarkaziText.ttf', 62, 700), fill=STAMP, **rtl)
        y += 92
        body = _font('MarkaziText.ttf', 42, 500)
        # Four lines hold a few hundred letters: the rest of a long article (a table of megabytes) is never read.
        lines = _lines(d, _plain(article.body[:BODY_MOST]), body, W - 2 * MARGIN - 24, 4)
        top = y
        for line in lines:
            d.text((right - 24, y), line, font=body, fill=INK, **rtl)
            y += 62
        d.rounded_rectangle([right - 5, top + 10, right, y - 16], radius=3, fill='#c9b9ee')
        words, again = source_words(text, article.printed_page, consolidated)
    else:
        short = len(text.title_ar) <= 70
        title = _font('MarkaziText.ttf', 64 if short else 50, 600)
        for line in _lines(d, _plain(text.title_ar), title, W - 2 * MARGIN, 3):
            d.text((right, y), line, font=title, fill=INK, **rtl)
            y += 86 if short else 68
        count = version.articles.count() if version else 0
        if count:
            d.text((right, y + 14), articles_ar(count), font=_font('ReadexPro.ttf', 30, 400), fill=INK_SOFT, **rtl)
        words, again = source_words(text, text.first_published_page, consolidated)
    pill(d, right, H - 48 - 64, words, again)
    return img


def card_path(text: Text, article: Article | None, request=None) -> Path:
    """The card's file, drawn the first time it is asked for and again whenever the text or the drawing changes, under
    the drawing limits (config/drawing.py: raises Busy), in a folder whose size is kept."""
    from config import drawing

    key = f'{STYLE}|{text.akn_uri}|{article.eid if article else ""}|{text.updated_at.isoformat()}'
    out = Path(settings.CORPUS_DIR) / 'cards' / f'{hashlib.sha1(key.encode(), usedforsecurity=False).hexdigest()}.png'
    return drawing.picture(out, lambda part: draw_card(text, article).save(part, optimize=True), request)
