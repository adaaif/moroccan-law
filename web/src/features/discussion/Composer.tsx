import { useQueryClient } from '@tanstack/react-query';
import { useEffect, useId, useRef, useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ME_KEY } from '@/features/accounts/accounts.service';
import { useRegistrationOpen } from '@/features/accounts/registration';
import { AR } from '@/features/corpus/format';
import { api } from '@/shared/services/api';
import { BlurEditor } from './BlurEditor';
import { discussionApi, POST_KINDS, upload, type Contribution, type Picture, type Similar, type Voice,
         type Writing } from './discussion.api';
import { ApiError } from '@/shared/services/api';
import { Returned } from './Returned';
import { MicIcon, Recorder } from './audio/Recorder';
import { VoicePlayer } from './audio/VoicePlayer';
import { errorText, placeName, reviewWait, useT } from './strings';
import { isSensitive } from './sensitive';

const MAX = 3000;
const TITLE_MAX = 140;

type PostKind = (typeof POST_KINDS)[number];
type Draft = { kind: PostKind; title?: string; body: string; anonymous: boolean; quote?: string };

function readDraft(key: string): Draft | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as Draft) : null;
  } catch {
    return null;
  }
}

function writeDraft(key: string, draft: Draft | null) {
  try {
    if (draft && (draft.body.trim() || draft.title?.trim() || draft.quote)) localStorage.setItem(key, JSON.stringify(draft));
    else localStorage.removeItem(key);
  } catch {
    // Private mode: no draft kept.
  }
}

/** Waits for the typing to stop before asking the server. */
function useSettled<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  useEffect(() => {
    const timer = window.setTimeout(() => setSettled(value), ms);
    return () => window.clearTimeout(timer);
  }, [value, ms]);
  return settled;
}

/**
 * The form (29 Oct 2026): a post in a topic, its title first, as a question or a post; or a comment under a post, the
 * words alone. A post may start from an article: its quote and the article go with it. A voice and pictures when they
 * are on (C1: off at launch), «بدون اسم» for text. A line under it says what not to write and that a model reads it
 * before it is published. Closed, it is one line that opens on a tap.
 *
 * Kept from the polish (19 Oct 2026): an account that has not confirmed its email writes all the same and confirms
 * with the code in place (W1); what would hold the words shows while typing, with a one-tap fix (W2); a question sees
 * the topic's questions that share its words (W3); the words wait on the device until sent (W4). New: the first post
 * asks for the agreement that a model reads it (law 09-08, art. 44); a post the model returns says the rule and may go
 * to a person as it is.
 */
export function Composer({ place, label = '', writing, parent, about, quote = '', onQuote, onDone, open: startOpen = false,
                           places }: {
  /** The topic's place a post goes to; for a comment, its post's address (the draft's key). */
  place: string;
  /** The article the quote is from, by its label. */
  label?: string;
  writing: Writing;
  parent?: Contribution;
  /** The article a post starts from. */
  about?: string;
  quote?: string;
  onQuote?: (quote: string) => void;
  onDone: (c: Contribution) => void;
  open?: boolean;
  /** Asked from an article: the topics a question about it may go to, the first chosen. */
  places?: { path: string; name: { ar: string; fr: string } }[];
}) {
  const { t, i18n } = useT();
  const id = useId();
  const client = useQueryClient();
  const draftKey = `law.draft:${place}:${parent?.id ?? 'top'}:${about ?? ''}`;
  const [restored] = useState(() => readDraft(draftKey));
  const [open, setOpen] = useState(startOpen || Boolean(restored));
  const [kind, setKind] = useState<PostKind>(restored?.kind ?? 'question');
  const [title, setTitle] = useState(restored?.title ?? '');
  const [body, setBody] = useState(restored?.body ?? '');
  const [anonymous, setAnonymous] = useState(restored?.anonymous ?? false);
  const [where, setWhere] = useState(places?.[0]?.path ?? place);
  const [agreed, setAgreed] = useState(false);
  const [voice, setVoice] = useState<Voice | null>(null);
  const [recording, setRecording] = useState(false);
  const [pictures, setPictures] = useState<Picture[]>([]);
  const [editing, setEditing] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState<'' | 'published' | 'held'>('');
  const [holds, setHolds] = useState<{ reasons: string[]; spans: [number, number, string][] }>({ reasons: [], spans: [] });
  const [similar, setSimilar] = useState<Similar[]>([]);
  const [different, setDifferent] = useState(false);
  const [code, setCode] = useState('');
  const [resent, setResent] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const proving = writing.why === 'email.not_proven';
  const asking = writing.consent === false;
  const settled = useSettled(body, 600);
  const settledTitle = useSettled(title, 600);
  const returned = error instanceof ApiError ? error.codeFor('check') : undefined;

  // Words quoted from the article open the form; a restored draft brings its quote back.
  useEffect(() => {
    if (quote) setOpen(true);
  }, [quote]);
  useEffect(() => {
    if (restored?.quote && !parent) onQuote?.(restored.quote);
    // Once, when the form first appears.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    if (open) writeDraft(draftKey, { kind, title: parent ? undefined : title, body, anonymous, quote: parent ? undefined : quote });
  }, [open, draftKey, kind, title, body, anonymous, quote, parent]);
  useEffect(() => {
    const words = [parent ? '' : settledTitle, settled].filter((x) => x.trim()).join('\n');
    if (!open || !words) {
      setHolds({ reasons: [], spans: [] });
      return;
    }
    let live = true;
    // The spans point into the words; a title's hold still shows its reason.
    discussionApi.check(settled).then((r) => live && setHolds(r)).catch(() => undefined);
    if (!parent && settledTitle.trim()) {
      discussionApi.check(settledTitle).then((r) => live && r.reasons.length
        && setHolds((h) => ({ reasons: [...new Set([...h.reasons, ...r.reasons])], spans: h.spans }))).catch(() => undefined);
    }
    return () => { live = false; };
  }, [settled, settledTitle, open, parent]);
  useEffect(() => {
    const words = `${settledTitle} ${settled}`.trim();
    if (!open || parent || kind !== 'question' || words.length < 20) {
      setSimilar([]);
      return;
    }
    let live = true;
    discussionApi.similar(where, words).then((r) => live && setSimilar(r.questions)).catch(() => undefined);
    return () => { live = false; };
  }, [settled, settledTitle, open, parent, kind, where]);

  const sent = done ? (
    <p role="status" className="m-0 text-meta text-in-force">
      {done === 'held' ? t('composer.heldNow') : t('composer.published')}
      {done === 'held' && writing.review_hours ? ` ${reviewWait(t, writing.review_hours)}` : ''}
    </p>
  ) : null;

  // What was just sent is said even when it was the day's last (the form closes after it).
  if (!writing.can && !proving) return <div className="flex flex-col gap-2">{sent}<Closed why={writing.why} /></div>;

  if (!open) {
    return (
      <div className="flex flex-col gap-2">
        <button type="button" onClick={() => { setOpen(true); setDone(''); }}
                className="flex min-h-12 w-full items-center rounded-control border border-rule bg-sheet px-4 text-start text-body text-ink-soft hover:border-stamp">
          {parent ? t('composer.startReply') : t('composer.start')}
        </button>
        {sent}
      </div>
    );
  }

  const addPicture = async (blob: Blob) => {
    setEditing(null);
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.append('picture', blob, 'picture.jpg');
    try {
      const picture = await upload<Picture>('/discussion/pictures/', form);
      setPictures((all) => [...all, picture]);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const reset = () => {
    setBody('');
    setTitle('');
    setVoice(null);
    setPictures([]);
    setAnonymous(false);
    setRecording(false);
    setDifferent(false);
    writeDraft(draftKey, null);
    onQuote?.('');
  };

  const send = async (insist = false) => {
    setBusy(true);
    setError(null);
    try {
      if (proving) {
        // W1: the code first, then the words, in one tap.
        const me = await api('/auth/email/prove/', { method: 'POST', json: { code } });
        client.setQueryData(ME_KEY, me);
      }
      const made = await discussionApi.contribute(parent ? {
        parent: parent.id, body, anonymous, voice: voice?.id, pictures: pictures.map((p) => p.id),
        consent: agreed || undefined, insist: insist || undefined,
      } : {
        path: where, kind, title, body, about: about || undefined, quote: quote || undefined, anonymous,
        voice: voice?.id, pictures: pictures.map((p) => p.id), consent: agreed || undefined, insist: insist || undefined,
      });
      reset();
      setOpen(false);
      setDone(made.held ? 'held' : 'published');
      onDone(made);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  };

  const drop = () => {
    if (voice) void discussionApi.dropVoice(voice.id).catch(() => undefined);
    for (const p of pictures) void discussionApi.dropPicture(p.id).catch(() => undefined);
    reset();
    setOpen(false);
  };

  /** Takes a matched span out of the words (W2): the one tap that spares a reviewer. */
  const takeOut = (start: number, end: number) => {
    setBody((b) => (b.slice(0, start) + b.slice(end)).replace(/[ \t]{2,}/g, ' '));
  };
  const empty = parent ? !body.trim() && !voice && !pictures.length : title.trim().length < 3;

  return (
    <form className="flex flex-col gap-3 rounded-control border-2 border-ink/80 bg-sheet p-3 sm:p-4"
          onSubmit={(e) => { e.preventDefault(); void send(); }}>
      {!parent ? (
        <>
          {places && places.length > 1 ? (
            <div role="radiogroup" aria-label={t('talk2.whereLabel')} className="flex flex-wrap items-center gap-1.5 text-meta">
              <span className="text-ink-soft">{t('talk2.where')}</span>
              {places.map((p) => (
                <button key={p.path} type="button" role="radio" aria-checked={where === p.path} onClick={() => setWhere(p.path)}
                        className={`h-10 rounded-full border px-3.5 ${where === p.path ? 'border-stamp bg-wash font-semibold text-stamp' : 'border-rule text-ink hover:border-stamp'}`}>
                  {placeName(p.name, i18n.language)}
                </button>
              ))}
            </div>
          ) : null}
          <div role="radiogroup" aria-label={t('composer.kindLabel')} className="flex flex-wrap gap-1.5">
            {POST_KINDS.map((k) => (
              <button key={k} type="button" role="radio" aria-checked={kind === k} onClick={() => setKind(k)}
                      className={`h-10 rounded-full border px-3.5 text-meta ${kind === k ? 'border-stamp bg-wash font-semibold text-stamp' : 'border-rule text-ink hover:border-stamp'}`}>
                {t(`kinds.${k}`)}
              </button>
            ))}
          </div>
          <p className="m-0 text-meta text-ink-soft">{t(`kindHints.${kind}`)}</p>
          <label htmlFor={`${id}-title`} className="sr-only">{t('talk2.titleLabel')}</label>
          <input id={`${id}-title`} dir="auto" value={title} maxLength={TITLE_MAX} autoFocus
                 onChange={(e) => setTitle(e.target.value)} placeholder={t(kind === 'question' ? 'talk2.titleQuestion' : 'talk2.titlePost')}
                 className="h-12 w-full rounded-control border border-field bg-paper px-3 text-lead font-semibold text-ink placeholder:font-normal placeholder:text-ink-soft focus:border-stamp focus:bg-sheet focus:outline-none" />
          {quote ? (
            <div className="flex items-start gap-2 border-s-[3px] border-stamp ps-3">
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="text-meta text-ink-soft">{t('composer.quoteFrom', { label })}</span>
                <q {...AR} className="font-law text-law leading-relaxed text-ink-soft [quotes:none]">{quote}</q>
              </div>
              <button type="button" onClick={() => onQuote?.('')} aria-label={t('composer.quoteRemove')}
                      className="grid size-10 shrink-0 place-items-center rounded-full text-ink-soft hover:bg-paper">×</button>
            </div>
          ) : about ? <p className="m-0 text-meta text-ink-soft">{t('composer.quoteHint')}</p> : null}
        </>
      ) : null}

      <label htmlFor={`${id}-body`} className="sr-only">{t('composer.placeholder')}</label>
      <textarea id={`${id}-body`} dir="auto" value={body} maxLength={MAX} rows={4} autoFocus={Boolean(parent)}
                onChange={(e) => setBody(e.target.value)} placeholder={t(parent ? 'talk2.commentPlaceholder' : 'composer.placeholder')}
                className="min-h-28 w-full resize-y rounded-control border border-field bg-paper px-3 py-2.5 text-body leading-relaxed text-ink placeholder:text-ink-soft focus:border-stamp focus:bg-sheet focus:outline-none" />
      {body.length > MAX - 400 ? <p className="m-0 text-end text-meta tabular-nums text-ink-soft">{t('composer.counter', { count: body.length })}</p> : null}
      {restored && body === restored.body && body ? <p className="m-0 text-meta text-ink-soft">{t('composer2.draftKept')}</p> : null}

      {holds.reasons.length ? (
        <div role="status" className="flex flex-col gap-2 rounded-control bg-amended-wash px-3 py-2.5 text-meta text-amended">
          <span>
            {t('composer2.holdLead')} {holds.reasons.map((r) => t(`heldReasons.${r}`)).join(' ')}
            {holds.reasons.some((r) => ['phone', 'email', 'link'].includes(r)) ? ` ${t('composer2.holdSolicit')}` : ''}
          </span>
          <span className="flex flex-wrap gap-1.5">
            {holds.spans.filter(([s, e]) => e > s).map(([s, e]) => (
              <button key={`${s}-${e}`} type="button" onClick={() => takeOut(s, e)}
                      className="rounded-control border border-amended bg-sheet px-2.5 py-1 text-meta font-medium text-amended hover:bg-paper">
                {t('composer2.holdFix', { words: body.slice(s, e) })}
              </button>
            ))}
          </span>
        </div>
      ) : null}

      {similar.length && !different ? (
        <div className="flex flex-col gap-2 rounded-control border border-rule p-3">
          <span className="text-meta font-semibold">{t('composer2.similarTitle')}</span>
          {similar.map((q) => (
            <Link key={q.id} to={q.path} className="flex flex-col gap-1 rounded-control bg-paper px-3 py-2 text-ink no-underline hover:text-ink">
              <span dir="auto" className="line-clamp-2 text-meta font-semibold">{q.title || q.body}</span>
              <span className="flex flex-wrap gap-3 text-meta text-ink-soft">
                {q.accepted ? <span className="font-semibold text-in-force">✓ {t('accepted')}</span> : null}
                <span>{t('composer2.similarAnswers', { count: q.answers })}</span>
                {q.useful ? <span>{t('usefulCount', { count: q.useful })}</span> : null}
              </span>
            </Link>
          ))}
          <button type="button" onClick={() => setDifferent(true)} className="self-start text-meta text-stamp hover:underline">
            {t('composer2.similarNo')}
          </button>
        </div>
      ) : null}

      {voice ? (
        <div className="flex flex-wrap items-center gap-2">
          <VoicePlayer id={voice.id} src={voice.src} durationMs={voice.duration_ms} peaks={voice.peaks} compact />
          <button type="button" onClick={() => { void discussionApi.dropVoice(voice.id).catch(() => undefined); setVoice(null); }}
                  className="h-10 rounded-control px-3 text-meta text-repealed hover:bg-paper">{t('recorder.remove')}</button>
        </div>
      ) : recording ? (
        <Recorder owner={id} onAttach={(v) => { setVoice(v); setRecording(false); setAnonymous(false); }}
                  onClose={() => setRecording(false)} />
      ) : null}

      {pictures.length ? (
        <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
          {pictures.map((p) => (
            <li key={p.id} className="relative">
              <img src={p.thumb} alt="" width={112} height={84} className="h-21 w-28 rounded-control border border-rule object-cover" />
              <button type="button" aria-label={t('pictures.remove')}
                      onClick={() => { void discussionApi.dropPicture(p.id).catch(() => undefined); setPictures((all) => all.filter((x) => x.id !== p.id)); }}
                      className="absolute -end-2.5 -top-2.5 grid size-9 place-items-center rounded-full border border-rule bg-sheet text-body shadow">×</button>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        {writing.voice && !voice && !recording ? (
          <button type="button" onClick={() => setRecording(true)}
                  className="inline-flex h-10 items-center gap-2 rounded-control border border-rule px-3 text-meta hover:border-stamp hover:text-stamp">
            <MicIcon />{t('composer.voice')}
          </button>
        ) : null}
        {writing.pictures ? (
          <>
            <button type="button" onClick={() => file.current?.click()} disabled={pictures.length >= 3 || busy}
                    title={pictures.length >= 3 ? t('composer.picturesFull') : undefined}
                    className="inline-flex h-10 items-center gap-2 rounded-control border border-rule px-3 text-meta hover:border-stamp hover:text-stamp disabled:opacity-50">
              <PictureIcon />{t('composer.picture')}
            </button>
            <input ref={file} type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" tabIndex={-1}
                   onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ''; if (f) setEditing(f); }} />
          </>
        ) : null}
        {kind === 'question' && !anonymous && !voice && !parent && isSensitive(where) ? (
          // A personal question (R12 of the for-everyone review): asking without a name is offered before it is sent.
          <p className="m-0 flex w-full flex-wrap items-center gap-2 rounded-control bg-talk-wash px-3 py-2 text-meta">
            {t('composer.namelessOffer')}
            <button type="button" onClick={() => setAnonymous(true)} className="h-10 rounded-control bg-talk px-3 font-semibold text-sheet">
              {t('composer.namelessYes')}
            </button>
          </p>
        ) : null}
        <label className={`inline-flex h-10 cursor-pointer items-center gap-2 rounded-control px-2 text-meta ${voice ? 'opacity-50' : ''}`}
               title={voice ? t('composer.anonymousVoice') : t('composer.anonymousHint')}>
          <input type="checkbox" checked={anonymous} disabled={Boolean(voice)} onChange={(e) => setAnonymous(e.target.checked)}
                 className="size-4 accent-[var(--color-stamp)]" />
          {t('composer.anonymous')}
        </label>
        {proving ? null : (
          <span className="ms-auto flex gap-2">
            <button type="button" onClick={drop} className="h-10 rounded-control px-3 text-meta text-ink-soft hover:bg-paper">{t('composer.cancel')}</button>
            <button type="submit" disabled={busy || empty || (asking && !agreed)}
                    className="h-10 rounded-control bg-stamp px-5 text-body font-semibold text-on-stamp hover:bg-stamp-deep disabled:opacity-60">
              {busy ? t('check.reading') : t('composer.send')}
            </button>
          </span>
        )}
      </div>

      {proving ? (
        <div className="flex flex-col gap-2.5 rounded-control bg-wash p-3">
          <span className="text-body font-semibold">{t('composer2.proveTitle')}</span>
          <span className="text-meta text-ink-soft">{t('composer2.proveSent', { email: writing.email_hint ?? '' })}</span>
          <span className="flex flex-wrap items-center gap-3">
            <label className="sr-only" htmlFor={`${id}-code`}>{t('account.code')}</label>
            <input id={`${id}-code`} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
                   inputMode="numeric" autoComplete="one-time-code" dir="ltr" placeholder="••••••"
                   className="h-11 w-36 rounded-control border border-field bg-sheet px-3 text-center text-lead tracking-[0.3em] focus:border-stamp focus:outline-none" />
            <button type="submit" disabled={busy || code.length !== 6 || empty || (asking && !agreed)}
                    className="h-11 rounded-control bg-stamp px-5 text-body font-semibold text-on-stamp hover:bg-stamp-deep disabled:opacity-60">
              {t('composer2.proveAndSend')}
            </button>
            <button type="button" className="text-meta text-stamp hover:underline"
                    onClick={async () => { try { await api('/auth/email/code/', { method: 'POST' }); setResent(true); } catch (e) { setError(e); } }}>
              {resent ? t('composer2.resent') : t('composer2.resend')}
            </button>
          </span>
        </div>
      ) : null}

      {anonymous ? <p className="m-0 text-meta text-ink-soft">{t('composer.anonymousHint')}</p> : null}
      {voice ? <p className="m-0 text-meta text-ink-soft">{t('composer.anonymousVoice')}</p> : null}
      {asking ? (
        // The first post's agreement (law 09-08, art. 44): a model reads it, abroad, before it is published.
        <label className="flex items-start gap-2.5 rounded-control bg-wash px-3 py-2.5 text-meta">
          <input type="checkbox" checked={agreed} onChange={(e) => setAgreed(e.target.checked)}
                 className="mt-0.5 size-4 shrink-0 accent-[var(--color-stamp)]" />
          <span>{t('check.consent')} <Link to="/privacy#check">{t('check.consentMore')}</Link></span>
        </label>
      ) : null}
      {returned ? <Returned rule={returned} busy={busy} onInsist={() => void send(true)} />
        : error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(t, error)}</p> : null}
      <p className="m-0 border-t border-dashed border-rule pt-2.5 text-meta text-ink-soft">
        {t('composer.privacy')}
      </p>
      {editing ? <BlurEditor file={editing} onDone={(b) => void addPicture(b)} onCancel={() => setEditing(null)} /> : null}
    </form>
  );
}

/** Why the form is not there, and the one step that opens it. */
export function Closed({ why }: { why: string | null }) {
  const { t } = useT();
  const location = useLocation();
  const back = { from: location.pathname };
  const registrationOpen = useRegistrationOpen();
  const action = why === 'account.sign_in' ? (
    <span className="flex gap-3">
      <Link to="/login" state={back} className="font-medium">{t('signIn')}</Link>
      {registrationOpen ? <Link to="/register" state={back} className="font-medium">{t('register')}</Link> : null}
    </span>
  ) : why === 'account.paused' ? (
    <Link to="/account#pause" className="font-medium">{t('account.title')}</Link>
  ) : null;
  // What the reader typed before being asked to sign in stays in sight (RD18 of the readers review, 9 Nov 2026): the
  // ask box kept it on the phone and sent them to this room, where their question was nowhere on the screen.
  const kept = why === 'account.sign_in' ? readDraft(`law.draft:${location.pathname}:top:`) : null;
  const words = kept ? [kept.title, kept.body].filter(Boolean).join(' — ') : '';
  return (
    <div className="flex flex-col gap-2 rounded-control bg-paper px-4 py-3 text-body">
      {words ? (
        <>
          <span className="font-medium">{t('keptDraft')}</span>
          <q dir="auto" className="border-s-[3px] border-talk ps-3 text-ink">{words}</q>
        </>
      ) : null}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-1 [&_a]:inline-flex [&_a]:min-h-11 [&_a]:items-center">
        <span className="text-ink-soft">{t(`why.${why ?? 'discussion.closed'}`)}</span>
        {action}
      </div>
    </div>
  );
}

export function PictureIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <rect x="3" y="5" width="18" height="14" rx="2" /><circle cx="9" cy="10" r="2" /><path d="m21 17-5-5-8 7" />
    </svg>
  );
}
