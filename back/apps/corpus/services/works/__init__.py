"""Which text is which (rows L1 and L2 of the links review): one address per text, worked out from a citation alone.

A law, an organic law, a dahir, a decree or decree-law, and an order the SGG numbers («3259.20») are known by
their kind and their number, and the number already carries its year: «القانون رقم 66.19» is
/akn/ma/act/loi/66-19 whether its own issue has been read or not. A text cited before its issue is read waits at
that address and is filled, never doubled, when the issue arrives. Decisions (often numbered by their own body:
«88/ق/2021», «46.22») and texts with no number keep an address with their year or their issue.

A citation is matched by kind and number, never by a number alone; when two texts could answer, nothing is linked.

Its two parts, every name importable from here as before: `identity` (a text's address from its kind and number, a
citation resolved, aliases followed, a code's address) and `moves` (the rows an address keeps moved to another, twins
merged, copies folded, a waiting row).
"""
from apps.corpus.services.works.identity import (
    ALWAYS_NUMBERED, DATED, FAMILY, KIND_OF, MINISTERS, OWN_NUMBERING, PREFIX, SGG_NUMBER, SUBTYPES, _plausible, address,
    candidates, canonical, choose, code_address, code_target, fold, follow, follow_many, kind_of, ministers_order,
    number_year, numbered, orient, oriented, path_of, resolve, resolve_dated, shape_kind, text_at, uri_for)
from apps.corpus.services.works.moves import (DAHIR_NUMBER, _repath, fold_copy, fold_dahir_numbers, merge, mergeable,
                                              move, wait)
