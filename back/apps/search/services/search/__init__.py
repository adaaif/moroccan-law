"""Search the corpus: a query read stage by stage and answered with texts and their articles, the suggestions as it is
typed, and «ابحث في هذا النص». Callers use the package as the module it was (`search.search(…)`, `search.suggest(…)`,
`search.warm()`); inside the app, each name is imported from its own module, and a test patches a name on the module
that reads it (a patch here reaches no module).

- query.py        the search itself: the query read in order (a citation, the words, the everyday words, the repairs,
                  meaning), the results grouped by text, the log; the threads that ask for the question's vector
- asking.py       the asking words set aside, a constitution by its year, a law's number typed the wrong way round
- quotes.py       words between quotes, searched as typed; any words as the index holds them in a row
- bm25.py         the index read by BM25 with what lifts an entry, and the rows a page of answers reads back
- snippets.py     a result's two lines around its first matched word
- beside.py       the official French beside the articles shown, and a topic's words of the law
- within.py       «ابحث في هذا النص»: the articles of one text that hold the words
- suggestions.py  what the box offers as a reader types, and the warm-up before a worker's first request
- titles.py       the titles a suggestion finds, kept in the process and in a file

Each table a process keeps has one home: the vector's threads in query.py, the titles in titles.py, the shelf's map in
suggestions.py, each cache beside the function it keeps.
"""
from apps.search.services.search.asking import ASKING, CITED_ARTICLE, CONSTITUTION_YEAR, asked_words
from apps.search.services.search.beside import door_french, topic_words, with_french
from apps.search.services.search.bm25 import CITED_BOOST, LIMIT, OLD_ERA, PHRASE_BOOST, SHELF_BOOST, TOPIC_BOOST
from apps.search.services.search.query import (AFTER_KINDS, JUMP_STATES, PAGE, PER_TEXT, QUERY_MOST, RULE_KINDS,
                                               TITLE_BOOST, TYPED_MOST, search, shown_paths)
from apps.search.services.search.quotes import QUOTED, quoted
from apps.search.services.search.snippets import LONG, SNIPPET, snippet
from apps.search.services.search.suggestions import COMPLETIONS, SUGGEST_MOST, suggest, warm
from apps.search.services.search.titles import SUGGEST_FROM, TITLES_READ
from apps.search.services.search.within import FIND_MOST, FORMS_MOST, find_in

# The private names other modules imported from the old module: their paths keep working.
from apps.search.services.search.asking import _constitution_of_year
from apps.search.services.search.bm25 import _brief, _shelf_paths, _texts
from apps.search.services.search.suggestions import _bare, _shelf_map, _topics
