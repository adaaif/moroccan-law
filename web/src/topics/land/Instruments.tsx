import { Link } from 'react-router-dom';
import { pick, refPath, useKitT, type Door } from '../kit/api';
import { useLandT } from './strings';

/** The land's instruments on its page (the land review, M11–M13): the clock (a limit as one bar, the days gone in
 *  ink and what is left in the topic's colour), the permit's road (a dashed lane and its stops, the lapse in red), the
 *  ownership certificate (a sheet under its double rule, two lines ticked and one in red). Each opens its tool. A phone
 *  lays them in a row; a desk stacks them in its side column with a line each. */
export default function Instruments({ slug, tools, side }: { slug: string; tools: Door[]; side: boolean }) {
  const { i18n } = useKitT();
  const { t } = useLandT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const drawings: Record<string, React.ReactNode> = { clock: <ClockMini />, permit: <RoadMini />, before: <CertMini /> };
  return (
    <ul className={`m-0 grid list-none gap-2 p-0 ${side ? '' : 'grid-cols-3'}`}>
      {tools.map((d) => (
        <li key={d.key}>
          <Link to={refPath(slug, d.to ?? `tools/${d.key}`)}
                className={`flex h-full rounded-card bg-sheet text-ink no-underline hover:text-stamp ${side ? 'items-center gap-3 px-3 py-3' : 'flex-col gap-2 px-2.5 pb-3 pt-2.5'}`}>
            <span className={side ? 'w-24 shrink-0' : 'w-full'}>{drawings[d.key]}</span>
            <span className="flex min-w-0 flex-col gap-0.5">
              <span lang={lang} className="text-meta font-semibold leading-snug sm:text-body">{pick(d.title, lang)}</span>
              <span lang={lang} className="text-meta leading-snug text-ink-soft">{side && d.lead ? pick(d.lead, lang) : t(`instrument.${d.key}`)}</span>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** A limit on one bar: the days gone, today's tick, what is left in the topic's colour. */
function ClockMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full rtl:-scale-x-100">
      <rect x="6" y="22" width="108" height="12" rx="5" className="fill-rule" />
      <rect x="6" y="22" width="78" height="12" rx="5" className="fill-ink" />
      <rect x="84" y="22" width="30" height="12" rx="5" className="fill-[var(--t)]" />
      <path d="M84 14v28" strokeWidth="2.2" className="stroke-ink" />
    </svg>
  );
}

/** The permit's road: a dashed lane, three stops, the lapse in red at its end. */
function RoadMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full rtl:-scale-x-100">
      <path d="M10 28h100" strokeWidth="3" strokeDasharray="7 5" className="stroke-[var(--t)]" />
      <circle cx="16" cy="28" r="6" strokeWidth="2.5" className="fill-[var(--t)] stroke-[var(--t)]" />
      <circle cx="46" cy="28" r="6" strokeWidth="2.5" className="fill-[var(--t)] stroke-[var(--t)]" />
      <circle cx="76" cy="28" r="6" strokeWidth="2.5" className="fill-sheet stroke-[var(--t)]" />
      <circle cx="104" cy="28" r="6" style={{ fill: 'var(--color-sign-red)' }} />
    </svg>
  );
}

/** The ownership certificate: a sheet, its double rule, two lines ticked and one left in red. */
function CertMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <rect x="30" y="3" width="60" height="50" rx="2" fill="#fff" strokeWidth="1.5" className="stroke-field" />
      <path d="M30 6h60M30 9h60" strokeWidth="1.5" className="stroke-[var(--t)]" />
      {[18, 29, 40].map((y) => <path key={y} d={`M50 ${y}h32`} strokeWidth="2.4" strokeLinecap="round" stroke="#C9C5BC" />)}
      <circle cx="40" cy="18" r="4" fill="#0F7B5F" /><circle cx="40" cy="29" r="4" fill="#0F7B5F" />
      <circle cx="40" cy="40" r="4" style={{ fill: 'var(--color-sign-red)' }} />
    </svg>
  );
}
