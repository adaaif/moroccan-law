import { useState } from 'react';
import { RoadIcon } from '../kit/icons';
import { GROUPS, type Offence } from './rules/fines';
import { useRoadT } from './strings';
import { fold } from './fold';

/** The offences as tiles by group, with a search over the words people use (F2 of the road tools review). Picking
 *  one closes the others to a single row with «بدّل», so the answer above stays in view. */
export function OffenceTiles<T extends Pick<Offence, 'key' | 'group' | 'icon'>>({ offences, value, onChange, label, cost }: {
  offences: T[];
  value: string;
  onChange: (key: string) => void;
  label: string;
  /** A short line under each tile: its class, its points. */
  cost?: (o: T) => string;
}) {
  const { t } = useRoadT();
  const [open, setOpen] = useState(!value);
  const [q, setQ] = useState('');
  const picked = offences.find((o) => o.key === value);
  const words = (o: T) => fold(`${t(`offences.${o.key}`)} ${t(`offenceWords.${o.key}`, { defaultValue: '' })}`);
  const found = q.trim() ? offences.filter((o) => fold(q).split(/\s+/).every((w) => words(o).includes(w))) : offences;
  if (picked && !open) {
    return (
      <div className="flex flex-col gap-1.5">
        <span className="text-body font-semibold">{label}</span>
        <div className="flex min-h-16 items-center gap-3 rounded-card bg-paper px-4 py-2">
          <span className="text-[color:var(--t)]"><RoadIcon name={picked.icon} size={28} /></span>
          <span className="flex min-w-0 flex-1 flex-col">
            <span className="text-body font-semibold leading-snug">{t(`offences.${picked.key}`)}</span>
            {cost ? <span className="text-meta text-ink-soft">{cost(picked)}</span> : null}
          </span>
          <button type="button" onClick={() => setOpen(true)} className="min-h-11 shrink-0 rounded-full border border-field bg-sheet px-4 text-body">{t('tiles.change')}</button>
        </div>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      <span className="text-body font-semibold">{label}</span>
      <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder={t('tiles.search')} aria-label={t('tiles.search')} dir="auto"
             className="h-12 w-full rounded-control border border-field bg-sheet px-3 text-body" />
      {GROUPS.map((g) => {
        const here = found.filter((o) => o.group === g);
        if (!here.length) return null;
        return (
          <div key={g} className="flex flex-col gap-1.5">
            <span className="text-meta font-semibold text-ink-soft">{t(`groups.${g}`)}</span>
            <ul className="m-0 grid list-none grid-cols-2 gap-2 p-0 sm:grid-cols-3">
              {here.map((o, i) => (
                <li key={o.key} className="motion-safe:animate-[rise_220ms_ease-out_both]" style={{ animationDelay: `${i * 25}ms` }}>
                  <button type="button" aria-pressed={o.key === value} onClick={() => { onChange(o.key); setOpen(false); setQ(''); }}
                          className={`flex h-full min-h-24 w-full flex-col items-start justify-between gap-2 rounded-card border px-3 py-2.5 text-start transition-[border-color,background-color,transform] duration-150 active:scale-[.97] motion-reduce:transition-none ${
                            o.key === value ? 'border-2 border-[var(--t)] bg-wash' : 'border-rule bg-sheet hover:border-field'}`}>
                    <span className="text-[color:var(--t)]"><RoadIcon name={o.icon} /></span>
                    <span className="text-body font-medium leading-snug">{t(`offences.${o.key}`)}</span>
                    {cost ? <span className="text-meta text-ink-soft">{cost(o)}</span> : null}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        );
      })}
      {!found.length ? <p className="m-0 text-body text-ink-soft">{t('tiles.none')}</p> : null}
    </div>
  );
}
