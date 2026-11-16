import { Link } from 'react-router-dom';
import { todayIso } from '@/shared/services/today';
import { pick, refPath, type Door } from '../kit/api';
import { useProfile } from '../kit/profile';
import { fine, OFFENCES } from './rules/fines';
import { useFines } from './rules/rates';
import { START } from './rules/points';
import { useRoadT } from './strings';

/** The road's instruments on its page (A8 of the road-signposted review): the fine as today's staircase for a class-two
 *  notice, the speed as its dial, the licence as its dots (full, or 20 when the reader said their licence is new: a
 *  simulation never shows anyone's real balance). Each opens its tool. A phone lays them in a row; a desk stacks them in
 *  its side column with a line each. */
export default function Instruments({ slug, tools, side }: { slug: string; tools: Door[]; side: boolean }) {
  const { t, i18n } = useRoadT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const nf = new Intl.NumberFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA');
  const today = todayIso();
  const rates = useFines(slug, today);
  const [mine] = useProfile(slug);
  const steps = fine(OFFENCES.find((o) => o.key === 'speed20') ?? OFFENCES[0], 'radar', today, rates.values).steps;
  const max = START[mine === 'probation' ? 'probation' : 'full'];
  const lines: Record<string, string> = {
    fine: t('instruments.fine', { amount: t('dh', { amount: nf.format(steps[0].amount) }) }),
    speed: t('instruments.speed'),
    points: t('instruments.points', { count: max }),
  };
  const drawings: Record<string, React.ReactNode> = {
    fine: <StairMini amounts={steps.map((s) => s.amount)} format={(n) => nf.format(n)} />,
    speed: <DialMini />,
    points: <DotsMini max={max} />,
  };
  return (
    <ul className={`m-0 grid list-none gap-2 p-0 ${side ? '' : 'grid-cols-3'}`}>
      {tools.map((d) => (
        <li key={d.key}>
          <Link to={refPath(slug, d.to ?? `tools/${d.key}`)}
                className={`flex h-full rounded-card bg-sheet text-ink no-underline hover:text-stamp ${side ? 'items-center gap-3 px-3 py-3' : 'flex-col gap-2 px-2.5 pb-3 pt-2.5'}`}>
            <span className={side ? 'w-24 shrink-0' : 'w-full'}>{drawings[d.key]}</span>
            <span className="flex min-w-0 flex-col gap-0.5">
              <span lang={lang} className="text-meta font-semibold leading-snug sm:text-body">{pick(d.title, lang)}</span>
              {side ? <span lang={lang} className="text-meta leading-snug text-ink-soft">{lines[d.key]}</span> : null}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Three steps rising, the first lit: the price today, then in 15 days, then in 30. They run left to right on every
 *  page, as the tool's staircase does (the chart rule of 1 Nov 2026, HM34). Its figures at the site's 14 px floor
 *  (UX15 of the phone-test review: they were 11). */
function StairMini({ amounts, format }: { amounts: number[]; format: (n: number) => string }) {
  const top = Math.max(...amounts);
  return (
    <svg viewBox="0 0 110 56" aria-hidden="true" className="block h-14 w-full">
      {amounts.map((a, i) => {
        const h = 18 + (34 * a) / top;
        const x = 4 + i * 35;
        return (
          <g key={i}>
            <rect x={x} y={56 - h} width="31" height={h} rx="3" className={i === 0 ? 'fill-[var(--t)]' : 'fill-rule'} />
            <text x={x + 15.5} y={56 - h + 15} textAnchor="middle" fontSize="14" fontWeight="700" className={i === 0 ? 'fill-on-stamp' : 'fill-ink'}>
              {format(a)}
            </text>
          </g>
        );
      })}
    </svg>
  );
}

/** A speedometer's arc, the limit's band in green, the needle past it: a dial is a dial and never mirrors. */
function DialMini() {
  const arc = (from: number, to: number) => {
    const p = (v: number) => [55 - 40 * Math.cos(Math.PI * v), 52 - 40 * Math.sin(Math.PI * v)];
    const [x1, y1] = p(from), [x2, y2] = p(to);
    return `M${x1.toFixed(1)} ${y1.toFixed(1)}A40 40 0 0 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`;
  };
  return (
    <svg viewBox="0 0 110 56" aria-hidden="true" className="block h-14 w-full" style={{ direction: 'ltr' }}>
      <path d={arc(0, 1)} fill="none" strokeWidth="8" className="stroke-rule" />
      <path d={arc(0, 0.42)} fill="none" strokeWidth="8" className="stroke-in-force" />
      <path d={arc(0.55, 0.75)} fill="none" strokeWidth="8" className="stroke-[var(--t)]" />
      <line x1="55" y1="52" x2="70" y2="18" strokeWidth="3" strokeLinecap="round" className="stroke-ink" />
      <circle cx="55" cy="52" r="4" className="fill-ink" />
    </svg>
  );
}

/** The licence's points, ten to a row. */
function DotsMini({ max }: { max: number }) {
  return (
    <svg viewBox="0 0 110 56" aria-hidden="true" className="block h-14 w-full">
      {Array.from({ length: max }, (_, i) => (
        <circle key={i} cx={10 + (i % 10) * 10} cy={12 + Math.floor(i / 10) * 14} r="3.6" className="fill-[var(--t)]" />
      ))}
    </svg>
  );
}
