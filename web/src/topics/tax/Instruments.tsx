import { Link } from 'react-router-dom';
import { pick, refPath, useKitT, type Door } from '../kit/api';
import { useTaxT } from './strings';

/** The tax's instruments on its page (the tax review): the scale's staircase (the salary), a house with its
 *  three quarters off (the communes' taxes), the vignette's horsepower dial. Each opens its tool. A phone lays them in a
 *  row; a desk stacks them in its side column with a line each. */
export default function Instruments({ slug, tools, side }: { slug: string; tools: Door[]; side: boolean }) {
  const { i18n } = useKitT();
  const { t } = useTaxT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const drawings: Record<string, React.ReactNode> = { salary: <StairsMini />, local: <HouseMini />, car: <DialMini /> };
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

/** The scale: six steps rising, the first flat (exempt), filled to a mark. */
function StairsMini() {
  const steps = [0, 10, 20, 30, 34, 37];
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      {steps.map((r, i) => {
        const h = 4 + r * 1.2;
        return <rect key={i} x={4 + i * 19} y={52 - h} width="18" height={h} className={i < 4 ? 'fill-[var(--t)]' : 'fill-rule'} />;
      })}
      <path d="M80 6v48" strokeWidth="2" strokeDasharray="3 3" className="stroke-ink" />
    </svg>
  );
}

/** A house, three quarters of its front shaded: the 75% off a main home. */
function HouseMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <path d="M36 26 60 8l24 18v26H36z" strokeWidth="2" strokeLinejoin="round" className="fill-sheet stroke-ink" />
      <path d="M36 26 60 8l24 18v26H36z" className="fill-[var(--t)]" style={{ clipPath: 'inset(0 0 0 25%)' }} />
      <rect x="54" y="36" width="12" height="16" className="fill-sheet" />
    </svg>
  );
}

/** The vignette's dial: horsepower bands as arcs, the needle on the first. */
function DialMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <path d="M24 50a36 36 0 0 1 72 0" fill="none" strokeWidth="8" className="stroke-rule" />
      <path d="M24 50a36 36 0 0 1 14-28" fill="none" strokeWidth="8" className="stroke-[var(--t)]" />
      <path d="M60 50 38 26" strokeWidth="3" strokeLinecap="round" className="stroke-ink" />
      <circle cx="60" cy="50" r="4" className="fill-ink" />
    </svg>
  );
}
