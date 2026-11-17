"""The editions of the database on disk: which may be served, which is the newest, the dated record of their hashes,
and which are let go when a new one is written.

An edition is a folder `OPEN_DATA_DIR/<YYYY-MM-DD>/` that `export_open_data` wrote. It is listed only when its
manifest says the current format and a licence that begins «ODbL»: folders written before (under another licence, in
another format) stay where they are, never served and never deleted. `latest` is the newest listed.

`OPEN_DATA_DIR/editions.jsonl` holds one line an export: the edition's date, its manifest's SHA-256 and its counts. It
outlives the folders, so an edition let go can still be proved by its hash."""
import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings

from config.inside import inside

# The format the export writes (the manifest's `format`, CHANGELOG.md). An edition of another format is not served.
FORMAT = 2
LICENCE = 'ODbL'
KEEP = 3                    # editions kept on disk when a new one is written
LOG = 'editions.jsonl'

# The files that describe an edition, given to anyone unless the position is closed, and the data files.
DESCRIBE = {'manifest.json': 'application/json', 'LICENCE.txt': 'text/plain; charset=utf-8',
            'README.md': 'text/markdown; charset=utf-8', 'schema.json': 'application/json',
            'CHANGELOG.md': 'text/markdown; charset=utf-8'}
DATA = {'texts.jsonl.gz': 'application/gzip', 'versions.jsonl.gz': 'application/gzip',
        'french.jsonl.gz': 'application/gzip', 'changes.jsonl.gz': 'application/gzip',
        'issues.jsonl.gz': 'application/gzip', 'aliases.jsonl.gz': 'application/gzip',
        'akn.zip': 'application/zip'}
DAY = re.compile(r'\d{4}-\d{2}-\d{2}')


@dataclass(frozen=True)
class Edition:
    date: str
    folder: Path
    manifest: dict
    sha256: str             # the manifest file's own hash, as written

    def file(self, name: str) -> dict | None:
        """What the manifest says of one of its files: its bytes, its hash and, for JSON lines, its lines."""
        return self.manifest.get('files', {}).get(name)


def root() -> Path:
    return Path(settings.OPEN_DATA_DIR)


def servable(manifest) -> bool:
    """Written by the export under today's licence and in today's format."""
    return (isinstance(manifest, dict) and manifest.get('format') == FORMAT
            and str(manifest.get('licence', '')).startswith(LICENCE))


def read(folder: Path) -> Edition | None:
    """The edition a folder holds, when it is one that may be served."""
    if not DAY.fullmatch(folder.name) or folder.is_symlink() or not folder.is_dir():
        return None
    try:
        data = (folder / 'manifest.json').read_bytes()
        manifest = json.loads(data)
    except (OSError, ValueError):
        return None
    if not servable(manifest) or manifest.get('date') != folder.name:
        return None
    return Edition(folder.name, folder, manifest, hashlib.sha256(data).hexdigest())


def listed() -> list[Edition]:
    """Every edition that may be served, the newest first."""
    if not root().is_dir():
        return []
    found = (read(folder) for folder in sorted(root().iterdir(), reverse=True))
    return [edition for edition in found if edition]


def latest() -> Edition | None:
    return next(iter(listed()), None)


def find(name: str) -> Edition | None:
    """`latest` or a date: the edition, when it may be served."""
    if name == 'latest':
        return latest()
    folder = inside(root(), name) if DAY.fullmatch(name or '') else None
    return read(folder) if folder else None


def record(edition: Edition, counts: dict) -> None:
    """One line for the edition just written in the dated record of hashes."""
    line = {'date': edition.date, 'sha256': edition.sha256, **counts}
    with open(root() / LOG, 'a', encoding='utf-8') as log:
        log.write(json.dumps(line, ensure_ascii=False) + '\n')


COUNTS = ('texts', 'articles', 'versions')


def history(counts: bool = False) -> list[dict]:
    """Every edition ever written in today's format, with its manifest's hash, the newest first: the record's lines,
    and an edition on disk the record lacks (one copied by hand). With `counts`, each says its texts, articles and
    versions too, as recorded (None where a line does not say)."""
    seen, out = set(), []
    try:
        lines = (root() / LOG).read_text(encoding='utf-8').splitlines()
    except OSError:
        lines = []
    for line in lines:
        try:
            entry = json.loads(line)
            pair = (str(entry['date']), str(entry['sha256']))
        except (ValueError, KeyError, TypeError):
            continue
        if pair not in seen:
            seen.add(pair)
            out.append({'date': pair[0], 'sha256': pair[1],
                        **({k: entry.get(k) for k in COUNTS} if counts else {})})
    for edition in reversed(listed()):
        if (edition.date, edition.sha256) not in seen:
            out.append({'date': edition.date, 'sha256': edition.sha256,
                        **({k: edition.manifest.get(k) for k in COUNTS} if counts else {})})
    # The newest day first; of two lines of one day (an export run twice), the later.
    return [e for _, e in sorted(enumerate(out), key=lambda pair: (pair[1]['date'], pair[0]), reverse=True)]


def prune(keep: int = KEEP) -> list[str]:
    """Let go of the editions past the newest `keep`. Only folders this format's export wrote are removed."""
    gone = []
    for edition in listed()[keep:]:
        shutil.rmtree(edition.folder)
        gone.append(edition.date)
    return gone
