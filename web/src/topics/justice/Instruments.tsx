import { Link } from 'react-router-dom';
import { pick, refPath, useKitT, type Door } from '../kit/api';
import { useJusticeT } from './strings';

/** Justice's instruments on its page (the justice review): the registry's date stamp over a requête (the last day to
 *  file), a clock with its 48 hours (the custody), the three tiers of courts with the way up lit (where to go). Each
 *  opens its tool. A phone lays them in a row; a desk stacks them in its side column with a line each. */
export default function Instruments({ slug, tools, side }: { slug: string; tools: Door[]; side: boolean }) {
  const { i18n } = useKitT();
  const { t } = useJusticeT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const drawings: Record<string, React.ReactNode> = { deadline: <StampMini />, custody: <ClockMini />, court: <TiersMini /> };
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

/** A requête's ruled lines and the registry's stamp pressed askew on it, a date's digits as bars. Never mirrored. */
function StampMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <rect x="22" y="3" width="76" height="50" rx="3" strokeWidth="1.4" className="fill-sheet stroke-field" />
      <path d="M30 12h58M30 19h46M30 26h54M30 33h38" strokeWidth="2.4" strokeLinecap="round" className="stroke-rule" />
      <g transform="rotate(-6 70 38)" style={{ stroke: 'var(--t)' }} fill="none">
        <rect x="48" y="26" width="44" height="24" rx="5" strokeWidth="2.4" />
        <rect x="51" y="29" width="38" height="18" rx="3" strokeWidth="0.9" />
        <path d="M57 38h7M68 38h4M76 38h8" strokeWidth="3" strokeLinecap="round" />
      </g>
    </svg>
  );
}

/** A clock face whose first two turns (48 hours) are drawn full in the topic's colour and the third (the 24 more) dashed. */
function ClockMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <circle cx="60" cy="28" r="23" strokeWidth="2" className="fill-sheet stroke-field" />
      <circle cx="60" cy="28" r="18" fill="none" strokeWidth="5" style={{ stroke: 'color-mix(in srgb, var(--t) 45%, transparent)' }} strokeDasharray="3 3" />
      <circle cx="60" cy="28" r="18" fill="none" strokeWidth="5" style={{ stroke: 'var(--t)' }} strokeDasharray="75.4 113.1" transform="rotate(-90 60 28)" />
      <path d="M60 28V16M60 28l7 5" strokeWidth="2.4" strokeLinecap="round" className="stroke-ink" />
    </svg>
  );
}

/** Three tiers of courts, the lowest lit, the way up drawn. */
function TiersMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <rect x="38" y="3" width="44" height="12" rx="3" strokeWidth="1.4" fill="none" className="stroke-field" strokeDasharray="3 2" />
      <rect x="32" y="22" width="56" height="12" rx="3" strokeWidth="1.4" className="fill-sheet stroke-field" />
      <rect x="26" y="41" width="68" height="12" rx="3" style={{ fill: 'color-mix(in srgb, var(--t) 22%, var(--color-sheet))', stroke: 'var(--t)' }} strokeWidth="1.6" />
      <path d="M60 41v-7M60 22v-7" strokeWidth="2" strokeLinecap="round" style={{ stroke: 'var(--t)' }} />
    </svg>
  );
}
