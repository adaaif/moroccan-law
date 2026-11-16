"""The links pipeline (rows L3–L10 of the links review; row 19 before it). For the texts given, by code:

1. read   every article of the text as published: the changes it makes to other texts (Change, «reading»), what it
          says of them without changing them (Mention: citations, «بتطبيق», redirected references, kept decrees,
          corrections, court rulings), and when each change takes effect (the article's own date, else the text's);
2. weigh  each change against its witnesses: the title's formula, the model's own list (texts.json), the SGG's
          notes, Adala's footnotes, the SGG's or Adala's later wording. The state follows: checked, confirmed, read,
          conflict or unclear;
3. apply  each changed text rebuilt in the order its changes take effect, into versions «consolidated by machine»
          dated by that day: one amending text's changes all or none, never a conflict or an unclear one;
4. stand  each text's status (in force, partly repealed, repealed, not yet in force) from its changes and dates.

Rows are kept by address, so texts can be read in any order: a change waits for the text it changes, and is applied
when that text arrives. What cannot be settled becomes a Doubt for a person. Nothing is guessed.

Callers use the package as the module it was (`engine.run(…)`, `engine.standing(…)`); inside the app, each name is
imported from its own module:

- reading.py   1. read: a text's changes to others and what it says of them, as printed
- when.py      when a text and its changes take effect, and the version it is read from
- targets.py   the address of what a citation names, and the text an instruction amends
- weighing.py  2. weigh: each change against its witnesses, and the state they allow
- rebuild.py   3. apply: each changed text rebuilt into versions «consolidated by machine»
- status.py    4. stand: where a text stands
- shared.py    the states shown as fact, and an article found by its number either way round
- pipeline.py  readdress, run (the stages for the texts given), prune_waiting
"""
from apps.consolidation.services.engine.pipeline import prune_waiting, readdress, run
from apps.consolidation.services.engine.reading import (BASIS_KINDS, LATER, VERBS, Read, read_copy_repeals, read_text,
                                                        read_visas, refuse_later)
from apps.consolidation.services.engine.rebuild import REPEALED, apply, apply_to, from_archive
from apps.consolidation.services.engine.shared import SHOWN, by_key, pick, variants
from apps.consolidation.services.engine.status import standing
from apps.consolidation.services.engine.targets import cited_title, target_of, where
from apps.consolidation.services.engine.weighing import (BELOW_LAW, LAW_RANK, OFFICIAL_EDITIONS, WITNESSES, check,
                                                         later_texts, model_list, weigh)
from apps.consolidation.services.engine.when import add_months, as_published, own_rule, own_start, takes_effect
