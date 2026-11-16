"""A text's one address, worked out from a citation alone: its kind and number (a number read backwards put back by
its shape), a citation resolved against the texts held and the aliases that lead elsewhere, a text cited by its day,
a code's address on a day, and a minister's order known by its heading."""
import re
from datetime import date

import ma_law

from apps.corpus.models import Alias, Text


SUBTYPES = {'law': 'loi', 'organic_law': 'loi-organique', 'dahir': 'dahir', 'decree': 'decret',
            'decree_law': 'decret-loi', 'order': 'arrete', 'decision': 'decision', 'circular': 'circulaire',
            'convention': 'convention', 'other': 'texte', 'bill': 'projet-loi'}
KIND_OF = {v: k for k, v in SUBTYPES.items()}
PREFIX = '/akn/ma/act'

# The kinds a citation's word may mean, the one it names first («القانون» is a law, or an organic law the
# citation did not call one).
FAMILY = {'law': ('law', 'organic_law'), 'organic_law': ('organic_law', 'law'), 'dahir': ('dahir',),
          'decree': ('decree', 'decree_law'), 'decree_law': ('decree_law', 'decree'),
          'order': ('order',)}
ALWAYS_NUMBERED = {'law', 'organic_law', 'dahir', 'decree', 'decree_law'}
SGG_NUMBER = re.compile(r'\d{1,5}-\d{2}')        # an order's or decision's number from the SGG: 3259-20
OWN_NUMBERING = re.compile(r'[/A-Za-zء-ي]')   # «88/ق/2021», «P/EA/16.20»: a body's own numbering


def fold(number: str) -> str:
    """«013-26» → 13-26: the first group's leading zeros go (013.26 and 13.26 are one law); the year's stay (2-00)."""
    if not number:
        return ''
    head, _, rest = number.partition('-')
    head = head.lstrip('0') or '0'
    return f'{head}-{rest}' if rest else head


def numbered(kind: str, number: str, printed: str = '') -> bool:
    """Whether kind and number alone name this text."""
    if not number:
        return False
    if kind in ALWAYS_NUMBERED:
        return True
    if kind == 'order':
        return bool(SGG_NUMBER.fullmatch(fold(number))) and not OWN_NUMBERING.search(printed or '')
    # A decision's number is often its body's own (the audiovisual council's «46.22», the electricity regulator's
    # «02.26»), shaped like the SGG's: it keeps an address with its year.
    return False


def orient(number: str) -> str:
    """A number an old scan's right-to-left line gave backwards, put back when its shape alone says so (the archive
    run, 28 Oct 2026): «290.81.1» is dahir 1.81.290 (a dahir's, decree's or royal order's number opens with 1, 2 or
    3), «82.1482» order 1482.82 and «00.2» law 2.00 (the year is two digits and comes last). Two groups of two digits
    («82.24») say nothing by their shape: they stay as printed (`oriented` weighs them)."""
    parts = number.split('-')
    if not all(p.isdigit() for p in parts):
        return number
    if len(parts) == 3 and len(parts[1]) == 2 and parts[2] in ('1', '2', '3') and parts[0] not in ('1', '2', '3'):
        return '-'.join(reversed(parts))
    if len(parts) == 2 and len(parts[0]) == 2 and (len(parts[1]) in (1, 3) or
                                                   (len(parts[1]) == 4 and parts[1][:2] not in ('19', '20'))):
        return f'{parts[1]}-{parts[0]}'      # «20.2019» stays: order 2019.20, or a year printed whole
    return number


def _plausible(number: str, on) -> bool:
    """Whether a number's last group can be the year of a text signed `on`: that year or up to fifteen before (a law
    keeps its bill's number), or the next (a date misread)."""
    return (on.year % 100 - int(number.rsplit('-', 1)[1])) % 100 in (*range(16), 99)


def oriented(kind: str, own: str, listed: str, on) -> tuple[str, bool]:
    """The number a text is addressed by, from its own heading (`own`) and its contents entry (`listed`), each put
    back by `orient`; and whether it is in doubt. Two groups of two digits read in both orders («82.24» in the heading,
    «24.82» in the contents) are settled by the year each would give a text signed `on`. A number whose year cannot
    be the text's while its reverse's can is in doubt: the text gets an address by its issue, never another's."""
    if kind not in FAMILY:                  # a decision's or circular's own numbering is never turned
        return own or listed, False
    own, listed = orient(own), orient(listed)
    number = own or listed
    if kind not in ('law', 'organic_law', 'order'):
        return number, False
    pair = lambda n: len(n.split('-')) == 2 and all(len(p) == 2 for p in n.split('-'))
    reverse = lambda n: '-'.join(reversed(n.split('-')))
    if own and listed and own != listed and pair(own) and reverse(own) == listed:
        fits = [n for n in (own, listed) if _plausible(n, on)]
        return (fits[0], False) if len(fits) == 1 else ('', True)
    if pair(number) and not _plausible(number, on) and _plausible(reverse(number), on):
        return '', True
    return number, False


def address(kind: str, number: str) -> str:
    return f'{PREFIX}/{SUBTYPES.get(kind, "texte")}/{fold(number)}'


def uri_for(kind: str, number: str, printed: str = '', fallback: str = '') -> str:
    """The address a text gets: from kind and number when they name it, else `fallback` (with its year or issue)."""
    return address(kind, number) if numbered(kind, number, printed) else fallback


def kind_of(uri: str) -> str:
    parts = uri.removeprefix(PREFIX + '/').split('/')
    return KIND_OF.get(parts[0], 'other')


def follow(uri: str) -> str:
    """An address after its aliases: an old address, a merged twin or a promulgating dahir leads to the text."""
    alias = Alias.objects.filter(alias=uri).values_list('uri', flat=True).first()
    return alias or uri


def follow_many(uris) -> dict[str, str]:
    """`follow` for many addresses in one query: each address after its aliases."""
    uris = set(uris)
    found = dict(Alias.objects.filter(alias__in=uris).values_list('alias', 'uri')) if uris else {}
    return {uri: found.get(uri) or uri for uri in uris}


def shape_kind(number: str) -> str | None:
    """A number typed alone says its kind only when its shape does: 1.58.250 a dahir, 2.22.729 a decree."""
    parts = fold(number).split('-')
    if len(parts) == 3 and parts[0] == '1':
        return 'dahir'
    if len(parts) == 3 and parts[0] == '2':
        return 'decree'
    return None


def resolve(kind: str | None, number: str | None) -> tuple[str, str]:
    """(address, state) for a citation of a text by kind and number. The state is `resolved` (one address answers,
    whether or not the site holds the text yet), `ambiguous` (two texts the site holds could answer: no link) or
    `unresolved` (no kind, or a body's own numbering: no address)."""
    found = candidates(kind, number)
    if isinstance(found, str):
        return '', found
    followed = [follow(uri) for uri in found]
    return choose(followed, set(Text.objects.filter(akn_uri__in=followed).values_list('akn_uri', flat=True)))


# The kinds a text cited by its date may be (a law before 1956 is a dahir), as `citations._find_text` reads them.
DATED = {'dahir': ('dahir', 'law'), 'law': ('law', 'dahir'), 'order': ('order',), 'decree': ('decree',)}


def resolve_dated(kind: str | None, day: str | None, words: str = '') -> tuple[str, str]:
    """(address, state) for a text cited by its kind and the day it was signed («الظهير الشريف الصادر في 9 رمضان 1331
    (12 غشت 1913)», H9 of the Bulletin-from-No.-1 review): the one text the site holds of that kind and day; of several, the one
    whose title holds most of the words the citation goes on with (two at least, twice the next one's); else no link
    («ambiguous»), never a guess."""
    kinds = DATED.get(kind or '')
    try:
        on = date.fromisoformat(day or '')
    except ValueError:
        return '', 'unresolved'
    found = list(Text.objects.filter(type__in=kinds, signed_on=on).values_list('akn_uri', 'title_ar')) if kinds else []
    if not found:
        return '', 'unresolved'
    if len(found) == 1:
        return found[0][0], 'resolved'
    plain = {'ظهير', 'شريف', 'صادر', 'متعلق', 'موافق', 'قرار', 'وزير', 'بشان'}
    wanted = set(ma_law.search_terms(words[:200])) - plain
    scored = sorted(((len(wanted & set(ma_law.search_terms(title or ''))), uri) for uri, title in found), reverse=True)
    if scored[0][0] >= 2 and scored[0][0] >= 2 * scored[1][0]:
        return scored[0][1], 'resolved'
    return '', 'ambiguous'


def candidates(kind: str | None, number: str | None) -> list[str] | str:
    """The addresses a citation by kind and number may name, before their aliases; or its state when it names none."""
    if not number:
        return 'unresolved'
    number = orient(fold(number))
    kind = kind or shape_kind(number)
    if kind not in FAMILY:
        return 'unresolved'
    if kind == 'order' and not numbered(kind, number):
        return 'unresolved'
    return [address(k, number) for k in FAMILY[kind]]


def choose(followed: list[str], held: set[str]) -> tuple[str, str]:
    """`resolve`'s answer once the candidates are followed and the ones the site holds are known."""
    held = [uri for uri in dict.fromkeys(followed) if uri in held]
    if len(held) > 1:
        # The kind the citation names wins over its neighbour («القانون» over an organic law with the same number).
        first = followed[0]
        return (first, 'resolved') if first in held else ('', 'ambiguous')
    if held:
        return held[0], 'resolved'
    return followed[0], 'resolved'


def canonical(uri: str) -> str:
    """A numbered text's address as people and assistants write it, the number as the BO prints it (…/loi/07-03,
    …/loi/07.03), → the address the site gives it (…/loi/7-03): `address` drops the first group's zeros. Claude asked the
    MCP for /ma/loi/07-03 on 4 Nov 2026 and was told no such text."""
    parts = uri.removeprefix(PREFIX + '/').split('/')
    if len(parts) == 2 and KIND_OF.get(parts[0]) in FAMILY:
        return address(KIND_OF[parts[0]], parts[1].replace('.', '-'))
    return uri


def text_at(uri: str) -> tuple[Text | None, str]:
    """The text an address leads to, and the address it now has (another one when the address is an alias, or was
    written with its number's leading zeros)."""
    text = Text.objects.filter(akn_uri=uri).first()
    if text is not None:
        return text, uri
    moved = follow(uri)
    if moved == uri and (written := canonical(uri)) != uri:
        moved = follow(written)
    text = Text.objects.filter(akn_uri=moved).first() if moved != uri else None
    return (text, moved) if text is not None else (None, uri)


def code_address(code: str, on=None) -> str:
    """A code cited by its name («ق.ل.ع», «مدونة الأسرة»): the address of the text that was that code on the day `on`
    (the citing text's publication; today when not given)."""
    uri, aliased = code_target(code, on)
    return follow(uri) if aliased else uri


def code_target(code: str, on=None) -> tuple[str, bool]:
    """`code_address` before its aliases: the address, and whether it is still to be followed."""
    from apps.corpus.services.codes import CODE_BEFORE, CODE_TEXTS, CODE_URIS
    for until, older in CODE_BEFORE.get(code, []) if on is not None else []:
        if str(on) < until:
            return address(*older), True
    if code in CODE_URIS:
        return CODE_URIS[code], False
    if code in CODE_TEXTS:
        kind, number = CODE_TEXTS[code]
        if on is not None and str(on)[:4] < number_year(number):
            # Cited before its own number's year, the name meant another text (a 1980 order's «قانون المسطرة
            # الجنائية» is the 1959 code, not law 22.01): no address rather than today's code (28 Oct 2026).
            return '', False
        return address(kind, number), True
    return '', False


def number_year(number: str) -> str:
    """The year a number carries, as four digits: law 22-01 → 2001, dahir 1-59-413 → 1959; '' when it carries none."""
    parts = number.split('-')
    yy = parts[1] if len(parts) == 3 else parts[-1] if len(parts) == 2 else ''
    if len(yy) != 2 or not yy.isdigit():
        return ''
    return ('19' if int(yy) >= 56 else '20') + yy


def path_of(uri: str) -> str:
    return '/ma' + uri.removeprefix(PREFIX)


def ministers_order(title: str, printed: str) -> bool:
    """A minister's order by its heading and its SGG number («قرار لوزير التجهيز … رقم 1234.20»): the model files
    many as decisions (14,422 on 20 Oct 2026), so citations of «القرار رقم 1234.20» found nothing at /arrete/1234-20."""
    return bool(MINISTERS.match((title or '').strip()) and re.fullmatch(r'\d{1,5}\.\d{2}', (printed or '').strip()))


MINISTERS = re.compile(r'^قرار\s+(?:مشترك|لوزير|للوزير|لوزيرة|للوزيرة|لرئيس الحكومة|لكاتب الدولة|لكاتبة الدولة)')
