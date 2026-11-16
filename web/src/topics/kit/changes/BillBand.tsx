import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import { todayIso } from '@/shared/services/today';
import { pick, useKitItem, useKitT, type Reform } from '../api';
import './words';
import './changes.css';

/** The running head of a page about a bill (the bill-page review, V10): it is not law and Parliament may change
 *  it; where it stands, as one line through its six stops — what it has passed drawn solid, what is left in a bill's
 *  dashes, the stop it stands at ringed; its next date; its text and its way a tap away. */
export function BillBand({ slug, bill, reform }: { slug: string; bill: string; reform?: string }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const r = useKitItem<Reform>(slug, 'reform', reform ?? '').data;
  const stops = r?.stages ?? [];
  const reached = stops.findIndex((s) => s.key === (r?.at ?? r?.stage));
  const today = todayIso();
  const next = r?.timeline.find((e) => e.date > today && e.short);
  return (
    <section className="ch-band" aria-label={t('bill.band')}>
      <p className="ch-band-what"><Draft />{t('bill.band')}</p>
      <p className="ch-band-links">
        {reform ? <Link to={`/topics/${slug}/reform/${reform}`}>{t('bill.path')}</Link> : null}
        <Link to={bill}>{t('bill.text')}</Link>
      </p>
      {stops.length ? (
        <ol className="ch-stops" aria-label={t('changes.where')}>
          {stops.map((s, i) => (
            <li key={s.key} className={i < reached ? 'done' : i === reached ? 'at' : ''} aria-current={i === reached ? 'step' : undefined}>
              <span>{pick(s.label, lang)}</span>
            </li>
          ))}
        </ol>
      ) : null}
      {next?.short ? <p className="ch-band-next">{t('changes.next', { what: pick(next.short, lang), date: longDate(next.date, lang) })}</p> : null}
    </section>
  );
}

/** A draft: a sheet with a pen across it. */
export function Draft() {
  return (
    <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <path d="M14 3H6v18h12V9z" strokeDasharray="3 2.5" /><path d="M10 15l7.5-7.5 2 2L12 17h-2z" />
    </svg>
  );
}
