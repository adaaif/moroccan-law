"""What the Bulletin's articles say about other texts, read in its set phrases: an amending article as instructions,
when a text takes effect, what its final provisions repeal, redirect or keep, and what its title says it does. Callers
use the package as the module it was (`from apps.consolidation.services.instructions import label_key, read`); inside
the app, each name is imported from its own module:

- labels.py      the BO's words made plain for matching, and an article's number read off its label
- amending.py    an amending article read as Instructions (modify, add, replace, repeal, words, or unclear)
- dates.py       when a text takes effect (When), and the day an amending article sets for itself
- provisions.py  the repeals, redirects and kept texts an article states (Clause), and a title's own links
"""
from apps.consolidation.services.instructions.amending import (COMPLETE, DIVISION, FINANCE, HEADING, MODIFY, NAMED,
                                                               PART_OF, PARTS, REPEAL, REPLACE, REPLACE_LATE,
                                                               REST_LINE, STAGES, WHOLE, WHOLE_KINDS, WORDS_SWAP,
                                                               WORDS_TAKE, Instructions, Unit, read, strays)
from apps.consolidation.services.instructions.dates import (AFTER, CITED, CLOSING, COUNTS, DAY_MONTH_YEAR, DAY_WORDS,
                                                            DELAY, IN_FORCE, LED, MONTH, MONTH_ENDED, MONTHS,
                                                            NEXT_MONTH, NEXT_WEEK, NTH_DAY, NTH_MONTH, NUMBERS,
                                                            PUBLICATION, SINCE, STAGED, THE_TEXT, THEN_PUBLICATION,
                                                            UNTIL, WITHIN, YEAR_OF, When, date_in, in_force,
                                                            lead_date)
from apps.consolidation.services.instructions.labels import DOTS, LABEL, TASHKEEL, label_key, number, plain
from apps.consolidation.services.instructions.provisions import (ESPECIALLY, ITEM, OBJECT, PART_AFTER, PART_BEFORE,
                                                                 REPEAL_AT, STOP, THOSE_IN, TITLE_AMENDS,
                                                                 TITLE_APPLIES, TITLE_CORRECTS, TITLE_RULES, Clause,
                                                                 clauses, title_links)

# The private name a module imported from the old module: its path keeps working.
from apps.consolidation.services.instructions.amending import _target
