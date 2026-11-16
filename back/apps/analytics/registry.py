"""What the site measures (the analytics review, 15 Nov 2026): tasks, never people. Every event a browser may send is
declared here, with the question it answers, the decision it serves, its category, who renews it and the day it ends.
The door (services/record.py) refuses any other name, and any property this file does not list for that name.

A property is one of four kinds, each bounded: a few fixed words (`Choice`), yes or no (`Bool`), a number in bands
(`Number`, rounded to its step) and a short string held to a strict pattern (`Pattern`: a host, an error's name, a
place in a built file, an endpoint). There is no other kind, so no free text reaches the table and nothing a reader
typed can.

The categories are the first two of the data categories Firefox's makers review every measure by: technical data (how
the site performs) and interaction data (what is used on it). Nothing of the later ones (what people store or write,
anything sensitive) is measured.

A measure stops on its `expires` day: past it, a test fails until someone renews it (a new date, because its question
is still asked) or removes it. That is how the list stays short. `manage.py write_measure_types` writes this file's
names and rules for the web (web/src/shared/analytics/measures.ts)."""
import math
import re
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings

TECHNICAL = 'technical'
INTERACTION = 'interaction'
CATEGORIES = (TECHNICAL, INTERACTION)

# Who renews or removes a measure: whoever runs the site (a role, not a person's name: the code names nobody).
OWNER = 'operator'
# Six months from the day the measures were declared.
EXPIRES = '2027-05-16'

# The kinds of page an event is shown on, from the web's routes (web/src/app/App.tsx, topics/kit/TopicArea.tsx):
#   home      /
#   law       /ma/<text>, /constitution, /texts/<id>
#   article   /ma/<text>/art_<n>
#   issue     /bo/<edition>/<number> (and its quality page), /pages/<document>/<index> (a printed page)
#   library   /library, /codes, /bo, /new, /places, /words, /words/<slug>
#   budget    /budget, /budget/<year>
#   search    /search
#   topic     /topics, /topics/<slug> and its pages, checklists, reform and changes, /situations
#   journey   /topics/<slug>/journeys/<key>
#   tool      /topics/<slug>/tools/<key>
#   blog      /blog
#   post      /blog/<slug>
#   talk      /discussion, /talk, /questions, /people/<username>, /explain
#   account   /me, /saved, /account, /login, /register, /forgot, /reset, /connect, /auth/google, /letters/stop, and the
#             reviewers' desks (/review, /topics/<slug>/review)
#   page      /about, /data, /rules, /privacy, /corrections, /check, /ai
#   embed     /embed/… (an article in another site's frame)
#   other     an address the app does not know
KINDS = ('home', 'law', 'article', 'issue', 'library', 'budget', 'search', 'topic', 'journey', 'tool', 'blog', 'post',
         'talk', 'account', 'page', 'embed', 'other')
LANGS = ('ar', 'fr')
SCREENS = ('phone', 'tablet', 'desk')        # the browser's width: under 640 px, under 1024 px, wider


class Choice:
    """One of a few fixed words."""

    def __init__(self, *values: str):
        self.values = values

    def valid(self, value) -> bool:
        return isinstance(value, str) and value in self.values

    def clean(self, value):
        return value

    def ts(self) -> str:
        return ' | '.join(quoted(v) for v in self.values)

    def rule(self) -> dict:
        return {'type': 'choice', 'values': list(self.values)}


class Bool:
    """Yes or no."""

    def valid(self, value) -> bool:
        return isinstance(value, bool)

    def clean(self, value):
        return value

    def ts(self) -> str:
        return 'boolean'

    def rule(self) -> dict:
        return {'type': 'bool'}


class Number:
    """A number in bands: from `lo` to `hi`, kept rounded to `step` (a load time to 50 ms), so no exact figure can
    single out one device."""

    def __init__(self, lo, hi, step):
        self.lo, self.hi, self.step = lo, hi, step
        self._step = Decimal(str(step))
        self._whole = self._step == self._step.to_integral_value()

    def valid(self, value) -> bool:
        return (isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
                and self.lo <= value <= self.hi)

    def clean(self, value):
        """The nearest band, a half going up (in decimals, so 0.125 is 0.13 as it reads)."""
        steps = (Decimal(repr(value)) / self._step).quantize(Decimal(1), rounding=ROUND_HALF_UP)
        banded = min(Decimal(str(self.hi)), max(Decimal(str(self.lo)), steps * self._step))
        return int(banded) if self._whole else float(banded)

    def ts(self) -> str:
        return 'number'

    def rule(self) -> dict:
        return {'type': 'number', 'lo': self.lo, 'hi': self.hi, 'step': self.step}


class Pattern:
    """A short string held to a pattern that leaves no room for words: `lower` lowercases it first."""

    def __init__(self, regex: str, max_len: int, lower: bool = False):
        self.regex, self.max_len, self.lower = regex, max_len, lower
        self._compiled = re.compile(regex)

    def valid(self, value) -> bool:
        return (isinstance(value, str) and 0 < len(value) <= self.max_len
                and self._compiled.fullmatch(value.lower() if self.lower else value) is not None)

    def clean(self, value):
        return value.lower() if self.lower else value

    def ts(self) -> str:
        return 'string'

    def rule(self) -> dict:
        return {'type': 'pattern', 'pattern': self.regex, 'most': self.max_len, 'lower': self.lower}


PROP_TYPES = (Choice, Bool, Number, Pattern)


@dataclass(frozen=True)
class Measure:
    question: str           # what the counts answer
    decides: str            # what is done differently with the answer
    category: str           # TECHNICAL or INTERACTION
    owner: str              # who renews or removes it
    expires: str            # the day it stops, YYYY-MM-DD
    props: dict             # property name → Choice, Bool, Number or Pattern


# A host as a browser's URL gives it (punycode for the others), lowercased.
HOST = r'^[a-z0-9-]+(\.[a-z0-9-]+)+$'
# How a reader came to a visit's first page, or to an address that leads nowhere. The browser may say it; else the
# door reads it from `ref` (services/sources.py).
SOURCE = Choice('direct', 'search', 'assistant', 'social', 'site')

MEASURES = {
    'page.shown': Measure(
        question='What is read, and how do people arrive?',
        decides='Which pages and which ways in are worked on first, and whether readers come back.',
        category=INTERACTION, owner=OWNER, expires=EXPIRES,
        props={
            'entry': Bool(),                        # the first page of a visit
            'source': SOURCE,                       # only with entry
            'ref': Pattern(HOST, 60, lower=True),   # the referring site's host alone
            # How long since this phone last opened the site, from a date kept on the phone; only with entry.
            'back': Choice('first', 'today', 'day', 'week', 'month', 'more', 'unknown'),
            # The periods this visit is the phone's first in: d(ay), w(eek), m(onth); 'x' the phone keeps nothing.
            'fresh': Choice('none', 'd', 'dw', 'dm', 'dwm', 'x'),
            'installed': Bool(),                    # opened from the installed app
        }),
    'tool.step': Measure(
        question='Which tools are finished, and where do people stop?',
        decides='Which tool is made simpler or removed, and which waits first for a reviewer.',
        category=INTERACTION, owner=OWNER, expires=EXPIRES,
        # The tool is the event's path (its page, as the topics' use counter writes it): one opening is one flow.
        props={'step': Choice('opened', 'answered', 'result', 'copied', 'shared', 'saved', 'picture', 'remind',
                              'listen', 'right', 'wrong', 'door', 'tick')}),
    'page.speed': Measure(
        question='How fast does a page come on a real phone?',
        decides='Which kind of page is made lighter first, and on which screen.',
        category=TECHNICAL, owner=OWNER, expires=EXPIRES,
        props={
            'lcp': Number(0, 60000, 50), 'inp': Number(0, 60000, 50), 'ttfb': Number(0, 60000, 50),   # ms
            'cls': Number(0, 5, 0.01),
            'net': Choice('slow-2g', '2g', '3g', '4g', ''),     # the browser's effective type; '' unknown
            'saver': Bool(),                                    # Save-Data
        }),
    'app.error': Measure(
        question='Which build broke which page?',
        decides='Whether a build is taken back, and which error is fixed first.',
        category=TECHNICAL, owner=OWNER, expires=EXPIRES,
        props={
            'error': Pattern(r'^[A-Za-z]{1,40}$', 40),          # the error's name («TypeError»), never its message
            'at': Pattern(r'^[A-Za-z0-9_./-]+:[0-9]+:[0-9]+$', 80),   # file:line:col in a built asset
        }),
    'api.failed': Measure(
        question='Which endpoint fails for readers?',
        decides='Which endpoint is fixed or made faster first.',
        category=TECHNICAL, owner=OWNER, expires=EXPIRES,
        props={
            'endpoint': Pattern(r'^/[a-z0-9_/-]+$', 60),        # the endpoint's pattern, without its own words
            'status': Number(0, 599, 1),                        # 0: no answer came
        }),
    'page.missing': Measure(
        question='Which links lead nowhere?',
        decides='Which old addresses are sent on, and which links are mended.',
        category=TECHNICAL, owner=OWNER, expires=EXPIRES,
        props={
            'source': SOURCE,                       # how the reader came to the dead address, when not from the site
            'ref': Pattern(HOST, 60, lower=True),   # the referring site's host alone
            'inside': Bool(),                       # the dead link was on one of the site's own pages
        }),
}

# page.shown's properties that only a visit's first page carries.
ENTRY_ONLY = ('source', 'back')

# An address as the app shows it, without its query or fragment (the door cuts them first).
PATH = r'^/[A-Za-z0-9_\-./]{0,199}$'
# The web build's short id.
BUILD = r'^[A-Za-z0-9]{1,8}$'
# A flow is a whole number the browser drew in memory, safe in JavaScript.
FLOW_MOST = 2**53
MOST_EVENTS = 40
MOST_BYTES = 16 * 1024


def expired(today: date) -> list[str]:
    """The measures past their day."""
    return [name for name, measure in MEASURES.items() if date.fromisoformat(measure.expires) < today]


def public() -> dict:
    """What /privacy says of the measures: how long a row is kept, and each measure's category and properties."""
    measures = [{'name': name, 'category': m.category, 'props': list(m.props)} for name, m in MEASURES.items()]
    return {'days': settings.ANALYTICS_DAYS, 'measures': measures}


def quoted(value: str) -> str:
    """A string as TypeScript writes it, in single quotes."""
    return "'" + value.replace('\\', '\\\\').replace("'", "\\'") + "'"
