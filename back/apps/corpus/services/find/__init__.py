"""What a reader writes to name a text, read on the server (W1 and W3–W6 of the library-search review, 10 Nov 2026). The
library's box and the header's box both ask here, so they read
alike. Exact lookups only, in a fixed number of queries, never a word search:

- a text's number wherever it stands in what was pasted (`ma_law`'s reader), the law before the dahir that
  promulgates it; an article of a text by its name, short form or number;
- a short form («ق.م.م»), a name a text had or has elsewhere («مدونة الأحوال الشخصية», «قانون العقوبات»), a code or
  core law by any of its names, a law by the words of its title;
- a text by its kind and the day it was signed, in either calendar («ظهير 2 أكتوبر 1984», «ظهير 9 رمضان 1331»), or
  by its kind, a year and a word; a finance law by its year, a bill never read as the law.

Each answer says whether it is sure: «فتح» opens a sure first answer only (W1). The server sends no sentence: codes and
data the web words in both languages. Issues, their pages and days alone are read in the browser from the issue map.

Its parts, every name importable from here as before: `typed` (what was typed, read as words, a kind, a day;
`spelled`), `kept` (the books' names and the laws' titles kept for a generation of the corpus) and `query` (`find`).
"""
from apps.corpus.services.find.typed import (
    _ABOUT, _BIS, _FIGURES, _KINDS, _LETTER, _MONTH, _MONTHS, _STOP, _WORDED, gregorian, kind_of, spelled, stem, stems,
    title_stems, words)
from apps.corpus.services.find.kept import _AMENDS, _KEPT, LAWLIKE, _address, _books, _cited, _kept, _laws, _titled
from apps.corpus.services.find.query import (
    _BILL, _CONSTITUTION, _FINANCE, _FINANCE_TITLE, _FRENCH_REF, _LATIN, _LETTERS, _NEWEST, _PROMULGATES, _YEAR, ANY_DAY,
    DATED, MOST, _answers, _finance, find)
