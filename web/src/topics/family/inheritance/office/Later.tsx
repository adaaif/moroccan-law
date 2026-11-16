import { Button } from '@/shared/components/ui';
import Stepper from '../../../kit/tool/Stepper';
import type { Area } from '../area';
import { EMPTY, most, sexOf, type Case, type Later as LaterCase } from '../case';
import { HEIRS, type Heir } from '../engine';
import { asked } from '../flow';
import { kin } from '../parts/say';
import { DeceasedContext, useT } from '../strings';

/** An heir who died after the deceased and before the division (IR26 of the inheritance review, IR7's first
 *  question): the reader picks who, among the kinds who inherit, then gives that person's own family on the day they
 *  died, asked as the calculator asks any family (`flow.asked`). Their part passes to their own heirs; the answer
 *  counts it. Several can be added; the part closes by clearing them. */
export default function Later({ c, set, answer, setOpen }: Area) {
  const { t } = useT();
  const lines = answer.state === 'ok' ? answer.result.lines : [];
  // Who can still be said to have died since: one entry each, no more than there are of that kind.
  const left = lines.filter((l) => l.count > c.later.filter((x) => x.heir === l.heir).length);
  const put = (i: number, patch: Partial<LaterCase>) => set({ later: c.later.map((x, j) => (j === i ? { ...x, ...patch } : x)) });
  return (
    <section aria-labelledby="later-title" className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
      <div className="flex flex-col gap-1">
        <h2 id="later-title" className="m-0 text-lead font-semibold">{t('office.later.title')}</h2>
        <p className="m-0 text-meta text-ink-soft">{t('office.later.lead')}</p>
      </div>
      {c.later.map((l, i) => (
        // Their family is their own: its names agree with them («خوها»), the heading with who died first.
        <DeceasedContext.Provider key={i} value={sexOf(l.heir)}>
          <Person c={c} person={l} title={t(`office.later.died_${sexOf(l.heir)}`, { who: kin(l.heir, 1, t) })}
                  gone={answer.state === 'ok' && Boolean(answer.later[i]?.gone)}
                  onChange={(patch) => put(i, patch)} onRemove={() => set({ later: c.later.filter((_, j) => j !== i) })} />
        </DeceasedContext.Provider>
      ))}
      {answer.state !== 'ok' ? <p className="m-0 text-body text-ink-soft">{t('office.later.first')}</p>
        : left.length ? (
          <div className="flex flex-col gap-1.5">
            <span className="text-body font-semibold">{t(c.later.length ? 'office.later.more' : 'office.later.pick')}</span>
            <div className="flex flex-wrap gap-2">
              {left.map((l) => (
                <button key={l.heir} type="button" onClick={() => set({ later: [...c.later, { heir: l.heir, counts: {}, branches: [] }] })}
                        className="min-h-11 rounded-full border border-dashed border-field bg-sheet px-4 text-body text-ink hover:border-stamp">
                  {t('office.later.add', { who: kin(l.heir, 1, t) })}
                </button>
              ))}
            </div>
          </div>
        ) : <p className="m-0 text-meta text-ink-soft">{t('office.later.none')}</p>}
      <Button variant="quiet" className="self-start" onClick={() => { set({ later: [] }); setOpen({ later: false }); }}>{t('office.close')}</Button>
    </section>
  );
}

/** One heir who died since, and their own family as counters. The first deceased is not among them: a child of the
 *  deceased is not asked about the parent who died first. */
function Person({ c, person, title, gone, onChange, onRemove }: {
  c: Case; person: LaterCase; title: string; gone: boolean; onChange: (patch: Partial<LaterCase>) => void; onRemove: () => void;
}) {
  const { t } = useT();
  const sex = sexOf(person.heir);
  const first: Heir | null = person.heir === 'son' || person.heir === 'daughter' ? (c.deceased === 'm' ? 'father' : 'mother') : null;
  const ask = asked({ ...EMPTY, deceased: sex, counts: person.counts });
  const kinds = HEIRS.filter((h) => h !== first && (ask.has(h) || (person.counts[h] ?? 0) > 0));
  return (
    <div className="flex flex-col gap-1 rounded-control bg-paper px-4 py-3">
      <div className="flex items-center justify-between gap-3">
        <h3 className="m-0 text-body font-semibold">{title}</h3>
        <Button variant="quiet" onClick={onRemove}>{t('office.remove')}</Button>
      </div>
      <p className="m-0 text-meta text-ink-soft">{t(`office.later.family_${sex}`)}. {t(`office.later.hint_${sex}`)}</p>
      {gone ? <p className="m-0 text-meta text-amended">{t('office.later.gone')}</p> : null}
      <div className="flex flex-col">
        {kinds.map((h) => (
          <Stepper key={h} label={kin(h, most(h) > 1 ? 2 : 1, t)} value={person.counts[h] ?? 0} max={most(h)}
                   onChange={(v) => onChange({ counts: { ...person.counts, [h]: v } })} />
        ))}
      </div>
    </div>
  );
}
