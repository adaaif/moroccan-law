"""The topic kit (F16 of the family plan): what a topic says beyond its texts, the same way for every topic.

A topic with a folder of its own (apps/topics/<slug>/) writes it there as YAML people can read and review:
`hub.yaml` (the doors by life event and the tools), `journeys.yaml` (numbered steps), `checklists.yaml` (the papers),
`pages.yaml` (facts, tables, lines), `reform.yaml` (one reform, or a list of changes each with its stage),
`series.yaml` and `rates.yaml` (figures by the dates they are in force, for the tools), `cards.yaml` (practice cards
by batches, each written by a person from one article: R10 of the road plan). Every item names the articles it rests on
(`cites`, the site's addresses) and the official pages it quotes (`sources`).

An item reaches readers once a person checked it: a row of `ItemCheck` records who and when, and the digests of the
articles it cited that day (the review desk, under the signed-in account, or `manage.py approve_topic family
journeys/marry --by …`). Checks live in the database: a deploy replaces the code's folder. While developing, drafts show
too, marked as drafts. An item one of whose articles has changed since its check says so («يحتاج مراجعة») until it is
checked again. Nothing here writes for readers: it serves what was written and checked, and the law's own words through
the articles it links.

Callers use the package as the module it was (`kit.load(…)`, `kit.hub(…)`, `kit.matching(…)`); inside it, each module
imports from the precise one, and a test patches a name on the module that reads it (`folder` and `BASE` in folders.py):

- folders.py     each topic's files read with its checks, every cache of the kit and the checks' version; `citing`
- items.py       what an item cites, its articles and their digests, whether it may be shown, its state, its links
- topic_page.py  the hub, an item's page, the dated changes, the calendar, the topics page's moments
- doors.py       the doors a question names or comes near, a door's articles, a search's private words
- checks.py      what check_topic reports, a check recorded, the reviewer's desk
"""
from apps.topics.services.kit.checks import items_of, problems, record_checks, review
from apps.topics.services.kit.doors import door_articles, door_cites, door_words, matching, nearest, private
from apps.topics.services.kit.folders import (BASE, CHECKS_KEY, CITING, KINDS, checks_version, citing, cites_of, folder,
                                             load, log, stamp, warm)
from apps.topics.services.kit.items import LINKS, articles, cited, cited_in_order, digest, links, shown, state
from apps.topics.services.kit.topic_page import (band, calendar, door_path, hub, latest, moments, page, reachable,
                                                upcoming)

# The private name other modules read through the kit (`kit._folders()`): it keeps working.
from apps.topics.services.kit.folders import _folders
