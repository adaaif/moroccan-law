import { useEffect, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { AR } from '@/features/corpus/format';
import { useSession } from '@/shared/stores/session';
import { VoicePlayer } from './audio/VoicePlayer';
import { Composer } from './Composer';
import { discussionApi, RULES, type Author, type Contribution, type Rule, type Writing } from './discussion.api';
import { Lightbox } from './Lightbox';
import { ReportSheet } from './ReportSheet';
import { TakedownSheet } from './TakedownSheet';
import { ago, errorText, pageOf, reviewWait, ruleNo, shortDate, useT } from './strings';
import { ApiError } from '@/shared/services/api';
import { Returned } from './Returned';
import { signature } from '@/features/corpus/article/message';

/** Who reviews this discussion, and the other questions a repeat could point to (M5, M9). */
export type Moderation = { can: boolean; questions: { id: number; title?: string; body: string }[] };

const SHOWN_ANSWERS = 3;

/** A contribution as readers see it: who (or «بدون اسم») with their karma, a post's kind, the quoted words, the
 *  text with its citations as links, its voice and pictures, «مفيد», and the comments under it. Its author also sees
 *  why it waits; a topic's moderator sees held ones in place and acts from its menu (M5). `path` is the post's own
 *  address (/talk/family/12). `bare`: the post's page frames it and lays out its comments itself (Comments.tsx), as a
 *  message (30 Oct 2026): who and when over the words in a bubble, the acts quiet under it (talk.css, «A post's page»). */
export function ContributionCard({ c, path, label, writing, asker, onChanged, reply = false, mod, allReplies = false,
  bare = false, after, lead, opener = false, quoted, onReplied, folded = false, onFold, hides = '' }: {
  c: Contribution;
  path: string;
  label: string;
  writing: Writing;
  /** A post's own page shows every comment; a list, the first ones. */
  allReplies?: boolean;
  /** The viewer asked the question this answers: «أفادني» is theirs to give. */
  asker?: boolean;
  onChanged: () => void;
  reply?: boolean;
  mod?: Moderation;
  bare?: boolean;
  /** Shown after the words, before the actions: the article a post started from. */
  after?: React.ReactNode;
  /** Bare: shown first in the bubble (a post's title). */
  lead?: React.ReactNode;
  /** Bare: written by the one who asked the question or wrote the post it is under (never said without a name). */
  opener?: 'question' | 'post' | false;
  /** Bare: the comment a first-level one answers when the reader cannot see it: its writer. */
  quoted?: { id: number; name: string | null; body: string } | null;
  /** Bare: after a reply to it is sent (the page may open its lane to show it). */
  onReplied?: (made: Contribution) => void;
  /** Bare, in a thread: folded to its byline (which folds and unfolds it too), and how many replies that hides. */
  folded?: boolean;
  onFold?: () => void;
  hides?: string;
}) {
  const { t, i18n } = useT();
  const signedIn = useSession((s) => s.tokens !== null);
  const [replying, setReplying] = useState(false);
  const [menu, setMenu] = useState(false);
  const [sheet, setSheet] = useState<'' | 'report' | 'takedown'>('');
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [useful, setUseful] = useState({ n: c.useful, on: c.voted });
  const [error, setError] = useState<unknown>(null);
  const [copied, setCopied] = useState(false);
  const [shown, setShown] = useState<number | null>(null);
  const menuRef = useRef<HTMLSpanElement>(null);

  // A menu closes on a tap elsewhere or Escape, on a phone as on a desk (F4).
  useEffect(() => {
    if (!menu) return;
    const away = (e: Event) => { if (!menuRef.current?.contains(e.target as Node)) setMenu(false); };
    const key = (e: KeyboardEvent) => e.key === 'Escape' && setMenu(false);
    document.addEventListener('pointerdown', away);
    document.addEventListener('keydown', key);
    return () => { document.removeEventListener('pointerdown', away); document.removeEventListener('keydown', key); };
  }, [menu]);

  const anchor = `c${c.id}`;
  const frame = bare ? '' : reply ? 'ms-4 border-s-2 border-rule ps-4 sm:ms-10' : 'border-t border-rule-soft pt-5';

  if (c.marker && bare) {
    return (
      <div id={anchor} className="tk-msg">
        <p className="tk-gone">{c.marker === 'removed' ? t('marker.removed', { n: ruleNo(c.rule) }) : t('marker.deleted')}</p>
      </div>
    );
  }
  if (c.marker) {
    return (
      <div id={anchor} className={`${frame} scroll-mt-28`}>
        <p className="m-0 rounded-control bg-paper px-4 py-2.5 text-meta text-ink-soft">
          {c.marker === 'removed' ? t('marker.removed', { n: ruleNo(c.rule) }) : t('marker.deleted')}
        </p>
        {bare ? null : <Replies c={c} path={path} label={label} writing={writing} onChanged={onChanged} mod={mod} />}
      </div>
    );
  }

  const vote = async () => {
    setError(null);
    try {
      const r = await discussionApi.useful(c.id, !useful.on);
      setUseful({ n: r.useful, on: r.voted });
    } catch (e) {
      setError(e);
    }
  };
  const accept = async () => {
    setError(null);
    try {
      await discussionApi.accept(c.id, !c.accepted);
      onChanged();
    } catch (e) {
      setError(e);
    }
  };
  const remove = async () => {
    try {
      await discussionApi.remove(c.id);
      onChanged();
    } catch (e) {
      setError(e);
    }
  };
  const copyLink = () => {
    void navigator.clipboard?.writeText(`${window.location.origin}${pageOf(path)}#${anchor}`);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };
  /** A question and its answer, as a WhatsApp message (R4). */
  const share = async () => {
    const answer = c.replies?.find((r) => r.accepted && r.body) ?? c.replies?.find((r) => r.body && !r.marker);
    const words = [label, '', `${t('kinds.question')}: ${[c.title, c.body].filter(Boolean).join(' — ')}`];
    if (answer) words.push('', `${t('shareAnswer')}: ${answer.body}`);
    words.push('', `${t('shareMore')}: ${window.location.origin}${pageOf(path)}`, '', signature(i18n.language));
    const message = words.join('\n');
    if (navigator.share) {
      try { await navigator.share({ text: message }); return; } catch (e) { if ((e as DOMException).name === 'AbortError') return; }
    }
    window.open(`https://wa.me/?text=${encodeURIComponent(message)}`, '_blank', 'noopener');
  };

  const flagged = c.held || c.hidden;
  const when = (
    <>
      <time dateTime={c.created_at} title={shortDate(c.created_at, i18n.language)}>{ago(c.created_at, i18n.language)}</time>
      {c.edited_at ? ` · ${t('edited')}` : ''}
    </>
  );
  const kind = c.kind !== 'comment'
    ? <span className={bare ? 'tk-kind' : 'rounded-full border border-stamp px-1.5 text-meta font-semibold leading-5 text-stamp'}>{t(`kinds.${c.kind}`)}</span>
    : null;
  const heldChip = mod?.can && c.held ? <span className="rounded-full bg-amended-wash px-1.5 text-meta font-semibold leading-5 text-amended">{t('mod.held')}</span> : null;
  // What was said: the bare card's bubble holds it.
  const said = (
    <>
      {bare && quoted ? (
        <a href={`#c${quoted.id}`} className="tk-quoted">
          <b dir="auto"><span className="tk-sr">{t('talk4.replyingTo')} </span>{quoted.name ?? t('anonymous')}</b>
          {quoted.body ? <span dir="auto">{quoted.body}</span> : null}
        </a>
      ) : null}
      {lead}
      {c.quote ? (
        <q {...AR} className="block border-s-[3px] border-stamp ps-3 font-law text-law leading-relaxed text-ink-soft [quotes:none]">{c.quote}</q>
      ) : null}
      {editing ? (
        <Edit c={c} onDone={() => { setEditing(false); onChanged(); }} />
      ) : c.body ? <Body body={c.body} links={c.links} /> : null}
      {c.voice ? (
        <VoicePlayer id={c.voice.id} src={c.voice.src} durationMs={c.voice.duration_ms} peaks={c.voice.peaks}
                     refresh={async () => (await discussionApi.voiceLink(c.voice!.id)).src} />
      ) : null}
      {c.pictures.length ? (
        <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
          {c.pictures.map((p, i) => (
            <li key={p.id}>
              <button type="button" onClick={() => setShown(i)} aria-label={t('pictures.open')}
                      className="block overflow-hidden rounded-control border border-rule hover:border-stamp">
                <img src={p.thumb} alt="" loading="lazy" width={160} height={120} className="h-30 w-40 object-cover" />
              </button>
            </li>
          ))}
        </ul>
      ) : null}
      {after}
    </>
  );
  const act = bare ? 'tk-act' : 'h-10 rounded-control px-3 hover:bg-paper hover:text-stamp';
  const acts = (
    <div className={bare ? 'tk-acts' : 'flex flex-wrap items-center gap-x-1 gap-y-1 text-meta text-ink-soft'}>
      <button type="button" onClick={() => void vote()} disabled={c.mine || !signedIn || c.held} aria-pressed={useful.on}
              title={c.mine ? undefined : t('usefulHint')}
              className={bare ? act : `inline-flex h-10 items-center gap-1.5 rounded-full border px-3 ${useful.on ? 'border-stamp bg-wash text-stamp' : 'border-rule text-ink'} disabled:cursor-default disabled:opacity-80`}>
        <ThumbIcon filled={useful.on} />{useful.n ? t('usefulCount', { count: useful.n }) : t('useful')}
      </button>
      {c.accepted && !bare ? <span className="px-2 text-meta font-semibold text-in-force">✓ {t('accepted')}</span> : null}
      {asker && !c.mine ? (
        <button type="button" onClick={() => void accept()} aria-pressed={c.accepted} title={t('acceptHint')}
                className={bare ? `${act} yes` : 'h-10 rounded-control px-3 text-in-force hover:bg-paper'}>{c.accepted ? `✓ ${t('accept')}` : t('accept')}</button>
      ) : null}
      {!c.held && writing.can ? (
        <button type="button" onClick={() => setReplying((r) => !r)} aria-expanded={replying} className={act}>{t('reply')}</button>
      ) : null}
      {!reply && c.kind === 'question' && !c.held ? (
        <button type="button" onClick={() => void share()} className={act}>{t('share')}</button>
      ) : null}
      <span ref={menuRef} className="relative">
        <button type="button" onClick={() => setMenu((m) => !m)} aria-expanded={menu} aria-haspopup="menu" aria-label={t('more')}
                className={bare ? act : 'grid size-11 place-items-center rounded-control hover:bg-paper'}>⋯</button>
        {menu ? (
          <span role="menu" className="absolute end-0 top-10 z-10 flex min-w-52 flex-col rounded-control border border-rule bg-sheet py-1 shadow-lg">
            <MenuItem onClick={() => { copyLink(); setMenu(false); }}>{copied ? t('linkCopied') : t('copyLink')}</MenuItem>
            {c.mine && c.body ? <MenuItem onClick={() => { setEditing(true); setMenu(false); }}>{t('edit')}</MenuItem> : null}
            {c.mine ? <MenuItem onClick={() => { setMenu(false); setDeleting(true); }} danger>{t('delete')}</MenuItem> : null}
            {!c.mine && signedIn ? <MenuItem onClick={() => { setSheet('report'); setMenu(false); }}>{t('report')}</MenuItem> : null}
            {!c.mine ? <MenuItem onClick={() => { setSheet('takedown'); setMenu(false); }}>{t('takedown.menu')}</MenuItem> : null}
          </span>
        ) : null}
      </span>
      {copied ? <span role="status" className="text-meta text-in-force">{t('linkCopied')}</span> : null}
    </div>
  );
  const named = c.anonymous || !c.author || 'deleted' in c.author ? null : c.author.name;
  // In a thread the whole byline folds the comment, as its handle does (a thumb finds it); its links keep their own.
  const foldBy = onFold ? (e: React.MouseEvent) => { if (!(e.target as HTMLElement).closest('a,button')) onFold(); } : undefined;
  if (bare && folded) {
    return (
      <article id={anchor} aria-labelledby={`${anchor}-who`} className="tk-msg" data-folded="">
        <header id={`${anchor}-who`} className="tk-msg-who" onClick={foldBy}>
          <span className="tk-initial" aria-hidden="true">{named ? [...named.trim()][0] : '•'}</span>
          <Who author={c.author} anonymous={c.anonymous} mine={c.mine} />
          <span className="tk-msg-when">{when}</span>
          {hides ? <button type="button" className="tk-hides" onClick={onFold}>{hides}</button> : null}
        </header>
      </article>
    );
  }
  return (
    <article id={anchor} aria-labelledby={`${anchor}-who`}
             data-asker={bare && opener ? '' : undefined} data-yes={bare && c.accepted ? '' : undefined}
             data-flag={bare && flagged && mod?.can ? '' : undefined}
             className={bare ? 'tk-msg' : `${frame} flex scroll-mt-28 flex-col gap-2.5 target:bg-target-wash ${flagged && mod?.can ? 'rounded-control bg-amended-wash/40' : ''}`}>
      {bare ? (
        <header id={`${anchor}-who`} className="tk-msg-who" onClick={foldBy} data-folds={onFold ? '' : undefined}>
          {/* People are named, never drawn (TalkParts' Initial, drawn by talk.css). */}
          <span className="tk-initial" aria-hidden="true">{named ? [...named.trim()][0] : '•'}</span>
          <Who author={c.author} anonymous={c.anonymous} mine={c.mine} />
          {opener ? <span className="tk-mark">{t(`talk4.opener.${opener}`, { context: c.author && 'form' in c.author && c.author.form === 'f' ? 'f' : undefined })}</span> : null}
          {kind}
          {heldChip}
          {c.accepted ? <span className="tk-yes">✓ {t('accepted')}</span> : null}
          <span className="tk-msg-when">{when}</span>
        </header>
      ) : (
        <header id={`${anchor}-who`} className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5 text-meta">
          <Who author={c.author} anonymous={c.anonymous} mine={c.mine} />
          {kind}
          {heldChip}
          <span className="ms-auto text-meta text-ink-soft">{when}</span>
        </header>
      )}
      {c.reply_to && !bare ? (
        <a href={`#c${c.reply_to.id}`} className="-mt-1 self-start text-meta text-ink-soft no-underline hover:text-stamp">
          ↩ {c.reply_to.name ? t('replyTo', { name: c.reply_to.name }) : t('replyToAnon')}
        </a>
      ) : null}
      {c.mine && c.review_note ? (
        <p className="m-0 rounded-control bg-amended-wash px-3 py-2 text-meta text-amended">{t('sentBack', { note: c.review_note })}</p>
      ) : c.held && c.mine ? (
        <p className="m-0 rounded-control bg-amended-wash px-3 py-2 text-meta text-amended">
          {t('held')}
          {c.held_reasons?.length ? ` ${c.held_reasons.filter((r) => r !== 'returned').map((r) => t(`heldReasons.${r}`)).join(' ')}` : ''}
          {writing.review_hours ? ` ${reviewWait(t, writing.review_hours)}` : ''}
        </p>
      ) : null}
      {c.hidden && (c.mine || mod?.can) ? <p className="m-0 rounded-control bg-amended-wash px-3 py-2 text-meta text-amended">{t('hiddenNote')}</p> : null}
      {c.duplicate_of ? (
        <p className="m-0 rounded-control bg-paper px-3 py-2 text-meta text-ink-soft">
          {t('duplicateNote')} <a href={`#c${c.duplicate_of}`}>{t('seeOriginal')}</a>
        </p>
      ) : null}
      {/* A short message keeps its acts beside it, a long one under it. */}
      {bare ? <div className="tk-msg-row"><div className="tk-msg-b">{said}</div>{acts}</div> : said}
      {c.outdated ? (
        <p className="m-0 text-meta text-amended">{t('outdated', { date: shortDate(c.version_on, i18n.language) })}</p>
      ) : null}
      {deleting ? (
        <div className="flex flex-wrap items-center gap-2 rounded-control bg-paper px-3 py-2 text-meta">
          <span>{t('deleteAsk')}</span>
          <button type="button" onClick={() => void remove()} className="h-10 rounded-control border border-repealed px-3 font-medium text-repealed hover:bg-sheet">{t('deleteYes')}</button>
          <button type="button" onClick={() => setDeleting(false)} className="h-10 rounded-control px-3 hover:bg-sheet">{t('deleteNo')}</button>
        </div>
      ) : null}
      {bare ? null : acts}
      {mod?.can && !c.mine ? <ModTools c={c} mod={mod} onChanged={onChanged} open={Boolean(flagged)} /> : null}
      {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
      {replying ? (
        <Composer place={path} label={label} writing={writing} parent={c} open
                  onDone={(made) => { setReplying(false); onChanged(); onReplied?.(made); }} />
      ) : null}
      {!reply && !bare ? <Replies c={c} path={path} label={label} writing={writing} asker={c.mine && c.kind === 'question'} onChanged={onChanged} mod={mod} all={allReplies} /> : null}
      {sheet === 'report' ? <ReportSheet c={c} onClose={() => setSheet('')} /> : null}
      {sheet === 'takedown' ? <TakedownSheet c={c} onClose={() => setSheet('')} /> : null}
      {shown !== null ? <Lightbox pictures={c.pictures} start={shown} onClose={() => setShown(null)} /> : null}
    </article>
  );
}

/** Answers under a contribution: the marked one and the two most useful, the rest on request (R6). A link to a
 *  hidden one opens them all. */
function Replies({ c, path, label, writing, asker, onChanged, mod, all: every = false }: {
  c: Contribution; path: string; label: string; writing: Writing; asker?: boolean; onChanged: () => void; mod?: Moderation;
  all?: boolean;
}) {
  const { t } = useT();
  const { hash } = useLocation();
  const all = c.replies ?? [];
  const targeted = all.slice(SHOWN_ANSWERS).some((r) => hash === `#c${r.id}`);
  const [open, setOpen] = useState(false);
  if (!all.length) return null;
  const showing = open || targeted || every ? all : all.slice(0, SHOWN_ANSWERS);
  return (
    <div className="mt-1 flex flex-col gap-4">
      {showing.map((r) => (
        <ContributionCard key={r.id} c={r} path={path} label={label} writing={writing} asker={asker} onChanged={onChanged} reply mod={mod} />
      ))}
      {all.length > SHOWN_ANSWERS && !every ? (
        <button type="button" onClick={() => setOpen((o) => !o)}
                className="ms-4 self-start rounded-control px-3 py-1.5 text-meta font-medium text-stamp hover:bg-paper sm:ms-10">
          {open || targeted ? t('fewerAnswers') : t('moreAnswers', { count: all.length - SHOWN_ANSWERS })}
        </button>
      ) : null}
    </div>
  );
}

/** A reviewer's acts, in place (M5): publish or look, remove under the suggested rule or another, send back with
 *  a note, pause the author, trust them, mark a repeated question. */
function ModTools({ c, mod, onChanged, open: startOpen }: { c: Contribution; mod: Moderation; onChanged: () => void; open: boolean }) {
  const { t } = useT();
  // Open on what waits for a decision; one small button on the rest, so a reviewer still reads a discussion.
  const [open, setOpen] = useState(startOpen);
  const [form, setForm] = useState<'' | 'remove' | 'back' | 'dup'>('');
  const [rule, setRule] = useState<Rule | ''>(c.suggested ?? '');
  const [note, setNote] = useState('');
  const [of, setOf] = useState('');
  const [state, setState] = useState<'' | 'done'>('');
  const [error, setError] = useState<unknown>(null);
  const run = async (body: Record<string, unknown>) => {
    setError(null);
    try {
      await discussionApi.act(c.id, body);
      setState('done');
      setForm('');
      onChanged();
    } catch (e) {
      setError(e);
    }
  };
  const chip = 'h-10 rounded-control border px-3 text-meta';
  if (!open) {
    return (
      <button type="button" onClick={() => setOpen(true)} aria-expanded={false}
              className="self-start rounded-control border border-dashed border-amended/60 px-2.5 py-1 text-meta font-semibold text-amended hover:bg-amended-wash">
        {t('mod.title')} ▾
      </button>
    );
  }
  return (
    <div className="flex flex-col gap-2 rounded-control border border-dashed border-amended/60 px-3 py-2">
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-meta font-semibold text-amended">{t('mod.title')}</span>
        {c.held ? <button type="button" className={`${chip} border-stamp bg-stamp font-semibold text-on-stamp`} onClick={() => void run({ act: 'approve' })}>{t('mod.approve')}</button> : null}
        {c.hidden ? <button type="button" className={`${chip} border-rule`} onClick={() => void run({ act: 'keep' })}>{t('mod.keep')}</button> : null}
        {c.suggested ? (
          <button type="button" className={`${chip} border-repealed text-repealed`} onClick={() => void run({ act: 'remove', rule: c.suggested })}>
            {t('mod.removeRule', { n: ruleNo(c.suggested) })}
          </button>
        ) : null}
        <button type="button" className={`${chip} border-rule`} onClick={() => setForm(form === 'remove' ? '' : 'remove')}>{t('mod.removeOther')}</button>
        <button type="button" className={`${chip} border-rule`} onClick={() => setForm(form === 'back' ? '' : 'back')}>{t('mod.sendBack')}</button>
        <button type="button" className={`${chip} border-rule`} onClick={() => void run({ act: 'pause', days: 7, rule: c.suggested ?? 'respect' })}>{t('mod.pause')}</button>
        <button type="button" className={`${chip} border-rule`} onClick={() => void run({ act: 'trust' })}>{t('mod.trust')}</button>
        {c.kind === 'question' && !c.parent ? <button type="button" className={`${chip} border-rule`} onClick={() => setForm(form === 'dup' ? '' : 'dup')}>{t('mod.duplicate')}</button> : null}
        {state ? <span role="status" className="text-meta text-in-force">{t('mod.done')}</span> : null}
      </div>
      {form === 'remove' ? (
        <div className="flex flex-wrap items-center gap-2">
          <select value={rule} onChange={(e) => setRule(e.target.value as Rule)} aria-label={t('review.rule')}
                  className="h-10 rounded-control border border-field bg-sheet px-2 text-meta">
            <option value="">{t('review.rule')}</option>
            {RULES.map((r, i) => <option key={r} value={r}>{i + 1}. {t(`rules.${r}`)}</option>)}
          </select>
          <button type="button" disabled={!rule} className={`${chip} border-repealed text-repealed`} onClick={() => void run({ act: 'remove', rule })}>{t('review.remove')}</button>
        </div>
      ) : null}
      {form === 'back' ? (
        <div className="flex flex-wrap items-center gap-2">
          <input value={note} onChange={(e) => setNote(e.target.value)} dir="auto" placeholder={t('mod.sendBackNote')}
                 className="h-10 min-w-0 flex-1 rounded-control border border-field bg-sheet px-2 text-meta" />
          <button type="button" disabled={!note.trim()} className={`${chip} border-stamp text-stamp`} onClick={() => void run({ act: 'send_back', note })}>{t('mod.send')}</button>
        </div>
      ) : null}
      {form === 'dup' ? (
        <div className="flex flex-wrap items-center gap-2">
          <select value={of} onChange={(e) => setOf(e.target.value)} aria-label={t('mod.duplicateOf')}
                  className="h-10 min-w-0 max-w-full flex-1 rounded-control border border-field bg-sheet px-2 text-meta">
            <option value="">{t('mod.duplicateOf')}</option>
            {mod.questions.filter((q) => q.id !== c.id).map((q) => <option key={q.id} value={q.id}>{(q.title || q.body).slice(0, 80)}</option>)}
          </select>
          <button type="button" disabled={!of} className={`${chip} border-stamp text-stamp`} onClick={() => void run({ act: 'duplicate', of: Number(of) })}>{t('mod.send')}</button>
        </div>
      ) : null}
      {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
    </div>
  );
}

/** The person: a link to their page, and their karma, its meaning a tap away; «بدون اسم»; «حساب محذوف». */
export function Who({ author, anonymous, mine }: { author: Author | null; anonymous: boolean; mine?: boolean }) {
  const { t } = useT();
  if (anonymous || !author) {
    return <span className="font-semibold">{t('anonymous')}{mine ? <span className="font-normal text-ink-soft"> ({t('you')})</span> : null}</span>;
  }
  if ('deleted' in author) return <span className="font-semibold text-ink-soft">{t('deletedAccount')}</span>;
  return (
    <>
      <Link to={`/people/${encodeURIComponent(author.username)}`} dir="auto" className="font-semibold text-ink no-underline hover:text-stamp">
        {/* '' when the patterns find a number or an insult in both the shown name and the username. */}
        {author.name || t('member')}
      </Link>
      {author.karma ? (
        <Meaning label={<><span aria-hidden="true">✦</span> {author.karma}</>} full={t('karma.count', { count: author.karma })}
                 hint={t('karma.hint')} className="inline-flex items-center gap-1 rounded-full bg-chip px-2 text-meta tabular-nums leading-7 text-ink-soft" />
      ) : null}
    </>
  );
}

/** Karma beside a name, its meaning a tap away (P7 of the polish review: a number said nothing to a reader who could
 *  not hover). */
function Meaning({ label, full, hint, className }: { label: React.ReactNode; full?: string; hint: string; className: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      {/* A 28 px chip with a 40 px reach: the reach is drawn by an empty ::after. */}
      <button type="button" aria-expanded={open} onClick={() => setOpen((o) => !o)} title={hint} aria-label={full}
              className={`relative after:absolute after:inset-x-0 after:-inset-y-1.5 after:content-[''] ${className}`}>{label}</button>
      {open ? <span role="note" className="basis-full text-meta text-ink-soft">{full ? `${full}. ` : ''}{hint}</span> : null}
    </>
  );
}

/** The words as written, with their citations as links into the site. */
export function Body({ body, links }: { body: string; links: { start: number; end: number; path: string }[] }) {
  const parts: React.ReactNode[] = [];
  let at = 0;
  for (const [i, l] of [...links].sort((a, b) => a.start - b.start).entries()) {
    if (l.start < at) continue;
    parts.push(body.slice(at, l.start));
    parts.push(<Link key={i} to={l.path} className="underline decoration-stamp/60 underline-offset-4">{body.slice(l.start, l.end)}</Link>);
    at = l.end;
  }
  parts.push(body.slice(at));
  return <p dir="auto" className="m-0 max-w-[70ch] whitespace-pre-line text-body leading-[1.85]">{parts}</p>;
}

function Edit({ c, onDone }: { c: Contribution; onDone: () => void }) {
  const { t } = useT();
  const [title, setTitle] = useState(c.title);
  const [body, setBody] = useState(c.body);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const returned = error instanceof ApiError ? error.codeFor('check') : undefined;
  const save = async (insist = false) => {
    setBusy(true);
    try {
      await discussionApi.edit(c.id, body, c.parent ? undefined : title, insist);
      onDone();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  return (
    <form className="flex flex-col gap-2" onSubmit={(e) => { e.preventDefault(); void save(); }}>
      {!c.parent && c.title ? (
        <input dir="auto" value={title} onChange={(e) => setTitle(e.target.value)} maxLength={140} aria-label={t('talk2.titleLabel')}
               className="h-11 w-full rounded-control border border-field bg-paper px-3 text-body font-semibold focus:border-stamp focus:bg-sheet focus:outline-none" />
      ) : null}
      <textarea dir="auto" value={body} onChange={(e) => setBody(e.target.value)} rows={4} maxLength={3000} autoFocus
                aria-label={t('edit')}
                className="w-full rounded-control border border-field bg-paper px-3 py-2 text-body leading-relaxed focus:border-stamp focus:bg-sheet focus:outline-none" />
      <div className="flex gap-2">
        <button type="submit" disabled={busy} className="h-10 rounded-control bg-stamp px-4 text-meta font-semibold text-on-stamp">{t('composer.save')}</button>
        <button type="button" onClick={onDone} className="h-10 rounded-control px-3 text-meta text-ink-soft hover:bg-paper">{t('composer.cancel')}</button>
      </div>
      {returned ? <Returned rule={returned} busy={busy} onInsist={() => void save(true)} />
        : error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
    </form>
  );
}

function MenuItem({ onClick, children, danger }: { onClick: () => void; children: React.ReactNode; danger?: boolean }) {
  return (
    <button type="button" onClick={onClick}
            className={`px-4 py-2.5 text-start text-meta hover:bg-paper ${danger ? 'text-repealed' : 'text-ink'}`}>{children}</button>
  );
}

function ThumbIcon({ filled }: { filled: boolean }) {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill={filled ? 'currentColor' : 'none'} stroke="currentColor" strokeWidth="1.8"
         strokeLinejoin="round" aria-hidden="true">
      <path d="M7 10v10H4V10h3Zm0 0 4-7a2 2 0 0 1 3 2l-1 5h5.5a2 2 0 0 1 2 2.3l-1.2 6A2 2 0 0 1 17.3 20H7" />
    </svg>
  );
}
