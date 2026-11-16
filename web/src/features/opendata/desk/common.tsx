import type { ReactNode } from 'react';
import { eventLine, iso, momentOf, type Account, type DeskEvent } from '../desk';
import { useD } from '../desk.strings';

/** A sheet's head: who, what it is (a few facts, between dots), and the way to close it. */
export function SheetHead({ title, line, onClose }: { title: string; line: ReactNode[]; onClose: () => void }) {
  const { t } = useD();
  return (
    <header className="dk-sheet-head">
      <div>
        <h2 tabIndex={-1}><bdi>{title}</bdi></h2>
        <p className="dk-dots"><span>{line.filter(Boolean).map((x, i) => <span key={i}>{x}</span>)}</span></p>
      </div>
      <button type="button" className="dk-close" onClick={onClose} aria-label={t('close')}>
        <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M6 6l12 12M18 6 6 18" /></svg>
      </button>
    </header>
  );
}

/** Label and value rows, one under the other; a value a person typed keeps its own direction. `short` values (a number,
 *  a date) stay beside their label on a phone too. */
export function Facts({ rows, short = false }: { rows: [string, ReactNode, boolean?][]; short?: boolean }) {
  return (
    <dl className={`dk-facts ${short ? 'short' : ''}`}>
      {rows.map(([label, value, typed]) => (
        <div key={label}><dt>{label}</dt><dd dir={typed ? 'auto' : undefined}>{value}</dd></div>
      ))}
    </dl>
  );
}

/** A sheet's part: its title on a rule. */
export function Part({ title, children }: { title: string; children: ReactNode }) {
  return <section className="dk-part"><h3>{title}</h3>{children}</section>;
}

/** The account behind a request or an access: its name, its address and whether it is proven, its age, its standing in
 *  the discussion. The address is shown here alone. */
export function AccountPart({ a }: { a: Account }) {
  const { t } = useD();
  const age = a.days === 0 ? t('sheet.joinedToday') : t('sheet.joined', { count: a.days });
  const posts = a.posts === 0 ? t('sheet.posts_zero') : t('sheet.posts', { count: a.posts });
  const removed = a.posts || a.removed ? (a.removed ? t('sheet.removed', { count: a.removed }) : t('sheet.removedNone')) : '';
  return (
    <Part title={t('sheet.account')}>
      <ul className="dk-account">
        <li><bdi dir="ltr">@{a.username}</bdi>{a.display_name && a.display_name !== a.username ? <span> · <bdi>{a.display_name}</bdi></span> : null}</li>
        <li><bdi dir="ltr">{a.email}</bdi> · <span className={a.email_proven ? 'ok' : 'warn'}>{a.email_proven ? `✓ ${t('sheet.proven')}` : t('sheet.unproven')}</span></li>
        <li>{age}</li>
        <li>{posts}{removed ? <span className={a.removed ? 'warn' : ''}> · {removed}</span> : null}</li>
        {a.paused ? <li className="warn">{t('sheet.paused')}</li> : null}
      </ul>
    </Part>
  );
}

/** What happened to a request or an access, the oldest first, a sentence each. */
export function History({ events }: { events: DeskEvent[] }) {
  const { t, i18n } = useD();
  if (!events.length) return null;
  return (
    <Part title={t('sheet.history')}>
      <ol className="dk-history">
        {events.map((e, i) => (
          <li key={`${e.at}-${i}`}>
            <span>{eventLine(t, e, i18n.language)}</span>
            <time dateTime={e.at}>{momentOf(e.at, i18n.language)}</time>
          </li>
        ))}
      </ol>
    </Part>
  );
}

/** A letter exactly as its person will read it, in their language, with where it goes. */
export function LetterView({ letter, to }: { letter: { language: string; subject: string; body: string }; to: string }) {
  const { t } = useD();
  const lang = letter.language === 'fr' ? 'fr' : 'ar';
  return (
    <div className="dk-letter-wrap">
      <p className="dk-lead">{t('act.letter')}</p>
      <article className="dk-letter" lang={lang} dir={lang === 'ar' ? 'rtl' : 'ltr'}>
        <b>{letter.subject}</b>
        <p>{letter.body}</p>
      </article>
      <p className="dk-small">{t('act.letterTo', { to: iso(to), lang: t(`act.langs.${lang}`) })}</p>
    </div>
  );
}
