"""Read-only API for the corpus: issues, texts with their articles and links, search. Public, no session.

The views live in modules by subject; every name stays importable from here (urls.py, the MCP, the law page's heads):

- `base`: the view with no session, a text's and an issue's reference;
- `issues`: the Bulletin's issues, an issue, how it was read, the issue map;
- `answer`: a text's answer, a window at a time, kept by generation (`text_payload`, `text_answer`, `outline`);
- `texts`: the views over one text, its outline, a bill's proposals, a link's picture and preview, the index, the
  day of reading's pass;
- `library`: the shelf, the library, the box, a year, the situations, the constitutions;
- `pages`: the site's pages Django answers with their own heads.
"""
from apps.corpus.api.views.base import PublicView, issue_ref, text_ref
from apps.corpus.api.views.issues import IssueDetail, IssueList, IssueMap, IssueQuality, last_numbers
from apps.corpus.api.views.answer import (
    CHUNK, MORE, OUTLINE_PER, OWN_FILE, WINDOW_MAX, Asked, Picked, _anchors, _MARKUP, _number, _versions, _WHOLE,
    _window, asked_range, first_words, fr_article, outline, outline_url, text_answer, text_payload)
from apps.corpus.api.views.texts import Card, Outline, Preview, Proposed, ReadingPass, TextAt, TextDetail, TextIndex
from apps.corpus.api.views.library import (
    ConstitutionAt, ConstitutionHistory, ConstitutionLineage, Find, Library, LibraryCard, Shelf, Situations, Year)
from apps.corpus.api.views.pages import issue_page, law_page, search_page, text_by_id, words_page
