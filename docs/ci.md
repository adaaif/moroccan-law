# Continuous integration

Every check is a script in `tools/ci/` or one command named beside its job below. The workflows in
`.github/workflows/` only set up a machine and call those scripts and commands, so a job that fails on GitHub is run
on your machine with the same command, and gives the same answer.

## What runs when

| What | When | Its jobs |
|---|---|---|
| `ci.yml` | every push (Dependabot's branches through their pull requests), every pull request, and by hand | what must pass before a change lands, in under ten minutes; `gate` is the one required check |
| `nightly.yml` | every night at 02:23 UTC, and by hand | the dependency audits, the browser's reader rebuilt, the search tests, the query-loop survey, coverage, the smoke |
| Dependabot (`.github/dependabot.yml`, in the private repository) | every Monday | update proposals, as pull requests that `ci.yml` checks |
| `tools/dev/hooks/pre-commit` | at each commit, once switched on | a few seconds of checks on the staged files |

A new advisory, a new compiler or a slow survey never turns a push red: those checks are in the nightly run, and a
red night is fixed in a change of its own.

### `ci.yml`, job by job

| Job | Runs when | Does | On your machine |
|---|---|---|---|
| `changes` | always | decides which parts changed (below) | |
| `workflows` | always | actionlint on the workflows, with shellcheck on every `run` block | `docker run --rm -v "$PWD:/repo" -w /repo rhysd/actionlint:1.7.12 -color` |
| `wheel` | the backend, search or smoke part changed | builds the Rust module `ma_law` once (maturin) and hands it to the other jobs as the artifact `ma-law-wheel`; cached by the hash of `crates/` | the `maturin build` line below |
| `backend` | backend | ruff; Django's checks, also `--deploy` on the production settings; `makemigrations --check`; the test suite; the sample loaded into an empty database | `tools/ci/backend.sh all` (or `lint`, `check`, `test`, `sample`) |
| `search` | search | the tests that need ParadeDB, against the server's image | `tools/ci/search.sh` with `TEST_DATABASE_URL` (below) |
| `web` | web | eslint with no warning allowed, `tsc -b`, the node tests and the shared vectors, the build, the first load's byte budget, the renderer's build | `tools/ci/web.sh all` (or `lint`, `types`, `test`, `build`, `budget`, `ssr`) |
| `smoke` | backend or web | the site booted on the sample (Django, the renderer, the built web), two law pages drawn by the renderer, a browser walking it | `tools/ci/smoke.sh` |
| `crates` | crates | the Rust crates' tests | `(cd crates && cargo test --locked)` |
| `secrets` | always | gitleaks over the whole history, with the allowance in `.gitleaks.toml` | `docker run --rm -v "$PWD:/repo" zricethezav/gitleaks:v8.30.1 git /repo --config /repo/.gitleaks.toml --redact` |
| `licences` | always | reuse lint: every file has its licence and copyright (`REUSE.toml`), every licence its text; then `tools/ci/names.py`: no earlier name of the project in the public tree but what `tools/ci/names-allowed.txt` lets through | `docker run --rm -v "$PWD:/data" fsfe/reuse:6.3.0 lint`, then `tools/ci/names.py` |
| `publish-gate` | in the private repository only (where `tools/publish/private-words.txt` exists) | the public tree exported as a draft and scanned | `tools/ci/publish-gate.sh` |
| `cla` | pull requests | the description holds the contributor agreement's line, or the author has a merged pull request already | |
| `gate` | always, last | fails when a job it needs failed or was cancelled; a job skipped because its files did not change counts as passed | |

**The parts.** `changes` compares the commit with a pull request's base, a push's previous tip, or, for a new
branch, where it left the default branch:

| Part | Paths | Its jobs |
|---|---|---|
| backend | `back/`, `crates/`, `deploy/`, `web/src/`, `web/public/`, `web/scripts/` (the backend's tests read the topics' rules, the routes and nginx's files) | `wheel`, `backend` |
| web | `web/`, `crates/`, `back/apps/blog/`, `back/apps/topics/` (the web's tests read the shared vectors, the posts and the topics' rates) | `web` |
| crates | `crates/` | `crates` |
| search | `back/apps/search/`, `back/apps/mcp/`, `back/apps/topics/`, and what their tests stand on: `back/apps/corpus/`, `back/apps/oauth/`, `back/config/`, `back/conftest.py`, `back/requirements/`, `crates/` | `wheel`, `search` |
| smoke | `back/`, `crates/`, `web/` | `wheel`, `smoke` |

A change to `.github/` or `tools/ci/` counts as every part, and so does a run with nothing to compare with: a run by
hand, the first push of a repository, a force-push whose old tip is gone. A change to the documentation alone runs
`workflows`, `secrets`, `licences` and `publish-gate`.

### `nightly.yml`, job by job

| Job | Does | On your machine |
|---|---|---|
| `audit-python` | pip-audit on the hashed lock (`back/requirements/lock.txt`) | `pip-audit --strict --disable-pip --require-hashes -r back/requirements/lock.txt` |
| `audit-web` | `npm audit` (high and critical fail) and the registry's signatures on the installed packages | `(cd web && npm audit --audit-level=high && npm audit signatures)` |
| `audit-rust` | cargo audit on `crates/Cargo.lock` | `(cd crates && cargo audit)` |
| `wasm` | the browser's reader rebuilt from `crates/` with the compiler and wasm-pack it was built with, compared byte for byte with the committed one, then checked against the shared vectors | `npm --prefix web run build:wasm && git diff --exit-code web/src/shared/wasm/ma_law/` |
| `search` | as in `ci.yml`, every night | `tools/ci/search.sh` |
| `loops` | the suite with `--query-loops`, compared with the kept list | `tools/ci/loops.sh` |
| `coverage` | the suite with coverage, above its floor; the report is kept as the artifact `coverage-reports` | `tools/ci/coverage.sh` |
| `smoke` | as in `ci.yml`, every night | `tools/ci/smoke.sh` |

## Running a job on your machine

The scripts install nothing and need no network. Set the machine up once, as CI does:

```bash
sudo apt-get install --no-install-recommends $(sed 's/#.*//' back/requirements/apt.txt)   # FriBiDi, Tesseract, ffmpeg
python3.13 -m venv back/.venv
back/.venv/bin/pip install --require-hashes --no-deps -r back/requirements/lock.txt   # CI's packages, by their hashes
back/.venv/bin/maturin build --release --locked -m crates/ma-py/Cargo.toml -o crates/target/wheels   # as the wheel job
back/.venv/bin/pip install --no-deps --force-reinstall crates/target/wheels/ma_law-*.whl
(cd web && npm ci)
(cd web && node_modules/.bin/playwright install --only-shell chromium)               # for the smoke only
```

A test that needs one of the system packages says so (`@pytest.mark.needs('tesseract')`). On a machine without it
the test is skipped and names what is missing; in CI (`CI=true`) a missing one stops the run before its first test,
so a green run never hides a check that did not run. A new system need is one line in `back/requirements/apt.txt`
and one in `NEEDS` (`back/conftest.py`).

The web's tests hold one check of the same kind. Morocco went back to Greenwich's time on 20 September 2026, and a
Node whose time zone data is older than the release 2026c (`node -p process.versions.tz`) still counts it an hour
ahead. On such a machine `web/tests/today.test.ts` skips that one check and says to update Node; in CI it runs. A
Node 22 can still carry older data (22.23.2 carries 2026a): there the skip is expected until a release of the 22 line
carries 2026c.

Then any job is one command from any folder: `tools/ci/backend.sh all`, `tools/ci/web.sh all`, `tools/ci/smoke.sh`.
Each script says what it does with `--help`, prints each command before it runs it (`+ …`), and stops at the first
failure. `PYTHON` names another interpreter (default `back/.venv/bin/python`). `WORKERS` caps pytest-xdist's processes
for `backend.sh test` (default: one per core; the suite takes about four minutes on four).

The search tests need PostgreSQL with ParadeDB, the image the server runs:

```bash
docker run -d --name law-ci-pg -p 127.0.0.1:5433:5432 -e POSTGRES_USER=law -e POSTGRES_PASSWORD=law \
  -e POSTGRES_DB=law paradedb/paradedb@sha256:c552094b6b68dcb0a4e7a3969963d801eaec02490db4d2dd032dcb096bc86cf8
TEST_DATABASE_URL=postgres://law:law@127.0.0.1:5433/law tools/ci/search.sh
```

## Reading a failure

1. **The run's page.** The `gate` job's summary lists every job with its result. Open the one that failed.
2. **The job's summary** (at the foot of the run's page) gives its result, the command that runs the same check on
   your machine, and, for the Python tests, the tests that failed.
3. **The job's log.** Each script prints the command it is about to run; the last `+ …` line before the error is the
   one that failed.
4. **The artifact `<job>-reports`**, kept 14 days when a job did not pass: the job's whole log, what its script left
   in `back/.reports` (pytest's JUnit files, coverage's report), and for the smoke the services' logs and a screenshot
   of each step the browser took. Locally, the backend's scripts leave the same files in `back/.reports`, and a failed
   smoke keeps its folder and prints where it is.
5. **Run the command on your machine.** It gives the same answer; if it does not, the difference is in the machine
   (a package outside the lock, a missing `ma_law` rebuild, another Python), and that is the bug.

Some jobs fail in their own way:

- **`changes`** decides what runs; its summary shows each part. To run every job, run the workflow by hand (Actions,
  CI, Run workflow).
- **`cla`**: add the agreement's line to the pull request's description, on a line of its own, then re-run the job:
  it reads the description as it is now.
- **`secrets`**: a finding is printed redacted, with its file, line and commit. A real secret is revoked first, then
  removed from the history. A false positive gets `gitleaks:allow` in a comment at the end of its line, or, for a
  whole shape of value, a narrow allowance in `.gitleaks.toml` with its reason.
- **`licences`**: a new file whose licence is not the application's (AGPL-3.0-only, the default) gets its line in
  `REUSE.toml`.
- **`publish-gate`** (in the private repository only): each line printed with its class must change before
  publishing (the public tree names no person, no machine and no home path); a file that is private as a whole is
  marked `export-ignore` in `.gitattributes` instead, a file the public tree does not have.
- **What `npm ci` prints** (moderate advisories, a deprecated package): judged at night, where `audit-web` fails on
  high and critical advisories only; a moderate one is updated in its own change once a fix exists.
- **An audit, at night**: update the package in a change of its own (`back/requirements/lock.sh` for Python,
  `npm update <name>` in `web/`, `cargo update -p <name>` in `crates/`). When no fixed version exists yet, the
  advisory may be ignored in the job by its identifier, with a dated reason, until one does.
- **`wasm`, at night**: run `crates/build.sh` with the job's compiler and wasm-pack (in `nightly.yml`) and commit
  the files it writes in `web/src/shared/wasm/ma_law/`.

## The query loops' list and the coverage floor

`tools/ci/loops.sh` runs the suite with `--query-loops`, which notes every line that runs one query again and again
in one call, and compares the functions it found with the kept list, `back/config/queryloops-kept.txt` (by file and
function, never by line). A function that is not on the list fails the night: its `NEW` line names it, the query and a
test that reaches it, and `back/.reports/loops.json` (in the artifact) has the whole survey. Fix it first: a list
reads its rows' related data in a fixed number of queries (`docs/rules.md`, «No query inside a loop»), with a test
that gives the code a few rows and ten times as many and expects the same count. A loop kept on purpose is written
into the list with `tools/ci/loops.sh --update`, which also drops the ones no longer found; commit the list with the
reason in the commit message.

`tools/ci/coverage.sh` runs the suite with coverage of lines and branches, writes `back/.reports/coverage.xml`
(Cobertura, kept as the artifact `coverage-reports` every night) and each app's figure, and fails when the total falls
under the floor: `fail_under` in `back/.coveragerc`. Raise the floor when coverage rises, in the change that raises
it; never lower it to make a change pass, only when it was set too high, in a commit that says why.

## Pinned actions and images

- Every action is named by its full commit hash, with its version in a comment on the same line
  (`actions/checkout@3d3c42e… # v7.0.1`): a tag can be moved, a commit cannot. Only GitHub's own actions
  (`actions/*`) are used; anything else is a few lines of shell or a pinned image. Dependabot proposes their updates
  and moves the hash and the comment together.
- The runner's image is named by its version (`runs-on: ubuntu-24.04`), never `ubuntu-latest`, which moves to the
  next Ubuntu when GitHub decides: the first run met Ubuntu 26.04, where the pinned Playwright cannot install its
  browser. Move every job to a newer image in a change of its own, once the tools support it.
- The local actions in `.github/actions/` hold the steps several jobs share: `wheel` (build or take `ma_law`),
  `back-env` (Python, the lock, the wheel), `web-env` (Node, `npm ci` without install scripts, headless Chromium)
  and `report` (the summary and the reports artifact).
- The images a step runs (actionlint, gitleaks, reuse) and the ParadeDB service are pinned by digest, with their
  version in a comment; Dependabot does not see them. To update one, pull the new version, read its digest with
  `docker inspect --format '{{index .RepoDigests 0}}' <image>:<version>`, and change the digest and the comment
  together. ParadeDB's digest is the one in `deploy/compose.yml`: the tests run on the server's engine.
- The tools the nightly run builds or installs (pip-audit, cargo-audit, the wasm compiler and wasm-pack) have their
  versions in `nightly.yml`.

## Dependabot

Dependency updates are proposed and merged in the private repository this one is exported from, and reach it with
the next export: its file, `.github/dependabot.yml`, is not in the public tree. There, every Monday, one pull request per ecosystem (Python, the web, the crates, the actions) for its minor and patch
updates, and one per major update. A version is proposed once it is a week old. Security updates come as soon as
their advisory, alone. After a Python update, run `back/requirements/lock.sh` and commit `lock.txt` if it changed:
Dependabot moves the pins it finds, while `lock.sh` resolves the three requirement files together.

It reads its file from the default branch only. An ecosystem keeps at most two
proposals open, and none is rebased by itself when the branch moves: each rebase would run the checks again, on
the account's minutes. Comment `@dependabot rebase` on a proposal when you take it up.

## The local hook

```bash
git config core.hooksPath tools/dev/hooks
```

At each commit, on the staged files only: the publishing scan on the staged contents (where the private word list
exists), ruff on the Python files, eslint on the web's files and actionlint on the workflows. A tool that is not
installed is skipped with a line saying so; the hook never blocks for a missing tool. `git commit --no-verify` skips
it, and CI checks everything again.

## What a maintainer sets on GitHub

- **A branch rule** (a ruleset on the default branch) that requires the status check `gate`, and no other: the jobs
  behind it come and go with the paths, `gate` is always there. On the public repository, the rule also requires a
  pull request and blocks force-pushes. A private repository on GitHub's free plan can have neither a ruleset nor
  branch protection (the settings answer «Upgrade to GitHub Pro or make this repository public»): until then `gate`
  is the one result to read after a push, and nothing stops a red commit.
- **Actions' permissions** (Settings, Actions, General): the workflow token read-only by default («Read repository
  contents and packages permissions»), Actions not allowed to create or approve pull requests, only actions created
  by GitHub allowed, and actions required to be pinned to a full commit hash. On the public repository, approval
  required before a first-time contributor's workflows run.
- **Dependabot** (Settings, Advanced Security): alerts on; version updates follow `.github/dependabot.yml`, in the
  private repository.
- **Secret scanning and push protection** on. They are free on a public repository; on a private one they need
  GitHub's paid security product, and the `secrets` job is the check there.
- **Who hears of a red night**: GitHub tells the last person who changed the `schedule` line of `nightly.yml`. On a
  public repository, GitHub stops the schedule after 60 days without activity; a push or a run by hand starts it again.
- **Minutes**: a private repository spends the account's included minutes on every job; GitHub's standard runners
  cost nothing on a public one. A push that touches every part bills about 25 minutes, a nightly run about 50:
  in a private copy, switch `nightly.yml` off in the repository's settings and run it by hand.

No workflow uses a secret, and none runs on `pull_request_target`: a pull request's code never runs with write access.

## Left out, for now

- **A workflow that publishes the public tree.** The public repository is an export of a private one
  (`docs/running.md`, «Publishing the public tree»): `tools/publish/export.sh` writes the tree, and a person decides
  each export.
- **CodeQL.** It is free on a public repository: its default setup is switched on in the settings, not here.
- **Deploying from CI.** The server is deployed by hand.
