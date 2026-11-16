# The rules of the codebase

What every change keeps. A change that breaks one says why in its pull request.

## The law

- **Official sources only.** The texts come from the SGG (the Bulletin Officiel), Adala (the Ministry of Justice),
  the courts and the official editions of the administrations. Nothing is taken from a private legal database. Every
  fetched file is kept with its hash.
- **The Bulletin prevails.** A consolidated version is labelled unofficial and links each amending BO page. An
  amendment the machine cannot place is marked unclear, never guessed.
- **Reuse cites and never distorts.** Official texts carry no copyright (law 2-00, art. 8). Reuse cites the source
  and its date and never distorts the text (law 31-13, art. 6). Court decisions lose their names before publication
  (law 09-08).
- **What people say is linked, never the law.** The law and its figures come from official texts only. Context,
  reactions and claims may come from the press, Parliament, unions, employers and experts. Each item is labelled by
  type, dated, with its headline as printed and one attributed sentence of the project's own (never the article's
  body), and linked out; a private copy is kept with its hash, never republished. A proposal is said as one, never
  drawn as the bill. A person adds each item; no model writes one.
- **A bill is never law.** A bill is a text of its own; what it would change is kept as a proposal, never applied.
- **No chat about the law.** Language models work only inside the pipeline (reading scans, finding a text's
  structure, the search's models) and in the discussion's check before publishing. Readers see «AI»
  («الذكاء الاصطناعي»), never a model's name.

## The code

- **No business logic in views.** Services live in `back/apps/<app>/services/`. A view validates, calls a service and
  answers.
- **One error shape:** `{"errors": [{"field": ..., "code": ...}]}`. The server never sends sentences; the web
  translates `errors.<field>.<code>` in both languages.
- **No query inside a loop.** A list reads its rows' related data in a fixed number of queries (`select_related`,
  `prefetch_related`, one `__in` query, an `Exists` or `Count` annotation). A public endpoint has a test that caps its
  query count, and the cap does not grow with the data.
- **Keyed by address.** Tables outside the corpus (discussions, explanations, corrections, follows) point at a text or
  an article by its address, never by a foreign key to a corpus row: a reload recreates those rows.
- **Rust only where it pays:** text folding, citation reading, the index. Each gives the same answer at index time,
  at query time and in the browser; `crates/vectors/` checks it.
- **Don't over-engineer.** No module, abstraction or service before the work that needs it.
- **Tests never touch the real corpus.** The suite points `CORPUS_DIR` at a temporary folder (`back/conftest.py`) and
  runs with no `data/` at all.

### Names

- Readers see «3adala» in Latin letters and «قانون» in Arabic. The code reads the Latin name from `SITE_NAME` in the
  backend's settings, and from the locales' `app.name` and `shared/services/fileName.ts` in the web; the letters, the
  gate page, the assistants' names and the share cards still write «قانون المغرب» themselves (`TRADEMARKS.md` says
  where a fork replaces it).
- The code's own names say `law` or a plain word, never a brand: units, containers, storage keys, test names. Prose
  says «the site».
- The public repository is `moroccan-law`.
- `tools/ci/names.py` fails on the project's earlier names; `tools/ci/names-allowed.txt` lists, one reason a line,
  the words that only look like one.

## Languages and direction

- **Arabic first.** Pages are right to left. French is a full second language, addressing the reader as `vous`.
- **Western digits**, as the Bulletin prints them.
- Text a person types gets `dir="auto"`; emails and passwords are left to right.
- The voice recorder and player stay left to right on Arabic pages. Charts run left to right, the percent sign to
  the right of its number.

## Accounts

- Sign in with the username or the email, in any letter case. Registering signs you in.
- «Email in use» leads into that account (the sign-in page, the address filled in), never to a second account.
- A session the server refuses signs the page out once and says so. Signing out ends this device only.
- Passwords: 8 characters or more, not only digits, not a common one, not like the name. The first broken rule is the
  error's code.
- While `REGISTRATION_OPEN` is off, `POST /api/auth/register/` answers 403 `registration.closed` and the web offers no
  new account.

## The discussion

- Keyed by the article's address, never a foreign key to a corpus row.
- A voice is the person's real voice: never anonymous, never edited, converted to AAC. Pictures lose their metadata.
- Holds come from fixed patterns. A removal names one of the seven rules. Nobody decides about their own words.
- Anything new in it needs its line on `/rules` or `/privacy`.

## Commits

- History lives in git: a commit says what was wrong, what the code does now, and what a deploy must do.
- Never commit a secret. Settings come from the environment (`back/.env.example`).
