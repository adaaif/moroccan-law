"""What the five tools answer (MC9–MC15 of the MCP review), from the services the site's API already uses and its
kept answers: the site hands over the law with its source and standing, and writes no answer (MC1).

Only the Bulletin's texts and articles, their versions and statuses, and the BO's issues go out: nothing waiting for a
person's review and nothing from the discussion (MC2). Every article carries its standing and its source (MC3).

Each function returns (text for the model, data); `search` and `fetch` return the shapes ChatGPT's deep research and
company knowledge expect (MC10), `{results: […]}` and `{id, title, text, url, metadata}`.

Callers use the package as the module it was (`law.search(…)`, `law.fetch(…)`, `law.Problem`); inside it, each module
imports from the precise one:

- common.py      the refusal, the site's addresses, the kept answers a text is read from, the facts said alike
- texts.py       search, fetch and read_articles (and articles, its data with the words)
- references.py  check_references
- issues.py      get_bulletin (bulletin, and its text and data)

The versioned API (apps/opendata/v1) answers with the same functions' data over plain HTTP, so one fix serves both
doors; a `Problem`'s `code` is its refusal there.
"""
from apps.mcp.services.law.common import (ISSUE_ID, LONG_ARTICLE, OFFICIAL_VERSIONS, STATUS, Problem, address,
                                          site)
from apps.mcp.services.law.issues import BULLETIN_TEXTS, bulletin, bulletin_data, bulletin_text
from apps.mcp.services.law.references import MAX_REFERENCES, STATES, check_references
from apps.mcp.services.law.texts import (CITED, MAX_RESULTS, MAX_RUN, OUTLINE_SHOWN, articles, fetch, read_articles,
                                         search)
