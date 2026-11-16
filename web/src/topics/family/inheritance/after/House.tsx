import { useState } from 'react';
import { Chips } from '../../../kit/tool/parts';
import { formatAmount } from '../money';
import { useT } from '../strings';
import LawChips from './LawChips';
import { outOf, payee, type Ok } from './payees';
import { code, law } from './refs';

/** «شنو نديرو بالدار؟» (IR24 of the inheritance review, 14 Nov 2026): a family owns a house, not dirhams. Three ways,
 *  one under the other as rows of one ledger, each with this family's own figures: stay co-owners (each one's part out
 *  of the common number, as the land registry writes it on the title); one keeps it (the reader picks who; what they
 *  pay the others, in all and to each); sell (each one's part of the price, and the auction when they cannot agree).
 *  Each with its articles: nobody is made to stay in co-ownership (39.08 art. 27, DOC 978, family code 395); a division
 *  in kind where possible, else a sale by auction (39.08 arts 313, 317, 318); a co-owner may take a share sold to a
 *  stranger at its price, within thirty days of being served (292, 304). */
export default function House({ answer }: { answer: Ok }) {
  const { t, tOf, i18n } = useT();
  const lang = i18n.language;
  const [keeper, setKeeper] = useState<string | null>(null);
  const m = answer.money;
  const paid = answer.paid;
  if (!m || !paid || m.net <= 0n) return null;
  const dh = (x: bigint) => t('after.dh', { amount: formatAmount(x, lang) });
  const groups = answer.shares.filter((s) => s.count > 0);
  const named = (s: (typeof groups)[number], count = s.count) => {
    const p = payee(s, answer, t, count, tOf);
    return (
      <span className="flex min-w-0 flex-col">
        <span>{p.name}{count > 1 ? ` (${count})` : ''}</span>
        {p.of ? <span className="text-meta text-ink-soft">{p.of}</span> : null}
      </span>
    );
  };
  const row = 'flex items-baseline justify-between gap-3 border-t border-rule py-2 first:border-t-0';
  // Who may keep it: anyone paid but the Treasury. The first of them until the reader picks.
  const keepers = groups.filter((s) => s.group !== 'treasury' && s.key !== 'treasury' && !s.key.endsWith('.treasury'));
  const k = keepers.find((s) => s.key === keeper) ?? keepers[0];
  const others = groups.map((s) => ({ s, count: s.count - (k && s.key === k.key ? 1 : 0) })).filter((o) => o.count > 0);
  const toOthers = others.reduce((sum, o) => sum + paid.each[o.s.key] * BigInt(o.count), 0n);
  const kept = k ? payee(k, answer, t, 1, tOf) : null;
  return (
    <section aria-labelledby="house-title" className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
      <div className="flex flex-col gap-1">
        <h2 id="house-title" className="m-0 text-lead font-semibold">{t('after.house.title')}</h2>
        <p className="m-0 text-body">{t('after.house.lead', { amount: formatAmount(m.gross, lang) })}</p>
        {m.net !== m.gross ? <p className="m-0 text-meta text-ink-soft">{t('after.house.net', { amount: formatAmount(m.net, lang) })}</p> : null}
      </div>

      <div className="flex flex-col gap-2 border-t-2 border-ink pt-3">
        <h3 className="m-0 text-body font-semibold">{t('after.house.stay')}</h3>
        <p className="m-0 text-meta text-ink-soft">{answer.common ? t('after.house.stayLead', { common: answer.common.toString() }) : t('after.house.stayPlain')}</p>
        <ul className="m-0 flex list-none flex-col p-0">
          {groups.map((s) => {
            const o = outOf(s, answer.common);
            return (
              <li key={s.key} className={row}>
                {named(s)}
                <span className="shrink-0 font-semibold tabular-nums">{t('after.house.outOf', { n: o.n.toString(), d: o.d.toString() })}</span>
              </li>
            );
          })}
        </ul>
        <p className="m-0 text-meta">{t('after.house.stayLaw')}</p>
        <LawChips refs={[law('rights', 27, t), law('doc', 978, t), code(395, t)]} />
      </div>

      {k && kept ? (
        <div className="flex flex-col gap-2 border-t-2 border-ink pt-3">
          <h3 className="m-0 text-body font-semibold">{t('after.house.keep')}</h3>
          {keepers.length > 1 ? (
            <Chips<string> label={t('after.house.keepWho')} value={k.key} onChange={setKeeper}
                           options={keepers.map((s) => {
                             const p = payee(s, answer, t, 1, tOf);
                             return { key: s.key, label: p.of ? `${p.name} · ${p.of}` : p.name };
                           })} />
          ) : null}
          <p className="m-0 text-body">
            {t(`after.house.keepPays_${kept.sex}`, { who: kept.name, amount: formatAmount(toOthers, lang) })}
          </p>
          <ul className="m-0 flex list-none flex-col p-0">
            {others.map((o) => (
              <li key={o.s.key} className={row}>
                {named(o.s, o.count)}
                <span className="shrink-0 tabular-nums">{dh(paid.each[o.s.key])}</span>
              </li>
            ))}
          </ul>
          <p className="m-0 text-meta text-ink-soft">{t('after.house.keepTax')}</p>
          <LawChips refs={[law('cgi', 133, t)]} />
        </div>
      ) : null}

      <div className="flex flex-col gap-2 border-t-2 border-ink pt-3">
        <h3 className="m-0 text-body font-semibold">{t('after.house.sell')}</h3>
        <p className="m-0 text-meta text-ink-soft">{t('after.house.sellLead', { amount: formatAmount(m.gross, lang) })}</p>
        <ul className="m-0 flex list-none flex-col p-0">
          {groups.map((s) => (
            <li key={s.key} className={row}>
              {named(s)}
              <span className="shrink-0 tabular-nums">{dh(paid.each[s.key])}</span>
            </li>
          ))}
        </ul>
        <p className="m-0 text-meta">{t('after.house.sellCourt')}</p>
        <LawChips refs={[law('rights', 313, t), law('rights', 317, t), law('rights', 318, t)]} />
        <p className="m-0 text-meta">{t('after.house.sellShare')}</p>
        <LawChips refs={[law('rights', 292, t), law('rights', 304, t)]} />
      </div>
    </section>
  );
}
