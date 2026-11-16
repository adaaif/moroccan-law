import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { LoadError } from '@/features/corpus/NotFound';
import { PageSkeleton } from '@/shared/components/ui';
import { ContributionCard, type Moderation } from './ContributionCard';
import { type CommentSort, type Contribution, moreReplies, useAround, type Writing } from './discussion.api';
import { useT } from './strings';

/** A post's comments in the reader's order (30 Oct 2026): the most useful with the asker's marked answer
 *  first, the newest, the oldest. The server sorts the same way, a page at a time. */
const SORTS: CommentSort[] = ['best', 'new', 'old'];
type Sort = CommentSort;

/** A comment with the replies the page shows under it, and how many more its door still holds. */
type Node = Contribution & { kids: Node[]; left: number };
/** What a comment's door has brought, with her own replies written since; the next page it holds. */
type Door = { rows: Contribution[]; next: number | null };

/** The tree as the page grows it (a threaded forum's tree, 30 Oct 2026): what the server sent (first-level comments
 *  with their first replies, or the line down to a linked comment), and under any comment the replies its door
 *  brought, one level per tap. A comment's door counts what the server holds and the page does not show. */
function grow(base: Contribution[], doors: ReadonlyMap<number, Door>): Node[] {
  const ids = new Set(base.map((c) => c.id));
  const under = new Map<number, Contribution[]>();
  for (const c of base) {
    if (c.reply_to && ids.has(c.reply_to.id)) under.set(c.reply_to.id, [...(under.get(c.reply_to.id) ?? []), c]);
  }
  const make = (c: Contribution): Node => {
    const seen = new Set<number>();
    const kids = [...(doors.get(c.id)?.rows ?? []), ...(under.get(c.id) ?? [])]
      .filter((k) => !seen.has(k.id) && Boolean(seen.add(k.id)));
    return { ...c, kids: kids.map(make), left: Math.max(0, (c.answers ?? 0) - kids.length) };
  };
  return base.filter((c) => !c.reply_to || !ids.has(c.reply_to.id)).map(make);
}

/** How many replies a folded comment hides, shown or still behind doors. */
const size = (n: Node): number => n.kids.reduce((s, k) => s + 1 + size(k), 0) + n.left;

type Ctx = {
  path: string; label: string; writing: Writing; mod: Moderation; onChanged: () => void; asker: boolean;
  opener: (c: Contribution) => 'question' | 'post' | false;
  count: (n: number) => string;
  open: (id: number) => void;
  asking: number | null;
  /** Her reply, shown at once under the comment it answers. */
  wrote: (to: number, made: Contribution) => void;
};

/**
 * The comments as a threaded forum draws them (30 Oct 2026, one design settled for every post's thread, adapted to a
 * conversation about the law): a tree, each comment beside its handle, a
 * circle in the topic's colour that folds it with every reply under it (so do its byline, and the rail beneath the
 * circle, the law's margin rule drawn down its replies); a first-level comment shows its first replies, and «عرض
 * الردود (N)» hangs on the rail to bring the rest in place, ten at a time, one level per tap. A link to one comment
 * (#c34) lands on the line of its conversation down to it, washed, with the way to every comment.
 */
export function Comments({ post, path, writing, mod, onChanged, sort, onSort, conversations, people, more, children }: {
  post: Contribution; path: string; writing: Writing; mod: Moderation; onChanged: () => void;
  sort: Sort; onSort: (s: Sort) => void;
  /** How many first-level comments the post holds, and how many people wrote its comments. */
  conversations: number; people: number;
  /** The next page of first-level comments, when there is one. */
  more: { loading: boolean; next: () => void } | null;
  /** The form for a new comment, between the heading and the comments. */
  children?: React.ReactNode;
}) {
  const { t, i18n } = useT();
  const location = useLocation();
  const nf = new Intl.NumberFormat(i18n.language === 'fr' ? 'fr-MA' : 'ar-MA');
  const rows = useMemo(() => post.replies ?? [], [post.replies]);
  // What each comment's door brought, kept per view (an order, or the line to a linked comment).
  const [doors, setDoors] = useState<ReadonlyMap<string, Door>>(new Map());
  const [asking, setAsking] = useState<number | null>(null);

  // A link to one comment (#c34) the page does not hold: the line of its conversation down to it, until she asks for
  // every comment (remembered against the visit that brought her, so a new link is a new ask).
  const target = /^#c\d+$/.test(location.hash) ? Number(location.hash.slice(2)) : null;
  const [allAt, setAllAt] = useState<string | null>(null);
  const view = (court: boolean) => (court ? `line${target}` : sort);
  const holds = target !== null && (rows.some((c) => c.id === target)
    || [...doors].some(([k, d]) => k.startsWith(`${sort}:`) && d.rows.some((c) => c.id === target)));
  const court = target !== null && allAt !== location.key && !holds;
  const around = useAround(post.id, court ? target : null);
  const base = useMemo(() => (court ? around.data?.replies ?? [] : rows), [court, around.data, rows]);
  const scope = view(court);
  const tree = useMemo(() => grow(base, new Map([...doors].filter(([k]) => k.startsWith(`${scope}:`))
    .map(([k, d]) => [Number(k.slice(scope.length + 1)), d]))), [base, doors, scope]);

  const open = (id: number) => {
    const door = doors.get(`${scope}:${id}`);
    if (asking !== null || (door && door.next === null)) return;
    setAsking(id);
    moreReplies(post.id, id, door?.next ?? 1)
      .then((page) => setDoors((was) => {
        const now = new Map(was);
        const seen = new Set<number>();
        const rows = [...(was.get(`${scope}:${id}`)?.rows ?? []), ...page.replies].filter((c) => !seen.has(c.id) && Boolean(seen.add(c.id)));
        now.set(`${scope}:${id}`, { rows, next: page.next_page });
        return now;
      }))
      .catch(() => undefined)
      .finally(() => setAsking(null));
  };
  const wrote = (to: number, made: Contribution) => setDoors((was) => {
    const now = new Map(was);
    const door = was.get(`${scope}:${to}`);
    now.set(`${scope}:${to}`, { rows: [...(door?.rows ?? []), made], next: door ? door.next : 1 });
    return now;
  });

  // Arriving at a comment (a link, the answer under the question): there, its words washed, once per visit; the mark
  // stays while she reads, as a link's receiver must find it.
  const landed = useRef('');
  useEffect(() => {
    if (target === null || landed.current === location.key) return;
    const el = document.getElementById(`c${target}`);
    if (!el) return;
    landed.current = location.key;
    el.scrollIntoView({ block: 'center' });
    document.querySelectorAll('.tk-msg.hit').forEach((x) => { if (x !== el) x.classList.remove('hit'); });
    el.classList.remove('hit');
    void el.offsetWidth;
    el.classList.add('hit');
  }, [target, location.key, tree]);

  // The one who asked, by their account: never a post without a name.
  const asker = post.anonymous || !post.author || 'deleted' in post.author ? null : post.author.username;
  const ctx: Ctx = {
    path, label: post.title, writing, mod, onChanged, asker: Boolean(post.mine && post.kind === 'question'),
    opener: (c) => (asker && !c.anonymous && c.author && 'username' in c.author && c.author.username === asker
      ? (post.kind === 'post' ? 'post' : 'question') : false),
    count: (n) => nf.format(n), open, asking, wrote,
  };
  return (
    <section aria-labelledby="comments" className="tk-comments">
      <div className="tk-chead">
        <h2 id="comments">{t('talk4.comments', { count: post.reply_count, n: nf.format(post.reply_count) })}</h2>
        {people > 1 ? <span className="tk-chead-n">{t('talk4.people', { count: people, n: nf.format(people) })}</span> : null}
        {conversations > 1 && !court ? (
          <div role="tablist" aria-label={t('talk2.commentSortLabel')} className="tk-seg">
            {SORTS.map((s) => (
              <button key={s} type="button" role="tab" aria-selected={sort === s} onClick={() => onSort(s)}>
                {t(`talk2.commentSorts.${s}`)}
              </button>
            ))}
          </div>
        ) : null}
      </div>
      {children}
      {court ? (
        <div className="tk-court">
          <span>{t('talk5.court')}</span>
          <button type="button" onClick={() => setAllAt(location.key)}>{t('talk5.all')}</button>
        </div>
      ) : null}
      {court && around.isLoading ? <PageSkeleton kind="text" />
        : court && around.error ? <LoadError error={around.error} retry={() => void around.refetch()} />
        : tree.length ? (
          <div className="tk-thread">
            {tree.map((n) => <Branch key={n.id} n={n} ctx={ctx} first />)}
          </div>
        ) : null}
      {more && !court ? (
        <button type="button" onClick={more.next} disabled={more.loading} className="tk-morebtn">
          {more.loading ? t('talk2.loadingComments') : t('talk2.moreComments')}
        </button>
      ) : null}
      {!court && tree.length >= 3 ? <Next /> : null}
    </section>
  );
}

/** A comment and what answers it: the handle and the rail at its side, its words, the replies the page shows, and its
 *  door. Folded, it is its byline and how many replies it hides. */
function Branch({ n, ctx, first = false }: { n: Node; ctx: Ctx; first?: boolean }) {
  const { t } = useT();
  const [folded, setFolded] = useState(false);
  const fold = () => setFolded((f) => !f);
  const hidden = size(n);
  return (
    <div className="tk-node">
      {/* The side folds the comment with every reply under it: the circle, and the rail a thumb finds. */}
      <button type="button" className="tk-handle" onClick={fold} aria-expanded={!folded}
              aria-label={folded ? t('talk5.unfold') : t('talk5.fold')}>
        <span className="tk-khatam" aria-hidden="true">
          <svg width="10" height="10" viewBox="0 0 10 10">
            <path d="M1.4 5H8.6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            {folded ? <path d="M5 1.4V8.6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" /> : null}
          </svg>
        </span>
        {folded ? null : <span className="tk-line" aria-hidden="true" />}
      </button>
      <div className="tk-main">
        {/* A first-level comment that answers one the reader cannot see still says whom it answers. */}
        <ContributionCard c={n} path={ctx.path} label={ctx.label} writing={ctx.writing} asker={ctx.asker} onChanged={ctx.onChanged}
                          mod={ctx.mod} bare opener={ctx.opener(n)}
                          quoted={first && n.reply_to ? { id: n.reply_to.id, name: n.reply_to.name, body: '' } : null}
                          folded={folded} onFold={fold}
                          hides={folded && hidden ? t('talk5.hides', { count: hidden, n: ctx.count(hidden) }) : ''}
                          onReplied={(made) => ctx.wrote(n.id, made)} />
        {!folded && n.kids.length ? (
          <div className="tk-kids">{n.kids.map((k) => <Branch key={k.id} n={k} ctx={ctx} />)}</div>
        ) : null}
        {!folded && n.left > 0 ? (
          <button type="button" className="tk-moredoor" aria-disabled={ctx.asking === n.id} aria-busy={ctx.asking === n.id}
                  onClick={() => ctx.open(n.id)}>
            {ctx.asking === n.id ? t('talk2.loadingComments')
              : n.kids.length ? t('talk5.more', { count: n.left, n: ctx.count(n.left) })
              : t('talk5.replies', { count: n.left, n: ctx.count(n.left) })}
          </button>
        ) : null}
      </div>
    </div>
  );
}

/** «التعليق التالي» on a phone (after the Apollo app's): from one first-level comment to the next, past a conversation
 *  she is not following; only while there is a next one. */
function Next() {
  const { t } = useT();
  const [there, setThere] = useState(true);
  useEffect(() => {
    const look = () => setThere([...document.querySelectorAll<HTMLElement>('.tk-thread > .tk-node')]
      .some((el) => el.getBoundingClientRect().top > 96));
    look();
    window.addEventListener('scroll', look, { passive: true });
    return () => window.removeEventListener('scroll', look);
  }, []);
  if (!there) return null;
  return (
    <button type="button" className="tk-next" aria-label={t('talk5.next')} title={t('talk5.next')}
            onClick={() => [...document.querySelectorAll<HTMLElement>('.tk-thread > .tk-node')]
              .find((el) => el.getBoundingClientRect().top > 96)
              ?.scrollIntoView({ block: 'start', behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' })}>
      <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round"
           strokeLinejoin="round" aria-hidden="true"><path d="m6 9 6 6 6-6" /></svg>
    </button>
  );
}
