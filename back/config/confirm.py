"""A command that rewrites every row of a database, or fills it with test rows, runs only on the database its operator
names: `--yes-on <database name>`, checked against the one Django is connected to. A stranger trying the command, or
an operator whose environment points at another database than they think, changes nothing."""
from pathlib import Path

from django.core.management.base import CommandError
from django.db import connections


def database_name(using: str = 'default') -> str:
    return str(connections[using].settings_dict['NAME'])


def add_argument(parser) -> None:
    parser.add_argument('--yes-on', dest='yes_on', metavar='DATABASE', default='',
                        help='the name of the database this command will rewrite: it must be the one connected')


def confirm(given: str | None, *, what: str, using: str = 'default') -> None:
    """Nothing happens unless `given` names the connected database (a SQLite file by its path or its file name)."""
    name = database_name(using)
    if given and given in (name, Path(name).name):
        return
    raise CommandError(f'{what} rewrites rows of the database «{name}»: give --yes-on {Path(name).name} to say it is '
                       'the one meant' + (f' (not «{given}»)' if given else ''))
