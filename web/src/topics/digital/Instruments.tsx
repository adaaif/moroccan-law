import { Link } from 'react-router-dom';
import { pick, refPath, useKitT, type Door } from '../kit/api';
import { useDigitalT } from './strings';

/** The digital's instruments on its page (the digital review): a thread where the law answers (the offences), a
 *  thread with the administration's last day (the information request), a letter with its lines (the data request). Each
 *  opens its tool. A phone lays them in a row; a desk stacks them in its side column with a line each. */
export default function Instruments({ slug, tools, side }: { slug: string; tools: Door[]; side: boolean }) {
  const { i18n } = useKitT();
  const { t } = useDigitalT();
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const drawings: Record<string, React.ReactNode> = { offence: <AnswerMini />, info: <ClockThreadMini />, letter: <LetterMini /> };
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

/** Your message, then two answers with an article's chip. Never mirrored. */
function AnswerMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <rect x="52" y="3" width="62" height="14" rx="6" style={{ fill: 'color-mix(in srgb, var(--t) 22%, var(--color-sheet))' }} />
      <rect x="6" y="21" width="74" height="14" rx="6" strokeWidth="1.2" className="fill-sheet stroke-field" />
      <path d="M12 28h44" strokeWidth="2.6" strokeLinecap="round" className="stroke-rule" />
      <rect x="6" y="39" width="58" height="14" rx="6" strokeWidth="1.2" className="fill-sheet stroke-field" />
      <rect x="11" y="43" width="22" height="6" rx="3" style={{ fill: 'var(--t)' }} />
    </svg>
  );
}

/** A request sent and the answer's last day, as a short thread with a clock. Never mirrored. */
function ClockThreadMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <rect x="56" y="5" width="58" height="14" rx="6" style={{ fill: 'color-mix(in srgb, var(--t) 22%, var(--color-sheet))' }} />
      <path d="M104 15l2 2 4-4" fill="none" strokeWidth="1.4" strokeLinecap="round" style={{ stroke: 'var(--t)' }} />
      <rect x="6" y="27" width="64" height="22" rx="7" strokeWidth="1.2" className="fill-sheet stroke-field" />
      <circle cx="20" cy="38" r="7" fill="none" strokeWidth="1.6" style={{ stroke: 'var(--t)' }} />
      <path d="M20 38v-4M20 38l3 2" strokeWidth="1.6" strokeLinecap="round" className="stroke-ink" />
      <path d="M33 35h30M33 41h20" strokeWidth="2.4" strokeLinecap="round" className="stroke-rule" />
    </svg>
  );
}

/** A letter: its heading line in the topic's colour, its lines, a signature. Never mirrored. */
function LetterMini() {
  return (
    <svg viewBox="0 0 120 56" aria-hidden="true" className="block h-14 w-full">
      <rect x="30" y="2" width="60" height="52" rx="3" strokeWidth="1.4" className="fill-sheet stroke-field" />
      <path d="M38 11h30" strokeWidth="3" strokeLinecap="round" style={{ stroke: 'var(--t)' }} />
      <path d="M38 20h44M38 27h40M38 34h44M38 41h28" strokeWidth="2.2" strokeLinecap="round" className="stroke-rule" />
      <path d="M62 49c3-5 5 2 8-1s4 2 7 0" fill="none" strokeWidth="1.4" strokeLinecap="round" className="stroke-ink" />
    </svg>
  );
}
