import { lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Sheet } from '@/shared/components/Sheet';
import { LinesSkeleton } from '@/shared/components/ui';
import '@/shared/locales/pages';
import { n, named } from './format';
import { type PlaceProfile, usePlace } from './places.api';

const FollowButton = lazy(() => import('@/features/follows/FollowButton'));

/** Its texts year by year as a strip of bars, per 1,000 texts of the year (PL4): the same height means the same share
 *  whatever the year's size. `pick` makes a bar a button for that year. */
export function YearBars({ years, picked, onPick, height = 64 }: {
  years: PlaceProfile['years']; picked?: [number, number] | null; onPick?: (year: number) => void; height?: number;
}) {
  const { t, i18n } = useTranslation();
  const share = years.map((y) => (y.total ? (1000 * y.texts) / y.total : 0));
  const top = Math.max(...share, 0.001);
  const w = 100 / Math.max(years.length, 1);
  return (
    <div className="pl-bars" dir="ltr" style={{ height }}>
      {years.map((y, i) => {
        const on = picked && y.year >= picked[0] && y.year <= picked[1];
        const h = `${Math.max(share[i] ? 3 : 0, (100 * share[i]) / top)}%`;
        const label = t('pages:places.yearBar', { year: y.year, count: y.texts, texts: n(y.texts, i18n.language), share: (share[i]).toFixed(1).replace('.', ',') });
        return onPick ? (
          <button key={y.year} type="button" className={on ? 'on' : ''} style={{ width: `${w}%` }} onClick={() => onPick(y.year)}
                  aria-label={label} title={label} aria-pressed={!!on}><i style={{ height: h }} /></button>
        ) : <span key={y.year} style={{ width: `${w}%` }} title={label}><i style={{ height: h }} /></span>;
      })}
    </div>
  );
}

/** The place's sheet (PL23): what a tap on a postmark or a dot opens, in the posts and in the finder alike. */
export function PlaceSheet({ slug, onClose }: { slug: string; onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const q = usePlace(slug);
  const p = q.data;
  return (
    <Sheet label={p ? named(p.place, lang) : t('pages:places.title')} onClose={onClose} half centered closeButton>
      <div className="pl-sheet">
        {!p ? <LinesSkeleton lines={4} /> : (
          <>
            <p className="pl-name" lang="ar" dir="rtl">{p.place.ar}</p>
            <p className="pl-meta">{[t(`pages:places.kind.${p.place.kind}`), lang === 'fr' ? null : p.place.fr].filter(Boolean).join(' · ')}</p>
            <p className="pl-count">{p.place.texts ? t('pages:places.named', { count: p.place.texts, texts: n(p.place.texts, lang), year: p.place.first?.date.slice(0, 4) ?? '' })
              : t('pages:places.never')}</p>
            {p.place.texts ? <YearBars years={p.years} height={48} /> : null}
            {p.place.first ? (
              <p className="pl-meta">{t('pages:places.firstShort', { date: p.place.first.date.slice(0, 4), form: p.place.first.form })}</p>
            ) : null}
            <div className="pl-sheet-go">
              <Link to={p.place.path} className="pl-go" onClick={onClose}>{t('pages:places.open', { count: p.place.texts })}</Link>
              <Suspense fallback={null}><FollowButton path={p.place.path} compact /></Suspense>
            </div>
          </>
        )}
      </div>
    </Sheet>
  );
}
