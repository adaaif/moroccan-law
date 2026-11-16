import { Link } from 'react-router-dom';
import { pick, refPath, useKitT, type Door } from '../kit/api';
import { useHealthT } from './strings';

/** Health's instruments on its page (S19 of the health review): the refund as its bar (70 back, 30 left), the
 *  feuille de soins' clock as two months on a line, the long-illness finder as its list. Each opens its tool. A phone lays
 *  them in a row; a desk stacks them in its side column with a line each. */
export default function Instruments({ slug, tools, side }: { slug: string; tools: Door[]; side: boolean }) {
  const { i18n } = useKitT();
  const { t } = useHealthT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const drawings: Record<string, React.ReactNode> = { refund: <RefundMini />, clock: <ClockMini />, illness: <ListMini /> };
  const lines: Record<string, string> = { refund: t('instruments.refundLine', { back: lang === 'fr' ? '70 DH' : '70 درهم' }), clock: t('instruments.clockLine'), illness: t('instruments.illnessLine') };
  return (
    <ul className={`m-0 grid list-none gap-2 p-0 ${side ? '' : 'grid-cols-3'}`}>
      {tools.map((d) => (
        <li key={d.key}>
          <Link to={refPath(slug, d.to ?? `tools/${d.key}`)}
                className={`flex h-full rounded-card bg-sheet text-ink no-underline hover:text-stamp ${side ? 'items-center gap-3 px-3 py-3' : 'flex-col gap-2 px-2.5 pb-3 pt-2.5'}`}>
            <span className={side ? 'w-24 shrink-0' : 'w-full'}>{drawings[d.key]}</span>
            <span className="flex min-w-0 flex-col gap-0.5">
              <span lang={lang} className="text-meta font-semibold leading-snug sm:text-body">{t(`instruments.${d.key}`, { defaultValue: pick(d.title, lang) })}</span>
              {side ? <span lang={lang} className="text-meta leading-snug text-ink-soft">{lines[d.key] ?? pick(d.lead, lang)}</span> : null}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** A hundred dirhams as one bar: seventy back in the topic's colour from the left (HM34), thirty in ink. */
function RefundMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <rect x="6" y="20" width="75" height="16" rx="3" className="fill-[var(--t)]" />
      <rect x="83" y="20" width="31" height="16" rx="3" className="fill-ink" />
      <path d="M6 44h75" strokeWidth="1.4" strokeDasharray="2 2" className="stroke-field" />
    </svg>
  );
}

/** Two months on a line: the first act's day, the last day marked in the topic's colour. */
function ClockMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full rtl:-scale-x-100">
      <path d="M8 30h104" strokeWidth="3" strokeLinecap="round" className="stroke-rule" />
      <path d="M8 30h62" strokeWidth="3" strokeLinecap="round" className="stroke-ink" />
      <circle cx="8" cy="30" r="5" className="fill-ink" />
      <circle cx="112" cy="30" r="6" className="fill-[var(--t)]" />
      {[37, 66, 95].map((x) => <path key={x} d={`M${x} 24v12`} strokeWidth="1.4" className="stroke-field" />)}
    </svg>
  );
}

/** A list of numbered lines, one found and marked in the topic's colour. */
function ListMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full rtl:-scale-x-100">
      {[10, 22, 34, 46].map((y, i) => (
        <g key={y}>
          <circle cx="14" cy={y} r="2.4" className={i === 1 ? 'fill-[var(--t)]' : 'fill-field'} />
          <path d={`M22 ${y}h${i === 1 ? 60 : 48 + (i % 2) * 18}`} strokeWidth="3" strokeLinecap="round" className={i === 1 ? 'stroke-[var(--t)]' : 'stroke-rule'} />
        </g>
      ))}
      <circle cx="100" cy="26" r="9" strokeWidth="2.6" fill="none" className="stroke-ink" />
      <path d="M107 33l7 7" strokeWidth="2.6" strokeLinecap="round" className="stroke-ink" />
    </svg>
  );
}
