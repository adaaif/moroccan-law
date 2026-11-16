# Contributing

Thank you for helping. Corrections of the law's text, fixes, tests and translations are all welcome.

## Before you start

- Read `docs/rules.md`: the rules every change keeps (official sources only, one error shape, no query inside a
  loop, Arabic first, no business logic in views).
- For anything larger than a fix, open an issue first and say what you want to change and why.
- A comment that cites `P18 of the polish review` points at a decision listed in `docs/decisions.md`.
- A security flaw goes to the address in `SECURITY.md`, never to a public issue.
- A question: open a blank issue and say in its title that it is one.

## A change

1. Run the site on the sample (README, «Quick start»).
2. Make the change, with a test that fails before it and passes after. Tests sit in `back/apps/<app>/tests/` (pytest)
   and `web/tests/` (Node's test runner).
3. Run what CI runs, the same scripts (`docs/ci.md` has the rest):
   ```bash
   tools/ci/backend.sh all                  # when you touched back/
   tools/ci/web.sh all                      # when you touched web/
   (cd crates && cargo test --locked)       # when you touched crates/
   ```
   `git config core.hooksPath tools/dev/hooks` switches on a hook that runs the quick ones on each commit's files.
4. Open a pull request. Say what was wrong, what it does now, and anything a deploy must do.

## Kinds of change

- **The law's words.** A misread word is corrected against the page image of the Bulletin, never from memory or from
  another site. Open an issue with the form «A word of the law read wrong»: the article's address, what the site
  shows, what the page prints, and the Bulletin's issue and page. On the site, «⋯» beside an article's number, then
  «تبليغ عن خطأ» («Signaler une erreur»), sends the same report from the article itself; and
  https://3adala.com/open-source shows the words the reading doubts, one at a time, for anyone to settle against the
  page. A fix is a YAML file in `back/apps/quality/data/`, applied by `apply_page_reading` (`docs/pipeline.md`,
  «Corrections against the page images»): corrections are recorded, never typed into the text.
- **Code.** Keep to the house style: plain names, short functions, comments that say what the code does and why. A
  public endpoint keeps its query-ceiling test.
- **Words on the site.** Every string is in both `ar.json` and `fr.json` with the same keys. French addresses the
  reader as `vous`.
- **Dependencies.** Add one only when the work needs it. Python packages are named in `back/requirements/` and
  locked, with their hashes, in `lock.txt`; run `back/requirements/lock.sh` to update it.
- **The Rust crates.** Run `crates/build.sh`: it builds the Python module and the browser's reader, and checks both
  against `crates/vectors/`. Commit the rebuilt files in `web/src/shared/wasm/ma_law/`. It needs the compiler and
  wasm-pack of `nightly.yml`'s `wasm` job, which rebuilds the reader and compares it byte for byte:
  `rustup toolchain install 1.99.1 --target wasm32-unknown-unknown`, `cargo install wasm-pack --locked --version
  0.15.0`, then `RUSTUP_TOOLCHAIN=1.99.1 crates/build.sh`. Another compiler writes other bytes.

## What is wanted, and what is not

**Wanted:** corrections read against the Bulletin's pages, the official French where the site lacks it, tests, speed,
accessibility, the search test sets.

**Out of scope:** a chat, or any model that answers readers; texts from a private legal database; legal advice; a
topic's words shown as checked before a person has checked them; anything `docs/decisions.md` lists as answered no.

## The contributor agreement

Every contribution is accepted under the contributor agreement in `CLA.md`. You keep the copyright in your work; you
grant the project the right to use it under this repository's licences and under other terms.

**The agreement is still a draft.** No lawyer has read it yet, and `CLA.md` says so in its first line. If its words
change, contributors are asked again.

Your contribution is published under the licence `REUSE.toml` gives its path: AGPL-3.0-only for code, CC-BY-NC-SA-4.0
for a topic's or the blog's words, ODbL-1.0 for data. The agreement also lets the Project Owner use it under other
terms, commercial ones included, which the NC licence does not give anyone else.

Say in your first pull request that you agree to `CLA.md`, by adding a line to its description:

```
I have read CLA.md and I agree to it for this contribution and my later ones.
```

The pull request's `cla` check looks for that line. If you add it after opening the pull request, re-run the check.

## Conduct

Everyone who takes part follows `CODE_OF_CONDUCT.md`.
