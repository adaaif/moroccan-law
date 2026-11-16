"""The archive run's parts (`manage.py archive`, the Bulletin-to-1956 review): the command in
apps/corpus/management/commands/archive.py is these classes together, each holding the methods of one subject.

- `common`: the one model the run pays for, an issue's work folder, the plan, an issue by its key;
- `exchange`: `archive export` and `archive import`, an issue carried between machines;
- `issues`: `archive register`, `archive queue` and `archive order`, the plan's issues;
- `work`: `archive work <phase>`, the issues a phase takes a chunk at a time, and `archive retry`;
- `steps`: each phase's step on a chunk (pilot, catalog, read, fix, texts);
- `measures`: `archive status` and `archive report`.
"""
