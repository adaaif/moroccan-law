import { useContext, useState } from 'react';
import { Button, Note } from '@/shared/components/ui';
import { Chips } from '../../../kit/tool/parts';
import type { Area } from '../area';
import type { WillCase } from '../case';
import { formatAmount } from '../money';
import Cites from '../parts/Cites';
import { RulesContext } from '../parts/rules';
import { useT } from '../strings';
import Amount from './Amount';
import type { Ok } from './payees';

const PARTS = ['1/3', '1/4', '1/5', '1/6', '1/8', '1/10'] as const;

/** What was left, and what leaves it first (IR5, IR23 of the inheritance review, 14 Nov 2026): one field for what
 *  was left, read the ways money is written here and said back under it; then, folded until opened or until the family
 *  said there is a will, what article 322 takes out before any share, in its order: the funeral, the debts, a dowry
 *  still owed, the will (a third at most, and for an heir only with the others' agreement). Once there is an amount, a
 *  ladder from what was left to what is shared. Hidden until someone is entered: the family comes first. */
export default function Estate({ c, set, answer, open, setOpen }: Area) {
  const { t, i18n } = useT();
  const old = useContext(RulesContext) === '1958';
  const lang = i18n.language;
  const [unfolded, setUnfolded] = useState(() => Boolean(c.funeral || c.debts || c.dowry || c.will));
  if (answer.state === 'empty') return null;
  const shown = unfolded || open.will;
  const fold = () => {
    setUnfolded(!shown);
    if (shown && open.will) setOpen({ will: false });
  };
  const dh = (x: bigint) => t('after.dh', { amount: formatAmount(x, lang) });
  return (
    <section id="estate" aria-labelledby="estate-title" className="flex flex-col gap-4 rounded-card bg-sheet px-5 py-5 sm:px-7">
      <div className="flex flex-col gap-1">
        <h2 id="estate-title" className="m-0 text-lead font-semibold">{t(`after.estate.title_${c.deceased}`)}</h2>
        <p className="m-0 text-meta text-ink-soft">{t('after.estate.lead')}</p>
      </div>
      <Amount label={t('after.estate.label')} quiet units value={c.estate} onChange={(estate) => set({ estate })} placeholder="800.000" />

      <div className="flex flex-col gap-3 border-t border-rule pt-3">
        <button type="button" aria-expanded={shown} aria-controls="estate-first" onClick={fold}
                className="inline-flex min-h-11 items-center gap-1.5 self-start text-start text-body font-semibold text-stamp">
          {t('after.estate.first')}
          <span aria-hidden="true" className={`transition-transform motion-reduce:transition-none ${shown ? 'rotate-180' : ''}`}>⌄</span>
        </button>
        {shown ? (
          <div id="estate-first" className="flex flex-col gap-4">
            <p className="m-0 text-meta text-ink-soft">{t('after.estate.firstLead')}</p>
            <Amount label={t('after.estate.funeral')} line={t('after.estate.funeralLine')} value={c.funeral} onChange={(funeral) => set({ funeral })} />
            <Amount label={t('after.estate.debts')} line={t('after.estate.debtsLine')} value={c.debts} onChange={(debts) => set({ debts })} />
            {c.deceased === 'm' || c.dowry ? (
              <Amount label={t('after.estate.dowry')} line={t('after.estate.dowryLine')} value={c.dowry} onChange={(dowry) => set({ dowry })} />
            ) : null}
            <Cites today={[322]} />
            <Will {...{ c, set, answer }} />
            {/* Art. 49, on what a couple acquired, is the 2004 code's: not said for an older death. */}
            {old ? null : (
              <Note tone="law" quiet>
                <p className="m-0 text-meta">{t('after.estate.couple')}</p>
                <Cites today={[49]} />
              </Note>
            )}
          </div>
        ) : null}
      </div>

      {answer.state === 'stop' && answer.why === 'overdrawn' && c.estate ? (
        <Note tone="warn" role="status">
          <p className="m-0 text-body">
            {t('after.estate.overdrawn', {
              out: formatAmount([c.funeral, c.debts, c.dowry].reduce((s, x) => s + (x ? BigInt(x) : 0n), 0n), lang),
              gross: formatAmount(BigInt(c.estate), lang),
            })}
          </p>
        </Note>
      ) : null}
      {answer.state === 'ok' ? <Ladder answer={answer} dh={dh} /> : null}
    </section>
  );
}

/** From what was left to what is shared, in article 322's order; the will beside the figure it takes from. */
function Ladder({ answer, dh }: { answer: Ok; dh: (x: bigint) => string }) {
  const { t } = useT();
  const m = answer.money;
  const will = answer.result.will;
  const willPaid = answer.paid?.each.will;
  if (answer.willWaits) return <p className="m-0 text-meta text-ink-soft">{t('after.estate.willWaits')}</p>;
  if (!m || (!m.funeral && !m.debts && !m.dowry && !will)) return null;
  const row = 'flex items-baseline justify-between gap-3 py-2';
  return (
    <div className="flex flex-col gap-1 border-t border-rule pt-3">
      <h3 className="m-0 text-body font-semibold">{t('after.estate.ladder')}</h3>
      <dl className="m-0 flex flex-col tabular-nums">
        <div className={row}><dt>{t('after.estate.gross')}</dt><dd className="m-0">{dh(m.gross)}</dd></div>
        {m.funeral ? <div className={`${row} border-t border-rule`}><dt>{t('after.estate.minusFuneral')}</dt><dd className="m-0">{dh(m.funeral)}</dd></div> : null}
        {m.debts ? <div className={`${row} border-t border-rule`}><dt>{t('after.estate.minusDebts')}</dt><dd className="m-0">{dh(m.debts)}</dd></div> : null}
        {m.dowry ? <div className={`${row} border-t border-rule`}><dt>{t('after.estate.minusDowry')}</dt><dd className="m-0">{dh(m.dowry)}</dd></div> : null}
        <div className={`${row} border-t-2 border-ink font-semibold`}><dt>{t('after.estate.net')}</dt><dd className="m-0">{dh(m.net)}</dd></div>
        {will ? <div className={`${row} border-t border-rule text-ink-soft`}><dt>{t('after.estate.willShare')}</dt><dd className="m-0">{dh(willPaid ?? 0n)}</dd></div> : null}
      </dl>
      {will?.cut ? (
        <p className="m-0 text-meta text-ink-soft">
          {t(will.cut === 'heir' ? 'after.estate.cutHeir' : answer.result.bequest.length ? 'after.estate.cutBequest' : 'after.estate.cutThird')}
        </p>
      ) : null}
      <Cites today={will ? [322, 277, 280, 303] : [322]} />
    </div>
  );
}

/** The will (arts 277, 280, 303): an amount or a part, whether it is for an heir, and whether the heirs agree, asked
 *  only where it changes something: a will to an heir, or one over the third. */
function Will({ c, set, answer }: Pick<Area, 'c' | 'set' | 'answer'>) {
  const { t } = useT();
  const w = c.will;
  if (!w) {
    return (
      <div className="flex flex-col gap-1.5">
        <span className="text-body font-semibold">{t('after.estate.will')}</span>
        <p className="m-0 text-meta text-ink-soft">{t('after.estate.willLine')}</p>
        <Button className="self-start" onClick={() => set({ will: { kind: 'part', value: '', heir: false, agreed: false } })}>{t('after.estate.willAdd')}</Button>
      </div>
    );
  }
  const put = (patch: Partial<WillCase>) => set({ will: { ...w, ...patch } });
  const cut = answer.state === 'ok' ? answer.result.will?.cut : null;
  const askAgreed = w.heir || w.agreed || cut === 'third';
  return (
    <fieldset className="m-0 flex flex-col gap-3 border-0 p-0">
      <legend className="p-0 text-body font-semibold">{t('after.estate.will')}</legend>
      <p className="m-0 -mt-1 text-meta text-ink-soft">{t('after.estate.willLine')}</p>
      <Chips<string> label={t(`after.estate.willKind_${c.deceased}`)} value={w.kind}
              options={[{ key: 'part', label: t('after.estate.kinds.part') }, { key: 'amount', label: t('after.estate.kinds.amount') }]}
              onChange={(kind) => kind !== w.kind && put({ kind: kind as WillCase['kind'], value: '' })} />
      {w.kind === 'part' ? (
        <Chips<string> label={t('after.estate.willPart')} value={w.value} options={PARTS.map((p) => ({ key: p, label: t(`after.estate.parts.${p}`) }))}
                onChange={(value) => put({ value })} />
      ) : (
        <Amount label={t('after.estate.willAmount')} value={w.value} onChange={(value) => put({ value })} />
      )}
      <Chips<string> label={t('after.estate.willHeir')} value={w.heir ? 'y' : 'n'}
              options={[{ key: 'n', label: t('after.estate.no') }, { key: 'y', label: t('after.estate.yes') }]}
              onChange={(k) => put({ heir: k === 'y' })} />
      {askAgreed ? (
        <div className="flex flex-col gap-1.5">
          <Chips<string> label={t('after.estate.willAgreed')} value={w.agreed ? 'y' : 'n'}
                  options={[{ key: 'n', label: t('after.estate.no') }, { key: 'y', label: t('after.estate.yes') }]}
                  onChange={(k) => put({ agreed: k === 'y' })} />
          <p className="m-0 text-meta text-ink-soft">{t(w.heir ? 'after.estate.agreedHeir' : 'after.estate.agreedThird')}</p>
        </div>
      ) : null}
      <Cites today={[277, 280, 303]} />
      <Button variant="quiet" className="self-start" onClick={() => set({ will: null })}>{t('after.estate.willRemove')}</Button>
    </fieldset>
  );
}
