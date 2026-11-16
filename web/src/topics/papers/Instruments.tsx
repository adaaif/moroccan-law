import { Link } from 'react-router-dom';
import { pick, refPath, useKitT, type Door } from '../kit/api';
import { usePapersT } from './strings';

/** The papers' instruments on their page (the papers review): the card with its end date where the card prints it,
 *  thirty days on a line to a birth's or a death's last day, the administration's road with its three stops. Each opens
 *  its tool. A phone lays them in a row; a desk stacks them in its side column with a line each. */
export default function Instruments({ slug, tools, side }: { slug: string; tools: Door[]; side: boolean }) {
  const { i18n } = useKitT();
  const { t } = usePapersT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const drawings: Record<string, React.ReactNode> = { card: <CardMini />, clock: <ClockMini />, counter: <RoadMini /> };
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

/** The card: its photo, two lines, and its end marked in the topic's colour; the chevrons at its foot. Never mirrored. */
function CardMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <rect x="22" y="3" width="76" height="50" rx="6" strokeWidth="1.5" className="fill-sheet" style={{ stroke: 'var(--t)' }} />
      <rect x="28" y="10" width="15" height="20" rx="1.5" style={{ fill: 'color-mix(in srgb, var(--t) 22%, transparent)' }} />
      <path d="M49 13h30M49 19h22" strokeWidth="3" strokeLinecap="round" className="stroke-rule" />
      <path d="M49 27h40" strokeWidth="4" strokeLinecap="round" style={{ stroke: 'var(--t)' }} />
      {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => <path key={i} d={`M${32 + i * 6} 42l-2.4 2 2.4 2`} fill="none" strokeWidth="1" style={{ stroke: 'var(--color-ink-soft)' }} />)}
    </svg>
  );
}

/** Thirty days on a line: the day it happened in ink, the last day in the topic's colour. */
function ClockMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full rtl:-scale-x-100">
      <path d="M8 30h104" strokeWidth="3" strokeLinecap="round" className="stroke-rule" />
      <path d="M8 30h40" strokeWidth="3" strokeLinecap="round" className="stroke-ink" />
      <circle cx="8" cy="30" r="5" className="fill-ink" />
      <circle cx="112" cy="30" r="6" className="fill-[var(--t)]" />
      {[30, 52, 74, 96].map((x) => <path key={x} d={`M${x} 25v10`} strokeWidth="1.4" className="stroke-field" />)}
    </svg>
  );
}

/** The administration's road: a dashed lane, three stops, the next ringed. */
function RoadMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full rtl:-scale-x-100">
      <path d="M10 28h100" strokeWidth="3" strokeDasharray="7 5" style={{ stroke: 'var(--t)' }} />
      <circle cx="12" cy="28" r="5.5" className="fill-[var(--t)]" />
      <circle cx="60" cy="28" r="6" strokeWidth="3" className="fill-sheet" style={{ stroke: 'var(--t)' }} />
      <circle cx="60" cy="28" r="10" strokeWidth="1.5" fill="none" style={{ stroke: 'color-mix(in srgb, var(--t) 35%, transparent)' }} />
      <circle cx="106" cy="28" r="5.5" strokeWidth="3" className="fill-sheet" style={{ stroke: 'var(--color-sign-red)' }} />
    </svg>
  );
}
