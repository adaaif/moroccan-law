"""A name's place inside a folder, or none.

A slug, a file's name or a date that comes from an address is checked where it is read (a URL converter, a pattern, a
list of known names). This is the second lock, at the door of the file system: the name is joined to its folder, the
path is normalised, and it is given back only if it still lies inside that folder. «..», an absolute path or a
separator smuggled in a name all come back as None."""
import os
from pathlib import Path


def inside(base, *parts: str) -> Path | None:
    root = os.path.normpath(str(base))
    full = os.path.normpath(os.path.join(root, *parts))
    if not full.startswith(root + os.sep):
        return None
    return Path(full)
