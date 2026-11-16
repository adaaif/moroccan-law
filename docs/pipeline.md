# The pipeline

How an issue of the Bulletin Officiel (BO) becomes articles, from the file to the search index.

```
fetch -> register -> pages -> OCR -> structure -> load -> links -> French -> corrections -> search index
```

Most steps are steps of one command, `process_issue`, and every step can run again. A step replaces what it wrote
before and keeps what a person checked. Commands are run with `python manage.py <command>` from `back/`.

```bash
python manage.py process_issue <key> --date YYYY-MM-DD --url <the file's address> --write
```

The key is the issue's number, with `-bis` for a bis issue (`7465-bis`). The steps are `ingest`, `ocr`, `number`,
`toc`, `texts`, `load` and `links`; `--steps texts,load` runs some of them. Without `--write`, nothing that calls the
model is sent.

## 1. Fetch

- Official sources only: the SGG (the Bulletin's editions and its consolidated texts), Adala (the Ministry of
  Justice's portal), the DGI (the tax code's yearly edition) and Parliament. Nothing comes from a private database.
- Every request goes through `apps/sources/services/fetch.py`: https only, a fixed list of hosts (redirects too),
  robots.txt read and obeyed, the project's own user agent (`FETCH_USER_AGENT`), one file at a time with a pause.
  A refusal stops the run; nothing tries another way round it.
- Every file is kept as fetched under `CORPUS_DIR`, with its sha256. The Bulletin fetchers add a line to the folder's
  `MANIFEST.tsv` (file, address, sha256, size, time, number, date). The lists they read are kept too, with their hashes.

| Command | Fetches |
|---|---|
| `fetch_new_issues` | the Arabic general edition's issues not held yet; then reads each with `process_issue` |
| `fetch_bo_french` | the French translation edition (`issues/bo_fr/`) |
| `fetch_conventions` | the international conventions' edition |
| `fetch_sgg_consolidated` | the SGG's consolidated texts |
| `fetch_adala` | one Adala file, registered for `load_adala` |

## 2. Register

The `ingest` step (`apps/sources/services/ingest.py`, `issue.py`) writes a `Document` (one file exactly as fetched,
unique by sha256, never edited; `producer` tells a scan from a born-digital file), its `Issue` (one issue in one
edition, its Hijri date kept as printed by `read_hijri_dates`) and a `Page` for each page.

## 3. Pages

- PDFium (`pypdfium2`) reads each page's text layer and draws its image (`apps/sources/services/render.py`).
- A page's `kind` is `text_layer`, `scan`, `mixed` or `blank`.
- **Born-digital text layers are not trusted for Arabic.** Ligatures come out reversed, some lines are in visual
  order, and Arabic inside a French file can be garbled. The layer is kept as extracted (`layer_text`) and serves
  only as a check of a reading: its letters on a text page, its amounts on a table page.
- `render_columns` cuts a two-column page at its rule or gutter. `is_sideways` finds a page printed in landscape.

## 4. OCR

- The `ocr` step reads every page with a language model through the API's message batches: the page whole, then
  column by column where it splits cleanly, and turned upright when it is sideways. The key comes from the
  environment only (`ANTHROPIC_API_KEY`); `--engine` picks the model.
- Every reading is an `OcrRun` and is never overwritten. `best_run` keeps the most complete reading the layer
  confirms; a table page never keeps a column reading. `clean_reading` makes `Page.text`: it drops the model's own
  notes and puts back amounts copied in visual order.
- **Tesseract is the witness.** It gives a page's orientation and line boxes, flags a reading that lost lines, and
  finds where an article stands on its page (`read_regions`). It never replaces a reading.
- **A ledger caps spending.** Each call's cost comes from the API's reported usage. OCR runs and the structuring
  ledger (under `CORPUS_DIR/reports/`) are added up, and a batch whose worst case would pass `OCR_BUDGET_USD` is
  refused before it is sent. `budget` prints what was spent, what is in flight, the cap and what is left.
- The `number` step reads the printed page numbers from the running heads (`renumber_pages` puts wrong ones right).
  `keep_best_readings` chooses each page's reading again without a model call.

## 5. Structure

The `toc` and `texts` steps (`apps/corpus/services/issue_structure/`, a module a step) cut an issue into texts and a
text into articles:

- `read_toc`: the model reads the issue's contents from its first pages.
- `segment_issue`: each entry's lines, from its own title line to the next text's, running heads left out.
- `split_articles`: **the articles are cut by code, never copied by a model.** An article starts at its heading
  («المادة …», or «الفصل» when the text has none), and the numbers must run in order. Divisions become each
  article's `heading_path`; signatures and annexes are the tail.
- `extract_texts`: the model only describes each text against a JSON schema (type, number, title, dates, preamble,
  signatures). Its lists of citations and amendments stay in `texts.json` as a witness, never loaded as links.
- The work files go to `CORPUS_DIR/reports/issues/<key>/` (`toc.json`, `texts.json`).
- `recut_swallowed` finds a text the contents missed inside the text before it and cuts it out.

## 6. Load

The `load` step (`load_texts`) writes the corpus (`apps/corpus/models.py`):

- `Text`: the work, at one address worked out from its kind and number, `/akn/ma/act/<kind>/<number>`
  (`apps/corpus/services/works/`). A text cited before its own issue is read waits at that address.
- `Version`: one language between two dates. `consolidation` says what it is: as published in the BO, by machine,
  checked by a person, the SGG's, Adala's or the DGI's edition, a bill, or a machine translation.
- `Article`: belongs to one version, with its printed page, so every version is whole.
- `Alias`: another address that leads to the text, such as the dahir that promulgated a law.
- `Mention`: an article citing another text, a decree applying a law, a reference taken over.
- `Text.latest_version()` picks the version that stands today; `reload_issues` loads issues again from `texts.json`.

## 7. Links and consolidation

`consolidate --yes-on law` runs this over the whole corpus; the `links` step runs it for one issue's texts and every
text they change (`apps/consolidation/services/engine/`). Rows are kept by address, so issues can be read in any
order: a change waits for its text.

- **Read** (`apps/consolidation/services/instructions/`, beside `engine/`): every article of every text is read by
  code: amending instructions (modify, add, replace, repeal, swap words), final provisions (whole-text repeals,
  references taken over, implementing texts kept), the title's formula and every citation (`ma-cite`).
- **Date**: an article's own date, else the text's entry into force (on publication, a stated date, a delay). A
  condition stays a condition, never a guessed date.
- **Weigh**: each change against its witnesses: the title, the model's list, the SGG's notes
  (`load_sgg_consolidated`), Adala's footnotes (`load_adala`), the DGI's notes (`load_dgi`), the later official
  wording. Its state is `checked`, `confirmed`, `read`, `conflict` or `unclear`. Only the first three are shown as
  fact and applied.
- **An amendment the machine cannot place is marked unclear, never guessed.** It becomes a `Doubt` with its reason
  (the target not named plainly, the article missing, dotted wording that finds no place, words not found).
  `read_unclear` asks the model to read those articles as one more witness, never alone. `apply_wordings` records a
  wording a person settled.
- **Apply, in legal time**: per changed text, by the day each change takes effect, on the version that stood before
  that day, one amending text whole or not at all. Each result is a version consolidated by machine, labelled
  unofficial, that links each amending BO page. The BO prevails.
- **Stand**: `Text.status` follows from the changes shown as fact: in force, partly repealed, repealed, not yet in
  force.
- A bill's changes are kept as `proposed` and never applied. `link_eval` measures the readings against the SGG's
  notes and Adala's footnotes.

## 8. The French

- The French comes from the BO's official translation edition. Only the Arabic is authoritative.
- `process_issue <key> --edition translation_fr` cuts a French issue at its «Article» headings and keeps each text
  beside the Arabic text it translates. `load_bo_french` reads one text's French from a scanned French issue, column
  by column, with Tesseract. `load_adala_french` loads Adala's French consolidation of a code.
- `FrenchText` and `FrenchArticle` (`apps/translations`) are keyed by the Arabic text's address and the article's
  number, never by row links. Either edition can be read first, and a reload of one never touches the other.
- A text whose Arabic is nowhere online may get a machine translation from the official French (`translate_french`,
  then `load_translated`). Its version is `translation`, and every page says so.

## 9. Corrections against the page images

- `apply_page_reading <file>` applies a YAML file from `apps/quality/data/`: the text, the file it was read in, and
  each word put right with its articles. The corrections are applied now and again at every reload of the text, and
  listed on the corrections page. Running a file twice changes nothing.
- The whole pages of the Bulletin read again on their images (`pages_reread_*.yaml`) are not in this repository:
  they come with the data release, and `apply_page_reading` says so when one is missing.
- `witness_pages` sets a text held from a file's layer against the Bulletin's own pages and lists each difference to
  read on the image. It writes nothing.
- `proofread` proposes fixes (reversed ligatures, letters of another alphabet, words cut in two); a person applies each.
- Readers report errors by an article's address (`POST /api/quality/reports/`), for a person to review.

## 10. The search index

- `build_search_index` writes one `SearchEntry` per article of each text's latest version, and one per title, keyed
  by address. Words are folded and stemmed by `ma-text`, the same way at index time and at query time.
- The words are searched with BM25 in ParadeDB (`pg_search`). `merge_search_index` rebuilds that index concurrently,
  one rebuild at a time, after large loads.
- **Meaning search** uses a local model: `embed_passages` writes `SearchPassage` rows (pgvector) with the model in
  `SEARCH_MODEL_DIR`, and `serve_models` holds the model in one process, listening on localhost only, to embed each
  question for every worker. Search fuses the nearest articles with BM25 (`SEARCH_MEANING`, `SEARCH_FUSION_WEIGHT`)
  and goes on with BM25 alone when the model server does not answer.
- A citation in a query is read first (`ma-cite`) and opens its article. No language model runs at query time.
- `search_eval` scores the test sets in `apps/search/goldset/`.
- Search needs PostgreSQL with ParadeDB and pgvector. On SQLite its tests are skipped.
