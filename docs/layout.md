# Layout

The repository holds three projects and the folders around them.

| Folder | What it holds |
|---|---|
| `back/` | Django and Django REST Framework: the pipeline, the corpus, the public API |
| `web/` | React, Vite and Tailwind: the site |
| `crates/` | Rust: text folding and citation reading, built for Python and for the browser |
| `deploy/` | the server's files as templates: systemd units, nginx, Docker Compose, the deploy script |
| `docs/` | these pages |
| `tools/ci/` | the scripts behind CI's checks, each run the same way on a developer's machine (`docs/ci.md`) |
| `tools/dev/` | the commit hook (`hooks/pre-commit`) and `moved.py` |
| `tools/publish/` | the export of the public tree and the scan that gates it (they run in the private repository) |
| `.github/` | the workflows and their shared steps, Dependabot, the issue forms, the pull request outline |

The corpus files (PDFs, page images, work files) live under `CORPUS_DIR`, by default `data/` at the repository
root. That folder is outside git.

## back/

```
manage.py              Django's entry point; dev settings by default
pytest.ini             test settings, tests under apps/, run in parallel
conftest.py            shared fixtures, among them `api` (DRF's APIClient)
ruff.toml              the linter's rules (tools/ci/backend.sh lint)
.coveragerc            what coverage counts, and its floor (tools/ci/coverage.sh)
.env.example           every setting, with its default
requirements/          base.txt, dev.txt (tests), prod.txt (the server), lock.txt (hashed, for CI) and lock.sh, which
                       writes it; apt.txt, the system's packages
scripts/               copy_sqlite_to_postgres.py, and health/, shelf/: the commands that loaded a topic's texts
                       from Adala, kept as a record of how they were read
config/                settings, URLs, WSGI and ASGI entry points, request helpers
apps/                  one Django app per part of the product; apps/tests/ holds the project-wide tests (the admin,
                       query loops, time, the development settings)
```

### config/

- `settings/base.py`: what every setting module shares: apps, JWT, password rules, Arabic and French, the
  Africa/Casablanca time zone, `CORPUS_DIR`, the pipeline's spending cap, the search switches.
- `settings/dev.py`: debug, a `.env` file, SQLite unless `DATABASE_URL` is set. Search needs PostgreSQL with
  ParadeDB and pgvector.
- `settings/test.py`: in-memory SQLite, a fast password hasher, throttles out of the way.
- `settings/prod.py`: refuses an insecure `SECRET_KEY`; allowed hosts come from the environment.
- `settings/pgcopy.py`: the settings of `scripts/copy_sqlite_to_postgres.py`.
- `urls.py`: `/admin/`, an `/api/` prefix per app (accounts at `/api/auth/`, analytics at `/api/measure/`, opendata at
  `/api/open/`, `/api/access/` and `/api/v1/`), the OAuth, SEO and gate addresses at the root, and the law's own
  addresses (`/ma/...`).
- `wsgi.py` serves the site; `mcp_asgi.py` serves the MCP server.
- Request helpers: `caching.py` (Cache-Control on public answers), `compress.py` (gzip for public answers),
  `timing.py` (Server-Timing stages), `querylog.py` (in development, flags a query shape repeated in one
  request), `malformed.py` (refuses malformed bodies before a view runs), `drawing.py` (pictures drawn on request),
  `confirm.py` (`--yes-on <database>` for commands that rewrite a whole database).
- `admin.py`: the admin site, read-only, with estimated counts on large tables. `saved.py`: the files a reader saves
  (their names, from `SITE_NAME`). `queryloops.py`: pytest's `--query-loops`, which notes a query run again and again
  in one call; `queryloops-kept.txt` lists the loops kept on purpose (`docs/ci.md`).

### apps/

| App | What it holds |
|---|---|
| `accounts` | the user model, sign-in by username or email, registration, tokens, password rules, letters |
| `blog` | posts that count the law, each computed from the corpus (`posts/`) |
| `budget` | finance laws as checked data: the balance, credits by ministry, posts; the finance bill's watcher |
| `consolidation` | which text changes which: changes read, weighed and applied into dated versions; doubts; the official consolidations |
| `corpus` | the law: texts, versions, articles, addresses, mentions; cutting an issue into texts; the read API |
| `discussion` | posts and comments on articles, marks of usefulness, reports, moderation |
| `explain` | plain-language explanations kept by address, with their history and review |
| `follows` | what an account follows (a law, an article, a topic) and the letters when it changes |
| `gate` | an optional password in front of the whole site (`GATE_PASSWORD`) |
| `mcp` | the MCP server that lets assistants read the law |
| `analytics` | what the site counts about its own use: tasks, never people |
| `media` | voices and pictures people attach: conversion, metadata removed, signed links |
| `oauth` | the OAuth 2.1 authorization server for the MCP resource |
| `opendata` | access on request: a request and its answer, an access and its keys with their limits and use, the versioned API (`/api/v1/`), the database's monthly edition and its download |
| `parliament` | bills as filed and their explanatory memoranda |
| `places` | the states and Moroccan places the Bulletin names |
| `quality` | readers' error reports, corrections read against page images, the proofreader |
| `search` | BM25 and meaning search, citations read first, everyday words, the test sets (`goldset/`) |
| `seo` | sitemaps, IndexNow, the search engines' crawler lists |
| `sources` | the evidence: fetched files, Bulletin issues, pages, OCR runs; the fetchers and readers |
| `topics` | life topics; each topic's folder (`apps/topics/<slug>/`: doors, journeys, checklists, pages as YAML) |
| `translations` | the official French beside the Arabic, kept by the Arabic text's address |

### Inside an app

- `models.py` and `migrations/`.
- `services/`: the logic. A view never holds it.
- `api/`: `urls.py` and `views.py`. A view validates with a serializer, calls a service and answers. A few small
  apps keep `urls.py` and `views.py` at their root (`blog`, `gate`, `opendata`, `seo`).
- `management/commands/`: one command per pipeline step or chore.
- `tests/`: `test_*.py`, plain pytest functions, most with the `api` fixture. Their names say the behaviour.
- `data/`: checked-in data files (JSON, YAML) the services read.
- A module that came to hold several subjects is a package of modules, one subject each (`apps/discussion/models/`,
  `apps/corpus/api/views/`, `apps/search/services/search/`). Its `__init__.py` says which module holds what and
  re-exports the names other code imports, so the old import paths work. Inside the app, code imports from the
  precise module, and a test patches a name in the module that looks it up. `tools/dev/moved.py` checks that such
  a split moved its code without changing it.

### Conventions

- One error shape: `{"errors": [{"field": ..., "code": ...}]}`. The server sends codes, never sentences
  (`serializer_errors_response` and `errors_response` in `apps/accounts/api/errors.py`).
- A new column gets a `db_default` as well as a `default`, so old code still running during a deploy can insert.
- Tables outside the corpus are keyed by address (the Akoma Ntoso URI, the article number), never by a foreign key to
  `Text` or `Article`: a reload recreates those rows.
- No query inside a loop. A list reads related rows in a fixed number of queries, and every public endpoint has a
  test that caps its query count. `manage.py perf_report` prints each public answer's queries, time and size.

## web/

```
index.html, vite.config.ts, eslint.config.js, tsconfig*.json
src/main.tsx              the query client, the router, i18n, the stylesheet
src/entry-server.tsx      the prerender's renderer
src/app/                  the shell: App (routes), Header, BottomBar, Footer, SearchSheet, InstallOffer
src/features/<name>/      one folder per feature: its screens, its API calls, its own CSS
src/topics/               a life topic's own pages: kit/, registry.ts, one folder per topic
src/shared/design/        app.css (Tailwind and the design tokens), french.css (the French law's face)
src/shared/components/    ui.tsx (the kit), Sheet.tsx and dismiss.ts, Field.tsx, buttons.ts, EmptyArt.tsx
src/shared/services/      api.ts (the one fetch wrapper), saved.ts, motion.ts, today.ts, title.ts, install.ts
src/shared/locales/       ar.json, fr.json, pages.ar.json, pages.fr.json, i18n.ts
src/shared/stores/        session.ts, reading.ts
src/shared/analytics/     the measures the site takes of its own use, tasks and never people (apps/analytics' half)
src/shared/wasm/ma_law/   the Rust crates built for the browser (written by crates/build.sh)
scripts/                  check-budget.mjs, prerender.mjs, ssr-server.mjs, check-ma-law.mjs, blog-posters.mjs,
                          fonts.md, icons.py, brand.py
tests/                    Node's own test runner over pure TypeScript (the topics' rules, dates, the session)
e2e/                      Playwright scripts, one per feature (npm run e2e:<name>)
public/                   sw.js, fonts/, brand/, icons/, geo/, blog/, manifest.webmanifest, favicon.ico,
                          apple-touch-icon.png
```

`src/features/` holds `accounts`, `blog`, `budget`, `corpus` (the home, the library, issues, a text, the page
viewer), `corrections`, `discussion`, `explain`, `follows`, `me`, `opendata`, `places`, `saved`, `search`, `shelf`,
`situations`, `topics` and `words`.

`src/topics/` holds `kit/` (the parts every topic with a folder uses: journeys, checklists, pages, tools, the hub's
extras), `registry.ts` (each topic's tools) and one folder per topic: `business`, `consumer`, `digital`, `family`,
`health`, `housing`, `justice`, `land`, `papers`, `road`, `tax`, `work`.

Rules:

- `@/` is `src/`.
- A feature owns its screens and its API calls.
- `shared/` never imports a feature; the shell (`app/`) may.
- Words that only lazy pages use go in `pages.*.json`, so the first load stays small.

## crates/

```
Cargo.toml    the workspace: ma-text, ma-cite, ma-py, ma-wasm
ma-text/      folding (one spelling per letter, no vowel marks or tatweel, Western digits, 65.99 as 65-99),
              light stemming, a query's search terms, Arabic typed on a French or English keyboard,
              Darija written in Latin letters
ma-cite/      Moroccan legal citations read from running text or a query: articles, ranges, texts by number
              or date, Bulletin issues; each points back to the words it was read from
ma-py/        the Python module `ma_law` (PyO3, built with maturin)
ma-wasm/      the same functions for the browser (wasm-bindgen)
vectors/      shared test cases (fold, stem, terms, cite, layout, arabizi)
build.sh      runs the Rust tests, installs the wheel into back/.venv, builds the WASM into web/, then checks
              both builds against vectors/
```

The rule: index time, query time and the browser give the same answer. `vectors/` is how that is checked, by
`web/scripts/check-ma-law.mjs` and `back/apps/search/tests/test_ma_law.py`.
