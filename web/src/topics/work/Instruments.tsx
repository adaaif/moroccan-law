import { Link } from 'react-router-dom';
import { pick, refPath, useKitT, type Door } from '../kit/api';
import { readDays } from './keep';
import { useWorkT } from './strings';

/** The work's instruments on its page (E6 of the work-counted review): what is owed as art. 53's staircase of years, the pay as
 *  the payslip the law writes, the CNSS days as one track with the reader's days on it once the days tool has them.
 *  Each opens its tool. A phone lays them in a row; a desk stacks them in its side column with a line each. */
export default function Instruments({ slug, tools, side }: { slug: string; tools: Door[]; side: boolean }) {
  const { i18n } = useKitT();
  const { t } = useWorkT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const days = readDays();
  const titles: Record<string, string | null> = {
    cnss: days === null ? null : t('instrument.days', { days }),
  };
  const drawings: Record<string, React.ReactNode> = {
    end: <StairsMini />,
    pay: <SlipMini />,
    cnss: <DaysMini days={days} />,
  };
  return (
    <ul className={`m-0 grid list-none gap-2 p-0 ${side ? '' : 'grid-cols-3'}`}>
      {tools.map((d) => (
        <li key={d.key}>
          <Link to={refPath(slug, d.to ?? `tools/${d.key}`)}
                className={`flex h-full rounded-card bg-sheet text-ink no-underline hover:text-stamp ${side ? 'items-center gap-3 px-3 py-3' : 'flex-col gap-2 px-2.5 pb-3 pt-2.5'}`}>
            <span className={side ? 'w-24 shrink-0' : 'w-full'}>{drawings[d.key]}</span>
            <span className="flex min-w-0 flex-col gap-0.5">
              <span lang={lang} className="text-meta font-semibold leading-snug sm:text-body">{titles[d.key] ?? pick(d.title, lang)}</span>
              {side && d.lead ? <span lang={lang} className="text-meta leading-snug text-ink-soft">{pick(d.lead, lang)}</span> : null}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Seven years of service as art. 53's steps: five of 96 hours, two of 144; the next band waits dashed. */
function StairsMini() {
  const steps = [96, 96, 96, 96, 96, 144, 144];
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      {steps.map((h, i) => <rect key={i} x={6 + i * 14.5} y={54 - h / 5} width="13" height={h / 5} rx="2" className="fill-[var(--t)]" />)}
      <rect x={6 + 7 * 14.5} y={54 - 144 / 5} width="12" height={144 / 5} rx="2" strokeWidth="1.4" strokeDasharray="3 2" fill="none" className="stroke-field" />
      <path d="M3 54.5h114" strokeWidth="1.4" className="stroke-ink" />
    </svg>
  );
}

/** A payslip: its lines and amounts, the gross ruled under them, the net in the topic's colour. */
function SlipMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full rtl:-scale-x-100">
      <rect x="22" y="2" width="76" height="52" rx="3" strokeWidth="1.5" className="fill-sheet stroke-rule" />
      {[12, 20, 28].map((y) => <g key={y}><path d={`M30 ${y}h${y === 20 ? 28 : 34}`} strokeWidth="2.4" strokeLinecap="round" className="stroke-field opacity-60" /><path d={`M80 ${y}h10`} strokeWidth="2.4" strokeLinecap="round" className="stroke-field opacity-60" /></g>)}
      <path d="M28 36h64" strokeWidth="1.6" className="stroke-ink" />
      <path d="M30 45h24" strokeWidth="3" strokeLinecap="round" className="stroke-ink" />
      <path d="M72 45h18" strokeWidth="3.4" strokeLinecap="round" className="stroke-[var(--t)]" />
    </svg>
  );
}

/** The days from 0 to the 70 % ceiling (7,560), the thresholds 1,320 and 3,240 marked, the reader's days filled once
 *  known (else a plain track). */
function DaysMini({ days }: { days: number | null }) {
  const x = (d: number) => 4 + (112 * Math.min(d, 7560)) / 7560;
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <rect x="4" y="22" width="112" height="10" rx="4" className="fill-rule" />
      {days !== null ? <rect x="4" y="22" width={Math.max(4, x(days) - 4)} height="10" rx="4" className="fill-[var(--t)]" /> : <rect x="4" y="22" width={x(1320) - 4} height="10" rx="4" opacity=".3" className="fill-[var(--t)]" />}
      {[1320, 3240].map((d) => <path key={d} d={`M${x(d)} 16v22`} strokeWidth="2" className="stroke-ink" />)}
      {days !== null ? <circle cx={x(days)} cy="27" r="5.5" className="fill-ink" /> : null}
    </svg>
  );
}
