"""A topic's link picture (U15 of the Moroccan-design review): 1200×630 on the paper, the mark, the topic's name and
line, its first doors in its colour, and its own arch, tall, at the far side. Drawn as the corpus's link cards are
(apps/corpus/services/cards.py), kept under CORPUS_DIR/cards/topics by what it shows."""
import hashlib
import json
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw

from apps.corpus.services.cards import H, INK, INK_SOFT, MARGIN, PAPER, STYLE, W, _font, _lines, arch_points, mark
from apps.topics.services import kit, topics

# The web's topic colours (web/src/shared/design/app.css, `--color-t-<slug>`), light.
COLOURS = {'family': '#c2417a', 'work': '#2f6fdb', 'housing': '#11806a', 'road': '#b86e00', 'consumer': '#a6338f',
           'land': '#5e7f1f', 'tax': '#8d6e00', 'health': '#c8463d', 'papers': '#0e7490', 'business': '#a0522d',
           'justice': '#3f51b5', 'digital': '#455a64'}


# The drawing's own version, in each card's key: a card drawn before a change to `draw` is drawn again.
DRAWING = 2


def _mix(colour: str, share: float) -> str:
    """`colour` at `share` over the paper, as color-mix does in the app."""
    c = [int(colour[i:i + 2], 16) for i in (1, 3, 5)]
    p = [int(PAPER[i:i + 2], 16) for i in (1, 3, 5)]
    return '#' + ''.join(f'{round(a * share + b * (1 - share)):02x}' for a, b in zip(c, p))


def content(slug: str, item: str = '') -> dict | None:
    """What a topic's card shows; with `item` («journeys/dismissed», «tools/end») that item's card (HM5 of
    the hard-moment review: a journey or a tool shared on WhatsApp previewed as the bare site): its title, its line, the topic's
    name as its one pill, in the topic's colour. None for an item not shown."""
    topic = topics.find(slug)
    if topic is None:
        return None
    hub = kit.hub(slug)
    if item:
        kind, _, key = item.partition('/')
        if kind == 'tools':
            found = next((t for t in (hub or {}).get('tools') or [] if t.get('key') == key and kit.shown(t)), None)
        elif kind in kit.KINDS:
            found = kit.page(slug, kind, key)
        else:
            found = None
        if not found or not found.get('title'):
            return None
        lead = (found.get('lead') or {}).get('ar') or topic['lead']['ar']
        return {'slug': slug, 'name': found['title']['ar'], 'lead': lead, 'doors': [topic['name']['ar']]}
    doors = [e['title']['ar'] for e in (hub or {}).get('events', [])][:3]
    return {'slug': slug, 'name': topic['name']['ar'], 'lead': topic['lead']['ar'], 'doors': doors}


def draw(c: dict) -> Image.Image:
    colour = COLOURS.get(c['slug'], '#5b3a9e')
    img = Image.new('RGB', (W, H), PAPER)
    d = ImageDraw.Draw(img)
    right = W - MARGIN
    d.polygon(arch_points(440, 132, 500), fill=_mix(colour, 0.16), outline=_mix(colour, 0.5), width=4)
    mark(d, right, 48, 66)
    rtl = {'direction': 'rtl', 'language': 'ar', 'anchor': 'ra'}
    width = right - 480
    y = 160
    # A topic's name is short; an item's or a post's title is a sentence: smaller, on three lines.
    size, rows = (78, 2) if len(c['name']) <= 24 else (58, 3)
    name = _font('ReadexPro.ttf', size, 700)
    for line in _lines(d, c['name'], name, width, rows):
        d.text((right, y), line, font=name, fill=INK, **rtl)
        y += round(size * 1.23)
    lead = _font('ReadexPro.ttf', 32, 400)
    for line in _lines(d, c['lead'], lead, width, 2):
        d.text((right, y + 6), line, font=lead, fill=INK_SOFT, **rtl)
        y += 48
    y += 34
    pill = _font('ReadexPro.ttf', 30, 600)
    x = right
    for door in c['doors']:
        w = int(d.textlength(door, font=pill, direction='rtl', language='ar')) + 48
        if x - w < 480:     # the next row, and no third
            if x == right or y > H - 170:
                break
            x, y = right, y + 74
        d.rounded_rectangle([x - w, y, x, y + 60], radius=30, fill=_mix(colour, 0.14))
        d.text((x - 24, y + 30), door, font=pill, fill=colour, direction='rtl', language='ar', anchor='rm')
        x -= w + 14
    return img


def card_path(slug: str, item: str = '') -> Path | None:
    c = content(slug, item)
    if c is None:
        return None
    return drawn(c)


def drawn(c: dict) -> Path:
    """The card's file, drawn once for what it shows (a blog post's too: apps/blog)."""
    slug = c['slug']
    key = hashlib.sha1(json.dumps([STYLE, DRAWING, c], ensure_ascii=False, sort_keys=True).encode(), usedforsecurity=False).hexdigest()
    out = Path(settings.CORPUS_DIR) / 'cards' / 'topics' / f'{slug}-{key[:16]}.png'
    if not out.exists():
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix('.tmp.png')
        draw(c).save(tmp, optimize=True)
        tmp.replace(out)
    return out
