import { useId, useState, type ReactNode } from 'react';
import { Sheet } from '@/shared/components/Sheet';
import { useDismiss } from '@/shared/components/dismiss';
import { buttonClass } from '@/shared/components/buttons';
import { todayIso } from '@/shared/services/today';
import { dateOf, lastDays, num, type UseDay } from '../desk';
import { said, useD } from '../desk.strings';

/** Where a request or an access opens: beside the list on a desk, the sheet from the bottom on a phone. Escape and the
 *  phone's back close either. */
export function Holder({ wide, label, onClose, children }: { wide: boolean; label: string; onClose: () => void; children: ReactNode }) {
  if (!wide) return <Sheet label={label} onClose={onClose}>{children}</Sheet>;
  return <Side label={label} onClose={onClose}>{children}</Side>;
}

function Side({ label, onClose, children }: { label: string; onClose: () => void; children: ReactNode }) {
  useDismiss(onClose);
  return <aside className="dk-side" aria-label={label}>{children}</aside>;
}

/** A part's title on a rule, a line under it, what it holds. */
export function Block({ title, lead, more, quiet = false, children, className = '' }: {
  title: ReactNode; lead?: ReactNode; more?: ReactNode; quiet?: boolean; children?: ReactNode; className?: string;
}) {
  const h = useId();
  return (
    <section className={`dk-block ${quiet ? 'quiet' : ''} ${className}`} aria-labelledby={h}>
      <header className="dk-block-head"><h2 id={h}>{title}</h2>{more}</header>
      {lead ? <p className="dk-lead">{lead}</p> : null}
      {children}
    </section>
  );
}

/** What failed, in words, and the way to try again. */
export function Failed({ error, retry }: { error: unknown; retry?: () => void }) {
  const { t } = useD();
  return (
    <p role="alert" className="dk-failed">
      {said(t, error)}{' '}
      {retry ? <button type="button" onClick={retry}>{t('retry')}</button> : null}
    </p>
  );
}

/** A refusal said under the form it belongs to. */
export function Refusal({ error }: { error: unknown }) {
  const { t } = useD();
  if (!error) return null;
  return <p role="alert" className="dk-refusal">{typeof error === 'string' ? error : said(t, error)}</p>;
}

/** Copies its text and says so for a moment. */
export function Copy({ text }: { text: string }) {
  const { t } = useD();
  const [done, setDone] = useState(false);
  const copy = () => {
    void navigator.clipboard?.writeText(text).then(() => { setDone(true); window.setTimeout(() => setDone(false), 1600); }, () => undefined);
  };
  return <button type="button" onClick={copy} aria-live="polite" className={buttonClass('quiet')}>{done ? t('copied') : t('copy')}</button>;
}

/** «المزيد»: the next page of a list. */
export function More({ has, busy, onMore }: { has: boolean; busy: boolean; onMore: () => void }) {
  const { t } = useD();
  if (!has) return null;
  return <button type="button" className="dk-more" disabled={busy} onClick={onMore}>{t('more')}</button>;
}

/**
 * Thirty days of a count as bars, drawn left to right on an Arabic page too, the oldest first and today last. One series,
 * so the title names it and no legend is drawn; each bar says its day and number on hover, and the numbers are in a
 * table under the chart for anyone who does not read the chart.
 */
export function Bars({ days, field, title }: { days: UseDay[]; field: 'calls' | 'articles'; title: string }) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  const filled = lastDays(days, todayIso());
  const most = Math.max(0, ...filled.map((d) => d[field]));
  return (
    <figure className="dk-chart">
      <figcaption><b>{title}</b>{most ? <span>{t('use.most', { n: num(most, lang) })}</span> : null}</figcaption>
      <div className="dk-bars" dir="ltr" aria-hidden="true">
        {filled.map((d) => (
          <span key={d.day} title={`${dateOf(d.day, lang)}: ${num(d[field], lang)}`}>
            <i className={d[field] ? 'on' : 'off'} style={{ height: d[field] && most ? `${Math.max(3, (d[field] / most) * 100)}%` : undefined }} />
          </span>
        ))}
      </div>
      <span className="dk-axis" dir="ltr"><span dir="auto">{dateOf(filled[0].day, lang)}</span><span dir="auto">{dateOf(filled[filled.length - 1].day, lang)}</span></span>
    </figure>
  );
}

/** The days' numbers as a table, the newest first, only the days that saw use. */
export function DayNumbers({ days }: { days: UseDay[] }) {
  const { t, i18n } = useD();
  const lang = i18n.language;
  if (!days.length) return null;
  return (
    <details className="dk-numbers">
      <summary>{t('use.numbers')}</summary>
      <table>
        <thead><tr><th scope="col">{t('use.day')}</th><th scope="col">{t('use.calls')}</th><th scope="col">{t('use.articles')}</th></tr></thead>
        <tbody>
          {days.slice().reverse().map((d) => (
            <tr key={d.day}><th scope="row">{dateOf(d.day, lang)}</th><td>{num(d.calls, lang)}</td><td>{num(d.articles, lang)}</td></tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}

/** Thirty days of calls as a small line, left to right, today at its end. */
export function Spark({ values, label }: { values: number[]; label: string }) {
  const most = Math.max(1, ...values);
  const step = values.length > 1 ? 60 / (values.length - 1) : 60;
  const points = values.map((v, i) => `${(i * step).toFixed(1)},${(19 - (v / most) * 17).toFixed(1)}`).join(' ');
  return (
    <svg className="dk-spark" viewBox="0 0 60 20" preserveAspectRatio="none" role="img" aria-label={label}>
      <line x1="0" y1="19.5" x2="60" y2="19.5" className="base" />
      <polyline points={points} />
    </svg>
  );
}

/** Calls by door, each door in words, the busiest first; a bar for each, left to right. */
export function DoorList({ doors, name }: { doors: Record<string, number>; name: (door: string) => string }) {
  const { i18n } = useD();
  const rows = Object.entries(doors).sort((a, b) => b[1] - a[1]);
  const most = Math.max(1, ...rows.map(([, n]) => n));
  return (
    <ul className="dk-doors">
      {rows.map(([door, n]) => (
        <li key={door}>
          <span className="name">{name(door)}<code dir="ltr">{door}</code></span>
          <span className="track" dir="ltr" aria-hidden="true"><i style={{ width: `${Math.max(1, (n / most) * 100)}%` }} /></span>
          <b>{num(n, i18n.language)}</b>
        </li>
      ))}
    </ul>
  );
}
