import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { BlogLinks } from '@/features/blog/BlogLinks';
import { usePageTitle } from '@/shared/services/title';
import { LinesSkeleton, Page } from '@/shared/components/ui';
import '@/shared/locales/pages';
import { MoroccoMap, WorldMap, type Dot } from './Maps';
import { n, named } from './format';
import { PlaceSheet } from './parts';
import { type PlaceCard, usePlaces, useTyped } from './places.api';
import './places.css';

const dot = (p: PlaceCard): Dot | null => (p.lat == null || p.lon == null ? null
  : { slug: p.slug, ar: p.ar, fr: p.fr, lat: p.lat, lon: p.lon, value: p.texts, gone: p.kind === 'gone' });

/** The places a list ranks, the most named first: a tap opens the place's sheet. */
function Rank({ rows, most, onPick }: { rows: PlaceCard[]; most: number; onPick: (slug: string) => void }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const top = rows[0]?.texts || 1;
  return (
    <ol className="pl-rank" dir="ltr">
      {rows.filter((r) => r.texts).slice(0, most).map((r, i) => (
        <li key={r.slug}>
          <button type="button" onClick={() => onPick(r.slug)}>
            <span className="r">{i + 1}</span>
            <span className="nm"><span className="ln"><b>{named(r, lang)}</b>{r.kind === 'gone' ? <small>{t('pages:places.kind.gone')}</small> : null}</span>
              <span className="bar" style={{ width: `${(100 * r.texts) / top}%` }} /></span>
            <span className="v">{n(r.texts, lang)}</span>
          </button>
        </li>
      ))}
    </ol>
  );
}

/** /places «البلدان والمدن» (PL19 of the places review, 1 Nov 2026), a tool of the library: every state and every
 *  Moroccan place the Bulletin named, found by typing any spelling (Arabic or Latin), or on the two maps: the world in
 *  postmarks, Morocco whole with its cities as dots. A tap opens the place's sheet; its page lists every article. */
export default function PlacesPage() {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  const rtl = lang !== 'fr';
  usePageTitle([t('pages:places.title')]);
  const all = usePlaces();
  const [q, setQ] = useState('');
  const typed = useTyped(q);
  const [sheet, setSheet] = useState<string | null>(null);
  const d = all.data;
  const world = useMemo(() => (d?.countries ?? []).map(dot).filter((x): x is Dot => !!x), [d]);
  const morocco = useMemo(() => (d?.cities ?? []).map(dot).filter((x): x is Dot => !!x), [d]);
  const texts = d?.years.reduce((s, y) => s + y.texts, 0) ?? 0;
  const first = d?.years[0]?.year ?? 1913;

  return (
    <Page width="wide" className="pl">
      <header className="pl-head">
        <h1>{t('pages:places.title')}</h1>
        <p className="lead">{d ? t('pages:places.lead', { texts: n(texts, lang), year: first, countries: d.countries.filter((c) => c.texts && c.kind === 'country').length,
          cities: d.cities.filter((c) => c.texts).length, communes: n(d.communes, lang) }) : t('pages:places.leadShort')}</p>
        <div className="pl-find" role="search">
          <label htmlFor="pl-q">{t('pages:places.find')}</label>
          <input id="pl-q" type="search" dir="auto" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('pages:places.findHint')} autoComplete="off" />
          {q.trim().length >= 2 ? (
            <ul className="pl-typed" aria-live="polite">
              {typed.data?.places.length ? typed.data.places.map((p) => (
                <li key={p.slug}><Link to={p.path}><b>{named(p, lang)}</b><span>{t(`pages:places.kind.${p.kind}`)}</span><span className="v">{n(p.texts, lang)}</span></Link></li>
              )) : typed.isFetching ? null : <li className="none">{t('pages:places.nothing', { q })}</li>}
            </ul>
          ) : null}
        </div>
      </header>

      {!d ? <LinesSkeleton lines={8} /> : (
        <>
          <section className="pl-inst" aria-labelledby="pl-world">
            <div className="pl-inst-head">
              <h2 id="pl-world">{t('pages:places.world')}</h2>
              <p>{t('pages:places.worldHow')}</p>
            </div>
            <WorldMap dots={world} onPick={setSheet} picked={sheet} rtl={rtl} label={t('pages:places.worldMap')} />
            <Rank rows={d.countries} most={12} onPick={setSheet} />
          </section>

          <section className="pl-inst ma" aria-labelledby="pl-ma">
            <div className="pl-inst-head">
              <h2 id="pl-ma">{t('pages:places.morocco')}</h2>
              <p>{t('pages:places.moroccoHow')}</p>
            </div>
            <div className="pl-ma-body">
              <MoroccoMap dots={morocco} onPick={setSheet} picked={sheet} rtl={rtl} label={t('pages:places.moroccoMap')} />
              <Rank rows={d.cities} most={12} onPick={setSheet} />
            </div>
          </section>

          <section className="pl-more" aria-labelledby="pl-units">
            <h2 id="pl-units">{t('pages:places.units')}</h2>
            <div className="pl-cols">
              <div><h3>{t('pages:places.regions')}</h3><Rank rows={d.regions} most={12} onPick={setSheet} /></div>
              <div><h3>{t('pages:places.provinces')}</h3><Rank rows={d.provinces} most={15} onPick={setSheet} /></div>
            </div>
          </section>

          <BlogLinks slugs={['countries', 'cities']} />
          <p className="pl-source">{t('pages:places.source')}</p>
        </>
      )}
      {sheet ? <PlaceSheet slug={sheet} onClose={() => setSheet(null)} /> : null}
    </Page>
  );
}
