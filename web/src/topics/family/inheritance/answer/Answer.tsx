import { useContext } from 'react';
import { Link } from 'react-router-dom';
import { ENGINE, type Case } from '../case';
import { formatAmount } from '../money';
import { moneyOf } from '../solve';
import Cites from '../parts/Cites';
import { RulesContext } from '../parts/rules';
import type { Answer } from '../solve';
import { useT } from '../strings';
import Family from './Family';
import Paper from './Paper';
import Steps from './Steps';
import Table from './Table';
import { CHOICES, NAMED_ART, lineName, money, sayIt, type Ok } from './words';

/** The answer (IR18–IR22 and the screen side of IR2, IR4, IR5, IR12 of the inheritance review), read at two depths:
 *  for the family, a line a person with the dirhams, the percentage and why; for the adoul, the table and the steps,
 *  folded under it; and the paper the family takes to the adouls. Nothing entered: one quiet line. A case the tool
 *  does not count: why, who decides, and the articles.
 *
 *  Not sticky on a desk: with the bar, the bequest and the folds it is taller than a screen, and a sticky column taller
 *  than the window hides its own end until the page's end. It sits at the top of the second column and scrolls. */
export default function AnswerView({ c, answer, code }: { c: Case; answer: Answer; code: string }) {
  const { t } = useT();
  if (answer.state === 'empty') {
    return <section data-answer className="rounded-card bg-sheet px-5 py-4"><p className="m-0 text-body text-ink-soft">{t('answer.empty')}</p></section>;
  }
  if (answer.state === 'stop') return <Stop c={c} why={answer.why} cites={answer.cites} code={code} />;
  return <Answered c={c} a={answer} code={code} />;
}

function Answered({ c, a, code }: { c: Case; a: Ok; code: string }) {
  const { t, i18n } = useT();
  const r = a.result;
  const m = money(a, t, i18n.language);
  // What a screen reader hears when the answer changes: who takes what, once, not the whole column.
  const said = a.shares.filter((s) => s.group !== 'later').map((s) => [lineName(s, t), sayIt(s.each, a.common, t), m.paid(s)].filter(Boolean).join(' ')).join(i18n.language === 'fr' ? ' ; ' : '؛ ');
  return (
    <section data-answer aria-labelledby="inh-answer" className="flex flex-col gap-5 rounded-card bg-sheet px-5 py-5 sm:px-7">
      <div className="flex flex-col gap-1">
        <h2 id="inh-answer" className="m-0 text-h3 font-bold">{t('answer.heading')}</h2>
        {r.named ? (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <p className="m-0 text-body text-stamp">{t('namedLead')}{t('answer.colon')}<span className="font-semibold">{t(`named.${r.named}`)}</span></p>
            <Cites today={[NAMED_ART[r.named]]} />
          </div>
        ) : null}
        <p className="sr-only" aria-live="polite">{said}</p>
      </div>
      <Family c={c} a={a} />
      <div className="flex flex-col">
        <Table a={a} />
        <Steps c={c} a={a} />
      </div>
      <Paper c={c} a={a} code={code} />
      <Version code={code} />
    </section>
  );
}

/** A case the tool does not count: why, in plain words, who decides, the articles, and the version it was said by. */
function Stop({ c, why, cites, code }: { c: Case; why: Extract<Answer, { state: 'stop' }>['why']; cites: Extract<Answer, { state: 'stop' }>['cites']; code: string }) {
  const { t, i18n } = useT();
  const mo = why === 'overdrawn' ? moneyOf(c) : null;
  const dh = (x: bigint) => t('answer.dh', { amount: formatAmount(x, i18n.language) });
  return (
    <section data-answer aria-live="polite" className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
      <h2 className="m-0 text-h3 font-bold">{t('answer.stop.title')}</h2>
      <p className="m-0 text-body">{t(`answer.stop.${why}`)}</p>
      {mo ? <p className="m-0 text-body tabular-nums">{t('answer.stop.overdrawnMoney', { gross: dh(mo.gross), out: dh(mo.funeral + mo.debts + mo.dowry) })}</p> : null}
      {why === 'mixed' ? <Link to={`${CHOICES}#mixed`} className="self-start text-body font-medium">{t('answer.stop.choices')}</Link> : null}
      {/* The mixed forms' articles come from the engine, in its book's numbers; the other stops are written here. */}
      {why === 'mixed' ? <Cites cites={cites} /> : <Cites today={cites} />}
      <Version code={code} />
    </section>
  );
}

/** The version line (IR12): which engine and which code said this, the case's code, and what changed since. */
function Version({ code }: { code: string }) {
  const { t } = useT();
  const rules = useContext(RulesContext);
  return (
    <div className="flex flex-col gap-0.5 border-t border-rule pt-3 text-meta text-ink-soft">
      <p className="m-0">{t('shell.version', { v: ENGINE, rules: t(`shell.rules.${rules}`) })}</p>
      {code ? <p className="m-0" style={{ overflowWrap: 'anywhere' }}>{t('shell.code', { code: `\u2066${code}\u2069` })}</p> : null}
      <Link to={`${CHOICES}#changes`} className="inline-flex min-h-11 items-center self-start font-medium">{t('shell.changes')}</Link>
    </div>
  );
}
