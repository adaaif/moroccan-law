import { Link } from 'react-router-dom';
import { pick, refPath, useKitT, type Door } from '../kit/api';
import { daysUntil } from '../kit/tool/days';
import { readPurchases } from './purchases';
import { nextLast, receipt } from './rules/receipt';
import { useConsumerT } from './strings';
import { todayIso } from '@/shared/services/today';

/** The consumer's instruments on its page (the consumer-receipt review): the receipt of a purchase's rights (once the
 *  reader kept a purchase, its soonest day as the title), the seven days of a withdrawal, the guarantee's year. Each
 *  opens its tool. A phone lays them in a row; a desk stacks them in its side column with a line each. */
export default function Instruments({ slug, tools, side }: { slug: string; tools: Door[]; side: boolean }) {
  const { i18n } = useKitT();
  const { t } = useConsumerT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const today = todayIso();
  // The soonest day among the kept purchases, with the line it belongs to.
  const soon = readPurchases().map((k) => ({ k, n: nextLast(receipt(k.purchase), today) }))
    .filter((x) => x.n?.last).sort((a, b) => (a.n!.last! < b.n!.last! ? -1 : 1))[0];
  const titles: Record<string, string | null> = {
    receipt: soon ? t('instrument.next', { days: t('return.left', { count: daysUntil(soon.n!.last!) }), what: soon.k.item || t(`receipt.lines.${soon.n!.key}.title`) }) : null,
  };
  const drawings: Record<string, React.ReactNode> = { receipt: <ReceiptMini />, return: <DaysMini />, guarantee: <YearMini /> };
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

/** A till receipt, torn top and foot, its lines and its total in the topic's colour. */
function ReceiptMini() {
  // The outline as one polygon: the top's teeth left to right, the bottom's right to left.
  const top = Array.from({ length: 14 }, (_, i) => `${34 + i * 4},${i % 2 ? 1 : 4}`);
  const bottom = Array.from({ length: 14 }, (_, i) => `${86 - i * 4},${i % 2 ? 55 : 52}`);
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <polygon points={[...top, '86,4', ...bottom, '34,52'].join(' ')} strokeWidth="1.2" strokeLinejoin="round" className="fill-sheet stroke-field" />
      {[12, 19, 26].map((y) => <g key={y}><path d={`M40 ${y}h22`} strokeWidth="2.2" strokeLinecap="round" className="stroke-field opacity-60" /><path d={`M70 ${y}h10`} strokeWidth="2.2" strokeLinecap="round" className="stroke-field opacity-60" /></g>)}
      <path d="M38 33h44" strokeWidth="1.2" strokeDasharray="2 2" className="stroke-ink" />
      <path d="M40 41h16" strokeWidth="2.6" strokeLinecap="round" className="stroke-ink" />
      <path d="M68 41h12" strokeWidth="3" strokeLinecap="round" className="stroke-[var(--t)]" />
    </svg>
  );
}

/** Seven days, the first counted, the last in the topic's colour: a withdrawal's window. */
function DaysMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full rtl:-scale-x-100">
      {Array.from({ length: 7 }, (_, i) => (
        <rect key={i} x={6 + i * 16} y="18" width="13" height="20" rx="3"
              className={i === 6 ? 'fill-[var(--t)]' : i === 0 ? 'fill-ink' : 'fill-rule'} />
      ))}
    </svg>
  );
}

/** A year from delivery: twelve months on one bar, the months gone filled. */
function YearMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full rtl:-scale-x-100">
      <rect x="6" y="22" width="108" height="12" rx="4" className="fill-rule" />
      <rect x="6" y="22" width="40" height="12" rx="4" className="fill-[var(--t)]" />
      {Array.from({ length: 11 }, (_, i) => <path key={i} d={`M${15 + i * 9} 22v12`} strokeWidth="1" className="stroke-sheet" />)}
      <path d="M46 14v28" strokeWidth="2.2" className="stroke-ink" />
    </svg>
  );
}
