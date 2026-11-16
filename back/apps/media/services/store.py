"""The bytes on disk under UPLOADS_DIR/<kind> (voices, pictures, cards): never a public folder. Names are random;
a name that escapes its folder is refused."""
import contextlib
import uuid
from pathlib import Path

from django.conf import settings

KINDS = ('voices', 'pictures')


def _root(kind: str) -> Path:
    assert kind in KINDS  # noqa: S101 — the callers name one of KINDS; no reader's words reach it
    return (Path(settings.UPLOADS_DIR) / kind).resolve()


def write(kind: str, data: bytes, ext: str) -> str:
    root = _root(kind)
    root.mkdir(parents=True, exist_ok=True)
    name = f'{uuid.uuid4().hex}.{ext}'
    tmp = root / f'.{name}.tmp'
    tmp.write_bytes(data)
    tmp.replace(root / name)
    return name


def path_of(kind: str, name: str) -> Path:
    root = _root(kind)
    path = (root / Path(name).name).resolve()
    if not name or path.parent != root:
        raise ValueError('the name escapes its folder')
    return path


def delete(kind: str, name: str) -> None:
    """Erase the bytes; a file already gone is fine, the row is the truth."""
    if not name:
        return
    with contextlib.suppress(OSError, ValueError):
        path_of(kind, name).unlink()
