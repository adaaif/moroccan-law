import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useLocation } from 'react-router-dom';
import { usePreview } from '@/features/corpus/corpus.api';
import { AR, longDate } from '@/features/corpus/format';
import { plainBody } from '@/features/corpus/article/message';
import { addressLabel } from '@/features/corpus/addressLabel';
import '@/shared/locales/pages';
import { ApiError } from '@/shared/services/api';
import { useSession } from '@/shared/stores/session';
import { explainApi, REGISTERS, useDetail, useRefresh, useWord, type Detail, type Full, type Register, type Revision } from './explain.api';
import { usePageTitle } from '@/shared/services/title';
import { Page, PageSkeleton } from '@/shared/components/ui';
import { textName } from '@/features/corpus/names';
import { LoadError } from '@/features/corpus/NotFound';
import { REASONS, RULES, type Reason, type Rule } from '@/features/discussion/discussion.api';
import { errorText, ruleNo, useT as useTalk } from '@/features/discussion/strings';

/** /explain/<address> (R8 of the for-everyone review): an explanation as Wikipedia keeps an article — what it says in each
 *  register, who wrote it, every earlier state, the addresses it rests on, whether a reviewer checked it — and, for
 *  someone who may write, the form to improve it. The law it explains is quoted above it, exactly. An edit waits for a
 *  reviewer behind the discussion's own gates while readers keep the checked words; readers report a state, and a
 *  reviewer of the text checks, keeps or removes one under a rule. */
export default function ExplainPage() {
  const { t } = useTranslation();
  const path = useLocation().pathname.replace(/^\/explain/, '');
  const detail = useDetail(path);
  usePageTitle([t('pages:explain.short')]);
  const [register, setRegister] = useState<Register>('ar');
  if (detail.isLoading) return <Main><PageSkeleton kind="text" /></Main>;
  const d = detail.data;
  if (!d) return <Main><LoadError error={detail.error} retry={() => void detail.refetch()} /></Main>;
  const e = d.registers[register];
  return (
    <Main>
      <Subject d={d} />
      <section className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-6 sm:px-8">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="m-0 text-h3 font-bold text-people">{t('pages:explain.short')}</h1>
          <div role="tablist" aria-label={t('pages:explain.registers')} className="inline-flex rounded-full bg-paper p-1 text-meta">
            {REGISTERS.map((r) => (
              <button key={r} role="tab" type="button" aria-selected={r === register} onClick={() => setRegister(r)}
                      className={`rounded-full px-3.5 py-1.5 ${r === register ? 'bg-people-fill font-semibold text-on-people' : 'text-ink-soft hover:text-ink'}`}>
                {t(`pages:explain.register.${r}`)}{d.registers[r] ? '' : ' ·'}
              </button>
            ))}
          </div>
        </div>
        {e ? <Shown d={d} e={e} register={register} /> : <p className="m-0 text-body text-ink-soft">{t('pages:explain.none')}</p>}
      </section>
      <Write d={d} register={register} current={e} />
      {e?.history.length ? <History d={d} e={e} register={register} /> : null}
    </Main>
  );
}

/** What is explained: an article quoted as printed, a text, or a word. */
function Subject({ d }: { d: Detail }) {
  const { t, i18n } = useTranslation();
  const preview = usePreview(d.kind === 'article' ? d.path : null).data;
  const word = useWord(d.kind === 'word' ? d.path.replace('/words/', '') : '').data;
  if (d.kind === 'word') {
    return (
      <Link to={d.path} className="rounded-card bg-sheet px-5 py-5 text-ink no-underline sm:px-8">
        <span className="text-meta text-ink-soft">{t('pages:explain.aboutWord')}</span>
        <p {...AR} className="m-0 text-h2 font-bold">{word?.concept.term?.ar ?? d.path.replace('/words/', '')}</p>
      </Link>
    );
  }
  if (d.kind === 'text' || !preview) {
    return <Link to={d.path} className="rounded-card bg-sheet px-5 py-4 font-medium no-underline sm:px-8">{t('pages:explain.toText')}</Link>;
  }
  return (
    <Link to={preview.path} className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 text-ink no-underline hover:text-ink sm:px-8">
      <span dir="auto" className="text-meta text-ink-soft">{textName(preview.text, i18n.language)}</span>
      <span {...AR} className="self-start rounded-full bg-paper px-3 py-1 text-body font-semibold">{preview.label}</span>
      <span {...AR} className="border-s-[3px] border-stamp-line ps-4 font-law text-law leading-[1.8]">{plainBody(preview.excerpt)}</span>
    </Link>
  );
}

/** What the discussion's guards found in a state, in the discussion's words. */
function Held({ reasons }: { reasons?: string[] }) {
  const { t } = useTalk();
  if (!reasons?.length) return null;
  return <p className="m-0 text-meta text-amended">{t('heldWhy', { reasons: reasons.map((r) => t(`heldReasons.${r}`, { defaultValue: r })).join(' ') })}</p>;
}

/** A reviewer's acts on one state: check the edit that waits, keep a reported state, remove one under a rule. Never on
 *  their own words: the server refuses, and says so. */
function ReviewActs({ d, register, revision, check = false, reports = 0 }: {
  d: Detail; register: Register; revision: number; check?: boolean; reports?: number;
}) {
  const { t } = useTranslation();
  const { t: talk } = useTalk();
  const refresh = useRefresh();
  const [rule, setRule] = useState<Rule | ''>('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await refresh();
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="flex flex-col gap-2">
      <div className="flex flex-wrap items-center gap-2">
        {check ? (
          <button type="button" disabled={busy} onClick={() => void act(() => explainApi.check(d.path, register))}
                  className="inline-flex h-11 items-center rounded-control bg-in-force px-4 text-body font-semibold text-sheet">
            {t('pages:explain.check')}
          </button>
        ) : null}
        {reports ? (
          <button type="button" disabled={busy} onClick={() => void act(() => explainApi.act(revision, 'keep'))}
                  className="inline-flex h-11 items-center rounded-control border border-rule px-4 text-body hover:bg-paper">
            {talk('review.keep')}
          </button>
        ) : null}
        <select value={rule} onChange={(ev) => setRule(ev.target.value as Rule | '')} aria-label={talk('review.rule')}
                className="h-11 rounded-control border border-field bg-sheet px-2 text-body">
          <option value="">{talk('review.rule')}</option>
          {RULES.map((r) => <option key={r} value={r}>{ruleNo(r)}. {talk(`rules.${r}`)}</option>)}
        </select>
        <button type="button" disabled={busy || !rule} onClick={() => void act(() => explainApi.act(revision, 'remove', rule))}
                className="inline-flex h-11 items-center rounded-control border border-repealed px-4 text-body text-repealed disabled:opacity-50">
          {talk('review.remove')}
        </button>
      </div>
      {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(talk, error)}</p> : null}
    </div>
  );
}

/** Reporting the words readers see, with the discussion's reasons: a reviewer of the text reads it, and its author never
 *  learns who reported. In place, under the words (the discussion's sheet would cost every first visit a chunk name). */
function Report({ revision, onClose }: { revision: number; onClose: () => void }) {
  const { t } = useTranslation();
  const { t: talk } = useTalk();
  const [reason, setReason] = useState<Reason | null>(null);
  const [details, setDetails] = useState('');
  const [state, setState] = useState<'' | 'busy' | 'sent'>('');
  const [error, setError] = useState<unknown>(null);
  if (state === 'sent') return <p role="status" className="m-0 text-body">{talk('reportSheet.sent')}</p>;
  const send = async () => {
    if (!reason) return;
    setState('busy');
    setError(null);
    try {
      await explainApi.report(revision, reason, details);
      setState('sent');
    } catch (err) {
      setError(err);
      setState('');
    }
  };
  return (
    <form onSubmit={(ev) => { ev.preventDefault(); void send(); }} className="flex flex-col gap-2 rounded-control border border-rule px-4 py-3">
      <fieldset className="m-0 border-0 p-0">
        <legend className="mb-1 p-0 text-body font-semibold">{t('pages:explain.reportTitle')}</legend>
        {REASONS.map((r) => (
          <label key={r} className="flex min-h-11 cursor-pointer items-center gap-3 text-body">
            <input type="radio" name="reason" value={r} checked={reason === r} onChange={() => setReason(r)} className="size-4 accent-[var(--color-stamp)]" />
            {talk(`reasons.${r}`)}
          </label>
        ))}
      </fieldset>
      <label className="flex flex-col gap-1 text-meta">
        {talk('reportSheet.details')}
        <textarea dir="auto" value={details} onChange={(ev) => setDetails(ev.target.value)} rows={2} maxLength={500}
                  className="rounded-control border border-field bg-sheet px-3 py-2 text-body" />
      </label>
      {error ? <p role="alert" className="m-0 text-meta text-repealed">{errorText(talk, error)}</p> : null}
      <div className="flex flex-wrap items-center gap-2">
        <button type="submit" disabled={!reason || state === 'busy'} className="h-11 rounded-control bg-stamp px-5 font-semibold text-on-stamp disabled:opacity-50">
          {talk('reportSheet.send')}
        </button>
        <button type="button" onClick={onClose} className="h-11 rounded-control px-4 text-ink-soft">{t('reading.close')}</button>
        <span className="text-meta text-ink-soft">{talk('reportSheet.who')}</span>
      </div>
    </form>
  );
}

function Shown({ d, e, register }: { d: Detail; e: Full; register: Register }) {
  const { t, i18n } = useTranslation();
  const { t: talk } = useTalk();
  const refresh = useRefresh();
  const signedIn = useSession((s) => s.tokens !== null);
  const [busy, setBusy] = useState(false);
  const [reporting, setReporting] = useState(false);
  const act = async (fn: () => Promise<unknown>) => {
    setBusy(true);
    try {
      await fn();
      await refresh();
    } finally {
      setBusy(false);
    }
  };
  const p = e.pending;
  return (
    <div className="flex flex-col gap-3">
      {e.waiting ? <p className="m-0 rounded-control bg-amended-wash px-4 py-2.5 text-body text-amended">{t('pages:explain.waiting')}</p> : null}
      {e.outdated ? <p className="m-0 rounded-control bg-amended-wash px-4 py-2.5 text-body text-amended">{t('pages:explain.outdated')}</p> : null}
      {e.headline ? <p dir="auto" className="m-0 text-lead font-semibold leading-snug">{e.headline}</p> : null}
      <p dir={register === 'fr' ? 'ltr' : 'rtl'} lang={register === 'fr' ? 'fr' : 'ar'} className="m-0 text-lead leading-[1.85]">{e.body}</p>
      {e.sources.length ? (
        <div className="flex flex-col gap-1.5">
          <span className="text-meta font-semibold text-ink-soft">{t('pages:explain.sources')}</span>
          <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
            {e.sources.map((s) => <li key={s}><Link to={s} className="inline-flex rounded-full bg-wash px-3 py-1 text-meta no-underline">{addressLabel(s, i18n.language, d.text_path)}</Link></li>)}
          </ul>
        </div>
      ) : null}
      <p className="m-0 flex flex-wrap items-center gap-x-3 gap-y-1 text-meta text-ink-soft">
        {e.checked_on ? <span>{t('pages:explain.checkedOn', { date: longDate(e.checked_on, i18n.language) })}</span> : null}
        <span>{t('pages:explain.editors', { count: e.editors })}</span>
      </p>
      <div className="flex flex-wrap items-center gap-2">
        {!e.waiting ? (
          signedIn ? (
            <button type="button" disabled={busy} aria-pressed={e.voted}
                    onClick={() => void act(() => explainApi.helpful(d.path, register, !e.voted))}
                    className={`inline-flex h-11 items-center gap-2 rounded-control px-4 text-body font-medium ${e.voted ? 'bg-people-fill text-on-people' : 'bg-paper text-ink hover:bg-people-wash'}`}>
              {t('pages:explain.helpful')}{e.helpful ? ` · ${e.helpful}` : ''}
            </button>
          ) : <Link to="/login" className="inline-flex h-11 items-center rounded-control bg-paper px-4 text-body no-underline">{t('pages:explain.helpful')}{e.helpful ? ` · ${e.helpful}` : ''}</Link>
        ) : null}
        {d.can_report && e.shown_id ? (
          <button type="button" onClick={() => setReporting(true)}
                  className="inline-flex h-11 items-center rounded-control px-4 text-body text-ink-soft hover:bg-paper hover:text-ink">
            {talk('report')}
          </button>
        ) : null}
      </div>
      {p ? (
        // The edit that waits: its author's and the reviewers' to read, while readers keep the words above.
        <div className="flex flex-col gap-2 rounded-control border border-dashed border-rule px-4 py-3">
          {!e.waiting ? (
            <>
              <p className="m-0 text-meta font-semibold">{p.mine ? t('pages:explain.pendingMine') : t('pages:explain.pendingOther')}</p>
              {p.headline ? <p dir="auto" className="m-0 font-semibold">{p.headline}</p> : null}
              <p dir={register === 'fr' ? 'ltr' : 'rtl'} lang={register === 'fr' ? 'fr' : 'ar'} className="m-0 text-body leading-relaxed">{p.body}</p>
            </>
          ) : null}
          {p.note ? <p dir="auto" className="m-0 text-meta text-ink-soft">«{p.note}»</p> : null}
          <Held reasons={p.held_reasons} />
          {d.can_review && !p.mine ? <ReviewActs d={d} register={register} revision={p.id} check /> : null}
        </div>
      ) : null}
      {reporting && e.shown_id ? <Report revision={e.shown_id} onClose={() => setReporting(false)} /> : null}
    </div>
  );
}

/** The form to write or improve the explanation in this register, for someone who may write (the discussion's gates). */
function Write({ d, register, current }: { d: Detail; register: Register; current?: Full }) {
  const { t } = useTranslation();
  const { t: talk } = useTalk();
  const signedIn = useSession((s) => s.tokens !== null);
  const refresh = useRefresh();
  // An edit starts from the newest words this person may read: the edit that waits, else those readers see.
  const start = current?.pending ?? current;
  const [open, setOpen] = useState(false);
  const [body, setBody] = useState(start?.body ?? '');
  const [headline, setHeadline] = useState(start?.headline ?? '');
  const [sources, setSources] = useState((start?.sources ?? []).join('\n'));
  const [note, setNote] = useState('');
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  if (!signedIn) {
    return <p className="m-0 rounded-card bg-sheet px-5 py-4 text-body sm:px-8">{t('pages:explain.signIn')} <Link to="/login">{t('nav.signIn')}</Link></p>;
  }
  if (!d.can_edit) return <p className="m-0 rounded-card bg-sheet px-5 py-4 text-body text-ink-soft sm:px-8">{t('pages:explain.closed')}</p>;
  if (!open) {
    return (
      <button type="button" onClick={() => { setBody(start?.body ?? ''); setHeadline(start?.headline ?? ''); setSources((start?.sources ?? []).join('\n')); setOpen(true); }}
              className="h-12 rounded-card bg-people-fill text-body font-semibold text-on-people">
        {current ? t('pages:explain.improve') : t('pages:explain.write')}
      </button>
    );
  }
  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    setBusy(true);
    setError('');
    try {
      await explainApi.save({ path: d.path, register, body, headline, note, consent: agreed || undefined,
                              sources: sources.split(/\s+/).map((s) => s.trim()).filter(Boolean) });
      await refresh();
      setOpen(false);
      setNote('');
    } catch (err) {
      const code = err instanceof ApiError ? err.errors[0] : null;
      setError(code ? t(`pages:explain.errors.${code.field}.${code.code}`, { defaultValue: errorText(talk, err) ?? t('pages:errors.unknown') }) : errorText(talk, err) ?? t('pages:errors.unknown'));
    } finally {
      setBusy(false);
    }
  };
  return (
    <form onSubmit={(ev) => void submit(ev)} className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-8">
      <p className="m-0 text-body text-ink-soft">{t('pages:explain.rules')}</p>
      {d.kind === 'text' ? (
        <label className="flex flex-col gap-1 text-body">
          {t('pages:explain.headline')}
          <input id="explain-headline" dir="auto" value={headline} onChange={(e) => setHeadline(e.target.value)} maxLength={200}
                 className="h-11 rounded-control border border-field bg-sheet px-3" />
        </label>
      ) : null}
      <label className="flex flex-col gap-1 text-body">
        {t('pages:explain.body', { register: t(`pages:explain.register.${register}`) })}
        <textarea id="explain-body" dir={register === 'fr' ? 'ltr' : 'rtl'} value={body} onChange={(e) => setBody(e.target.value)} rows={7}
                  maxLength={4000} required className="rounded-control border border-field bg-sheet px-3 py-2 leading-relaxed" />
      </label>
      <label className="flex flex-col gap-1 text-body">
        {t('pages:explain.sourcesField')}
        <textarea id="explain-sources" dir="ltr" value={sources} onChange={(e) => setSources(e.target.value)} rows={2}
                  placeholder="/ma/loi/67-12/art_33" className="rounded-control border border-field bg-sheet px-3 py-2 font-mono text-meta" />
      </label>
      <label className="flex flex-col gap-1 text-body">
        {t('pages:explain.note')}
        <input id="explain-note" dir="auto" value={note} onChange={(e) => setNote(e.target.value)} maxLength={200}
               className="h-11 rounded-control border border-field bg-sheet px-3" />
      </label>
      {!d.consent ? (
        // The first state asks, as the discussion's first post does, before the artificial intelligence reads it.
        <label className="flex items-start gap-2 text-meta">
          <input type="checkbox" checked={agreed} onChange={(ev) => setAgreed(ev.target.checked)} required className="mt-1 size-4 accent-[var(--color-stamp)]" />
          <span>{talk('check.consent')} <Link to="/privacy#check">{talk('check.consentMore')}</Link></span>
        </label>
      ) : null}
      {error ? <p role="alert" className="m-0 text-body text-repealed">{error}</p> : null}
      <div className="flex gap-2">
        <button type="submit" disabled={busy || !body.trim() || (!d.consent && !agreed)} className="h-11 rounded-control bg-stamp px-5 font-semibold text-on-stamp disabled:opacity-50">
          {t('pages:explain.publish')}
        </button>
        <button type="button" onClick={() => setOpen(false)} className="h-11 rounded-control px-4 text-ink-soft">{t('reading.close')}</button>
      </div>
    </form>
  );
}

/** Every earlier state this person may read, newest first: who changed it, why, and the words as they were. Readers
 *  see the checked ones; an author their own too; a reviewer every one, with what held it and its reports, and the acts. */
function History({ d, e, register }: { d: Detail; e: Full; register: Register }) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState<number | null>(null);
  return (
    <section className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-5 sm:px-8">
      <h2 className="m-0 text-lead font-semibold">{t('pages:explain.history', { count: e.history.length })}</h2>
      <ol className="m-0 flex list-none flex-col p-0">
        {e.history.map((r) => (
          <li key={r.id} className="border-t border-rule py-2.5 first:border-t-0">
            <button type="button" onClick={() => setOpen(open === r.id ? null : r.id)} aria-expanded={open === r.id}
                    className="flex w-full flex-wrap items-baseline gap-x-3 text-start text-body">
              <span className="font-medium">{r.author ?? t('pages:explain.nameless')}</span>
              <span className="text-ink-soft">{longDate(r.created_at.slice(0, 10), i18n.language)}</span>
              {r.note ? <span dir="auto" className="text-ink-soft">«{r.note}»</span> : null}
              <State r={r} />
            </button>
            {open === r.id ? (
              <div className="mt-2 flex flex-col gap-2">
                <p dir="auto" className="m-0 rounded-control bg-paper px-3 py-2 text-body leading-relaxed">{r.body}</p>
                <Held reasons={r.held_reasons} />
                {d.can_review && r.state !== 'removed' ? <ReviewActs d={d} register={register} revision={r.id} reports={r.reports} /> : null}
              </div>
            ) : null}
          </li>
        ))}
      </ol>
    </section>
  );
}

/** A state's standing, for those who see more than the checked ones. */
function State({ r }: { r: Revision }) {
  const { t } = useTranslation();
  if (r.state === 'checked' && !r.reports) return null;
  const said = r.state === 'removed' ? t('pages:explain.state.removed', { n: ruleNo(r.rule) })
    : r.state === 'checked' ? '' : t(`pages:explain.state.${r.state}`);
  return (
    <span className="text-meta text-amended">
      {[said, r.reports ? t('pages:explain.state.reports', { count: r.reports }) : ''].filter(Boolean).join(' · ')}
    </span>
  );
}

function Main({ children }: { children: React.ReactNode }) {
  return <Page width="reading" className="gap-4">{children}</Page>;
}
