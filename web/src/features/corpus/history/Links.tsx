import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { LinkState, LinkText, RepealNote, TextDetail } from '../corpus.api';
import { AR, longDate } from '../format';
import { Stamp } from '../article/Stamp';
import { issueLabel, textName } from './linkWords';
import '@/shared/locales/pages';

export function TextLink({ x, title = false }: { x: LinkText; title?: boolean }) {
  const { t } = useTranslation();
  const words = title && x.title ? x.title : textName(x, t);
  const note = x.in_corpus ? null : <span className="text-ink-soft"> ({t('links.notHeld')})</span>;
  return x.path
    ? <><Link to={x.path} className="no-underline"><bdi {...AR}>{words}</bdi></Link>{note}</>
    : <span><bdi {...AR}>{words}</bdi>{note}</span>;
}

/** The state of a link in words, the same everywhere: shown as fact only when checked, confirmed or read. */
export function StateChip({ state }: { state: LinkState }) {
  const { t } = useTranslation();
  if (!state) return null;
  const tone = state === 'confirmed' || state === 'checked' ? 'bg-wash text-in-force'
    : state === 'read' ? 'bg-chip text-ink-soft' : 'bg-amended-wash text-repealed';
  return <span className={`rounded-full px-1.5 py-0.5 text-meta ${tone}`}>{t(`links.states.${state}`)}</span>;
}

/** Under a text's title: where it stands today, what changed it last, and how much of the BO the site has read since
 *  it was published (rows L5–L7, L13). */
/** `only`: «warnings» under the title (repealed, repeal coming, not yet in force), «last» in «حول هذا النص» (what
 *  changed it last: U4 of the Moroccan-design review, so a law's page starts with the law). */
export function StandingLine({ d, only }: { d: TextDetail; only?: 'warnings' | 'last' }) {
  return (
    <>
      <Standing d={d} only={only} />
      {d.eras?.length && only !== 'last' ? <Eras eras={d.eras} /> : null}
    </>
  );
}

/** The texts a code has been, drawn to scale (C3 of the constitution review): each as wide as the years it stood and
 *  as tall as its text, right to left in Arabic, in violet tints that darken toward today's; this one outlined, each a
 *  link. Loaded with the standing line, after the law's words. */
function Eras({ eras }: { eras: NonNullable<TextDetail['eras']> }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const day = (iso: string | null) => (iso ? new Date(`${iso}T00:00:00Z`).getTime() : Date.now());
  const dated = eras.filter((e) => e.from);
  const ordered = eras.every((e, i) => i === 0 || day(e.from) >= day(eras[i - 1].from));
  if (dated.length !== eras.length || eras.length < 2 || !ordered) return <EraChips eras={eras} />;
  const start = day(eras[0].from), span = Date.now() - start;
  const most = Math.max(...eras.map((e) => e.size), 1);
  const side = lang === 'ar' ? 'right' : 'left';
  return (
    <nav aria-label={t('pages:eras.title')} className="flex flex-col gap-1.5" data-noprint>
      <span className="text-meta text-ink-soft">{t('pages:eras.title')}</span>
      {/* The years' labels reach past their bands to stay centred: kept inside the page (PX8: 4 px over a phone's edge). */}
      <div className="relative h-[7.5rem] border-b border-ink sm:h-[8.5rem]" style={{ overflowX: 'clip' }}>
        {eras.map((e, i) => {
          const at = (100 * (day(e.from) - start)) / span, width = (100 * (day(e.until) - day(e.from))) / span;
          const height = Math.max(8, Math.round((78 * e.size) / most));
          const name = e.name[lang] ?? e.name.ar;
          const tint = 0.28 + (0.72 * i) / (eras.length - 1);
          const narrow = width < 6;
          const band = (
            <>
              <span aria-hidden="true" className={`absolute inset-x-0 bottom-0 rounded-t-[3px] bg-stamp ${e.here ? 'ring-2 ring-ink ring-offset-1 ring-offset-sheet' : ''}`}
                    style={{ height: `${height}%`, opacity: tint }} />
              <span className={`absolute inset-x-[-1.5rem] text-center font-law text-body font-semibold ${e.here ? 'text-stamp' : 'text-ink'}`}
                    style={{ bottom: `calc(${height}% + ${narrow ? 1.5 : 0.2}rem)` }}>
                {e.year ?? ''}{e.current ? <span aria-hidden="true" className="ms-1 inline-block size-2 rounded-full bg-in-force align-middle" /> : null}
              </span>
            </>
          );
          const style = { [side]: `${at}%`, width: `${width}%` } as React.CSSProperties;
          return e.here
            ? <span key={e.path} aria-current="page" title={name} className="absolute bottom-0 top-0" style={style}>{band}<span className="sr-only">{name}</span></span>
            : <Link key={e.path} to={e.path} title={name} className="absolute bottom-0 top-0 no-underline hover:opacity-90" style={style}>
                {band}<span className="sr-only">{name}{e.current ? t('pages:eras.current') : ''}</span>
              </Link>;
        })}
      </div>
    </nav>
  );
}

/** The same texts as a row of years, where their dates are not all known. */
function EraChips({ eras }: { eras: NonNullable<TextDetail['eras']> }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  return (
    <nav aria-label={t('pages:eras.title')} className="flex flex-wrap items-center gap-2 text-body">
      <span className="text-meta text-ink-soft">{t('pages:eras.title')}</span>
      {eras.map((e) => {
        const name = e.name[lang] ?? e.name.ar;
        const words = (
          <>
            {e.current ? <span aria-hidden="true" className="size-2 rounded-full bg-in-force" /> : null}
            {e.year ?? name}
          </>
        );
        const cls = 'inline-flex min-h-11 items-center gap-1.5 rounded-full px-3.5 font-medium no-underline';
        return e.here
          ? <span key={e.path} aria-current="page" title={name} className={`${cls} bg-stamp text-on-stamp`}>{words}</span>
          : <Link key={e.path} to={e.path} title={name} className={`${cls} border border-rule bg-sheet text-ink hover:text-stamp`}>
              {words}{e.current ? <span className="sr-only">{t('pages:eras.current')}</span> : null}
            </Link>;
      })}
    </nav>
  );
}

function Standing({ d, only }: { d: TextDetail; only?: 'warnings' | 'last' }) {
  const { t, i18n } = useTranslation();
  const s = d.standing;
  if (!s) return null;
  const lines: React.ReactNode[] = [];
  const warnings = only !== 'last', last = only !== 'warnings';
  const repeal = (note: RepealNote, key: string) => (
    <p key={key} className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 text-body">
      <span className="font-medium text-repealed">
        {key === 'repealed'
          ? note.on ? t('links.repealedOn', { date: longDate(note.on, i18n.language) }) : t('links.repealed')
          : note.on ? t('links.repealPendingOn', { date: longDate(note.on, i18n.language) }) : t('links.repealPending')}
      </span>
      <span>{key === 'repealed' ? t('links.by') : t('links.byPending')} <TextLink x={note.by} /></span>
      {note.issue ? <Stamp line issue={issueLabel(note.issue, note.issue_bis, t)} page={note.page} /> : null}
      <StateChip state={note.state} />
    </p>
  );
  if (warnings && s.repealed) lines.push(repeal(s.repealed, 'repealed'));
  if (warnings && s.repeal_pending) lines.push(repeal(s.repeal_pending, 'pending'));
  if (warnings && s.repeal_pending?.rule === 'condition' && s.repeal_pending.words)
    lines.push(<p key="cond" {...AR} className="m-0 max-w-[60ch] rounded-control bg-amended-wash px-3 py-2 font-law text-law leading-snug text-amended">«{s.repeal_pending.words}»</p>);
  if (warnings && s.in_force_on) lines.push(<p key="on" className="m-0 text-body text-amended">{t('links.inForceOn', { date: longDate(s.in_force_on, i18n.language) })}</p>);
  if (warnings && s.in_force_when)
    lines.push(<p key="when" className="m-0 flex max-w-[64ch] flex-col gap-1 text-body text-amended">
      <span>{t('links.inForceWhen')}</span><span {...AR} className="font-law text-law leading-snug">«{s.in_force_when}»</span>
    </p>);
  if (last && s.last && !s.repealed)
    lines.push(
      <p key="last" className="m-0 flex flex-wrap items-center gap-x-2 gap-y-1 text-body">
        {/* «غيّره نص واحد: القانون 65.21»; with more, «غيّره نصان، آخرها …» (P7 of the polish review: «آخرها» after one
            text read as a mistake). */}
        <span>{t('links.changed', { count: s.changes })}{s.changes === 1 ? t('links.colon') : `${t('corpus.listSep')}${t('links.lastBy')} `}<TextLink x={s.last.by} /></span>
        {s.last.issue.number ? <Stamp line issue={issueLabel(s.last.issue.number, s.last.issue.bis, t)} page={s.last.issue.page} /> : null}
        {s.last.effective_on && s.last.effective_on !== s.last.published_on
          ? <span className="text-ink-soft">{t('links.takesEffect', { date: longDate(s.last.effective_on, i18n.language) })}</span> : null}
      </p>,
    );
  if (!lines.length) return null;
  return <div className="flex flex-col gap-2">{lines}</div>;
}

/** One sentence on what the site has read: «no change found» is said only of the issues read (row L5). */
export function Coverage({ d }: { d: TextDetail }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const c = d.standing.coverage;
  if (!c || !d.version) return null;
  if (c.before) return <p className="m-0 max-w-[64ch] text-meta text-ink-soft">{t('links.coverageBefore', { year: c.from.slice(0, 4) })}</p>;
  const latest = c.latest ? c.latest.key : '';
  // The archive's issues before 2019 are read by kind: their decisions may wait (Z23 of the archive's second reading).
  const unfound = c.unfound || c.waiting ? (
    <>{c.unfound ? <> {t('links.coverageUnfound', { count: c.unfound })}</> : null}{c.waiting ? <> {t('links.coverageWaiting', { count: c.waiting })}</> : null}</>
  ) : null;
  // The answer names the first 40 unread issues and counts them all (an archive text has thousands after it).
  const count = c.missing_count ?? c.missing.length;
  if (!count) return <p className="m-0 max-w-[64ch] text-meta text-ink-soft">{t('links.coverageAll', { latest })}{unfound}</p>;
  return (
    <p className="m-0 max-w-[64ch] text-meta text-ink-soft">
      {t('links.coverageMissing', { latest, count })}{unfound}{' '}
      <button type="button" onClick={() => setOpen((o) => !o)} aria-expanded={open} className="font-medium text-stamp">
        {open ? t('links.hideMissing') : t('links.showMissing')}
      </button>
      {open ? (
        <span className="flex flex-wrap gap-x-3 gap-y-1 pt-1 tabular-nums">
          {c.missing.map((m) => <bdi key={m.key} dir="ltr">{m.key.replace('-bis', ` ${t('corpus.suffix.bis')}`)}</bdi>)}
          {count > c.missing.length ? <span>{t('links.missingMore', { count: count - c.missing.length })}</span> : null}
        </span>
      ) : null}
    </p>
  );
}


/** A law asked on a day before the oldest version the site holds (HM26 of the hard-moment review: a link to the tax
 *  code's art. 73 on 1 January 2024 showed the 2026 edition with no word that 2024 is not held, though the scale changed
 *  in 2025): said, with the texts that changed it between the two days that the site knows of. */
export function OnBefore({ d, on }: { d: TextDetail; on: string }) {
  const { t, i18n } = useTranslation();
  const from = d.version?.valid_from;
  if (!from || !on || on >= from || d.versions.some((v) => v.valid_from && v.valid_from <= on)) return null;
  const between = d.amended_by.filter((x) => {
    const day = x.effective_on ?? x.published_on ?? '';
    return day > on && day <= from;
  });
  return (
    <div role="note" className="flex flex-col gap-1.5 rounded-control bg-amended-wash px-4 py-3 text-body text-ink">
      <p className="m-0">{t('pages:onBefore.lead', { on: longDate(on, i18n.language), from: longDate(from, i18n.language) })}</p>
      {between.length ? (
        <p className="m-0 text-meta text-ink-soft">
          {t('pages:onBefore.between')}{' '}
          {between.map((x, i) => (
            <span key={i}>{i ? '، ' : ''}{x.by.path ? <Link to={x.by.path}>{textName(x.by, t)}</Link> : textName(x.by, t)}</span>
          ))}
        </p>
      ) : null}
    </div>
  );
}
