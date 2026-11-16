import { Link } from 'react-router-dom';
import { pick, refPath, useKitT, type Door } from '../kit/api';
import { readAge, readDue } from '../kit/progress';
import { daysUntil } from '../kit/tool/days';

/** The journeys whose day the reader may have given, the soonest limit first on the dates instrument. */
const DATED = ['journeys/birth', 'journeys/heirs', 'journeys/divorce-agreement', 'journeys/talaq', 'journeys/shiqaq', 'journeys/kafala'];

/** The family's instruments on its page (G4 of the family-papers review): the inheritance as a small family over
 *  one split bar, a child's years as their bars with the age the reader last chose, the next limit as a strip of days
 *  once a journey has the reader's day. Each opens its tool or page. A phone lays them in a row; a desk stacks them in
 *  its side column with a line each. */
export default function Instruments({ slug, tools, side }: { slug: string; tools: Door[]; side: boolean }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const age = readAge(slug);
  const dues = DATED.map((ref) => readDue(slug, ref)).filter((d): d is NonNullable<typeof d> => d !== null)
    .map((d) => ({ ...d, left: daysUntil(d.last) })).filter((d) => d.left >= 0).sort((a, b) => a.left - b.left);
  const due = dues[0];
  const titles: Record<string, string | null> = {
    years: age === null ? null : t('instrument.age', { years: t('line.years', { count: age }) }),
    dates: due ? t('journey.left', { days: t('days', { count: due.left }) }) : null,
  };
  const drawings: Record<string, React.ReactNode> = {
    inheritance: <TreeMini />,
    years: <YearsMini age={age ?? 9} />,
    dates: <DaysMini left={due?.left ?? null} />,
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

/** The deceased in ink, three heirs under, and the estate as one bar split among them. */
function TreeMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <path d="M60 14v8M30 22h60M30 22v6M90 22v6M60 22v6" strokeWidth="2" fill="none" className="stroke-field" />
      <rect x="48" y="2" width="24" height="12" rx="4" className="fill-ink" />
      {[18, 48, 78].map((x) => <rect key={x} x={x} y="28" width="24" height="11" rx="4" strokeWidth="2" className="fill-sheet stroke-[var(--t)]" />)}
      <rect x="6" y="45" width="40" height="9" rx="2" className="fill-[var(--t)]" />
      <rect x="47" y="45" width="20" height="9" className="fill-[var(--t)] opacity-70" />
      <rect x="68" y="45" width="20" height="9" className="fill-[var(--t)] opacity-70" />
      <rect x="89" y="45" width="15" height="9" className="fill-[var(--t)] opacity-45" />
      <rect x="105" y="45" width="9" height="9" rx="2" className="fill-[var(--t)] opacity-25" />
    </svg>
  );
}

/** Three of a child's spans (the custody to 18, the choice from 15, the pension to 25 for a student) and the age across
 *  them, in the reading direction like the page's picture. */
function YearsMini({ age }: { age: number }) {
  const x = (n: number) => 4 + (112 * n) / 25;
  const spans = [[0, 18], [15, 18], [0, 25]] as const;
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full rtl:-scale-x-100">
      {spans.map(([from, to], i) => (
        <g key={i}>
          <rect x="4" y={8 + i * 12} width="112" height="7" rx="3" className="fill-rule" />
          <rect x={x(from)} y={8 + i * 12} width={x(to) - x(from)} height="7" rx="3"
                className={age >= from && age < to ? 'fill-[var(--t)]' : 'fill-field'} />
        </g>
      ))}
      <path d={`M${x(age)} 3v42`} strokeWidth="2.4" className="stroke-ink" />
    </svg>
  );
}

/** Thirty days, those gone filled, today in ink, the last in the topic's colour; a plain month before a day is given. */
function DaysMini({ left }: { left: number | null }) {
  const gone = left === null ? 0 : Math.max(0, 30 - 1 - Math.min(left, 29));
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full rtl:-scale-x-100">
      {Array.from({ length: 30 }, (_, i) => {
        const cls = left === null ? 'fill-rule' : i < gone ? 'fill-[var(--t)] opacity-40' : i === gone ? 'fill-ink' : i === 29 ? 'fill-[var(--t)]' : 'fill-rule';
        return <rect key={i} x={2 + (i % 15) * 7.8} y={i < 15 ? 10 : 30} width="6" height="15" rx="2" className={cls} />;
      })}
    </svg>
  );
}
