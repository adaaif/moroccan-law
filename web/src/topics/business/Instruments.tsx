import { Link } from 'react-router-dom';
import { pick, refPath, useKitT, type Door } from '../kit/api';
import { useBusinessT } from './strings';

/** The business's instruments on their page (the business review): four stamps, two pressed and two struck (the
 *  forms the law opens); a cheque, its date and the twenty days after it; an invoice and the clock past its term. Each
 *  opens its tool. A phone lays them in a row; a desk stacks them in its side column with a line each. */
export default function Instruments({ slug, tools, side }: { slug: string; tools: Door[]; side: boolean }) {
  const { i18n } = useKitT();
  const { t } = useBusinessT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const drawings: Record<string, React.ReactNode> = { form: <FormMini />, cheque: <ChequeMini />, late: <LateMini /> };
  return (
    <ul className={`m-0 grid list-none gap-2 p-0 ${side ? '' : 'grid-cols-3'}`}>
      {tools.map((d) => (
        <li key={d.key}>
          <Link to={refPath(slug, d.to ?? `tools/${d.key}`)}
                className={`flex h-full rounded-card bg-sheet text-ink no-underline hover:text-stamp ${side ? 'items-center gap-3 px-3 py-3' : 'flex-col gap-2 px-2.5 pb-3 pt-2.5'}`}>
            <span className={side ? 'w-24 shrink-0' : 'w-full'}>{drawings[d.key]}</span>
            <span className="flex min-w-0 flex-col gap-0.5">
              <span lang={lang} className="text-meta font-semibold leading-snug sm:text-body">{t(`instruments.${d.key}`, { defaultValue: pick(d.title, lang) })}</span>
              {side ? <span lang={lang} className="text-meta leading-snug text-ink-soft">{t(`instruments.${d.key}Line`, { defaultValue: pick(d.lead, lang) })}</span> : null}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Four small stamps askew: two pressed in the topic's ink, two struck. Never mirrored. */
function FormMini() {
  const at = [[8, 8], [62, 6], [10, 32], [64, 31]] as const;
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      {at.map(([x, y], i) => (
        <g key={i} transform={`rotate(${i % 2 ? 3 : -4} ${x + 22} ${y + 9})`}>
          <rect x={x} y={y} width="44" height="18" rx="2.5" fill="none" strokeWidth="1.8"
                style={{ stroke: i < 2 ? 'var(--t)' : 'var(--color-rule)' }} />
          <path d={`M${x + 8} ${y + 9}h28`} strokeWidth="2.6" strokeLinecap="round"
                style={{ stroke: i < 2 ? 'color-mix(in srgb, var(--t) 55%, transparent)' : 'var(--color-rule)' }} />
          {i >= 2 ? <path d={`M${x + 4} ${y + 15}l36-12`} strokeWidth="1.4" style={{ stroke: 'var(--color-ink-soft)' }} /> : null}
        </g>
      ))}
    </svg>
  );
}

/** A cheque: its band, its amount box, its date in the topic's colour, its signature. Never mirrored. */
function ChequeMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <rect x="10" y="6" width="100" height="44" rx="4" strokeWidth="1.5" className="fill-sheet stroke-field" />
      <rect x="10" y="6" width="100" height="8" rx="4" style={{ fill: 'color-mix(in srgb, var(--t) 25%, transparent)' }} />
      <rect x="72" y="18" width="32" height="9" rx="1.5" strokeWidth="1.3" fill="none" className="stroke-field" />
      <path d="M16 22h40M16 29h28" strokeWidth="2.6" strokeLinecap="round" className="stroke-rule" />
      <path d="M78 36h24" strokeWidth="3.4" strokeLinecap="round" style={{ stroke: 'var(--t)' }} />
      <path d="M18 43c3-7 5 3 8-1s4 3 7 0 3 2 6-1" fill="none" strokeWidth="1.4" strokeLinecap="round" className="stroke-ink" />
    </svg>
  );
}

/** An invoice and a clock past its term: the paper's lines, and the hand gone into the red. */
function LateMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full rtl:-scale-x-100">
      <rect x="18" y="4" width="44" height="48" rx="3" strokeWidth="1.5" className="fill-sheet stroke-field" />
      <path d="M25 14h30M25 21h22M25 28h30M25 35h18" strokeWidth="2.4" strokeLinecap="round" className="stroke-rule" />
      <circle cx="84" cy="30" r="16" strokeWidth="2.2" className="fill-sheet" style={{ stroke: 'var(--t)' }} />
      <path d="M84 30V19" strokeWidth="2.4" strokeLinecap="round" className="stroke-ink" />
      <path d="M84 30l9 6" strokeWidth="2.4" strokeLinecap="round" style={{ stroke: 'var(--color-sign-red)' }} />
      <path d="M84 14a16 16 0 0 1 14 8" fill="none" strokeWidth="4" strokeLinecap="round" style={{ stroke: 'color-mix(in srgb, var(--color-sign-red) 55%, transparent)' }} />
    </svg>
  );
}
