import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { AR } from '@/features/corpus/format';
import { api } from '@/shared/services/api';
import { staffSeen, upload } from './discussion.api';
import { BlurEditor } from './BlurEditor';
import { VoicePlayer } from './audio/VoicePlayer';
import { Body, Who } from './ContributionCard';
import { RULES, type Contribution, type Label, type Reason, type Rule } from './discussion.api';
import { useNoIndex } from './noindex';
import { ago, clock, errorText, labelName, pageOf, placeName, reviewWait, ruleNo, shortDate, useT } from './strings';
import { usePageTitle } from '@/shared/services/title';
import { Page } from '@/shared/components/ui';

type Tab = 'held' | 'reported' | 'explain' | 'appeals' | 'pauses' | 'ledger' | 'guide' | 'reviewers';
/** «باختصار» to check or reported: each opens on its own page, where the reviewer acts. */
type ExplainWaiting = { items: { path: string; register: 'ar' | 'darija' | 'fr'; kind: 'article' | 'text' | 'word';
                                 pending: boolean; held_reasons: string[]; reports: number; since: string }[] };
type Context = { article: string; parent: { id: number; title: string; body: string; kind: string; anonymous: boolean } | null;
                 recent: { id: number; path: string; body: string; created_at: string; state: string; rule: Rule | null }[];
                 trusted: boolean; suggested: Rule | null };
type Card = Contribution & {
  path: string; label: Label; post_title: string; held_reasons: string[]; held_spans: [number, number, string][];
  deleted: boolean; removed: boolean; hidden: boolean; rule: Rule | null; waiting_since: string | null;
  reports: { reasons: Partial<Record<Reason, number>>; details: string[]; moments: number[];
             takedowns: { details: string; contact: string }[] };
  record: { contributions: number; removed: number; paused: number }; revisions: string[]; context: Context;
};
type Queue = { tab: Tab; counts: Record<'held' | 'reported' | 'appeals' | 'pauses', number>; staff: boolean;
               median_hours: number | null; items: (Card | AppealItem | PauseItem)[] };
type AppealItem = { id: number; text: string; created_at: string; on: 'contribution' | 'pause';
                    pause: { until: string | null; rule: Rule } | null; contribution: Card | null };
type PauseItem = { id: number; until: string | null; rule: Rule; note: string; started_at: string;
                   waiting_second_eye: boolean; asked_by_me: boolean; who: string | null; path: string | null };
type Ledger = { actions: { verb: string; created_at: string; rule: Rule | null; note: string; actor: string | null;
                           target: string | null; path: string | null; contribution: number | null }[] };

const UNDO_SECONDS = 10;
const act = (pk: number, body: object) => api(`/discussion/review/contributions/${pk}/`, { method: 'POST', json: body });

/** An act waits ten seconds before it is sent, so «تراجع» can take it back (M6). */
type Pending = { id: number; body: object; label: string; left: number };

/** /review: the reviewers' queue (D10, and the polish of 19 Oct 2026). One card per contribution carries what is
 *  needed to decide (M1), the suggested rule (M2), redaction (M3), send back (M4); the worst first (M7); a keyboard
 *  and an undo (M6); the guide and staff's choice of each topic's moderators (M12, 29 Oct 2026). */
export default function ReviewPage() {
  const { t } = useT();
  usePageTitle([t('review.title')]);
  const [tab, setTab] = useState<Tab>('held');
  const client = useQueryClient();
  const [pending, setPending] = useState<Pending[]>([]);
  const [focus, setFocus] = useState(0);
  const timers = useRef<Map<number, number>>(new Map());
  useNoIndex();
  const queue = useQuery<Queue | Ledger | ExplainWaiting | null>({
    queryKey: ['discussion', 'review', tab],
    queryFn: () => tab === 'ledger' ? api<Ledger>('/discussion/review/ledger/')
      : tab === 'explain' ? api<ExplainWaiting>('/explain/waiting/')
      : ['guide', 'reviewers'].includes(tab) ? Promise.resolve(null) : api<Queue>(`/discussion/review/?tab=${tab}`),
    retry: false,
  });
  const counts = useQuery({ queryKey: ['discussion', 'review', 'held'], queryFn: () => api<Queue>('/discussion/review/?tab=held').then((d) => staffSeen(d.staff, d)),
                            retry: false });
  const changed = useCallback(() => void client.invalidateQueries({ queryKey: ['discussion', 'review'] }), [client]);

  const send = useCallback(async (p: Pending) => {
    timers.current.delete(p.id);
    setPending((all) => all.filter((x) => x.id !== p.id));
    try {
      await act(p.id, p.body);
    } finally {
      changed();
    }
  }, [changed]);
  const schedule = (id: number, body: object, label: string) => {
    const p: Pending = { id, body, label, left: UNDO_SECONDS };
    setPending((all) => [...all.filter((x) => x.id !== id), p]);
    window.clearInterval(timers.current.get(id));
    let left = UNDO_SECONDS;
    const timer = window.setInterval(() => {
      left -= 1;
      if (left <= 0) {
        window.clearInterval(timer);
        void send(p);
      } else {
        setPending((all) => all.map((x) => (x.id === id ? { ...x, left } : x)));
      }
    }, 1000);
    timers.current.set(id, timer);
  };
  const undo = (id?: number) => {
    const target = id ?? pending.at(-1)?.id;
    if (target === undefined) return;
    window.clearInterval(timers.current.get(target));
    timers.current.delete(target);
    setPending((all) => all.filter((x) => x.id !== target));
  };
  const pendingRef = useRef(pending);
  pendingRef.current = pending;
  // Leaving the page sends what is waiting rather than losing it.
  useEffect(() => {
    const flush = () => {
      for (const p of pendingRef.current) {
        window.clearInterval(timers.current.get(p.id));
        void fetch(`/api/discussion/review/contributions/${p.id}/`, {
          method: 'POST', keepalive: true, body: JSON.stringify(p.body),
          headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${tokenOf()}` },
        });
      }
    };
    window.addEventListener('pagehide', flush);
    return () => window.removeEventListener('pagehide', flush);
  }, []);

  const cards = queue.data && 'items' in queue.data && ['held', 'reported'].includes(tab) ? (queue.data.items as Card[]) : [];
  // The keyboard (M6): J/K move, A the card's first act, E redact what was matched and publish, B send back,
  // R remove under the suggested rule, U undo.
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      const el = e.target as HTMLElement;
      if (['INPUT', 'TEXTAREA', 'SELECT'].includes(el.tagName) || e.metaKey || e.ctrlKey || e.altKey) return;
      const c = cards[focus];
      const k = e.key.toLowerCase();
      if (k === 'j' || k === 'k') {
        const next = Math.max(0, Math.min(cards.length - 1, focus + (k === 'j' ? 1 : -1)));
        setFocus(next);
        document.getElementById(`q${cards[next]?.id}`)?.scrollIntoView({ block: 'center' });
      } else if (k === 'u') undo();
      else if (c && k === 'a') schedule(c.id, primary(tab), t(primaryLabel(c, tab)));
      else if (c && k === 'r' && c.context.suggested) schedule(c.id, { act: 'remove', rule: c.context.suggested }, t('review.removeSuggested', { n: ruleNo(c.context.suggested) }));
      else if (c && k === 'e' && c.held_spans.some(([s, e2]) => e2 > s)) schedule(c.id, { act: 'redact', spans: c.held_spans.filter(([s, e2]) => e2 > s).map(([s, e2]) => [s, e2]) }, t('review.redactMatched'));
      else if (c && k === 'b') document.getElementById(`back-${c.id}`)?.focus();
      else return;
      e.preventDefault();
    };
    document.addEventListener('keydown', key);
    return () => document.removeEventListener('keydown', key);
  });

  if (counts.error) return <Shell><p className="text-repealed">{t('review.notReviewer')}</p></Shell>;
  const n = counts.data?.counts;
  const staff = Boolean(counts.data?.staff);
  const tabs: Tab[] = ['held', 'reported', 'explain', 'appeals', 'pauses', 'ledger', 'guide', ...(staff ? ['reviewers'] as Tab[] : [])];
  return (
    <Shell>
      <div className="-mx-4 flex flex-col gap-5 bg-sheet px-5 py-7 sm:mx-0 sm:rounded-card sm:px-8">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <h1 className="m-0 font-law text-h1 font-semibold">{t('review.title')}</h1>
          {counts.data?.median_hours ? <span className="text-meta text-ink-soft">{reviewWait(t, counts.data.median_hours, ['review.medianMinutes', 'review.median'])}</span> : null}
        </div>
        <div role="tablist" className="flex flex-wrap gap-1.5">
          {tabs.map((k) => (
            <button key={k} type="button" role="tab" aria-selected={tab === k} onClick={() => { setTab(k); setFocus(0); }}
                    className={`h-10 rounded-full border px-4 text-meta ${tab === k ? 'border-stamp bg-stamp text-on-stamp' : 'border-rule hover:border-stamp'}`}>
              {t(`review.tabs.${k}`)}{n && k in n && n[k as keyof typeof n] ? ` (${n[k as keyof typeof n]})` : ''}
            </button>
          ))}
        </div>
        {['held', 'reported'].includes(tab) ? (
          <p className="m-0 flex flex-wrap items-center gap-x-3 gap-y-1 text-meta text-ink-soft" dir="ltr">
            <span>{t('review.keys')}</span><Kbd>J</Kbd>/<Kbd>K</Kbd><Kbd>A</Kbd><Kbd>E</Kbd><Kbd>B</Kbd><Kbd>R</Kbd><Kbd>U</Kbd>
          </p>
        ) : null}
        {queue.isLoading ? <p className="m-0 text-ink-soft">{t('loading')}</p> : null}
        {tab === 'guide' ? <Guide /> : null}
        {tab === 'reviewers' ? <Reviewers /> : null}
        {queue.data && tab === 'ledger' ? <LedgerList data={queue.data as Ledger} onChanged={changed} /> : null}
        {queue.data && ['held', 'reported'].includes(tab) ? (
          cards.length ? (
            <div className="flex flex-col gap-4">
              {cards.map((c, i) => {
                const p = pending.find((x) => x.id === c.id);
                return p ? (
                  <div key={c.id} role="status" className="flex flex-wrap items-center gap-3 rounded-control border border-dashed border-rule px-4 py-3 text-meta">
                    <span className="font-semibold">{p.label}</span>
                    <span className="text-ink-soft">{t('review.undoIn', { s: p.left })}</span>
                    <button type="button" onClick={() => undo(c.id)} className="ms-auto h-10 rounded-control border border-stamp px-4 font-semibold text-stamp hover:bg-wash">
                      {t('review.undoNow')}
                    </button>
                  </div>
                ) : (
                  <QueueCard key={c.id} c={c} tab={tab} staff={queue.data && 'staff' in queue.data ? queue.data.staff : false}
                             focused={i === focus} onFocus={() => setFocus(i)} schedule={schedule} onChanged={changed} />
                );
              })}
            </div>
          ) : <p className="m-0 text-body text-ink-soft">{t('review.empty')}</p>
        ) : null}
        {queue.data && tab === 'explain' ? <ExplainList data={queue.data as ExplainWaiting} /> : null}
        {queue.data && tab === 'appeals' ? (
          (queue.data as Queue).items.length
            ? <div className="flex flex-col gap-4">{(queue.data as Queue).items.map((item) => <AppealCard key={item.id} a={item as AppealItem} onChanged={changed} />)}</div>
            : <p className="m-0 text-body text-ink-soft">{t('review.empty')}</p>
        ) : null}
        {queue.data && tab === 'pauses' ? (
          (queue.data as Queue).items.length
            ? <div className="flex flex-col gap-4">{(queue.data as Queue).items.map((item) => <PauseCard key={item.id} p={item as PauseItem} onChanged={changed} />)}</div>
            : <p className="m-0 text-body text-ink-soft">{t('review.empty')}</p>
        ) : null}
      </div>
    </Shell>
  );
}

/** «باختصار» waiting for this reviewer: an edit to check, or a state readers reported. */
function ExplainList({ data }: { data: ExplainWaiting }) {
  const { t, i18n } = useT();
  if (!data.items.length) return <p className="m-0 text-body text-ink-soft">{t('review.empty')}</p>;
  return (
    <ul className="m-0 flex list-none flex-col gap-2 p-0">
      {data.items.map((e) => (
        <li key={`${e.path}:${e.register}`} className="flex flex-col gap-1 rounded-control border border-rule px-4 py-3">
          <Link to={`/explain${e.path}`} dir="ltr" className="self-start font-mono text-meta font-semibold no-underline">{e.path}</Link>
          <span className="text-meta text-ink-soft">
            {[e.pending ? t('review.explain.pending') : '', e.reports ? t('review.explain.reports', { count: e.reports }) : '',
              ago(e.since, i18n.language)].filter(Boolean).join(' · ')}
          </span>
          {e.held_reasons.length ? <span className="text-meta">{t('review.heldFor')} {e.held_reasons.map((r) => t(`heldReasons.${r}`, { defaultValue: r })).join('، ')}</span> : null}
        </li>
      ))}
    </ul>
  );
}

function tokenOf(): string {
  try {
    return (JSON.parse(localStorage.getItem('law.session') ?? '{}') as { access?: string }).access ?? '';
  } catch {
    return '';
  }
}

/** The card's first act, by tab: publish a held one (dropping what was matched when there is some), keep a
 *  reported one. */
function primary(tab: Tab): object {
  return tab === 'held' ? { act: 'approve' } : { act: 'keep' };
}

function primaryLabel(c: Card, tab: Tab): string {
  return tab === 'held' ? 'mod.approve' : c.hidden ? 'review.unhide' : 'review.keep';
}

function age(since: string | null): { label: string; tone: string } {
  if (!since) return { label: '', tone: '' };
  const hours = (Date.now() - new Date(since).getTime()) / 3_600_000;
  return { label: since, tone: hours < 6 ? 'bg-in-force-wash text-in-force' : hours < 24 ? 'bg-amended-wash text-amended' : 'bg-repealed/15 text-repealed' };
}

/** The words, with what a hold matched marked in amber; words the reviewer selects can be removed alone (M3). */
function Marked({ c, onSelect }: { c: Card; onSelect: (span: [number, number] | null) => void }) {
  const ref = useRef<HTMLParagraphElement>(null);
  useEffect(() => {
    const change = () => {
      const s = document.getSelection();
      const el = ref.current;
      if (!s || !el || s.rangeCount === 0 || s.isCollapsed || !el.contains(s.getRangeAt(0).commonAncestorContainer)) {
        onSelect(null);
        return;
      }
      const range = s.getRangeAt(0);
      const before = document.createRange();
      before.selectNodeContents(el);
      before.setEnd(range.startContainer, range.startOffset);
      const start = before.toString().length;
      onSelect([start, start + range.toString().length]);
    };
    document.addEventListener('selectionchange', change);
    return () => document.removeEventListener('selectionchange', change);
  }, [onSelect]);
  const spans = c.held_spans.filter(([s, e]) => e > s).sort((a, b) => a[0] - b[0]);
  const parts: React.ReactNode[] = [];
  let at = 0;
  spans.forEach(([s, e], i) => {
    parts.push(c.body.slice(at, s));
    parts.push(<mark key={i} className="rounded-[2px] bg-amended-wash text-amended">{c.body.slice(s, e)}</mark>);
    at = e;
  });
  parts.push(c.body.slice(at));
  return <p ref={ref} dir="auto" className="m-0 whitespace-pre-line text-body leading-[1.85]">{parts}</p>;
}

function QueueCard({ c, tab, staff, focused, onFocus, schedule, onChanged }: {
  c: Card; tab: Tab; staff: boolean; focused: boolean; onFocus: () => void;
  schedule: (id: number, body: object, label: string) => void; onChanged: () => void;
}) {
  const { t, i18n } = useT();
  const [rule, setRule] = useState<Rule | ''>(c.context.suggested ?? '');
  const [days, setDays] = useState<'3' | '7' | '28' | 'permanent'>('7');
  const [note, setNote] = useState('');
  const [back, setBack] = useState('');
  const [dup, setDup] = useState('');
  const [selected, setSelected] = useState<[number, number] | null>(null);
  const [jump, setJump] = useState<{ ms: number; at: number } | null>(null);
  const [covering, setCovering] = useState<{ id: string; file: File } | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [revealed, setRevealed] = useState<{ username: string; display_name: string; email: string } | null>(null);
  const onSelect = useCallback((span: [number, number] | null) => setSelected(span), []);
  const matched = c.held_spans.filter(([s, e]) => e > s).map(([s, e]) => [s, e]);
  const waited = age(c.waiting_since);
  const direct = async (body: object) => {
    setError(null);
    try {
      const r = await act(c.id, { ...body, note });
      if ((body as { act: string }).act === 'reveal') setRevealed(r as typeof revealed);
      else onChanged();
    } catch (e) {
      setError(e);
    }
  };
  const cover = async (pictureId: string, src: string) => {
    const blob = await (await fetch(src)).blob();
    setCovering({ id: pictureId, file: new File([blob], 'picture.webp', { type: blob.type }) });
  };
  const sendCovered = async (blob: Blob) => {
    if (!covering) return;
    const form = new FormData();
    form.append('picture', blob, 'picture.jpg');
    setCovering(null);
    try {
      await upload(`/discussion/review/contributions/${c.id}/pictures/${covering.id}/`, form);
      onChanged();
    } catch (e) {
      setError(e);
    }
  };
  const chip = 'h-10 rounded-control px-4 text-meta font-medium';
  return (
    <article id={`q${c.id}`} onClick={onFocus}
             className={`flex scroll-mt-28 flex-col gap-3 rounded-control border p-4 sm:p-5 ${focused ? 'border-stamp ring-1 ring-stamp' : 'border-rule'}`}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 text-meta text-ink-soft">
        {c.label.place ? (
          <>
            <Link to={`${pageOf(c.path)}#c${c.id}`} dir="auto" className="font-semibold no-underline">{c.post_title || t('review.post')}</Link>
            <span className="min-w-0 flex-1 text-body text-talk">{labelName(c.label, i18n.language)}</span>
          </>
        ) : (
          <>
            <Link to={`${pageOf(c.path)}#c${c.id}`} className="font-semibold no-underline"><bdi {...AR}>{t('review.on', { article: c.label.article })}</bdi></Link>
            <span dir="auto" className="min-w-0 flex-1 text-body">{c.label.text}</span>
          </>
        )}
        {waited.label ? <span className={`rounded-full px-2 text-meta font-semibold ${waited.tone}`}>{t('review.waitedFor', { time: ago(waited.label, i18n.language) })}</span> : null}
      </div>
      {c.context.article ? <details className="text-meta">
        <summary className="cursor-pointer text-ink-soft">{t('review.articleText')}</summary>
        <p {...AR} className="m-0 mt-2 whitespace-pre-line border-s-[3px] border-stamp ps-3 font-law text-law leading-relaxed text-ink-soft">{c.context.article}</p>
      </details> : null}
      {c.context.parent ? (
        <div className="rounded-control bg-paper px-3 py-2 text-meta">
          <span className="text-meta text-ink-soft">{t('review.parentQ')}</span>
          {c.context.parent.title ? <p dir="auto" className="m-0 font-semibold">{c.context.parent.title}</p> : null}
          <p dir="auto" className="m-0 line-clamp-3">{c.context.parent.body}</p>
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-2 text-meta">
        {c.anonymous ? <span className="text-ink-soft">{t('review.anonymous')}</span> : <Who author={c.author} anonymous={false} />}
        {c.kind !== 'comment' ? <span className="rounded-full border border-stamp px-1.5 text-meta font-semibold text-stamp">{t(`kinds.${c.kind}`)}</span> : null}
        {c.context.trusted ? <span className="rounded-full bg-in-force-wash px-1.5 text-meta text-in-force">{t('review.trusted')}</span> : null}
        {c.hidden ? <span className="rounded-full bg-amended-wash px-1.5 text-meta text-amended">{t('review.hidden')}</span> : null}
        {c.held_reasons.includes('returned') ? <span className="rounded-full bg-wash px-1.5 text-meta text-stamp">{t('review.returned')}</span> : null}
      </div>
      <p className="m-0 text-meta text-ink-soft">{t('review.record', c.record)}</p>
      {c.context.recent.length ? (
        <details className="text-meta">
          <summary className="cursor-pointer text-ink-soft">{t('review.recent')}</summary>
          <ul className="m-0 mt-2 flex list-none flex-col gap-1 p-0">
            {c.context.recent.map((r) => (
              <li key={r.id} className="flex gap-2">
                <span className={r.state === 'removed' ? 'text-repealed' : r.state === 'published' ? 'text-in-force' : 'text-amended'}>
                  {r.state === 'removed' ? t('account.states.removed', { n: ruleNo(r.rule) }) : r.state === 'published' ? t('account.states.published') : t('account.states.held')}
                </span>
                <span dir="auto" className="min-w-0 truncate">{r.body}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {c.held_reasons.filter((r) => r !== 'returned').length ? (
        <p className="m-0 flex flex-wrap gap-1.5 text-meta">
          <span className="text-ink-soft">{t('review.heldFor')}</span>
          {c.held_reasons.filter((r) => r !== 'returned').map((r) => <span key={r} className="rounded-full bg-amended-wash px-2 text-amended">{t(`heldReasons.${r}`)}</span>)}
        </p>
      ) : null}
      {c.reports.takedowns.map((d, i) => (
        <div key={i} className="rounded-control border border-repealed/50 px-3 py-2 text-meta">
          <span className="font-semibold text-repealed">{t('review.takedown')}</span>
          <p dir="auto" className="m-0">{d.details}</p>
          {d.contact ? <p className="m-0 text-meta text-ink-soft">{t('review.contact')} <bdi dir="auto">{d.contact}</bdi></p> : null}
        </div>
      ))}
      {Object.keys(c.reports.reasons).length ? (
        <p className="m-0 flex flex-wrap gap-1.5 text-meta">
          <span className="text-ink-soft">{t('review.reports')}:</span>
          {Object.entries(c.reports.reasons).map(([r, k]) => <span key={r} className="rounded-full bg-amended-wash px-2 text-amended">{t(`reasons.${r}`)} ×{k}</span>)}
        </p>
      ) : null}
      {c.quote ? <q {...AR} className="block border-s-[3px] border-stamp ps-3 font-law text-law text-ink-soft [quotes:none]">{c.quote}</q> : null}
      {c.body ? <Marked c={c} onSelect={onSelect} /> : null}
      {c.voice ? (
        <div className="flex flex-col gap-2">
          <VoicePlayer id={c.voice.id} src={c.voice.src} durationMs={c.voice.duration_ms} peaks={c.voice.peaks} jump={jump} />
          {c.reports.moments.length ? (
            <span className="flex flex-wrap gap-1.5">
              {c.reports.moments.map((ms, i) => (
                <button key={i} type="button" onClick={() => setJump({ ms, at: Date.now() })} dir="ltr"
                        className="h-10 rounded-full border border-amended px-3 text-meta text-amended hover:bg-amended-wash">
                  {t('review.moment', { time: clock(ms) })}
                </button>
              ))}
            </span>
          ) : null}
        </div>
      ) : null}
      {c.pictures.length ? (
        <div className="flex flex-wrap gap-3">
          {c.pictures.map((p) => (
            <figure key={p.id} className="m-0 flex flex-col gap-1">
              <a href={p.full} target="_blank" rel="noreferrer"><img src={p.thumb} alt="" className="h-28 rounded-control border border-rule" /></a>
              <button type="button" onClick={() => void cover(p.id, p.full)} className="text-meta text-stamp hover:underline">{t('review.coverPicture')}</button>
            </figure>
          ))}
        </div>
      ) : null}
      {c.revisions.length ? (
        <details className="text-meta"><summary className="cursor-pointer text-ink-soft">{t('review.revisions')}</summary>
          <ol className="m-0 mt-2 ps-5">{c.revisions.map((d, i) => <li key={i} dir="auto" className="whitespace-pre-line">{d}</li>)}</ol></details>
      ) : null}
      {c.reports.details.length ? (
        <details className="text-meta"><summary className="cursor-pointer text-ink-soft">{t('review.details')}</summary>
          <ul className="m-0 mt-2 ps-5">{c.reports.details.map((d, i) => <li key={i} dir="auto">{d}</li>)}</ul></details>
      ) : null}

      <div className="flex flex-col gap-2 border-t border-rule-soft pt-3">
        <div className="flex flex-wrap items-center gap-2">
          {tab === 'held' && matched.length ? (
            <button type="button" className={`${chip} bg-stamp text-on-stamp hover:bg-stamp-deep`}
                    onClick={() => schedule(c.id, { act: 'redact', spans: matched }, t('review.redactMatched'))}>{t('review.redactMatched')}</button>
          ) : null}
          <button type="button" className={`${chip} ${tab === 'held' && matched.length ? 'border border-rule hover:bg-paper' : 'bg-stamp text-on-stamp hover:bg-stamp-deep'}`}
                  onClick={() => schedule(c.id, primary(tab), t(primaryLabel(c, tab)))}>{t(primaryLabel(c, tab))}</button>
          {selected ? (
            <button type="button" className={`${chip} border border-stamp text-stamp hover:bg-wash`}
                    onClick={() => schedule(c.id, { act: 'redact', spans: [selected], publish: tab === 'held' }, t('review.redactSelected'))}>{t('review.redactSelected')}</button>
          ) : null}
          {c.context.suggested ? (
            <button type="button" className={`${chip} border border-repealed text-repealed hover:bg-paper`}
                    onClick={() => schedule(c.id, { act: 'remove', rule: c.context.suggested }, t('review.removeSuggested', { n: ruleNo(c.context.suggested) }))}>
              {t('review.removeSuggested', { n: ruleNo(c.context.suggested) })}
            </button>
          ) : null}
        </div>
        {c.context.suggested ? <p className="m-0 text-meta text-ink-soft">{t('review.suggested')} {ruleNo(c.context.suggested)}. {t(`rules.${c.context.suggested}`)} · {t('review.selectHint')}</p> : <p className="m-0 text-meta text-ink-soft">{t('review.selectHint')}</p>}
        <div className="flex flex-wrap items-center gap-2">
          <select value={rule} onChange={(e) => setRule(e.target.value as Rule)} aria-label={t('review.rule')}
                  className="h-10 rounded-control border border-field bg-sheet px-2 text-meta">
            <option value="">{t('review.rule')}</option>
            {RULES.map((r, i) => <option key={r} value={r}>{i + 1}. {t(`rules.${r}`)}</option>)}
          </select>
          <button type="button" disabled={!rule} className={`${chip} border border-repealed text-repealed hover:bg-paper disabled:opacity-50`}
                  onClick={() => schedule(c.id, { act: 'remove', rule }, t('review.remove'))}>{t('review.remove')}</button>
          <select value={days} onChange={(e) => setDays(e.target.value as typeof days)} aria-label={t('review.pause')}
                  className="h-10 rounded-control border border-field bg-sheet px-2 text-meta">
            {(['3', '7', '28', 'permanent'] as const).map((d) => <option key={d} value={d}>{t(`review.days.${d}`)}</option>)}
          </select>
          <button type="button" disabled={!rule} className={`${chip} border border-rule hover:bg-paper disabled:opacity-50`}
                  onClick={() => void direct({ act: 'pause', days, rule })}>{t('review.pause')}</button>
          <button type="button" className={`${chip} border border-rule hover:bg-paper`}
                  onClick={() => void direct({ act: c.context.trusted ? 'untrust' : 'trust' })}>{c.context.trusted ? t('review.untrust') : t('review.trust')}</button>
          {staff && c.anonymous ? <button type="button" className={`${chip} border border-rule hover:bg-paper`} onClick={() => void direct({ act: 'reveal' })}>{t('review.reveal')}</button> : null}
        </div>
        {days === 'permanent' ? <p className="m-0 text-meta text-ink-soft">{t('review.permanentNote')}</p> : null}
        <div className="flex flex-wrap items-center gap-2">
          <input id={`back-${c.id}`} value={back} onChange={(e) => setBack(e.target.value)} dir="auto" placeholder={t('review.sendBackNote')}
                 className="h-10 min-w-0 flex-1 rounded-control border border-field bg-paper px-3 text-meta focus:border-stamp focus:bg-sheet focus:outline-none" />
          <button type="button" disabled={!back.trim()} className={`${chip} border border-stamp text-stamp hover:bg-wash disabled:opacity-50`}
                  onClick={() => schedule(c.id, { act: 'send_back', note: back }, t('review.sendBack'))}>{t('review.sendBack')}</button>
        </div>
        {c.kind === 'question' && !c.parent ? (
          <div className="flex flex-wrap items-center gap-2">
            <input value={dup} onChange={(e) => setDup(e.target.value.replace(/\D/g, ''))} inputMode="numeric" dir="ltr"
                   placeholder={t('review.duplicateId')} aria-label={t('review.duplicateId')}
                   className="h-10 w-40 rounded-control border border-field bg-paper px-3 text-meta focus:border-stamp focus:bg-sheet focus:outline-none" />
            <button type="button" disabled={!dup} className={`${chip} border border-rule hover:bg-paper disabled:opacity-50`}
                    onClick={() => void direct({ act: 'duplicate', of: Number(dup) })}>{t('review.duplicate')}</button>
          </div>
        ) : null}
        <input value={note} onChange={(e) => setNote(e.target.value)} dir="auto" placeholder={c.anonymous && staff ? t('review.revealNote') : t('review.note')}
               className="h-10 rounded-control border border-field bg-paper px-3 text-meta focus:border-stamp focus:bg-sheet focus:outline-none" />
        {revealed ? <p className="m-0 text-meta font-semibold">{t('review.revealed', { name: revealed.display_name || revealed.username, email: revealed.email })}</p> : null}
        {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
      </div>
      {covering ? <BlurEditor file={covering.file} onDone={(b) => void sendCovered(b)} onCancel={() => setCovering(null)} /> : null}
    </article>
  );
}

function AppealCard({ a, onChanged }: { a: AppealItem; onChanged: () => void }) {
  const { t } = useT();
  const [error, setError] = useState<unknown>(null);
  const decide = async (outcome: 'lifted' | 'kept') => {
    try {
      await api(`/discussion/review/appeals/${a.id}/`, { method: 'POST', json: { outcome } });
      onChanged();
    } catch (e) {
      setError(e);
    }
  };
  return (
    <article className="flex flex-col gap-3 rounded-control border border-rule p-4 sm:p-5">
      <h3 className="m-0 text-body font-semibold">{t(`review.appealOn.${a.on}`)}</h3>
      {a.pause ? <p className="m-0 text-meta text-ink-soft">{t('marker.removed', { n: ruleNo(a.pause.rule) })}</p> : null}
      {a.contribution?.rule ? <p className="m-0 text-meta text-ink-soft">{t('marker.removed', { n: ruleNo(a.contribution.rule) })}</p> : null}
      {a.contribution?.body ? <div className="rounded-control bg-paper p-3"><Body body={a.contribution.body} links={a.contribution.links} /></div> : null}
      <blockquote dir="auto" className="m-0 border-s-[3px] border-stamp ps-3 text-body">{a.text}</blockquote>
      <div className="flex gap-2">
        <button type="button" onClick={() => void decide('lifted')} className="h-10 rounded-control bg-stamp px-4 text-meta font-medium text-on-stamp hover:bg-stamp-deep">{t('review.lifted')}</button>
        <button type="button" onClick={() => void decide('kept')} className="h-10 rounded-control border border-rule px-4 text-meta hover:bg-paper">{t('review.kept')}</button>
      </div>
      {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
    </article>
  );
}

function PauseCard({ p, onChanged }: { p: PauseItem; onChanged: () => void }) {
  const { t, i18n } = useT();
  const [error, setError] = useState<unknown>(null);
  const run = async (body: object) => {
    try {
      await api(`/discussion/review/pauses/${p.id}/`, { method: 'POST', json: body });
      onChanged();
    } catch (e) {
      setError(e);
    }
  };
  return (
    <article className="flex flex-col gap-2 rounded-control border border-rule p-4">
      <div className="flex flex-wrap items-center gap-3 text-body">
        <span className="font-semibold" dir="auto">{p.who ?? t('anonymous')}</span>
        <span className="text-ink-soft">{t('marker.removed', { n: ruleNo(p.rule) })}</span>
        <span className="text-ink-soft">{p.until ? t('review.until', { date: shortDate(p.until, i18n.language) }) : t('review.forGood')}</span>
        {p.waiting_second_eye ? <span className="rounded-full bg-amended-wash px-2 text-meta text-amended">{p.asked_by_me ? t('review.askedByYou') : t('review.waitingSecond')}</span> : null}
      </div>
      {p.path ? <Link to={pageOf(p.path)} className="text-meta no-underline">{p.path}</Link> : null}
      <div className="flex gap-2">
        {p.waiting_second_eye && !p.asked_by_me ? <button type="button" onClick={() => void run({ act: 'confirm' })} className="h-10 rounded-control bg-stamp px-4 text-meta font-medium text-on-stamp">{t('review.confirm')}</button> : null}
        <button type="button" onClick={() => void run({ act: 'lift' })} className="h-10 rounded-control border border-rule px-4 text-meta hover:bg-paper">{t('review.lift')}</button>
      </div>
      {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
    </article>
  );
}

function LedgerList({ data, onChanged }: { data: Ledger; onChanged: () => void }) {
  const { t, i18n } = useT();
  const [error, setError] = useState<unknown>(null);
  if (!data.actions.length) return <p className="m-0 text-body text-ink-soft">{t('review.empty')}</p>;
  return (
    <ol className="m-0 flex list-none flex-col p-0 text-meta">
      {data.actions.map((a, i) => (
        <li key={i} className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-t border-rule-soft py-2.5 first:border-t-0">
          <time dateTime={a.created_at} className="w-28 shrink-0 text-meta text-ink-soft">{ago(a.created_at, i18n.language)}</time>
          <span dir="auto" className="font-semibold">{a.actor ?? 'قانون'}</span>
          <span>{t(`review.verbs.${a.verb}`, { defaultValue: a.verb })}</span>
          {a.rule ? <span className="text-ink-soft">({t(`rules.${a.rule}`)})</span> : null}
          {a.target ? <span dir="auto" className="text-ink-soft">→ {a.target}</span> : null}
          {a.note ? <span dir="auto" className="text-ink-soft">«{a.note}»</span> : null}
          {a.path ? <Link to={`${pageOf(a.path)}${a.contribution ? `#c${a.contribution}` : ''}`} className="text-meta no-underline">{a.path.replace(/^\/(ma|talk)\//, '')}</Link> : null}
          {a.verb === 'remove' && a.contribution ? (
            <button type="button" className="ms-auto text-meta text-stamp hover:underline"
                    onClick={async () => {
                      try { await act(a.contribution!, { act: 'restore' }); onChanged(); } catch (e) { setError(e); }
                    }}>{t('review.restore')}</button>
          ) : null}
        </li>
      ))}
      {error ? <li role="alert" className="text-repealed">{errorText(t, error)}</li> : null}
    </ol>
  );
}

/** Per rule, two cases to remove and two to keep (M12): one reading of the rules across reviewers. */
function Guide() {
  const { t } = useT();
  return (
    <div className="flex flex-col gap-5">
      <p className="m-0 max-w-[66ch] text-body text-ink-soft">{t('review.guideLede')}</p>
      {RULES.map((r, i) => (
        <section key={r} className="flex flex-col gap-2 border-t border-rule-soft pt-4">
          <h3 className="m-0 text-body font-semibold">{i + 1}. {t(`rules.${r}`)}</h3>
          <div className="grid gap-3 sm:grid-cols-2">
            {(['remove', 'keep'] as const).map((k) => (
              <div key={k} className={`rounded-control px-3 py-2 ${k === 'remove' ? 'bg-amended-wash' : 'bg-in-force-wash'}`}>
                <span className={`text-meta font-semibold ${k === 'remove' ? 'text-amended' : 'text-in-force'}`}>{t(k === 'remove' ? 'review.guideRemove' : 'review.guideKeep')}</span>
                <ul className="m-0 mt-1 ps-5 text-meta">
                  {(t(`guide.${r}.${k}`, { returnObjects: true }) as string[]).map((x) => <li key={x}>{x}</li>)}
                </ul>
              </div>
            ))}
          </div>
        </section>
      ))}
    </div>
  );
}

type ReviewerItem = { user: number; username: string; name: string; text_paths: string[]; karma: number; appointed_at: string };
type PlaceItem = { path: string; slug: string; name: { ar: string; fr: string } };
type Candidate = { user: number; username: string; name: string; karma_here: number };

/** Staff: each topic's moderators, chosen from its community (29 Oct 2026): for a topic, the people whose
 *  words it found most useful, by the karma they earned there; appoint and end (M12). */
function Reviewers() {
  const { t, i18n } = useT();
  const client = useQueryClient();
  const [place, setPlace] = useState('');
  const list = useQuery({
    queryKey: ['discussion', 'review', 'reviewers', place],
    queryFn: () => api<{ reviewers: ReviewerItem[]; places: PlaceItem[]; candidates?: Candidate[] }>(
      `/discussion/review/reviewers/${place ? `?place=${encodeURIComponent(place)}` : ''}`),
  });
  const [username, setUsername] = useState('');
  const [chosen, setChosen] = useState<string[]>([]);
  const [error, setError] = useState<unknown>(null);
  const refresh = () => void client.invalidateQueries({ queryKey: ['discussion', 'review', 'reviewers'] });
  const names = new Map((list.data?.places ?? []).map((p) => [p.path, placeName(p.name, i18n.language)]));
  const appoint = async (who: string, places: string[]) => {
    setError(null);
    try {
      await api('/discussion/review/reviewers/', { method: 'POST', json: { username: who, places } });
      setUsername('');
      setChosen([]);
      refresh();
    } catch (err) {
      setError(err);
    }
  };
  return (
    <div className="flex flex-col gap-5">
      {list.data?.reviewers.length ? (
        <ul className="m-0 flex list-none flex-col p-0">
          {list.data.reviewers.map((r) => (
            <li key={r.user} className="flex flex-wrap items-center gap-3 border-t border-rule-soft py-3 text-body first:border-t-0">
              <span dir="auto" className="font-semibold">{r.name}</span>
              {r.karma ? <span className="text-meta tabular-nums text-ink-soft">✦ {r.karma}</span> : null}
              <span className="text-meta text-ink-soft">
                {r.text_paths.length ? r.text_paths.map((p) => names.get(p) ?? p).join('، ') : t('review.allTexts')}
              </span>
              <button type="button" className="ms-auto text-meta text-repealed hover:underline"
                      onClick={async () => { await api(`/discussion/review/reviewers/${r.user}/`, { method: 'DELETE' }); refresh(); }}>{t('review.end')}</button>
            </li>
          ))}
        </ul>
      ) : <p className="m-0 text-body text-ink-soft">{t('review.reviewersNone')}</p>}
      <section className="flex flex-col gap-3 rounded-control bg-paper p-4">
        <h3 className="m-0 text-body font-semibold">{t('review.candidatesTitle')}</h3>
        <select value={place} onChange={(e) => setPlace(e.target.value)} aria-label={t('review.candidatesPlace')}
                className="h-10 max-w-full self-start rounded-control border border-field bg-sheet px-3 text-meta">
          <option value="">{t('review.candidatesPlace')}</option>
          {(list.data?.places ?? []).map((p) => <option key={p.path} value={p.path}>{placeName(p.name, i18n.language)}</option>)}
        </select>
        {place && list.data?.candidates ? (
          list.data.candidates.length ? (
            <ul className="m-0 flex list-none flex-col p-0">
              {list.data.candidates.map((c) => (
                <li key={c.user} className="flex flex-wrap items-center gap-3 border-t border-rule-soft py-2 text-body first:border-t-0">
                  <Link to={`/people/${encodeURIComponent(c.username)}`} dir="auto" className="font-semibold no-underline">{c.name}</Link>
                  <span className="text-meta tabular-nums text-ink-soft">{t('review.karmaHere', { count: c.karma_here })}</span>
                  <button type="button" onClick={() => void appoint(c.username, [place])}
                          className="ms-auto h-10 rounded-control border border-stamp px-3 text-meta font-medium text-stamp hover:bg-wash">
                    {t('review.appointHere')}
                  </button>
                </li>
              ))}
            </ul>
          ) : <p className="m-0 text-meta text-ink-soft">{t('review.candidatesNone')}</p>
        ) : null}
      </section>
      <form className="flex flex-col gap-2 rounded-control bg-paper p-4" onSubmit={(e) => { e.preventDefault(); void appoint(username, chosen); }}>
        <h3 className="m-0 text-body font-semibold">{t('review.appoint')}</h3>
        <label className="flex flex-col gap-1 text-meta">{t('review.appointUser')}
          <input value={username} onChange={(e) => setUsername(e.target.value)} dir="auto" className="h-10 rounded-control border border-field bg-sheet px-3" />
        </label>
        <fieldset className="m-0 flex flex-wrap gap-1.5 border-0 p-0 text-meta">
          <legend className="mb-1 p-0">{t('review.appointPlaces')}</legend>
          {(list.data?.places ?? []).map((p) => (
            <label key={p.path} className={`flex h-10 cursor-pointer items-center rounded-full border px-3 ${chosen.includes(p.slug) ? 'border-stamp bg-wash text-stamp' : 'border-rule'}`}>
              <input type="checkbox" className="sr-only" checked={chosen.includes(p.slug)}
                     onChange={(e) => setChosen((all) => e.target.checked ? [...all, p.slug] : all.filter((x) => x !== p.slug))} />
              {placeName(p.name, i18n.language)}
            </label>
          ))}
        </fieldset>
        <button type="submit" disabled={!username.trim() || !chosen.length} className="h-10 self-start rounded-control bg-stamp px-5 text-meta font-semibold text-on-stamp disabled:opacity-60">{t('review.appointGo')}</button>
        {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
      </form>
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return <kbd className="rounded-[3px] border border-b-2 border-rule bg-sheet px-1.5 font-mono text-meta text-ink">{children}</kbd>;
}

function Shell({ children }: { children: React.ReactNode }) {
  return <Page width="reading" className="gap-5">{children}</Page>;
}
