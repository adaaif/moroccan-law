"""What an address says before an account is built on it, since sign-up opened with real letters (3 Nov 2026).

The format check alone lets two kinds of address through:

- MISSPELT providers, such as gamil.com and gpail.com. Both run a mail server: the code went to whoever squats the
  misspelling, and a reset link would hand them the account. A typed address on a misspelt provider is answered with
  the fix (`email.typo` and its `suggestion`) until the person keeps theirs (`email_confirmed`); no mail ever leaves for
  it (`mail_blocked`).
- THROWAWAY inboxes (yopmail, temp-mail's rotating domains): nobody can ever reset them. Refused (`email.disposable`).

The throwaway list is a plain file (`apps/accounts/data/`, its README says where it comes from).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'

# A provider that lives under ONE domain: «gmail.fr» does not exist.
ONE_TLD = {
    'gmail': 'gmail.com', 'googlemail': 'googlemail.com', 'icloud': 'icloud.com', 'ymail': 'ymail.com',
    'protonmail': 'protonmail.com', 'proton': 'proton.me', 'menara': 'menara.ma', 'wanadoo': 'wanadoo.fr',
    'laposte': 'laposte.net', 'free': 'free.fr', 'orange': 'orange.fr', 'sfr': 'sfr.fr',
}
# One name under many country endings: hotmail.be, outlook.nl, yahoo.es are the diaspora's real addresses.
MULTI_TLD = {'hotmail', 'outlook', 'live', 'yahoo', 'msn', 'aol', 'gmx'}
# Real look-alikes one key from a big provider: never corrected either.
REAL_NAMES = set(ONE_TLD) | MULTI_TLD | {
    'mail', 'email', 'me', 'mac', 'web', 'libero', 'yandex', 'rocketmail', 'zoho', 'tutanota', 'fastmail', 'hey',
}
# What a slip of the finger is matched against, the most common first (a tie goes to gmail). Short names (live, msn,
# aol, free…) are never fuzzy targets: too many real domains sit one letter away.
FUZZY_1 = ['gmail', 'hotmail', 'outlook', 'yahoo', 'icloud', 'googlemail', 'protonmail', 'proton',
           'menara', 'wanadoo', 'laposte', 'orange']
FUZZY_2 = {'hotmail', 'outlook', 'icloud', 'googlemail', 'protonmail'}  # long enough for two slips

# Endings that do not exist, typed for .com / .fr (.co, .cm and .om DO exist: fixed only on a known provider).
BOGUS_TLD = {'con': 'com', 'cmo': 'com', 'comm': 'com', 'coom': 'com', 'vom': 'com', 'xom': 'com',
             'ocm': 'com', 'cpm': 'com', 'clm': 'com', 'fe': 'fr', 'ff': 'fr', 'frr': 'fr'}
PROVIDER_TLD = {**BOGUS_TLD, 'co': 'com', 'cm': 'com', 'om': 'com'}
# No inbox can live there (RFC 2606 / 6761).
RESERVED_TLDS = {'test', 'example', 'invalid', 'localhost', 'local'}

# What an Arabic keyboard slips in around a Latin address: direction marks, isolates, zero-widths, the soft hyphen, BOM.
_INVISIBLE = dict.fromkeys(map(ord, '​‌‍‎‏‪‫‬‭‮'
                                    '⁦⁧⁨⁩﻿­'), None)

_format = EmailValidator()


def _dl(a: str, b: str) -> int:
    """Damerau-Levenshtein distance (optimal string alignment)."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def clean_address(raw: str | None) -> str:
    """The address as typed, minus what nobody meant to type: invisible marks, spaces, a full-width «＠», and the
    domain's punctuation (a comma or «،» where the dot goes, doubled or trailing dots). The domain is lowercased; the
    local part keeps its case (uniqueness ignores it anyway)."""
    s = (raw or '').translate(_INVISIBLE).replace('＠', '@')
    s = re.sub(r'\s+', '', s)
    if s.count('@') != 1:
        return s
    local, domain = s.split('@')
    domain = domain.lower().replace('،', '.').replace(',', '.')
    domain = re.sub(r'\.{2,}', '.', domain).strip('.')
    return f'{local}@{domain}'


def _suggest(domain: str) -> tuple[str | None, int]:
    """(the provider domain this one was meant to be, how many letters of the NAME it changes): 0 for an ending, a
    missing dot or a one-domain provider; 1 or 2 for a slip of the finger. Never a real country ending (hotmail.be), a
    real look-alike (ymail.com, mail.com) or a domain far from every provider."""
    d = (domain or '').strip().lower().strip('.')
    if not d:
        return None, 0
    if '.' not in d:                                   # «gmail», «gmailcom», «hotmailfr»
        for name in [*ONE_TLD, *sorted(MULTI_TLD)]:
            if d == name:
                return ONE_TLD.get(name, f'{name}.com'), 0
            rest = d[len(name):]
            if d.startswith(name) and rest in ('com', 'fr', 'net', 'me', 'ma'):
                return ONE_TLD.get(name, f'{name}.{rest}'), 0
        return None, 0
    name, _, tld = d.rpartition('.')
    if '.' in name:                                    # ac.ma, co.uk, a sub-domain: left alone
        return None, 0
    edits = 0
    if name in ONE_TLD:
        fix = ONE_TLD[name]
    elif name in REAL_NAMES:
        fix = f'{name}.{PROVIDER_TLD.get(tld, tld)}'
    else:
        # A distance is at least the difference in length: only names within two letters of a provider's are measured,
        # so the table is never built over a long name.
        near = [n for n in FUZZY_1 if abs(len(n) - len(name)) <= 2]
        best = min(near, key=lambda n: _dl(name, n)) if near else None
        dist = _dl(name, best) if best else 3
        if dist == 1 or (dist == 2 and best in FUZZY_2):
            fix, edits = ONE_TLD.get(best, f'{best}.{PROVIDER_TLD.get(tld, tld)}'), dist
        elif tld in BOGUS_TLD:                         # mycompany.con → mycompany.com
            fix = f'{name}.{BOGUS_TLD[tld]}'
        else:
            return None, 0
    return (fix, edits) if fix != d else (None, 0)


def _misspelt(domain: str) -> str | None:
    """The fix when a domain reads as a MISSPELT provider. One slip from a provider, a misspelling is what the person
    made; two (yopmail ↔ hotmail), a throwaway is what they chose."""
    fix, edits = _suggest(domain)
    if fix and (edits <= 1 or not is_disposable(domain)):
        return fix
    return None


def _read_list(name: str) -> set[str]:
    path = DATA_DIR / name
    if not path.exists():
        return set()
    out = set()
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.split('#', 1)[0].strip().lower()
        if line:
            out.add(line)
    return out


@lru_cache(maxsize=1)
def disposable_domains() -> frozenset[str]:
    allow = _read_list('disposable_allow.txt') | set(ONE_TLD.values())
    return frozenset((_read_list('disposable_domains.txt') | _read_list('disposable_extra.txt')) - allow)


def is_disposable(domain: str) -> bool:
    """A throwaway inbox's domain, or a sub-domain of one (x.yopmail.com)."""
    parts = (domain or '').strip().lower().strip('.').split('.')
    blocked = disposable_domains()
    return any('.'.join(parts[i:]) in blocked for i in range(len(parts) - 1))


@dataclass(frozen=True)
class Verdict:
    email: str                       # cleaned: what is stored when it passes
    code: str | None = None          # None · invalid · disposable · typo
    suggestion: str | None = None    # the corrected address, for typo


def check(raw: str | None, *, confirmed: bool = False) -> Verdict:
    """One verdict for a typed address (sign-up, a new address). `confirmed`: the person saw the suggestion and kept
    the address as typed; a misspelt-looking domain then passes (it is still sent no mail)."""
    email = clean_address(raw)
    if email.count('@') != 1:
        return Verdict(email, 'invalid')
    local, domain = email.split('@')
    if not local or not domain:
        return Verdict(email, 'invalid')
    fix = _misspelt(domain)
    if fix and not confirmed:
        return Verdict(email, 'typo', f'{local}@{fix}')
    if is_disposable(domain):
        return Verdict(email, 'disposable')
    try:
        _format(email)
    except ValidationError:
        return Verdict(email, 'invalid')
    if domain.rpartition('.')[2] in RESERVED_TLDS:
        return Verdict(email, 'invalid')
    return Verdict(email)


def mail_blocked(email: str | None) -> bool:
    """True for an address on a misspelt provider: a code or a reset link there lands in a squatter's inbox."""
    if not email or '@' not in email:
        return False
    return _misspelt(email.rsplit('@', 1)[1]) is not None


def typed_fix(raw: str | None) -> str | None:
    """The corrected address for one typed at sign-in or at «نسيت كلمة السر» on a misspelt provider
    («<name>@gmial.com» → <name>@gmail.com), else None."""
    email = clean_address(raw)
    if email.count('@') != 1:
        return None
    local, domain = email.split('@')
    fix = _misspelt(domain) if local and domain else None
    return f'{local}@{fix}' if fix else None


GMAIL = {'gmail.com', 'googlemail.com'}


def inbox(email: str | None) -> str:
    """The inbox an address reaches, for counting what is sent to it: lowercased, without a «+tag», and for Gmail
    without the dots of its name (Gmail delivers «a.b+x» at gmail.com to the inbox «ab»)."""
    email = clean_address(email).lower()
    if email.count('@') != 1:
        return email
    local, domain = email.split('@')
    local = local.split('+', 1)[0]
    if domain in GMAIL:
        local, domain = local.replace('.', ''), 'gmail.com'
    return f'{local}@{domain}'


def mask(email: str | None) -> str:
    """«ka•••@gmail.com»: where a reset link went, shown back to someone who typed that address."""
    email = (email or '').strip()
    if '@' not in email:
        return ''
    local, domain = email.rsplit('@', 1)
    keep = 1 if len(local) <= 3 else 2
    return f'{local[:keep]}•••@{domain}'
