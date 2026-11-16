"""Demo discussions in the topics (a dev database only: it refuses to run without DEBUG), for the screenshots and the
end-to-end script of 29 Oct 2026: the demo-* people, posts and comments in the family, housing, justice, work and tax
topics (the words of demo_content.py, written for the demo; people and stories are invented), votes, marked answers,
a held post and a reported one; then demo_cases.py (30 Oct 2026): posts in every topic and every state a moderator
meets, a moderator in every topic, and the accounts to try it with (demo-tester, demo-new, demo-unproven). Everything
goes through the services, the check set to 'pass' (no model is asked; the check's verdicts are the demo's own, model
'demo'). Running it again replaces what it made. Every demo account gets one password: DEMO_PASSWORD from the
environment, else one drawn at each run and printed once at the end (the end-to-end script reads DEMO_PASSWORD). No
password is written in the code: a server never holds these accounts switched on (`check --deploy` refuses it)."""
import os
import random
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import User
from apps.discussion.management.commands import demo_cases, demo_content as words
from apps.discussion.models import (Action, Appeal, Ban, Check, Contribution, Discussion, Follow, Notice, Point,
                                    Reviewer, Trust)
from apps.discussion.services import compose, counters, places, reports, review, votes

FAMILY, HOUSING, JUSTICE, WORK, TAX = '/talk/family', '/talk/housing', '/talk/justice', '/talk/work', '/talk/tax'
ART_49 = '/ma/loi/70-03/art_49'

HOUSING_POSTS = [
    ('question', 'مول الدار بغا يزيد 15% فالكرا', 'مول الدار طلب مني نزيد 15% في الكراء وما زال ما كملناش عامين من العقد. '
     'واش عندو الحق؟', '/ma/loi/67-12/art_34', '%8 بالنسبة للمحلات المعدة للسكنى'),
    ('question', 'الكرا ديالي 400 درهم: شحال يقدر يزيد؟', 'كنخلص 400 درهم فالشهر. سمعت بلي المحكمة تقدر تزيد كثر من 8%. '
     'واش صحيح؟', '/ma/loi/67-12/art_35', ''),
    ('post', 'تجربتي مع الإفراغ', 'جاني إنذار بالإفراغ بلا سبب واضح. مشيت للمحكمة وطلبت يبين السبب الجدي، والقاضي رفض '
     'الإفراغ. الإشعار خاصو يكون فيه السبب.', '/ma/loi/67-12/art_45', ''),
    ('question', 'Le bailleur peut-il garder la caution ?', 'Je quitte l’appartement le mois prochain. Le propriétaire '
     'dit qu’il garde la caution pour « usure ». En a-t-il le droit ?', '', ''),
]
HOUSING_ANSWERS = [
    'حسب المادة 32 لا يجوز رفع الكراء قبل ثلاث سنوات من العقد، والمادة 34 تحدد النسبة في 8% للسكنى.',
    'إلا كان الكرا 400 درهم ولا أقل، المادة 35 كتعطي للمحكمة سلطة تقدير أوسع. خاص تمشي للمحكمة باش تعرف.',
    'Le dépôt de garantie se rend à la sortie, après l’état des lieux ; vérifiez ce que dit votre contrat.',
]
WORK_POSTS = [
    ('question', 'طردوني بلا إنذار بعد 6 سنين', 'خدمت 6 سنين فشركة، وطردوني نهار واحد بلا حتى ورقة. شنو هي حقوقي؟',
     '/ma/loi/65-99/art_53', ''),
    ('question', 'واش الساعات الإضافية كتخلص؟', 'كنخدم 10 ساعات فالنهار وكنخلص غير 8. واش هادشي قانوني؟', '', ''),
    ('post', 'نصيحة: احتفظوا بأوراق الأجرة', 'من تجربتي: ورقة الأداء والتصريح فالضمان الاجتماعي هما أول حاجة كيطلبو '
     'منك فالمحكمة. احتفظو بيهم كاملين.', '', ''),
]
WORK_ANSWERS = [
    'المادة 53 من مدونة الشغل كتحدد التعويض عن الفصل حسب الأقدمية. ومن حقك تطلب ورقة الشغل وشهادة الأجرة.',
    'الساعات الإضافية كتخلص بزيادة على الأجر العادي. شوف المادة 201 من مدونة الشغل.',
]
MODERATORS = {'hamid': [FAMILY], 'khadija': [HOUSING, WORK], 'karim': [JUSTICE, TAX]}


def _title(question: str) -> str:
    """A question's first sentence as its title, as people write one."""
    first = question.split('؟')[0].split('?')[0].strip()
    cut = ' '.join(first.split()[:9])
    return (cut + ('…' if len(first.split()) > 9 else '') + ('؟' if '؟' in question else '?' if '?' in question else ''))[:120]


class Command(BaseCommand):
    help = 'Seed demo discussions in the topics (dev only).'

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError('Demo data goes on a development database only.')
        self.rng = random.Random(29)
        password = os.environ.get('DEMO_PASSWORD') or secrets.token_urlsafe(12)
        self.password = make_password(password)        # hashed once, for every demo account
        with override_settings(DISCUSSION_CHECK='pass', DISCUSSION_OPEN=True), transaction.atomic():
            self.clear()
            self.people = {name: self.person(name, shown, form, lang) for name, shown, form, lang, _ in words.PEOPLE}
            self.staff = self.person('staff', 'فريق قانون', 'm', 'ar', staff=True)
            # To try it by hand: the tester (no agreement to the check yet), a newcomer, an email not proven yet.
            self.people['tester'] = self.person('tester', 'سارة', 'f', 'ar', consent=False)
            self.person('new', 'ياسين', 'm', 'ar', consent=False, joined_days=0)
            self.person('unproven', 'حنان', 'f', 'ar', consent=False, proven=False)
            self.seed()
            states = demo_cases.run(self)
            self.recount()
        self.stdout.write(f'{Contribution.objects.filter(discussion__path__startswith="/talk/").count()} contributions '
                          f'in the topics; password for every demo account: {password}')
        for name, c in states.items():
            self.stdout.write(f'  {name:22} {places.post_path(c)}  by {c.author.username}')

    def clear(self):
        """Everything the development's people wrote and did, the old seeds' article threads (shown nowhere since
        29 Oct 2026) and the end-to-end runs' included, so the moderators' queues hold only the cases below."""
        demo = User.objects.filter(Q(username__startswith='demo-') | Q(email__endswith='@demo.law.invalid'))
        Contribution.objects.filter(author__in=demo).delete()
        for model, field in ((Point, 'user'), (Check, 'user'), (Ban, 'user'), (Appeal, 'user'), (Trust, 'user'),
                             (Notice, 'user'), (Follow, 'user'), (Reviewer, 'user'), (Action, 'actor')):
            model.objects.filter(**{f'{field}__in': demo}).delete()
        Action.objects.filter(target__in=demo).delete()
        # Locks a run's tester left on a topic.
        Discussion.objects.filter(path__startswith='/talk/', locked_by__in=demo).update(locked_at=None, locked_by=None)
        counters.every_discussion()

    def person(self, name, shown, form, lang, staff=False, consent=True, proven=True, joined_days=90) -> User:
        now = timezone.now()
        user, _ = User.objects.get_or_create(username=f'demo-{name}', defaults={
            'email': f'demo-{name}@demo.law.invalid', 'display_name': shown, 'address_form': form,
            'preferred_language': lang, 'is_staff': staff})
        # Every run, so the password printed at the end opens every demo account.
        user.password = self.password
        user.is_active = True
        user.email_proven_at = now - timedelta(days=60) if proven else None
        user.check_consent_at = now if consent else None
        user.date_joined = now - timedelta(days=joined_days)
        user.save()
        return user

    def when(self, c: Contribution, days_ago: float):
        at = timezone.now() - timedelta(days=days_ago)
        Contribution.objects.filter(pk=c.pk).update(created_at=at, active_at=at if c.parent_id is None else None)
        c.created_at = at

    def write(self, who, place, kind, title, body, about='', quote='', days=3.0):
        c = compose.contribute(self.people[who], path=place, kind=kind, title=title, body=body, about=about,
                               quote=quote)
        self.when(c, days)
        return c

    def comment(self, who, parent, body, days):
        c = compose.contribute(self.people[who], parent_id=parent.pk, body=body)
        self.when(c, days)
        return c

    def vote(self, c, n):
        others = [u for u in self.people.values() if u.pk != c.author_id]
        for u in self.rng.sample(others, min(n, len(others))):
            votes.useful(u, c.pk)

    def seed(self):
        names = list(self.people)
        rng = self.rng
        # The family topic: article 49's questions, stories and opinions, with their explanations as answers.
        quotes = iter(words.ART49_QUOTES)
        asked = []
        for i, q in enumerate(words.QUESTIONS_49[:14]):
            who = names[(i * 3 + 1) % len(names)]
            quote = next(quotes, '') if i % 3 == 0 else ''
            post = self.write(who, FAMILY, 'question', _title(q), q, about=ART_49, quote=quote, days=20 - i * 1.3)
            asked.append(post)
        for i, post in enumerate(asked[:10]):
            answer = self.comment(names[(i * 5 + 2) % len(names)], post, words.EXPLANATIONS_49[i % len(words.EXPLANATIONS_49)],
                                  days=19 - i * 1.3)
            self.vote(answer, rng.randint(1, 9))
            if i % 3 == 0:
                votes.accept(self.people[next(n for n, u in self.people.items() if u.pk == post.author_id)], answer.pk)
            for k in range(rng.randint(0, 3)):
                pool = [words.REPLY_AGREE, words.REPLY_DISAGREE, words.REPLY_ASK, words.REPLY_THANKS][k % 4]
                self.comment(names[(i + k * 7) % len(names)], post, rng.choice(pool), days=18 - i * 1.3 - k * 0.2)
        for i, story in enumerate(words.EXPERIENCES_49[:5]):
            post = self.write(names[(i * 7 + 4) % len(names)], FAMILY, 'post', _title(story), story, about=ART_49,
                              days=15 - i * 2)
            self.vote(post, rng.randint(2, 12))
        for i, opinion in enumerate(words.OPINIONS_49['pro'][:3] + words.OPINIONS_49['cons'][:3]):
            post = self.write(names[(i * 11 + 6) % len(names)], FAMILY, 'post', _title(opinion), opinion, days=12 - i)
            self.vote(post, rng.randint(0, 6))
            self.comment(names[(i * 13 + 3) % len(names)], post,
                         rng.choice(words.REPLY_DISAGREE if i % 2 else words.REPLY_AGREE), days=11.5 - i)
        for path, place in (('/ma/loi/70-03/art_40', FAMILY), ('/ma/loi/70-03/art_53', FAMILY),
                            ('/ma/dahir/1-59-413/art_480', JUSTICE), ('/ma/loi/50-25/art_7', TAX)):
            small = words.SMALL[path]
            for i, q in enumerate(small['questions']):
                post = self.write(names[(i * 4 + 9) % len(names)], place, 'question', _title(q), q, about=path,
                                  quote=small['quotes'][0] if small['quotes'] and i == 0 else '', days=9 - i)
                if i < len(small['explanations']):
                    answer = self.comment(names[(i * 6 + 5) % len(names)], post, small['explanations'][i], days=8.5 - i)
                    self.vote(answer, rng.randint(1, 5))
            for i, opinion in enumerate(small['opinions'][:2]):
                self.write(names[(i * 9 + 8) % len(names)], place, 'post', _title(opinion), opinion, days=7 - i)
        # The housing and work topics: a few posts from the article, answered.
        for place, posts, answers in ((HOUSING, HOUSING_POSTS, HOUSING_ANSWERS), (WORK, WORK_POSTS, WORK_ANSWERS)):
            for i, (kind, title, body, about, quote) in enumerate(posts):
                post = self.write(names[(i * 5 + 3) % len(names)], place, kind, title, body, about=about, quote=quote,
                                  days=4 - i * 0.7)
                if i < len(answers):
                    answer = self.comment(names[(i * 3 + 10) % len(names)], post, answers[i], days=3.5 - i * 0.7)
                    self.vote(answer, rng.randint(2, 7))
                self.vote(post, rng.randint(0, 4))
        # What moderators find: a post with a phone number (held) and one reported for exposing someone.
        self.write('salma', FAMILY, 'post', 'محامية مزيانة فهاد الملفات', words.HELD_49[0], days=0.4)
        reported = self.write('karim', FAMILY, 'post', _title(words.REPORTED_49[0]), words.REPORTED_49[0], days=1)
        for who in ('loubna', 'ayoub'):
            reports.file(self.people[who], reported.pk, reason='abuse')
        for who, paths in MODERATORS.items():
            review.appoint(self.staff, self.people[who], paths)

    def recount(self):
        counters.every_discussion()
        for post in Contribution.objects.filter(discussion__path__startswith='/talk/', parent=None):
            counters.replies(post)
