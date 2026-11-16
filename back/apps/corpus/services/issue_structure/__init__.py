"""A read issue into texts: its table of contents, each text cut out of the issue, then the corpus records.

The model reads the table of contents and, for each text, what needs reading: its title, number, dates,
preamble, signatures, citations and amendments. The articles themselves are never copied by a model (asked to
copy a 30-page law word for word, Haiku stopped after two articles): they are cut out of the OCR text by their
headings, so every article is the page's own words, with the page it starts on.

The steps live in modules, every name importable from here as before:

- `toc`: the contents step (`read_toc`), its schema and instructions;
- `segment`: an issue's lines and where each text starts in them (`issue_lines`, `segment_issue`);
- `articles`: a text's lines into its articles (`split_articles`, `whole_text`);
- `texts`: the texts step, by the model or by code (`texts_requests`, `texts_answered`, `describe_by_code`);
- `printed`: numbers and days as printed (`normalize_number`, `article_number`, `ordinal_value`, `cited_day`);
- `load`: the texts into the corpus (`load_texts`, `as_law`, `settle`).
"""
from apps.corpus.services.issue_structure.toc import (
    MAX_PAGES_PER_TEXT, OLD_TOC, TOC_PAGES, TOC_SCHEMA, TOC_SYSTEM, TYPES, _before_1956, read_toc, toc_system)
from apps.corpus.services.issue_structure.segment import (
    _BODY_OPENS, _CONTENTS_HEAD, _DECOR, _HEADER, _KINDS, _MARKS, _PLAIN, _TATWEEL, _digits, _start_of, _words,
    contents_block, issue_lines, running_head, segment_issue)
from apps.corpus.services.issue_structure.printed import (
    _CITING, _DIGITS, _GREGORIAN, _HUNDRED, _MONTHS, _NUMBER, _TENS, _UNITS, _WORDS, ORDINALS, _date, _days,
    article_number, cited_day, normalize_number, ordinal_value, ordinal_words)
from apps.corpus.services.issue_structure.articles import (
    _ARTICLE_WORDS, _BETWEEN, _DIVISION, _END, _NUMBERED, _ONE_PIECE, _SINGLE, _TAIL, _article_head, _follows,
    _is_subject, _opening, _resumes, one_piece, single_article, split_articles, whole_text)
from apps.corpus.services.issue_structure.texts import (
    _BY_TITLE, _DECIDES, _ISSUER, _SIGNATURE, _SIGNED, _VISA, OLD_TEXT, TEXT_SCHEMA, TEXT_SYSTEM, _entry_key,
    describe_by_code, extract_texts, text_system, texts_answered, texts_requests)
from apps.corpus.services.issue_structure.load import (
    _AFTER_TITLE, _NOT_RUBRIC, _OWN, _PROMULGATES, FIRST_PRINTS, SUBTYPES, as_law, contents_rubric, first_print_of,
    load_texts, own_heading_at, own_name, settle)
