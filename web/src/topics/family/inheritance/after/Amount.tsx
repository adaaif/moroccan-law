import { useId, useState } from 'react';
import { formatAmount, inMillions, parseAmount, type Unit } from '../money';
import { useT } from '../strings';

const MILLION = /مليون|ملايين|million/i;
const read = (raw: string, unit: Unit): string => {
  const v = parseAmount(raw, unit);
  return v ? v.toString() : '';
};
/** Still being typed: a mark or a space at its end, «800.» on its way to «800.000». */
const typing = (raw: string) => /[.,٫\s]$/.test(raw);

/** An amount typed the ways it is written here (IR5 of the inheritance review): «800000», «800.000», «800 000»,
 *  «1.200.000», «80 مليون», Arabic digits, or millions of centimes by the switch. What the reader types stays in the
 *  field while they type; under it the amount is said back at once, «800.000 درهم · 80 مليون سنتيم», so a slip is seen
 *  before the shares are, and what is not an amount is said in one line. Stored as centimes in digits, '' when empty;
 *  a change from elsewhere (a link opened, the case restarted) shows the stored amount formatted. */
export default function Amount({ label, line, value, onChange, units = false, quiet = false, placeholder }: {
  label: string;
  /** What the amount is, in one line under its label. */
  line?: string;
  value: string;
  onChange: (centimes: string) => void;
  /** The switch «درهم / مليون سنتيم». */
  units?: boolean;
  /** The label is heard, not shown: a section's heading already asks the question. */
  quiet?: boolean;
  placeholder?: string;
}) {
  const { t, i18n } = useT();
  const lang = i18n.language;
  const id = useId();
  const shown = (v: string) => (v ? formatAmount(BigInt(v), lang) : '');
  const [raw, setRaw] = useState(() => shown(value));
  const [unit, setUnit] = useState<Unit>('dh');
  const [prev, setPrev] = useState(value);
  if (value !== prev) {
    setPrev(value);
    if (read(raw, unit) !== value) { setRaw(shown(value)); setUnit('dh'); }
  }
  const type = (next: string, u: Unit = unit) => {
    setRaw(next);
    if (!typing(next)) onChange(read(next, u));
  };
  const active: Unit = MILLION.test(raw) ? 'million' : unit;
  const bad = raw.trim() !== '' && !typing(raw) && parseAmount(raw, unit) === null;
  const v = value ? BigInt(value) : null;
  const millions = v === null ? null : inMillions(v);
  const said = bad ? t('after.amount.bad')
    : v === null ? '' : [t('after.dh', { amount: formatAmount(v, lang) }), millions ? t('after.millions', { n: millions }) : ''].filter(Boolean).join(' · ');
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className={quiet ? 'sr-only' : 'text-body font-semibold'}>{label}</label>
      {line ? <p id={`${id}-line`} className="m-0 text-meta text-ink-soft">{line}</p> : null}
      <div className="flex flex-wrap items-center gap-2">
        <input id={id} inputMode="decimal" dir="auto" autoComplete="off" value={raw} placeholder={placeholder}
               onChange={(e) => type(e.target.value)} aria-invalid={bad || undefined}
               aria-describedby={[line ? `${id}-line` : '', `${id}-said`].filter(Boolean).join(' ')}
               style={{ flexBasis: '8rem' }}
               className="h-12 min-w-0 flex-1 rounded-control border border-field bg-sheet px-3 text-body tabular-nums" />
        {units ? (
          <span role="radiogroup" aria-label={t('after.amount.unit')} className="flex gap-1.5">
            {(['dh', 'million'] as const).map((u) => (
              <button key={u} type="button" role="radio" aria-checked={active === u}
                      onClick={() => { setUnit(u); type(raw.replace(MILLION, '').trim(), u); }}
                      className={`min-h-11 rounded-full border px-3 text-body ${active === u ? 'border-ink bg-ink font-semibold text-sheet' : 'border-field bg-sheet text-ink'}`}>
                {t(`after.amount.${u}`)}
              </button>
            ))}
          </span>
        ) : null}
      </div>
      <p id={`${id}-said`} aria-live="polite" className={`m-0 text-meta tabular-nums ${bad ? 'text-amended' : 'text-ink-soft'}`}>{said}</p>
    </div>
  );
}
