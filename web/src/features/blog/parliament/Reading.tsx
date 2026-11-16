import { useTranslation } from 'react-i18next';
import { useWidth } from '../viz';
import { daysToRead } from './time';

/**
 * How long the law in force takes to read at a time a day: the laws, then the dahirs and decrees, then the ministers'
 * orders, end to end on one track of years, left to right on every page, each part named under it with its time. The
 * reader picks the time a day; the track redraws (the motion answers the choice).
 */
export type Layer = { key: string; words: number; name: string; time: string };

export function Reading({ layers, wpm, minutes, aria, yearsWord }: {
  layers: Layer[];
  wpm: number;
  minutes: number;
  aria: string;
  yearsWord: (n: number) => string;
}) {
  const { i18n } = useTranslation('blog');
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const days = layers.map((l) => daysToRead(l.words, wpm, minutes));
  const total = days.reduce((s, d) => s + d, 0);
  const yearsTotal = total / 365;
  const ticks = yearsTotal > 20 ? 10 : yearsTotal > 6 ? 2 : yearsTotal > 2 ? 1 : 0.25;
  const max = Math.max(ticks, Math.ceil(yearsTotal / ticks) * ticks);
  const x = (d: number) => (d / 365 / max) * width;
  let at = 0;
  return (
    <div ref={ref} className="pl-read" dir="ltr" role="img" aria-label={aria}>
      <div className="pl-track">
        {layers.map((l, i) => {
          const left = x(at);
          at += days[i];
          return <span key={l.key} className={`pl-seg is-${l.key}`} style={{ left, width: Math.max(2, x(at) - left) }} />;
        })}
      </div>
      <div className="pl-ticks">
        {Array.from({ length: Math.round(max / ticks) + 1 }, (_, k) => k * ticks).map((tv) => (
          <span key={tv} style={{ left: (tv / max) * width }}>{Number.isInteger(tv) ? tv : tv.toLocaleString(i18n.language === 'fr' ? 'fr-FR' : 'en-US')}</span>
        ))}
      </div>
      <p className="pl-ticks-unit" dir={i18n.language === 'fr' ? 'ltr' : 'rtl'}>{yearsWord(Math.round(max))}</p>
      <ul className="pl-layers" dir={i18n.language === 'fr' ? 'ltr' : 'rtl'}>
        {layers.map((l) => (
          <li key={l.key} className={`is-${l.key}`}><i aria-hidden="true" /><span className="pl-layer-name">{l.name}</span><b>{l.time}</b></li>
        ))}
      </ul>
    </div>
  );
}
