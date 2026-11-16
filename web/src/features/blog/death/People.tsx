import { useTranslation } from 'react-i18next';
import { n, useWidth } from '../viz';

/**
 * The people under a death sentence at each of the CNDH's reports, one dot a person, a column a report, left to right on
 * every page: the count over each column, its year under it. A tap on a column names its report below.
 */
export function People({ years, picked, onPick, aria }: {
  years: { year: number; n: number }[];
  picked: number;
  onPick: (y: number) => void;
  aria: string;
}) {
  const { i18n } = useTranslation('blog');
  const [ref, width] = useWidth<HTMLDivElement>(640);
  const per = width < 520 ? 5 : 10;
  return (
    <div ref={ref} className="dp-people" dir="ltr" role="group" aria-label={aria}>
      {years.map((y) => (
        <button key={y.year} type="button" className={`dp-col${picked === y.year ? ' is-on' : ''}`} aria-pressed={picked === y.year}
                onClick={() => onPick(y.year)}>
          <span className="dp-col-n">{n(y.n, i18n.language)}</span>
          <span className="dp-dots" style={{ gridTemplateColumns: `repeat(${per}, var(--dp-dot))` }} aria-hidden="true">
            {Array.from({ length: y.n }, (_, i) => <i key={i} />)}
          </span>
          <span className="dp-col-year">{y.year}</span>
        </button>
      ))}
    </div>
  );
}
