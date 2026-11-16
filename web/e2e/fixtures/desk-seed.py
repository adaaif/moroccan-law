# Rows for the access desk's end-to-end run (e2e/desk.e2e.mjs), made through the site's own services on a throwaway
# database: requests that wait (one late, one answered after a question, a change request), one that waits for its
# account's answer, one declined, two live accesses with thirty days of use, keys and downloads, one ending soon.
# Run by `manage.py shell -c` at the start of each run: the accounts of an earlier run go first, with what they asked.
# It makes a superuser, so it refuses anything but a development database, and its accounts' password is drawn by
# the run that calls it (E2E_PASSWORD), never written here.
import os
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils import timezone

from apps.discussion.models import Contribution, Discussion
from apps.opendata.models import Access, AccessDay, Download, Event, Request
from apps.opendata.services import keys, requests

if not settings.DEBUG:
    raise SystemExit('desk-seed: for a development database only (DEBUG is off here)')
SECRET = os.environ['E2E_PASSWORD']
U = get_user_model()
now = timezone.now()
today = timezone.localdate()


def account(name, days=60):
    user, made = U.objects.get_or_create(username=name, defaults={'email': f'{name}@example.org'})
    if made:
        user.set_password(SECRET)
        user.date_joined = now - timedelta(days=days)
        user.email_proven_at = user.date_joined
        user.save()
    return user


def sent(name, who, kind, purpose, *, api=True, data=False, volume='small', runs_at='', age=60, days_ago=0):
    user = account(name, age)
    r = requests.send(user, {'name': who, 'kind': kind, 'purpose': purpose, 'wants_api': api, 'wants_data': data,
                             'runs_at': runs_at, 'volume': volume, 'commercial': kind == 'company',
                             'terms': settings.ACCESS_TERMS, 'consent': True})
    back(r, days_ago)
    return r


def back(r, days):
    """The request as if sent `days` days ago."""
    if days:
        at = now - timedelta(days=days)
        Request.objects.filter(pk=r.pk).update(created_at=at, waiting_since=at)
        Event.objects.filter(request=r).update(at=at)


chief = account('chief-desk', 400)
chief.set_password(SECRET)       # kept from an earlier run: this run's password
chief.save(update_fields=['password'])
U.objects.filter(pk=chief.pk).update(is_superuser=True, is_staff=True)
chief.refresh_from_db()

earlier = U.objects.filter(Q(username__startswith='desk-') | Q(username__startswith='e2edesk'))
Access.objects.filter(user__in=earlier).delete()      # an access holds on to its request
earlier.delete()
late = sent('desk-newsroom', 'Rédaction Exemple', 'newsroom', 'Vérifier les références de lois citées dans nos articles.',
            volume='medium', runs_at='redaction.example.ma', age=90, days_ago=9)
U.objects.filter(pk=late.user_id).update(preferred_language='fr')   # its letters are written in French
place, _ = Discussion.objects.get_or_create(path='/talk/work', defaults={'text_path': '/talk/work'})
for i in range(4):
    Contribution.objects.create(discussion=place, author=late.user, kind='post', title=f'سؤال {i}', body=f'ملاحظة {i}',
                                removed_at=now if i == 3 else None)

lab = sent('desk-lab', 'مختبر القانون الرقمي', 'school', 'درس عن قانون الشغل في الكلية، يعرض المواد بمصدرها ورابطها.',
           data=True, age=30, days_ago=2)
requests.ask(lab, chief, 'ما اسم الكلية؟')
requests.answer(lab.user, 'كلية الحقوق بالرباط، شعبة القانون الخاص.')

sent('desk-association', 'جمعية الحق في المعلومة', 'association', 'أداة تشرح للناس القوانين التي تمسهم، بلغة بسيطة.',
     age=14, days_ago=4)

startup = sent('desk-startup', 'Lexa SARL', 'company', 'Une application mobile de veille juridique pour PME.',
               volume='large', runs_at='https://lexa.example.ma', age=8, days_ago=1)
requests.ask(startup, chief, 'Quel volume de requêtes prévoyez-vous par jour ?')

no = sent('desk-declined', 'Copie Totale', 'company', 'Tout copier.', data=True, age=2, days_ago=12)
requests.decline(no, chief, 'scope')

# Two holders: one ending in twelve days, used every day; one that asks to change what it holds.
first = sent('desk-holder', 'منصة الشغل', 'company', 'منصة تجيب الأجراء عن حقوقهم بمواد مدونة الشغل.', data=True,
             volume='medium', runs_at='https://chogl.example.ma', age=200, days_ago=40)
held = requests.accept(first, chief, api=True, data=True, size='app', ends_on=today + timedelta(days=12))
keys.make(first.user, 'الخادم')
doors = ['v1.search', 'v1.articles', 'v1.text', 'v1.references', 'mcp']
AccessDay.objects.bulk_create([
    AccessDay(access=held, day=today - timedelta(days=k), calls=300 + (k * 137) % 900, articles=120 + (k * 53) % 400,
              doors={d: (300 + (k * 137) % 900) // (i + 2) for i, d in enumerate(doors)},
              limits={'minute': 3} if k == 0 else {})
    for k in range(1, 29) if k % 6])
Download.objects.create(access=held, edition=today.isoformat(), file='texts.jsonl.gz', by='key')
Download.objects.create(access=held, edition=today.isoformat(), file='akn.zip', by='account')

second = sent('desk-second', 'Juris Atlas', 'person', 'Une thèse sur la codification au Maroc.', age=120, days_ago=50)
small = requests.accept(second, chief, api=True, data=False, size='try')
keys.make(second.user, 'thèse')
AccessDay.objects.bulk_create([AccessDay(access=small, day=today - timedelta(days=k), calls=40 + k, articles=10 + k,
                                         doors={'v1.search': 30 + k, 'v1.text': 10})
                               for k in (2, 3, 5, 8, 13)])
change = requests.change(second.user, {'wants_api': True, 'wants_data': True, 'size': 'app',
                                       'why': 'Il me faut la base entière pour compter les renvois.'})
back(change, 3)
print('seeded')
