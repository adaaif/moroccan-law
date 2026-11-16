import { useTranslation } from 'react-i18next';
import { hundred, money } from './money';
import './words';

export type Share = { label: string; value: number; color: string };

/** Out of every 100 dirhams: one square a dirham, in the shares' order, with the legend that says it in words.
 *  The squares are a picture of the legend; the legend is the content (screen readers read only it). */
export function HundredGrid({ shares, caption, total }: { shares: Share[]; caption: string; total: number }) {
  const { t, i18n } = useTranslation();
  const counts = hundred(shares.map((s) => s.value));
  const squares = shares.flatMap((s, i) => Array.from({ length: counts[i] }, () => s.color));
  return (
    <figure className="m-0 grid items-start gap-8 md:grid-cols-[minmax(0,300px)_1fr]">
      <div aria-hidden="true" className="grid aspect-square w-full max-w-[300px] grid-cols-10 gap-[3px]">
        {squares.map((color, i) => <span key={i} className={`rounded-[3px] ${color}`} />)}
      </div>
      <figcaption className="flex flex-col gap-4">
        <p className="m-0 text-lead">
          {caption} <span className="text-ink-soft">({money(total, i18n.language, t)})</span>
        </p>
        <ul className="m-0 flex list-none flex-col gap-2.5 p-0">
          {shares.map((s, i) => (
            <li key={s.label} className="flex items-baseline gap-3">
              <span aria-hidden="true" className={`size-3 flex-none translate-y-0.5 rounded-[3px] ${s.color}`} />
              <span className="whitespace-nowrap font-law text-h2 font-semibold leading-none">{t('budget.dirhams', { count: counts[i] })}</span>
              <span className="text-body">
                <span lang="ar" dir="rtl">{s.label}</span>{' '}
                <span className="text-ink-soft">{money(s.value, i18n.language, t)}</span>
              </span>
            </li>
          ))}
        </ul>
      </figcaption>
    </figure>
  );
}
