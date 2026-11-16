"""What the archive run's parts share: the one model it pays for, an issue's work folder, the plan, an issue by its
key, and a page whose words read as a table of contents."""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError

from apps.sources.models import Edition, Issue
from apps.sources.services import archive, witness


MODEL = 'claude-haiku-5-5'


def workdir(key: str) -> Path:
    path = Path(settings.CORPUS_DIR) / 'reports' / 'issues' / key
    path.mkdir(parents=True, exist_ok=True)
    return path


def plan() -> dict:
    path = archive.root() / 'plan.json'
    if not path.exists():
        raise CommandError(f'{path} is missing: copy the plan there first.')
    return json.loads(path.read_text())


def issue_of(key: str, edition: str = Edition.GENERAL_AR) -> Issue | None:
    number, suffix = Issue.parse_key(key)
    return (Issue.objects.select_related('document')
            .filter(edition=edition, number=number, suffix=suffix).first())


def looks_like_contents(text: str) -> bool:
    lines = [line for line in text.splitlines() if witness.letters(line) >= 8]
    return bool(lines) and sum(1 for line in lines if witness._REF.search(line)) / len(lines) >= 0.3
