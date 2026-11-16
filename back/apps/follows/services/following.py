"""An account's follows (R13 of the for-everyone review) and the letters they bring: one letter a person, the changes
they had not been told, then they are told. What stood when one began to follow is known already. An account follows
FOLLOWS_MAX addresses at most, listed and told in a fixed number of queries whatever they are."""
from django.conf import settings
from django.db import transaction

from apps.accounts.services import mail
from apps.accounts.services.refusals import Refused
from apps.follows.models import Follow
from apps.follows.services import news

# Far above what a person follows for letters (a device follows on its own, without this bound); a bound on what one
# account can make the letters' job and its list read.
FOLLOWS_MAX = 300

VERBS = {'ar': {'repealed': 'نسخ', 'other': 'غيّر'}, 'fr': {'repealed': 'a abrogé', 'other': 'a modifié'}}


def follow(user, path: str) -> dict:
    what = news.describe(path)
    mine = Follow.objects.filter(user=user)
    if not mine.filter(path=what['path']).exists():
        if mine.count() >= FOLLOWS_MAX:
            raise Refused('follows', 'too_many', 409)
        Follow.objects.get_or_create(user=user, path=what['path'], defaults={'told': news.keys(what['path'])})
    return what


def unfollow(user, path: str) -> None:
    Follow.objects.filter(user=user, path=str(path or '').strip()).delete()


def listed(user) -> list[dict]:
    """What the account follows, newest first: the texts, articles and places they name read once for all."""
    rows = list(Follow.objects.filter(user=user).order_by('-created_at'))
    known = news.known_of([f.path for f in rows])
    out = []
    for f in rows:
        try:
            out.append({**news.describe(f.path, known), 'since': f.created_at.date()})
        except Exception:  # noqa: BLE001 — a text gone from the site leaves the list, not the page
            continue
    return out


def line(what: dict, item: dict, lang: str) -> str:
    """One change as a letter says it: «المادة 34 من قانون الكراء: غيّرها القانون رقم 2.24 (الجريدة الرسمية عدد 7547،
    الصفحة 7012)»."""
    ar = lang == 'ar'
    named = what['name'][lang]
    if item['kind'] == 'new_text':
        t = item['text']
        return (f"{named}: نص جديد — {t['title']} (الجريدة الرسمية عدد {t['issue']})" if ar
                else f"{named} : nouveau texte — {t['title']} (BO n° {t['issue']})")
    verbs = item['verbs']
    verb = VERBS[lang]['repealed' if verbs == ['repealed'] else 'other']
    by = item['by']['number'].replace('-', '.')
    by = (f"{'القانون' if item['by']['kind'] == 'law' else 'النص'} رقم {by}" if ar
          else f"{'la loi' if item['by']['kind'] == 'law' else 'le texte'} n° {by}")
    where = what.get('article') or ''
    if not where and item['articles']:
        n = '، '.join(item['articles'][:6]) if ar else ', '.join(item['articles'][:6])
        where = (f'المواد {n}' if ar else f'les articles {n}') if len(item['articles']) > 1 else (
            f'المادة {n}' if ar else f'l’article {n}')
    issue = item['issue']
    printed = ((f"الجريدة الرسمية عدد {issue['number']}" + (f"، الصفحة {issue['page']}" if issue['page'] else '')) if ar
               else (f"BO n° {issue['number']}" + (f", page {issue['page']}" if issue['page'] else '')))
    said = f"{named}: {by} {verb} {where} ({printed})" if ar else f"{named} : {by} {verb} {where} ({printed})"
    if not item['settled']:
        said += ' — لم نتحقق منه بعد' if ar else ' — pas encore vérifié'
    return ' '.join(said.split())


def send_letters() -> int:
    """A letter to each person whose follows changed since they were last told, then they are told. Run after the
    links pipeline read a new issue."""
    sent = 0
    follows = list(Follow.objects.select_related('user').filter(
        user__email_notices=True, user__email_proven_at__isnull=False, user__deleted_at__isnull=True).order_by('user_id', 'id'))
    by_user: dict = {}
    for f in follows:
        by_user.setdefault(f.user, []).append(f)
    # What everyone follows, read once for all of them: a few queries in all, not a few a person (nor, for a topic, a
    # state or a commune, a few a follow).
    known = news.known_of(list(dict.fromkeys(f.path for f in follows)), recent=True)
    for user, rows in by_user.items():
        lang = user.preferred_language if user.preferred_language in ('ar', 'fr') else 'ar'
        lines, told = [], []
        for f in rows:
            try:
                what = news.describe(f.path, known)
            except Exception:  # noqa: BLE001
                continue
            fresh = [i for i in news.items(what, known) if i['key'] not in set(f.told)]
            if fresh:
                lines += [f"• {line(what, i, lang)}\n  {settings.SITE_URL}{what['path']}" for i in fresh[:10]]
                told.append((f, [i['key'] for i in fresh]))
        if not lines:
            continue
        # A letter and its follows told go together, a person at a time: one write for their follows.
        with transaction.atomic():
            for f, new in told:
                f.told = f.told + new
            Follow.objects.bulk_update([f for f, _ in told], ['told'])
            transaction.on_commit(lambda u=user, ls=lines: mail.send(u, 'follows', lines='\n\n'.join(ls),
                                                                     follows=f'{settings.SITE_URL}/me/following'))
        sent += 1
    return sent
