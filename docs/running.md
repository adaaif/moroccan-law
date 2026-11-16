# Running it

## What you need

- Python 3.13 (the version CI tests; 3.12 is allowed but not tested), Rust (https://rustup.rs) and Node 22.18 or newer
  in the 22 line (the web's tests are TypeScript, which Node runs without a build step from 22.18).
- From the system: FriBiDi (Arabic in the share pictures), Tesseract with its Arabic and French data (a scan's
  orientation, an article's place on its printed page) and ffmpeg (voice notes). `back/requirements/apt.txt` lists
  the Debian and Ubuntu packages and the line that installs them. The site starts without them; the tests that
  need one are skipped on your machine and say which, and CI installs them all.
- Optional: Docker, for PostgreSQL with ParadeDB (search) and Redis (the shared cache).

## The backend

```bash
cd back
python3 -m venv .venv
.venv/bin/pip install --require-hashes --no-deps -r requirements/lock.txt   # CI's packages, by their hashes
.venv/bin/pip install --no-deps ../crates/ma-py                               # the Rust module, built from ../crates
.venv/bin/python manage.py migrate
.venv/bin/python manage.py load_sample            # a small corpus: the 2011 Constitution and BO 7278
.venv/bin/python manage.py runserver 8020
```

`manage.py` uses `config.settings.dev`: debug on, SQLite in `back/db.sqlite3` unless `DATABASE_URL` is set, the
discussion and sign-up open, letters printed to the console. Settings come from the environment or `back/.env`; every
one is listed, with its default, in `back/.env.example`.

`load_sample` loads into an empty database only. To start again, delete `back/db.sqlite3` and migrate.

## The web

```bash
cd web
npm ci
npm run dev                                       # http://localhost:5190, /api sent to Django on 8020
```

`WEB_PORT` and `API_TARGET` run a second pair beside the first (`web/.env.example` lists what the scripts read).

## PostgreSQL, for search

Search runs BM25 in ParadeDB (`pg_search`) and meaning search in pgvector, so it needs PostgreSQL with both. From the
repository's root, with the image `deploy/compose.yml` pins for the server:

```bash
docker run -d --name law-dev-pg -p 127.0.0.1:5432:5432 \
  -e POSTGRES_USER=law -e POSTGRES_PASSWORD=law -e POSTGRES_DB=law \
  paradedb/paradedb@sha256:c552094b6b68dcb0a4e7a3969963d801eaec02490db4d2dd032dcb096bc86cf8
until docker exec law-dev-pg pg_isready -q -h 127.0.0.1 -U law; do sleep 1; done
cd back
echo 'DATABASE_URL=postgres://law:law@localhost:5432/law' >> .env    # manage.py reads back/.env
.venv/bin/python manage.py migrate
.venv/bin/python manage.py load_sample
```

Then start runserver again: it reads `back/.env` when it starts. `pg_isready` asks over TCP because the image's first
start runs a server on its socket alone, then restarts it. Another PostgreSQL already on 5432: publish the container on
another port (`-p 127.0.0.1:5434:5432`) and write that port in the address.

**Meaning search** needs the model's folder (`SEARCH_MODEL_DIR`, by default `models/bge-m3-int8` at the repository's
root, outside git) and the model server beside Django. The code reads two files there: `model.onnx`, bge-m3 (BAAI,
MIT licence) as the int8 ONNX export Xenova publishes (`onnx/sentence_transformers_int8.onnx` at
https://huggingface.co/Xenova/bge-m3), and its `tokenizer.json`. Keep a `SOURCE.txt` beside them that says where they
came from and their hashes. The files the site's own server runs:

```bash
mkdir -p models/bge-m3-int8 && cd models/bge-m3-int8
curl -L -o model.onnx https://huggingface.co/Xenova/bge-m3/resolve/main/onnx/sentence_transformers_int8.onnx
curl -L -o tokenizer.json https://huggingface.co/Xenova/bge-m3/resolve/main/tokenizer.json
sha256sum model.onnx tokenizer.json
# e5b42096865cef734247dd8c7a44e35d305b70ba0c3736758065e1cad50f6453  model.onnx
# 6710678b12670bc442b99edc952c4d996ae309a7020c1fa0096dd245c2faf790  tokenizer.json
```

Another export gives other vectors: embed the passages again with it. Then, from `back/`:

```bash
.venv/bin/python manage.py embed_passages        # the articles' vectors
.venv/bin/python manage.py serve_models          # 127.0.0.1:8090
```

Without the server, search goes on with BM25 alone.

## Redis

Without `REDIS_URL`, development keeps request limits in the process and keeps no answer. To run as production
does:

```bash
docker run -d --name law-dev-redis -p 127.0.0.1:6379:6379 redis:8-alpine \
  redis-server --save '' --appendonly no --maxmemory 512mb --maxmemory-policy volatile-lru
export REDIS_URL=redis://127.0.0.1:6379/0
```

## Tests

CI runs each check through one script in `tools/ci/` (`tools/ci/backend.sh all`, `tools/ci/web.sh all`,
`tools/ci/smoke.sh`, …); `docs/ci.md` lists them and sets a machine up as CI does. The commands below are the pieces.

```bash
cd back && .venv/bin/python -m pytest             # config.settings.test: in-memory SQLite, in parallel (xdist)
```

The search tests that need ParadeDB skip unless `TEST_DATABASE_URL` names a PostgreSQL server with it. The suite
points `CORPUS_DIR` at a temporary folder, so it runs with no `data/` folder.

```bash
cd web
npm run lint && npx tsc -b                        # lint and types
node --test tests/*.test.ts                       # the rules of the topics' tools, dates, the session
npm run build && npm run check:budget             # the first load's byte budget
npm run e2e:accounts                              # Playwright; both dev servers running (see package.json for all)
```

```bash
(cd crates && cargo test --locked)
crates/build.sh            # the Python module and the browser's reader, both checked against crates/vectors/
```

`crates/build.sh` needs the compiler and wasm-pack that `nightly.yml`'s `wasm` job names (`CONTRIBUTING.md`, «The
Rust crates»): another compiler writes other bytes.

`manage.py perf_report` prints every public answer's queries, repeated query shapes, time and size.

## The pipeline

Reading an issue needs an API key (`ANTHROPIC_API_KEY`) and a spending cap (`OCR_BUDGET_USD`); nothing is sent
without `--write`. `docs/pipeline.md` has the steps. The fetchers read official sites: run them sparingly, and never
against a site that refuses them.

## A server

`deploy/` holds the server's files as templates: systemd units, nginx, a Cloudflare tunnel, Docker Compose for
PostgreSQL and Redis. `deploy/deploy.sh [--system] [--host HOST]` deploys the commit at HEAD. It needs four values,
none with a default, from the environment or from a private `deploy/private/site.sh`:

| Variable | What |
|---|---|
| `HOST` | the server, as ssh names it |
| `RUN_USER` | the account the services run as |
| `ROOT` | the folder on the server that holds the app, its venv, `.env`, data and backups |
| `DOMAIN` | the site's address, such as `example.org` |

It writes them into the units, `nginx.conf` and `tunnel.yml` (`@USER@`, `@ROOT@`, `@DOMAIN@`) on the server before
installing them. Secrets are written on the server, in `ROOT/.env`, never in the repository.

## Publishing the public tree

The public repository is an export of a private one. `tools/publish/export.sh <commit> <dir>` writes the tree of a commit
into a directory, leaving out every path `.gitattributes` marks `export-ignore`, then refuses it while
`tools/publish/scan.py` finds private material or a placeholder is left. It never pushes and never makes a remote.
These tools run in the private repository; a public clone has no word list and no `.gitattributes`, so there the scan
says it has nothing to look for and the export stops.
