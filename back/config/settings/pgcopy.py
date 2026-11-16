"""Dev settings with the SQLite file as a second database ('sqlite'), for scripts/copy_sqlite_to_postgres.py.
DATABASE_URL must point 'default' at Postgres."""
from .dev import *  # noqa: F403

DATABASES['sqlite'] = {  # noqa: F405
    'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
    'OPTIONS': {'timeout': 60},
}
