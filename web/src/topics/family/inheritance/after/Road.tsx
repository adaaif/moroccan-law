import { Link } from 'react-router-dom';
import { formatAmount } from '../money';
import type { Money } from '../solve';
import { useT } from '../strings';
import LawChips from './LawChips';
import { code, law, type Ref } from './refs';

/** «ومن بعد؟» (IR25 of the inheritance review, 14 Nov 2026): the road after the answer, in order, each step with its
 *  article and, where there is an amount, this family's figure. The death declared within 30 days (decree 2.22.04
 *  art. 40); the deed of heirs before adouls of the appeal-court district of the deceased's home (law 51.26 art. 48),
 *  twelve witnesses at least for a witnesses' deed (art. 67), a copy for each heir (family code 394); the inventory,
 *  registered at 1 % (tax code art. 133, D 9°), a partition at 1.5 % (C 6°); and when the heirs sell, the profit
 *  counted from the value on the day of death written in the inventory (art. 65). Then the topic's journey. */
export default function Road({ money }: { money: Money | null }) {
  const { t, i18n } = useT();
  const lang = i18n.language;
  const figure = (num: bigint, den: bigint) => (money && money.gross > 0n
    ? t('after.road.figure', { base: formatAmount(money.gross, lang), duty: formatAmount((money.gross * num) / den, lang) }) : null);
  const steps: { key: string; line: string; figure?: string | null; refs: Ref[] }[] = [
    { key: 'death', line: t('after.road.deathLine'), refs: [law('civil', 40, t)] },
    { key: 'deed', line: t('after.road.deedLine'), refs: [law('adouls', 48, t), law('adouls', 67, t), code(394, t)] },
    { key: 'inventory', line: t('after.road.inventoryLine', { rate: '1\u00a0%' }), figure: figure(1n, 100n), refs: [law('cgi', 133, t)] },
    { key: 'partition', line: t('after.road.partitionLine', { rate: '1,5\u00a0%' }), figure: figure(15n, 1000n), refs: [law('cgi', 133, t)] },
    { key: 'sale', line: t('after.road.saleLine'), refs: [law('cgi', 65, t)] },
  ];
  return (
    <section aria-labelledby="road-title" className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
      <div className="flex flex-col gap-1">
        <h2 id="road-title" className="m-0 text-lead font-semibold">{t('after.road.title')}</h2>
        <p className="m-0 text-meta text-ink-soft">{t('after.road.lead')}</p>
      </div>
      {/* Down one dashed line, as the topic's journeys are drawn. */}
      <ol className="m-0 flex list-none flex-col p-0">
        {steps.map((s, i) => {
          const last = i === steps.length - 1;
          return (
            <li key={s.key} className="flex gap-3">
              <div aria-hidden="true" className="flex shrink-0 flex-col items-center">
                <span className="mt-1.5 size-3 shrink-0 rounded-full bg-[var(--t)]" />
                {last ? null : <span className="my-1 flex-1 border-s-2 border-dashed border-field" />}
              </div>
              <div className={`flex min-w-0 flex-1 flex-col gap-1.5 ${last ? '' : 'pb-5'}`}>
                <h3 className="m-0 text-body font-semibold">{t(`after.road.${s.key}`)}</h3>
                <p className="m-0 text-body">{s.line}</p>
                {s.figure ? <p className="m-0 text-body font-semibold tabular-nums">{s.figure}</p> : null}
                <LawChips refs={s.refs} />
              </div>
            </li>
          );
        })}
      </ol>
      <Link to="/topics/family/journeys/heirs" className="inline-flex min-h-11 items-center self-start text-body font-medium">
        {t('after.road.journey')}
      </Link>
    </section>
  );
}
