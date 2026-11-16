# The database's format: its changes

The manifest's `format` names the format an edition was written in. A new field, a field renamed or a new file makes a
new format; an edition is served only in the current one.

## Format 2 (16 November 2026)

- Six files of JSON lines: `versions.jsonl.gz` (every version of a text through time but its newest),
  `french.jsonl.gz` (the official French, article by article), `changes.jsonl.gz` (which text changes which, in every
  state, the unclear and conflicting ones included), `issues.jsonl.gz` (the Bulletin's issues held) and
  `aliases.jsonl.gz` (older addresses), beside `texts.jsonl.gz`, whose records keep their shape.
- A text's `source` gains `edition` and `sha256` (the Bulletin file it was read from); a version gains `file` (the file
  its words were read from) and `pages`.
- `README.md`, `schema.json` (a JSON Schema for one line of each file) and this file.
- The manifest says `format`, counts `versions`, and gives each JSON-lines file's `lines` and the zip's `entries`.
  `GET /api/open/` gives the manifest's own SHA-256 and every edition's.
- The licence says that machine consolidations and translations made by artificial intelligence are marked and are
  not official, and that personal data the Bulletin prints is the recipient's responsibility under law 09-08.

## Format 1 (until November 2026)

`texts.jsonl.gz`, `akn.zip`, `LICENCE.txt` and a manifest without a `format`. Its editions are no longer served.
