# The database of @SITE@ («قانون»), format @FORMAT@

قاعدة بيانات «قانون»: كل نص من نصوص الجريدة الرسمية للمملكة المغربية، مادة مادة، بكل نسخه عبر الزمن، مع ترجمته
الفرنسية الرسمية حيث توجد، والصفحة التي طُبعت فيها كل مادة، وأيّ نص عدّل أيّ نص. وحده النص المنشور في الجريدة
الرسمية يُعتدّ به.

La base de données de «قانون» : chaque texte du Bulletin officiel du Royaume du Maroc, article par article, avec toutes
ses versions dans le temps, sa traduction officielle en français quand elle existe, la page où chaque article a été
imprimé, et quel texte en modifie quel autre. Seul le texte publié au Bulletin officiel fait foi.

The rest of this file is in English: it names the files and their fields.

## An edition

An edition is the database as it stood on one day, written on the first day of each month. Its folder holds:

| File | One line is |
|---|---|
| `texts.jsonl.gz` | a text: its facts, its newest version with its articles, the changes it makes that are settled, the texts it cites |
| `versions.jsonl.gz` | another version of a text (every version but the one `texts.jsonl.gz` carries), with its articles |
| `french.jsonl.gz` | the official French of a text, article by article, with the Bulletin issue that printed it |
| `changes.jsonl.gz` | one change to one article: which text makes it, in which issue, from when, its source and its state |
| `issues.jsonl.gz` | an issue of the Bulletin held, with its file's hash and page count |
| `aliases.jsonl.gz` | an older address of a text, and the address it leads to |
| `akn.zip` | not lines: one Akoma Ntoso 3.0 XML file a text, its newest version |
| `manifest.json` | not lines: the edition's date, its format, its counts, and each file's bytes, SHA-256 and lines |
| `schema.json` | not lines: a JSON Schema for one line of each `.jsonl.gz` file |
| `LICENCE.txt`, `README.md`, `CHANGELOG.md` | not lines: the licence, this file, the format's changes |

Each `.jsonl.gz` file is gzip-compressed UTF-8, one JSON object a line. Read it a line at a time: the texts file alone
holds hundreds of thousands of articles.

No article's words are written twice across files: a text's newest version is in `texts.jsonl.gz` only, its other
versions in `versions.jsonl.gz`. Each version is whole, so an article that did not change between two versions is in
both.

## Checking a copy

`manifest.json` gives each file's SHA-256 (`sha256sum texts.jsonl.gz`). The manifest's own SHA-256 is given beside it
at `GET @SITE_URL@/api/open/` (`sha256`, and `editions`: every edition's date and manifest hash). An access given the
database may also ask for `RECEIPT.txt`: a receipt naming its holder, the edition and the manifest's hash.

## The kinds of version

Every version names its kind (`version.kind`). **Only `as_published` is the official text**, and only as the Bulletin
printed it: the rest are aids to reading.

| Kind | What it is |
|---|---|
| `as_published` | the text as the Bulletin printed it, read from the issue's file |
| `machine` | consolidated by machine: the text with the changes later texts make to it applied by code (unofficial) |
| `checked` | consolidated and checked by a person (unofficial) |
| `sgg` | the consolidation of the General Secretariat of the Government (for information; the Bulletin prevails) |
| `adala` | the consolidation of Adala, the Ministry of Justice's portal (for information; the Bulletin prevails) |
| `dgi` | the tax administration's yearly edition of the tax code (for information; the Bulletin prevails) |
| `bill` | a bill as filed in Parliament or as a chamber voted it: not law |
| `translation` | an Arabic text made by artificial intelligence from the official French, where the Arabic issue is not held: not the official text |

## Fields

Dates are `YYYY-MM-DD`. A field the record has nothing for is `null` (a string field read as printed may be `""`).
Addresses come twice: `akn_uri`, the text's Akoma Ntoso work address (`/akn/ma/act/loi/65-99`), and `path`, its address
on the site (`/ma/loi/65-99`: prefix it with @SITE_URL@). They stay the same across editions.

### An article (in `texts` and `versions`)

- `eid`: the article's id in the text (`art_8`); `path`: its address on the site.
- `label`: as printed («المادة 8», «الفصل 488»); `number`: normalised (`8`, `618-1`, `5-bis`).
- `heading_path`: the headings above it (book, title, chapter, section), outermost first.
- `page`: the printed page of the Bulletin it starts on, when known.
- `body`: its words as read, in a light Markdown: each line a paragraph, `**…**` around words printed in bold, a
  table as lines of cells between `|`.

### A version (`version`, in `texts` and `versions`)

- `kind`: above. `language`: `ar` or `fr`. `translated_from`: for a `translation`, the language it was made from.
- `valid_from`, `valid_to`: the days the version stands between (`valid_to` is `null` while it stands).
- `file`: the file its words were read from, by its `source` (`sgg_bo` the Bulletin, `adala`, `sgg_consolidated`,
  `dgi`…) and SHA-256; `null` for a version built rather than read (a machine's consolidation).
- `pages`: the printed pages it was read from, as `1112-1118`.

### `texts.jsonl.gz`

- `akn_uri`, `path`, `type` (`law`, `dahir`, `decree`, `order`…), `number` (as printed: `65.99`), `title` (Arabic).
- `signed_on`, `signed_on_hijri` (as printed), `authority` (who issued it), `status` (`in_force`, `partly_repealed`,
  `repealed`, `not_yet_in_force`, `unknown`: as the site reads it from the changes it holds).
- `source`: the issue that first printed it: `issue` (`7533`, `7465-bis`), `edition` (`general_ar`…), `date`, `page`
  (its first printed page), `sha256` (the issue's file).
- `version`: the version this record carries, its newest in force today; `articles`: that version's articles.
- `citation`: the text's reference as Moroccan lawyers write it.
- `amends`: the changes this text makes to others that are settled (`state` `checked`, `confirmed` or `read`); every
  change, settled or not, is in `changes.jsonl.gz`.
- `cites`: the texts it cites, by `akn_uri`.

### `versions.jsonl.gz`

`akn_uri`, `path`, `version`, `articles`: as above. A text's versions come together, the oldest first.

### `french.jsonl.gz`

- `akn_uri`, `path`: the Arabic text's addresses. `type`, `number`, `title` (French), `signed_on`.
- `source`: the issue of the Bulletin's French edition (`translation_fr`) that printed it: `issue`, `date`, `pages`,
  `sha256` (the issue's file).
- `consolidated_to`: when set, the French stands as consolidated at that date, not as the issue printed it: an article
  changed since may be older than its Arabic.
- `articles`: `label` (as printed: «Article premier»), `number` (as the Arabic article's, to join the two), `page`,
  `body`. The Arabic alone is authoritative; the French is the official translation.

### `changes.jsonl.gz`

- `target`, `target_path`: the text changed; `article`: the article changed (`null` for the whole text).
- `action`: `modified`, `added`, `replaced` (repealed and replaced), `repealed`, `words` (words replaced).
- `by`: the text that makes the change: `akn_uri` and `path` when the site holds it, `kind`, `number`, `article` (its
  article that makes the change, as printed).
- `issue`, `page`, `published_on`: where and when the change was published; `takes_effect` and `effective_rule`
  (`publication`, `stated`, `after` a delay, on a `condition` no date can be read for).
- `source`: `reading` (read in the amending text in the Bulletin), `sgg`, `adala`, `dgi` (what that official
  consolidation's note states), `bill` (proposed by a bill).
- `state`, for a reading: `checked` (by a person), `confirmed` (the reading and another source agree), `read` (read,
  nothing against it), `conflict` (a source disagrees), `unclear` (the code could not read or place it: marked, never
  guessed and never hidden); `proposed` for a bill's (not law, never applied); `null` for what an official
  consolidation's note states.

### `issues.jsonl.gz`

- `edition` (`general_ar` the authoritative Arabic, `translation_fr` the official French, `conventions_ar`…), `number`,
  `suffix` (`bis`), `key` (`7465-bis`), `date`, `hijri_date` (as printed), `path` (its address on the site).
- `first_page`: its first printed page (pages run on through a year); `copy_of`: the issue whose cover bears this
  number too, when this one is its copy.
- `file`: the issue's file: `sha256`, `pages`, `bytes`, `url` (where it was fetched from).

### `aliases.jsonl.gz`

`alias` and `alias_path` (an older address), `akn_uri` and `path` (the text it leads to), `reason`: `moved` (its
address before addresses were worked out from kind and number), `merged` (a twin merged into it), `dahir` (the dahir
that promulgated it), `copy` (the same text cut from a copy of its issue), `twin` (the same printed text cut twice).

## What is not here

The accounts and everything people wrote on the site (the discussion, explanations), the topics (their guides,
journeys and tools), search logs, drafts, the page images and the Bulletin's files themselves (only their hashes), a
version's visas and signatures, and the changes read only by a model (a witness, never placed alone).

## How to cite

Credit @ADDRESS@ and each text's source: its Bulletin issue and date. The `citation` field gives
a text's reference in Arabic. Reuse cites the source and its date and never distorts the text (law 31-13, art. 6).

## Licence and personal data

`LICENCE.txt` holds the licence: the official texts carry no copyright (law 2-00, art. 8); the database built from
them is under the Open Database License 1.0. What the Bulletin prints about named people in individual decisions is
personal data: whoever receives this database is alone responsible for what they do with it under law 09-08.
