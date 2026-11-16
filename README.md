# قانون · 3adala

A free search of Moroccan law, article by article. Every text of the Bulletin Officiel (BO), the Arabic with the
official French beside it, each article tied to the printed page it came from, with all its versions. The site is
Arabic first, with French as a full second language.

There is no chat about the law. Language models work only inside the pipeline (reading scanned pages, finding a
text's structure, translating the texts only the French edition holds) and in the check that reads a post before the
discussion publishes it; search's meaning model runs on the server. None of them answers a reader or writes the law's
words. What readers see is the law as published, and the people who discuss it.

The live site is https://3adala.com.

## Quick start, on the sample

You need Python 3.13 (the version CI tests; 3.12 is allowed but not tested), Rust (from https://rustup.rs: the text
and citation reader is a Rust module), and Node 22.18 or newer in the 22 line (the web's tests are TypeScript, which
Node runs without a build step from 22.18). The share pictures, the scans and the voice notes also need three things
from the system, listed in `back/requirements/apt.txt`; the quick start runs without them. The first install takes a
few minutes and about 500 MB.

```bash
cd back
python3 -m venv .venv
.venv/bin/pip install --require-hashes --no-deps -r requirements/lock.txt   # CI's packages, by their hashes
.venv/bin/pip install --no-deps ../crates/ma-py                               # builds the Rust module
.venv/bin/python manage.py migrate                 # SQLite, in back/db.sqlite3
.venv/bin/python manage.py load_sample             # the 2011 Constitution and one Bulletin issue
.venv/bin/python manage.py runserver 8020          # the API; the site is on 5190 (next block)
```

In a second terminal:

```bash
cd web
npm ci
npm run dev                                        # http://localhost:5190
```

Then open:

- http://localhost:5190/ma/dahir/1-11-91 — the 2011 Constitution, 181 articles, with its official French.
- http://localhost:5190/bo/general_ar/7278 — BO 7278 of 29 February 2024: eleven laws and their pages as read.
- http://localhost:5190/ma/loi/1-22 — law 01.22 on credit information bureaus, with its French from BO 7410.

Search needs PostgreSQL (below): on SQLite the search page answers an error; suggestions and «find in this text» work.

The sample holds the texts and the pages' readings, not the PDFs. A page shows its reading; to see its image, fetch
the file from the address its `sources.Document` row holds (the SGG's or Adala's) to the path that row names under
`data/`, and compare its hash with the row's. For BO 7278, from `back/`:

```bash
.venv/bin/python manage.py shell -c "from apps.sources.models import Document as D; [print(d.url, d.path, d.sha256) for d in D.objects.all()]"
curl --create-dirs -o ../data/issues/bo_ar/BO_7278_ar.pdf https://www.sgg.gov.ma/BO/AR/3111/2024/BO_7278_Ar.pdf
sha256sum ../data/issues/bo_ar/BO_7278_ar.pdf
```

The site draws a page's image from its file when the page is opened.

**Search** needs PostgreSQL with ParadeDB (BM25) and pgvector. With Docker, the image the server runs, from the
repository's root:

```bash
docker run -d --name law-dev-pg -p 127.0.0.1:5432:5432 \
  -e POSTGRES_USER=law -e POSTGRES_PASSWORD=law -e POSTGRES_DB=law \
  paradedb/paradedb@sha256:c552094b6b68dcb0a4e7a3969963d801eaec02490db4d2dd032dcb096bc86cf8
until docker exec law-dev-pg pg_isready -q -h 127.0.0.1 -U law; do sleep 1; done
cd back
echo 'DATABASE_URL=postgres://law:law@localhost:5432/law' >> .env    # manage.py reads back/.env
.venv/bin/python manage.py migrate && .venv/bin/python manage.py load_sample
```

Then stop runserver and start it again: it reads `back/.env` when it starts, and a line there reaches every terminal,
which `export` does not. A PostgreSQL of your own already on 5432? Publish the container on another port
(`-p 127.0.0.1:5434:5432`) and write that port in the address.

On SQLite everything but search works. Search by meaning also needs its model and `manage.py serve_models`
(`docs/running.md`); without them, search uses BM25 alone. `back/.env.example` lists every setting.

## Tests

Every check CI runs is a script in `tools/ci/` or one command named beside its job in `docs/ci.md`, and gives the
same answer on your machine:

```bash
tools/ci/backend.sh all       # ruff, Django's checks, the test suite on SQLite, the sample loaded
tools/ci/web.sh all           # eslint, types, the node tests, the build, the first load's budget, the renderer
tools/ci/smoke.sh             # the site booted on the sample, walked in a browser
(cd crates && cargo test --locked)
TEST_DATABASE_URL=postgres://law:law@127.0.0.1:5432/law_ci_t tools/ci/search.sh  # search's tests, on the ParadeDB above
```

`.github/workflows/ci.yml` runs them on every push and pull request, with a secrets scan and the licence check;
`.github/workflows/nightly.yml` adds the dependency audits, the browser's reader rebuilt from its source, the
query-loop survey and coverage. `docs/ci.md` says what runs when, how to set a machine up as CI does, and how to read
a failure.

## What is where

- `back/`: Django and Django REST Framework. The pipeline (fetch, OCR, structure, links), the corpus, the API.
- `web/`: React, Vite and Tailwind. The site.
- `crates/`: Rust. Arabic and French text folding and citation reading, built for Python and for the browser, giving
  the same answer at index time, at query time and in the browser.
- `deploy/`: the server's files, as templates.
- `docs/`: how to run it, the layout, the rules of the codebase, the pipeline, the design.

## Where the law comes from

Official sources only:

- the Bulletin Officiel, from the Secrétariat Général du Gouvernement (https://www.sgg.gov.ma): the Arabic general
  edition, the official French translation, the conventions' edition;
- the Ministry of Justice's portal Adala (https://adala.justice.gov.ma): texts and their consolidations;
- the DGI's yearly edition of the tax code, and the Parliament's documents for bills.

Every fetched file is kept with its SHA-256, and the database records each file's hash and address
(`sources.Document`). The fetchers read the official sites' own lists, one file at a time with a pause, and obey
robots.txt. They give each site the name `FETCH_USER_AGENT` sets, your project's and a page that says who runs it, and
refuse to start without one. In `back/apps/sources/management/commands/`: `fetch_new_issues` for the Arabic issues
since 2019, `fetch_bo_french` for the French edition, `fetch_conventions`, `fetch_sgg_consolidated`, `fetch_adala`. In
`back/apps/parliament/`: `fetch_bills` for the bills as filed with the Chamber of Representatives. The DGI's yearly
edition of the tax code is downloaded by hand: its site refuses scripts.

The Arabic issues from 1913 to 2018 were read from a copy of the SGG's own PDFs, the same files byte for byte. The
code that made that copy is not here; `manage.py archive register` registers a plan's files with their hashes, so
anyone can fetch an issue from the SGG and compare it with the hash the database holds.

Official texts carry no copyright in Morocco (law 2-00, article 8). Reuse cites the source and its date and never
distorts the text (law 31-13, article 6). A consolidated version is labelled unofficial and links each amending BO
page: the Bulletin prevails.

## Licences

| What | Licence |
|---|---|
| The application: `back/`, `web/`, `deploy/`, `tools/`, `docs/` | AGPL-3.0-only |
| The Rust crates (`crates/`) and their WASM build | MIT OR Apache-2.0 |
| Database-like data: the apps' `data/` folders, the search test sets, the sample, figures | ODbL-1.0 |
| Editorial text: the topic folders (`back/apps/topics/<slug>/`), each topic's own words and its tools' words (the locales under `web/src/topics/<slug>/`), the blog's posts, words and posters | CC-BY-NC-SA-4.0 |
| Third-party files (fonts, lean-qr, domain lists, GeoNames positions, Natural Earth's maps, the crates the WASM build links) | their own, see `NOTICE` |
| The name «قانون» / 3adala, the wordmark, the icons | not licensed, see `TRADEMARKS.md` |

The interface's words (`web/src/shared/locales/`, each feature's locales, the topic kit's) are the application's:
AGPL-3.0-only. The topics' and the blog's words are non-commercial: a copy that serves them commercially replaces them.

`REUSE.toml` maps every path to its licence; the texts are in `LICENSES/`. Much of the editorial text and the test
sets was drafted with a language model and checked by people to varying degrees. The site says so once under every
page and in full on its about page; drafts are marked as drafts.

The site links its own source in its footer (`SOURCE_URL`). If you run a changed copy for other people, the AGPL
(section 13) asks you to offer them your changed source the same way: set `SOURCE_URL` to your repository.

## What is not in this repository, and why

- **The corpus.** The PDFs, page images and readings of the whole archive (tens of gigabytes) live outside git, in
  `CORPUS_DIR`. A data release under the ODbL is planned, separately from the code.
- **The Bulletin's pages read again on their images.** These whole-page corrections are full official pages, many of
  them notices about private people (land registration, heirs, addresses). The Bulletin printed them; a public git
  history is mirrored and cannot be corrected, so they come with the data release instead.
- **The moderation check's test set.** It is made of posts written to break the discussion's rules, with invented
  names beside accusations. It stays in a private evaluation set.
- **One search tuning set.** Its questions were collected from the web without a record of where each came from, and
  rewording them would change what it measures, so it is kept out rather than published.
- **Operations.** The one-off run scripts (but `back/scripts/health/` and `back/scripts/shelf/`, kept as a record of
  how two topics' texts were loaded from Adala), the backup copy and the real server's names and addresses. `deploy/`
  holds the same files as templates.

## Contributing and security

See `CONTRIBUTING.md` (contributions are accepted under `CLA.md`), `CODE_OF_CONDUCT.md`, and `SECURITY.md` for how to
report a flaw privately. Questions: open an issue. Anything else: contact@3adala.com.
