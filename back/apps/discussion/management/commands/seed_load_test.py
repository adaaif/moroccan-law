"""A load test of the discussion, run on purpose against one named database (`--yes-on <its name>`, checked against the
database Django is connected to: without it, or naming another, it writes nothing). --users accounts «load-001»…
(…@load.law.invalid, unusable passwords, named «مستخدم تجريبي 001» so no reader takes them for people, joined today:
the site shows them, unlike the development's «demo-…»); --posts posts spread over the topics' places; --comments
comments under them, most under a few posts (a long tail, as a real site has), a third answering another comment; with
--viral N, one comment of the busiest post draws N of them (half answering each other), the oldest so it leads that
post. Written in bulk, not through compose (no check, no notice, no follow), dated over the last --days days, then
counted as the services count. The words are neutral lines of this file, never a claim about the law. --remove takes
it all away: the accounts, and with them every row they wrote. Nothing is paid.

On PostgreSQL the rows are made by the database itself, a million at a time (built for 100,000 users, a million posts
and ten million comments): INSERT … SELECT over generate_series, nothing crossing the wire but the counts. The comments
fall on the posts as a long tail (post rank ⌊P·u³⌋: the busiest draws about 1 % of them), two thirds under the post, a
sixth answering one of those, a sixth answering an answer; --viral N answers the busiest post's first comment N times,
each reply to it or to an earlier one, so the conversation is a deep tree. --remove there deletes whole threads by SQL,
a batch at a time, and leaves to Django only what someone else touched.

    seed_load_test --yes-on law_load                   # 100 users, 100 posts, 100,000 comments
    seed_load_test --yes-on law_load --viral 3000      # one conversation of 3,000 replies too
    seed_load_test --yes-on law_load --users 100000 --posts 1000000 --comments 10000000 --days 365 --viral 10000
    seed_load_test --yes-on law_load --users 5 --posts 3 --comments 50
    seed_load_test --yes-on law_load --remove"""
import random
import time
from contextlib import contextmanager
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection, transaction
from django.db.models import Max, Q
from django.utils import timezone

from apps.accounts.models import User
from apps.discussion.models import Contribution, Discussion, Kind
from apps.discussion.services import counters, places
from config import confirm

PREFIX, DOMAIN = 'load-', '@load.law.invalid'
NAME = 'مستخدم تجريبي {:03d}'

QUESTIONS = [
    'شنو هي الوثائق اللي خاصني نوجد قبل ما نمشي للإدارة؟', 'شكون عندو تجربة مع هاد الإجراء؟',
    'واش كاين شي أجل خاصني نحترمو فهاد الحالة؟', 'فين خاصني نمشي باش نبدا؟', 'شحال كياخد هاد الإجراء ديال الوقت؟',
    'واش خاصني محامي ولا نقدر نمشي بوحدي؟', 'كيفاش نعرف واش هاد القرار نهائي؟', 'شنو ندير إلا رفضو الطلب ديالي؟',
    'واش كاين شي نموذج ديال الطلب؟', 'Quelqu’un a-t-il déjà fait cette démarche ?', 'Quels papiers faut-il préparer ?',
    'واش هاد القانون مازال خدام بيه ولا تبدل؟', 'شكون اللي مسؤول على هاد الملف؟', 'واش نقدر نطلب نسخة من الملف ديالي؟',
]
TITLES = [('ar', 'سؤال على {}'), ('ar', 'تجربتي مع {}'), ('ar', 'محتاج معلومة على {}'), ('ar', 'شي حد يعاوني ف{}'),
          ('fr', 'Une question sur {}')]
LINES = [
    'شكرا على السؤال، حتى أنا عندي نفس المشكل.', 'حتى أنا بغيت نعرف الجواب.', 'تبع معانا الموضوع.',
    'جربت هادشي العام اللي فات، خدا معايا شي شهرين.', 'سول فالإدارة المختصة، هوما اللي عندهم الخبر اليقين.',
    'الله يسهل عليك.', 'واش لقيتي شي جواب فالأخير؟', 'خاصك تحتافظ بجميع الأوراق والنسخ.', 'قرا المادة فالنص كامل.',
    'Merci pour le partage.', 'Même situation pour moi.', 'Bon courage, tenez-nous au courant.',
    'كاين اللي قال لي نمشي للمحكمة نيشان.', 'أنا مشيت بوحدي وما احتاجيتش محامي، ولكن كل حالة وحالتها.',
    'زيد فصل شوية باش نفهمو الحالة ديالك.', 'شكرا، الجواب واضح دابا.', 'كتب الطلب بخط واضح ودير نسخة.',
    'المرة الجاية سول قبل ما توقع.', 'عندي سؤال قريب من هادا.', 'ساعدني هاد الموضوع بزاف.',
]


def _title(rng: random.Random, place) -> str:
    """«سؤال على الشغل»: a title in the place's short name (a door's), in the title's language."""
    lang, pattern = rng.choice(TITLES)
    names = place.short or place.name
    return pattern.format(names.get(lang) or names['ar'])[:140]


def _body(rng: random.Random, low: int = 1, high: int = 3) -> str:
    return ' '.join(rng.sample(LINES, rng.randint(low, high)))


def _shares(rng: random.Random, posts: int, comments: int) -> list[int]:
    """How many comments each post gets: a long tail (weight 1/rank^1.1), at least three each, the rest to the first."""
    weights = [1 / (i + 1) ** 1.1 for i in range(posts)]
    total = sum(weights)
    shares = [max(3, int(comments * w / total)) for w in weights]
    shares[0] += comments - sum(shares)
    rng.shuffle(shares)
    return shares


class Command(BaseCommand):
    help = 'Load-test the discussion: test accounts, posts and comments written in bulk (or --remove them).'

    def add_arguments(self, parser):
        parser.add_argument('--users', type=int, default=100)
        parser.add_argument('--posts', type=int, default=100)
        parser.add_argument('--comments', type=int, default=100_000)
        parser.add_argument('--days', type=int, default=4, help='the content is dated over the last N days')
        parser.add_argument('--viral', type=int, default=0, help='replies one comment of the busiest post draws')
        parser.add_argument('--seed', type=int, default=30)
        parser.add_argument('--remove', action='store_true')
        confirm.add_argument(parser)

    def handle(self, *args, users, posts, comments, days, seed, remove, viral, yes_on='', **opts):
        confirm.confirm(yes_on, what='The load test')
        mine = User.objects.filter(username__startswith=PREFIX, email__endswith=DOMAIN)
        pg = connection.vendor == 'postgresql'
        if remove:
            started = time.time()
            n = mine.count()
            if pg:
                self._pg_remove()
            with transaction.atomic():
                mine.delete()
                counters.every_discussion()
            self.stdout.write(f'removed {n} test accounts and everything they wrote in {time.time() - started:.0f}s')
            return
        if mine.exists():
            raise CommandError(f'{mine.count()} test accounts are already there: --remove first.')
        if comments < 3 * posts:
            raise CommandError('--comments must be at least three a post.')
        if pg:
            return self._pg_seed(users, posts, comments, days, seed, viral)
        rng = random.Random(seed)
        now = timezone.now()
        start = now - timedelta(days=days)
        stamp = lambda lo, hi: lo + timedelta(seconds=rng.uniform(0, max(1.0, (hi - lo).total_seconds())))
        field = Contribution._meta.get_field('created_at')
        started = time.time()
        field.auto_now_add = False      # the rows carry their own dates; put back below
        try:
            with transaction.atomic():
                people = User.objects.bulk_create([
                    User(username=f'{PREFIX}{i:03d}', email=f'{PREFIX}{i:03d}{DOMAIN}', display_name=NAME.format(i),
                         password='!load-test', date_joined=now) for i in range(1, users + 1)])
                rooms = []
                for place in places.all_places():
                    d, _ = Discussion.objects.get_or_create(path=place.path, defaults={'text_path': place.path})
                    rooms.append((place, d))
                heads = []
                for i in range(posts):
                    place, room = rooms[i % len(rooms)]
                    at = stamp(start, now - timedelta(hours=6))
                    heads.append(Contribution(
                        discussion=room, author=rng.choice(people), kind=rng.choice([Kind.QUESTION, Kind.QUESTION, Kind.POST]),
                        title=_title(rng, place), body=f'{rng.choice(QUESTIONS)} {_body(rng, 0, 2)}'.strip(),
                        links=[], created_at=at, active_at=at))
                heads = Contribution.objects.bulk_create(heads, batch_size=500)
                written, shares = 0, _shares(rng, posts, comments)
                busiest = max(shares)
                for head, share in zip(heads, shares):
                    top = [Contribution(discussion=head.discussion, parent=head, author=rng.choice(people), kind=Kind.COMMENT,
                                        body=_body(rng), links=[], created_at=stamp(head.created_at, now))
                           for _ in range(share - share // 3)]
                    hot = viral and share == busiest
                    if hot:                 # the conversation that draws: the post's first comment
                        top[0].created_at = head.created_at + timedelta(microseconds=1)
                    top = Contribution.objects.bulk_create(top, batch_size=2000)
                    answers, drawn = [], []
                    for _ in range(min(viral, share // 3) if hot else 0):
                        to = top[0] if not drawn or rng.random() < 0.5 else rng.choice(drawn)
                        drawn.append(Contribution.objects.create(
                            discussion=head.discussion, parent=head, reply_to=to, author=rng.choice(people),
                            kind=Kind.COMMENT, body=_body(rng, 1, 2), links=[], created_at=stamp(to.created_at, now)))
                    for _ in range(share // 3 - len(drawn)):
                        to = rng.choice(top)
                        answers.append(Contribution(discussion=head.discussion, parent=head, reply_to=to, author=rng.choice(people),
                                                    kind=Kind.COMMENT, body=_body(rng, 1, 2), links=[],
                                                    created_at=stamp(to.created_at, now)))
                    Contribution.objects.bulk_create(answers, batch_size=2000)
                    written += len(top) + len(drawn) + len(answers)
                counters.every_post(Q(pk__in=[h.pk for h in heads]))
                counters.every_discussion()
        finally:
            field.auto_now_add = True
        # A bulk insert leaves Postgres planning on the tables' old sizes: «answered» was about ten times slower until
        # its statistics were read again.
        if connection.vendor == 'postgresql':
            with connection.cursor() as cursor:
                for model in (Contribution, Discussion, User):
                    cursor.execute(f'ANALYZE {connection.ops.quote_name(model._meta.db_table)}')
        self.stdout.write(f'{len(people)} test accounts, {len(heads)} posts, {written} comments in {time.time() - started:.0f}s; '
                          f'the busiest post holds {max(shares)} comments')

    # ── PostgreSQL: the database makes the rows ──────────────────────────────────────────────────────────────────────

    def _say(self, started: float, what: str) -> None:
        self.stdout.write(f'[{time.time() - started:6.0f}s] {what}')
        self.stdout.flush()

    def _pg_seed(self, users, posts, comments, days, seed, viral):
        started = time.time()
        rooms = []
        for place in places.all_places():
            d, _ = Discussion.objects.get_or_create(path=place.path, defaults={'text_path': place.path})
            rooms.append((d.pk, [_title(random.Random(i), place) for i in range(8)]))
        rest = comments // 3
        viral = min(viral, rest)
        tops, r1 = comments - rest, (rest - viral + 1) // 2
        r2 = rest - viral - r1
        args = {'q': QUESTIONS, 'l': LINES, 'nq': len(QUESTIONS), 'nl': len(LINES), 'days': days}
        # One body: a question (posts) or a line, then up to two more lines.
        lines = "(%(l)s::text[])[g.l1] || CASE g.nb WHEN 0 THEN '' WHEN 1 THEN ' ' || (%(l)s::text[])[g.l2] " \
                "ELSE ' ' || (%(l)s::text[])[g.l2] || ' ' || (%(l)s::text[])[g.l3] END"
        draws = "1 + floor(random() * %(nl)s)::int AS l1, 1 + floor(random() * %(nl)s)::int AS l2, " \
                "1 + floor(random() * %(nl)s)::int AS l3, floor(random() * 3)::int AS nb, random() AS t, random() AS v"
        columns = ('discussion_id, parent_id, reply_to_id, author_id, kind, title, body, links, about, quote, anonymous, '
                   'article_digest, created_at, held_reasons, held_spans, review_note, removed_rule, useful_count, '
                   'reply_count, active_at')
        with connection.cursor() as c, _unchecked(c, self.stdout):
            c.execute('SELECT setseed(%s)', [(seed % 997) / 997])
            c.execute(
                "INSERT INTO users (password, is_superuser, username, is_staff, is_active, date_joined, email, display_name, "
                "preferred_language, address_form, email_notices) "
                "SELECT '!load-test', false, %(p)s || n, false, true, now(), %(p)s || n || %(d)s, %(name)s || n, 'ar', '', false "
                "FROM (SELECT CASE WHEN i < 1000 THEN lpad(i::text, 3, '0') ELSE i::text END AS n "
                "      FROM generate_series(1, %(u)s) i) s",
                {'p': PREFIX, 'd': DOMAIN, 'name': NAME.format(0)[:-3], 'u': users})
            c.execute('CREATE TEMP TABLE load_users ON COMMIT PRESERVE ROWS AS '
                      'SELECT row_number() OVER (ORDER BY id)::int AS rn, id FROM users WHERE username LIKE %s AND email LIKE %s',
                      [PREFIX + '%', '%' + DOMAIN])
            c.execute('CREATE UNIQUE INDEX ON load_users (rn)')
            c.execute('CREATE TEMP TABLE load_rooms (rn int PRIMARY KEY, discussion_id bigint, titles text[])')
            for i, (pk, titles) in enumerate(rooms, 1):
                c.execute('INSERT INTO load_rooms VALUES (%s, %s, %s)', [i, pk, titles])
            self._say(started, f'{users:,} test accounts')
            args.update(nu=users, nr=len(rooms))
            for n in _chunks(posts):
                c.execute(
                    "WITH g AS MATERIALIZED (SELECT 1 + floor(random() * %(nu)s)::int AS ur, 1 + floor(random() * %(nr)s)::int AS rr, "
                    "1 + floor(random() * 8)::int AS ti, 1 + floor(random() * %(nq)s)::int AS qi, random() AS k, "
                    f"{draws} FROM generate_series(1, %(n)s)) "
                    f"INSERT INTO discussion_contribution ({columns}) "
                    "SELECT r.discussion_id, NULL, NULL, u.id, CASE WHEN g.k < 2.0 / 3 THEN 'question' ELSE 'post' END, "
                    "r.titles[g.ti], (%(q)s::text[])[g.qi] || CASE WHEN g.nb = 0 THEN '' ELSE ' ' || (%(l)s::text[])[g.l1] END, "
                    "'[]', '', '', false, '', s.at, '[]', '[]', '', '', 0, 0, s.at "
                    "FROM g JOIN load_users u ON u.rn = g.ur JOIN load_rooms r ON r.rn = g.rr "
                    "CROSS JOIN LATERAL (SELECT now() - make_interval(days => %(days)s) "
                    "  + (make_interval(days => %(days)s) - interval '6 hours') * g.t AS at) s",
                    {**args, 'n': n})
                self._say(started, f'posts: +{n:,}')
            c.execute('CREATE TEMP TABLE load_posts AS SELECT row_number() OVER (ORDER BY c.id)::int AS rn, c.id, '
                      'c.discussion_id, c.created_at FROM discussion_contribution c JOIN load_users u ON u.id = c.author_id '
                      'WHERE c.parent_id IS NULL')
            c.execute('CREATE UNIQUE INDEX ON load_posts (rn)')
            args['np'] = posts
            under = (f"INSERT INTO discussion_contribution ({columns}) "
                     "SELECT p.discussion_id, p.{parent}, {to}, u.id, 'comment', '', " + lines + ", '[]', '', '', false, '', "
                     "s.at, '[]', '[]', '', '', floor(power(g.v, 8) * 40)::int, 0, NULL "
                     "FROM g JOIN {source} p ON p.rn = g.pr JOIN load_users u ON u.rn = g.ur "
                     "CROSS JOIN LATERAL (SELECT p.created_at + (now() - p.created_at) * g.t AS at) s")
            # Two thirds under the posts, the busiest first: rank ⌊P·u³⌋.
            for n in _chunks(tops):
                c.execute(
                    "WITH g AS MATERIALIZED (SELECT 1 + floor(%(np)s * power(random(), 3))::int AS pr, "
                    f"1 + floor(random() * %(nu)s)::int AS ur, {draws} FROM generate_series(1, %(n)s)) "
                    + under.format(parent='id', to='NULL', source='load_posts'), {**args, 'n': n})
                self._say(started, f'comments under the posts: +{n:,}')
            c.execute('CREATE TEMP TABLE load_tops AS SELECT row_number() OVER (ORDER BY c.id)::int AS rn, c.id, c.parent_id, '
                      'c.discussion_id, c.created_at FROM discussion_contribution c JOIN load_posts p ON p.id = c.parent_id')
            c.execute('CREATE UNIQUE INDEX ON load_tops (rn)')
            for total, source, what in ((r1, 'load_tops', 'answers to a comment'), (r2, 'load_answers', 'answers to an answer')):
                if source == 'load_answers':
                    c.execute('CREATE TEMP TABLE load_answers AS SELECT row_number() OVER (ORDER BY c.id)::int AS rn, c.id, '
                              'c.parent_id, c.discussion_id, c.created_at FROM discussion_contribution c '
                              'JOIN load_posts p ON p.id = c.parent_id WHERE c.reply_to_id IS NOT NULL')
                    c.execute('CREATE UNIQUE INDEX ON load_answers (rn)')
                c.execute(f'SELECT count(*) FROM {source}')
                size = c.fetchone()[0]
                for n in _chunks(total):
                    c.execute(
                        f"WITH g AS MATERIALIZED (SELECT 1 + floor(random() * {size})::int AS pr, "
                        f"1 + floor(random() * %(nu)s)::int AS ur, {draws} FROM generate_series(1, %(n)s)) "
                        + under.format(parent='parent_id', to='p.id', source=source), {**args, 'n': n})
                    self._say(started, f'{what}: +{n:,}')
            if viral:
                self._pg_viral(c, viral, columns, lines, draws, args)
                self._say(started, f'one conversation of {viral:,} replies')
            for table in ('load_users', 'load_rooms', 'load_posts', 'load_tops', 'load_answers'):
                c.execute(f'DROP TABLE IF EXISTS {table}')
        mine = Q(author__username__startswith=PREFIX, author__email__endswith=DOMAIN)
        counters.every_post(mine)
        self._say(started, 'posts counted')
        busiest = Contribution.objects.filter(mine, parent=None).aggregate(m=Max('reply_count'))['m']
        counters.every_discussion()
        self._say(started, 'places counted')
        with connection.cursor() as c:
            for model in (Contribution, Discussion, User):
                c.execute(f'ANALYZE {connection.ops.quote_name(model._meta.db_table)}')
        self._say(started, f'{users:,} test accounts, {posts:,} posts, {comments:,} comments; '
                           f'the busiest post holds {busiest:,} comments')

    def _pg_viral(self, c, viral, columns, lines, draws, args):
        """The busiest post's first comment answered `viral` times, each reply to it or (half the time) to an earlier
        reply, each after the one it answers: a deep tree."""
        c.execute('SELECT p.id, p.discussion_id, p.created_at FROM load_posts p WHERE p.rn = 1')
        post, room, at = c.fetchone()
        c.execute('SELECT id FROM discussion_contribution WHERE parent_id = %s AND reply_to_id IS NULL '
                  'ORDER BY created_at, id LIMIT 1', [post])
        hot = c.fetchone()[0]
        c.execute("UPDATE discussion_contribution SET created_at = %s + interval '1 microsecond' WHERE id = %s", [at, hot])
        c.execute(
            f"WITH g AS MATERIALIZED (SELECT i, 1 + floor(random() * %(nu)s)::int AS ur, {draws} "
            "FROM generate_series(1, %(n)s) i) "
            f"INSERT INTO discussion_contribution ({columns}) "
            "SELECT %(room)s, %(post)s, %(hot)s, u.id, 'comment', '', " + lines + ", '[]', '', '', false, '', "
            "%(at)s + (now() - %(at)s) * (g.i::float / (%(n)s + 1)), '[]', '[]', '', '', floor(power(g.v, 8) * 40)::int, 0, NULL "
            "FROM g JOIN load_users u ON u.rn = g.ur ORDER BY g.i",
            {**args, 'n': viral, 'room': room, 'post': post, 'hot': hot, 'at': at})
        c.execute('CREATE TEMP TABLE load_viral AS SELECT row_number() OVER (ORDER BY id)::int AS rn, id '
                  'FROM discussion_contribution WHERE parent_id = %s AND reply_to_id = %s', [post, hot])
        c.execute('CREATE UNIQUE INDEX ON load_viral (rn)')
        c.execute(
            'UPDATE discussion_contribution c SET reply_to_id = COALESCE(e.id, %s) '
            'FROM (SELECT id, CASE WHEN rn = 1 OR random() < 0.5 THEN 0 ELSE 1 + floor(random() * (rn - 1))::int END AS j '
            '      FROM load_viral) x LEFT JOIN load_viral e ON e.rn = x.j WHERE c.id = x.id', [hot])
        c.execute('DROP TABLE load_viral')

    def _pg_remove(self):
        """Whole threads of the test accounts deleted by SQL, a batch of posts at a time; a thread someone else wrote in, or
        a row of another table points into, is left for Django's delete, which follows every relation."""
        started = time.time()
        outside = [(rel.related_model._meta.db_table, rel.field.column) for rel in Contribution._meta.related_objects
                   if rel.related_model is not Contribution]
        outside += [(f.remote_field.through._meta.db_table, f.m2m_column_name()) for f in Contribution._meta.many_to_many]
        with connection.cursor() as c, _unchecked(c, self.stdout):
            c.execute('CREATE TEMP TABLE load_users AS SELECT id FROM users WHERE username LIKE %s AND email LIKE %s',
                      [PREFIX + '%', '%' + DOMAIN])
            c.execute('CREATE UNIQUE INDEX ON load_users (id)')
            touched = ' UNION '.join(
                [f'SELECT COALESCE(c.parent_id, c.id) FROM {t} r JOIN discussion_contribution c ON c.id = r.{col}'
                 for t, col in outside]
                + ['SELECT c.parent_id FROM users u JOIN discussion_contribution c ON c.author_id = u.id '
                   'WHERE c.parent_id IS NOT NULL AND NOT (u.username LIKE %s AND u.email LIKE %s)'])
            c.execute('CREATE TEMP TABLE load_doomed AS SELECT row_number() OVER (ORDER BY c.id)::int AS rn, c.id '
                      'FROM discussion_contribution c JOIN load_users u ON u.id = c.author_id '
                      f'WHERE c.parent_id IS NULL AND c.id NOT IN ({touched})', [PREFIX + '%', '%' + DOMAIN])
            c.execute('CREATE UNIQUE INDEX ON load_doomed (rn)')
            c.execute('SELECT count(*) FROM load_doomed')
            threads = c.fetchone()[0]
            self._say(started, f'{threads:,} threads to delete')
            c.execute('WITH d AS (SELECT id, duplicate_of_id FROM discussion_contribution WHERE duplicate_of_id IS NOT NULL) '
                      'UPDATE discussion_contribution x SET duplicate_of_id = NULL FROM d JOIN discussion_contribution t '
                      'ON t.id = d.duplicate_of_id WHERE x.id = d.id AND COALESCE(t.parent_id, t.id) IN (SELECT id FROM load_doomed)')
            step, done = 20_000, 0
            while done < threads:
                with transaction.atomic():
                    c.execute('DROP TABLE IF EXISTS load_batch')
                    c.execute('CREATE TEMP TABLE load_batch AS SELECT id FROM load_doomed '
                              'WHERE rn > %s AND rn <= %s', [done, done + step])
                    c.execute('DELETE FROM discussion_contribution c USING load_batch b WHERE c.parent_id = b.id')
                    gone = c.rowcount
                    c.execute('DELETE FROM discussion_contribution c USING load_batch b WHERE c.id = b.id')
                    gone += c.rowcount
                done += step
                self._say(started, f'threads {min(done, threads):,} of {threads:,} (+{gone:,} rows)')
            for table in ('load_batch', 'load_doomed', 'load_users'):
                c.execute(f'DROP TABLE IF EXISTS {table}')


@contextmanager
def _unchecked(cursor, out):
    """The rows are right by construction (each points at a row made before it, a thread is deleted whole), so the
    foreign keys' row-by-row checks are skipped while the SQL runs: they took 190 µs a deleted row, 35 minutes for ten
    million. Needs a superuser, as the site's database role is; without one the checks run and it is only slower."""
    try:
        with transaction.atomic():
            cursor.execute('SET session_replication_role = replica')
    except DatabaseError:
        out.write('the foreign keys stay checked (not a superuser): slower')
    try:
        yield
    finally:
        cursor.execute('SET session_replication_role = DEFAULT')


def _chunks(total: int, size: int = 1_000_000):
    """A million rows a statement, so each commit stays a few seconds and the log shows the run moving."""
    while total > 0:
        yield min(size, total)
        total -= size
