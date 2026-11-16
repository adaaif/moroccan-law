"""The blog's posts («قانون بالأرقام», 31 Oct 2026): each a folder under `apps/blog/posts/<slug>/` with `meta.yaml` (its
title and lead in both languages, its date, and the facts a person read on the Bulletin's pages) and `figures.json`
(what `manage.py blog_figures <slug>` counted, frozen on the day it was counted: a post says what was true then).
Read from disk once per process; nothing here touches the database."""
import csv
import io
import json
from functools import cache
from pathlib import Path

import yaml

from apps.blog.services import (absent, agreements, ages, bulletin, deadlines, death, emergency, expropriation, ministry, mokri, parliament, speed, drinks, strike, cities, clock, constitutions, countries, errata, holidays, marquise, months, staples,
                                wages, waits, words, writers)

ROOT = Path(__file__).resolve().parent.parent / 'posts'
# What each post counts, by its slug.
COUNTS = {'from-no-1': lambda meta: bulletin.count(*meta['span'], meta.get('reports_read', [])),
          'six-constitutions': constitutions.count,
          'words-in-the-law': words.count,
          'who-writes': writers.count,
          'december': months.count,
          'minimum-wage': wages.count,
          'holidays': holidays.count,
          'signed-to-published': waits.count,
          'errata': errata.count,
          'agreements': agreements.count,
          'countries': countries.count,
          'cities': cities.count,
          'clock': clock.count,
          'marquise': marquise.count,
          'bread-gasoil': staples.count,
          'ages': ages.count,
          'article-28': drinks.count,
          'strike': strike.count,
          'whatsapp': absent.count,
          'death-penalty': death.count,
          'parliament': parliament.count,
          'speed': speed.count,
          'deadlines': deadlines.count,
          'expropriation': expropriation.count,
          'mokri': mokri.count,
          'ministry': ministry.count,
          'emergency': emergency.count}
# A post that took another's place keeps its old address (C1 of the posts-from-No.-1 review, 6 Nov 2026: «سبعون سنة» became
# the Bulletin from No. 1 under the same number); the places' two short posts were folded into the long ones,
# /blog/cities and /blog/countries (6 Nov 2026).
MOVED = {'seventy-years': 'from-no-1', 'countries-in-brief': 'countries', 'cities-in-brief': 'cities'}


def slugs() -> list[str]:
    return sorted(p.name for p in ROOT.iterdir() if (p / 'meta.yaml').exists())


@cache
def meta(slug: str) -> dict | None:
    path = ROOT / MOVED.get(slug, slug) / 'meta.yaml'
    return yaml.safe_load(path.read_text(encoding='utf-8')) if path.exists() else None


@cache
def figures(slug: str) -> dict | None:
    """A post's counted figures."""
    path = ROOT / MOVED.get(slug, slug) / 'figures.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None


def summary(slug: str) -> dict:
    """A post as lists name it."""
    m = meta(slug)
    return {k: m.get(k) for k in ('slug', 'number', 'status', 'date', 'counted_on', 'title', 'lead')}


def listing() -> list[dict]:
    """The posts, the newest first."""
    return sorted((summary(s) for s in slugs()), key=lambda p: (p['number'] or 0), reverse=True)


def post(slug: str) -> dict | None:
    m, f = meta(slug), figures(slug)
    if m is None or f is None:
        return None
    return {**m, 'figures': f}


def years_csv(slug: str) -> str | None:
    """The post's yearly table as a CSV, the columns named as the figures name them."""
    f = figures(slug)
    if f is None or 'years' not in f:
        return None
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(f['year_fields'])
    writer.writerows(f['years'])
    return out.getvalue()


def write_figures(slug: str) -> Path:
    """Count the post's figures again from the database and keep them beside its meta."""
    m = meta(slug)
    if m is None or slug not in COUNTS:
        raise KeyError(slug)
    path = ROOT / slug / 'figures.json'
    path.write_text(json.dumps(COUNTS[slug](m), ensure_ascii=False, separators=(',', ':')) + '\n', encoding='utf-8')
    figures.cache_clear()
    return path
