import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Sheet } from '@/shared/components/Sheet';
import { span, useNum } from './library.api';
import type { Archive, Held, Year } from './map';
import '@/shared/locales/pages';

/** Years the strata mark with a dot and say under them: the Bulletin's first issue (in French), the first in Arabic,
 *  independence, two issues a week. */
const MARKS = [1912, 1913, 1956, 1996];

/** A year's issues as ticks on a strip, left to right as time runs, each as tall as its texts on one scale for every
 *  year (`most`): violet the Arabic, ochre the French edition's of 1912–1925, a short grey tick one held without texts.
 *  `span` years from `from` share the strip (a phone's decade row). */
function ticks(issues: Held[], most: number, from: number, span: number): React.ReactNode {
  let a = '', f = '', z = '';
  for (const x of issues) {
    const at = (((x.y - from) + (x.doy + 0.5) / x.dim) / span * 100).toFixed(2);
    const h = (28 - (3 + Math.sqrt(x.texts / most) * 23)).toFixed(1);
    if (x.pagesOnly) z += `M${at} 28V23`;
    else if (x.edition === 'translation_fr') f += `M${at} 28V${h}`;
    else a += `M${at} 28V${h}`;
  }
  return <><path className="tz" d={z} /><path className="tf" d={f} /><path className="ta" d={a} /></>;
}

function Strip({ issues, most, from, span = 1, seps = false }: { issues: Held[]; most: number; from: number; span?: number; seps?: boolean }) {
  return (
    <svg viewBox="0 0 100 28" preserveAspectRatio="none" aria-hidden="true">
      {seps ? <path className="sep" d={Array.from({ length: span - 1 }, (_, k) => `M${((k + 1) / span) * 100} 0V28`).join('')} /> : null}
      {ticks(issues, most, from, span)}
    </svg>
  );
}

function useSaid() {
  const { t } = useTranslation();
  const num = useNum();
  return (y: Year) => [
    t('pages:lib2.issuesN', { count: y.ar.length, n: num(y.ar.length) }) + (y.ar.length ? ` (${span(y.min, y.max)})` : ''),
    t('pages:lib2.textsN', { count: y.texts, n: num(y.texts) }),
    y.fr.length ? t('pages:lib3.strata.frenchN', { count: y.fr.length, n: num(y.fr.length) }) : '',
  ].filter(Boolean).join(t('corpus.listSep'));
}

/** The whole Bulletin on one screen (LB8 of the every-code review): a row a decade, newest on top, its years left to
 *  right, each a strip of its issues with its first and last numbers under it; a year opens /bo on it. On a phone a row is
 *  the decade's strip and opens its ten years in a sheet. */
export function Strata({ archive, current }: { archive: Archive; current?: number }) {
  const { t } = useTranslation();
  const num = useNum();
  const said = useSaid();
  const [decade, setDecade] = useState<number | null>(null);
  const most = useMemo(() => Math.max(1, ...archive.ar.map((x) => x.texts)), [archive]);
  const newest = Math.max(...archive.years.keys());
  const decades: number[] = [];
  for (let d = Math.floor(newest / 10) * 10; d >= 1910; d -= 10) decades.push(d);
  const of = (dec: number) => {
    const years = Array.from({ length: 10 }, (_, k) => archive.years.get(dec + k)).filter((y): y is Year => !!y);
    return { years, issues: years.flatMap((y) => [...y.ar, ...y.fr]), count: years.reduce((n, y) => n + y.ar.length, 0),
             min: Math.min(...years.filter((y) => y.ar.length).map((y) => y.min)), max: Math.max(0, ...years.map((y) => y.max)) };
  };
  return (
    <div className="lb-strata">
      <div className="lb-sgrid" dir="ltr">
        {decades.map((dec) => (
          <div key={dec} className="lb-dec">
            <span className="lb-dlab">{dec}</span>
            {Array.from({ length: 10 }, (_, k) => {
              const y = archive.years.get(dec + k);
              if (!y) return <span key={k} className="lb-yr none" aria-hidden="true" />;
              const mark = MARKS.includes(y.year) ? t(`pages:lib3.strata.mark${y.year}`) : '';
              return (
                <Link key={k} to={`/bo?year=${y.year}`} className={`lb-yr${mark ? ' mk' : ''}`} aria-current={current === y.year ? 'page' : undefined}
                      aria-label={`${y.year}: ${said(y)}${mark ? `. ${mark}` : ''}`} title={mark || undefined}>
                  <b>{y.year}</b>
                  <Strip issues={[...y.ar, ...y.fr]} most={most} from={y.year} />
                  <small>{y.ar.length ? `${y.min}–${y.max}` : t('pages:lib3.strata.frenchOnly')}</small>
                </Link>
              );
            })}
          </div>
        ))}
      </div>
      <ol className="lb-decs" dir="ltr">
        {decades.map((dec) => {
          const d = of(dec);
          return (
            <li key={dec}>
              <button type="button" className={`lb-decrow${current !== undefined && current >= dec && current < dec + 10 ? ' on' : ''}`} onClick={() => setDecade(dec)}
                      aria-label={`${dec}–${dec + 9}: ${t('pages:lib2.issuesN', { count: d.count, n: num(d.count) })}${d.count ? ` (${span(d.min, d.max)})` : ''}`}>
                <span className="lb-dlab">{dec}</span>
                <span className="lb-dstrip">
                  <Strip issues={d.issues} most={most} from={dec} span={10} seps />
                  <span className="lb-dyrs" aria-hidden="true">
                    {Array.from({ length: 10 }, (_, k) => <span key={k}>{archive.years.has(dec + k) ? String(dec + k).slice(2) : ''}</span>)}
                  </span>
                </span>
              </button>
            </li>
          );
        })}
      </ol>
      <p className="lb-key">
        <span><i />{t('pages:lib3.strata.keyArabic')}</span>
        <span><i className="f" />{t('pages:lib3.strata.keyFrench')}</span>
        <span><i className="z" />{t('pages:lib3.strata.keyPages')}</span>
        <span><i className="m" />{MARKS.map((y) => `${y} ${t(`pages:lib3.strata.mark${y}`)}`).join(t('corpus.listSep'))}</span>
      </p>
      {decade !== null ? (
        <Sheet label={`${decade}–${decade + 9}`} onClose={() => setDecade(null)} closeButton half>
          <div className="lb-decsheet">
            <h2 dir="ltr">{decade}–{decade + 9}</h2>
            <ol>
              {of(decade).years.map((y) => (
                <li key={y.year}>
                  <Link to={`/bo?year=${y.year}`} className="lb-yrow" dir="ltr" onClick={() => setDecade(null)} aria-label={`${y.year}: ${said(y)}`}>
                    <b>{y.year}</b><Strip issues={[...y.ar, ...y.fr]} most={most} from={y.year} />
                    <small dir="auto">{said(y)}</small>
                  </Link>
                </li>
              ))}
            </ol>
          </div>
        </Sheet>
      ) : null}
    </div>
  );
}

/** A year on a phone (LB9): its months newest first, each one row of its issues, the day large and the number under it;
 *  «مكرر» said, the French edition's dashed, one held without texts quiet. */
export function YearMonths({ year }: { year: Year }) {
  const { t, i18n } = useTranslation();
  const num = useNum();
  const locale = i18n.language === 'fr' ? 'fr-MA' : 'ar-MA';
  const month = new Intl.DateTimeFormat(locale, { month: 'long', timeZone: 'UTC' });
  const all = [...year.ar, ...year.fr].sort((a, b) => a.date.localeCompare(b.date) || a.number - b.number);
  const months = new Map<number, Held[]>();
  for (const x of all) months.set(x.m, [...(months.get(x.m) ?? []), x]);
  return (
    <div className="lb-months2">
      {[...months].reverse().map(([m, list]) => (
        <section key={m} className="lb-mo" aria-label={month.format(new Date(Date.UTC(year.year, m, 1)))}>
          <h3>{month.format(new Date(Date.UTC(year.year, m, 1)))}<small>{t('pages:lib2.issuesN', { count: list.length, n: num(list.length) })}</small></h3>
          <ol className="lb-chips">
            {list.map((x) => {
              const number = x.last ? `${x.number}–${x.last}` : `${x.number}${x.suffix ? ` ${t(`corpus.suffix.${x.suffix}`)}` : ''}`;
              const what = x.pagesOnly ? t('pages:lib3.issue.pagesOnlyShort') : t('pages:lib2.textsN', { count: x.texts, n: num(x.texts) });
              return (
                <li key={`${x.edition}${x.key}`}>
                  <Link to={`/bo/${x.edition}/${x.key}`} className={`lb-chip${x.edition === 'translation_fr' ? ' fr' : ''}${x.pagesOnly ? ' z' : ''}`}
                        aria-label={`${x.d} ${month.format(new Date(Date.UTC(year.year, m, 1)))}: ${number}${t('corpus.listSep')}${what}`}>
                    <b>{x.d}</b><span>{number}</span>
                  </Link>
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}
