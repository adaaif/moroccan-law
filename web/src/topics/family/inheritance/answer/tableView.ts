import { sexOf } from '../case';
import { sayShare } from '../parts/say';
import { tableOf, type Row } from '../table';
import { groupName, type Ok, type T } from './words';

/** The table as words: the sentence, what it applies to, the header and the rows, and all of it as text to copy. */
export function tableView(a: Ok, t: T) {
  const r = a.result;
  const tb = tableOf(r);
  const last = tb.radd ?? tb.awl ?? tb.base;
  // The groups' shares out of the last base the sentence names, when each is whole there (the code's own notation);
  // else out of the number the engine's groups come right from.
  const whole = (n: bigint, d: bigint) => (n * last) % d === 0n;
  const fits = r.lines.every((l) => whole(l.own.n, l.own.d)) && whole(r.ownTreasury.n, r.ownTreasury.d);
  const of = fits ? last : tb.working;
  const group = (row: Row, i: number) => (fits ? (r.lines[i].own.n * last) / r.lines[i].own.d : row.group);
  const sentence = [
    t('answer.table.base', { n: tb.base.toString() }),
    tb.awl ? t('answer.table.awl', { n: tb.awl.toString() }) : '',
    tb.radd ? t('answer.table.radd', { n: tb.radd.toString() }) : '',
    tb.corrected !== last ? t('answer.table.tashih', { n: tb.corrected.toString() }) : '',
  ].filter(Boolean).join(' ');
  const taken = [
    r.bequestTotal.n > 0n ? t('answer.table.whatBequest') : '',
    r.will && r.will.granted.n > 0n ? t('answer.table.whatWill') : '',
    r.tanzil && r.tanzil.total.n > 0n ? t('answer.table.whatTanzil') : '',
  ].filter(Boolean);
  const applies = r.left.n !== r.left.d && taken.length
    ? t('answer.table.applies', { what: taken.join(t('answer.table.and')), share: sayShare(r.left, t) }) : null;
  const how = (row: Row) => (row.basis === 'asaba' ? t('answer.table.asaba')
    : t('answer.say', { who: t(row.basis === 'fard' ? 'answer.table.fard' : 'answer.table.both'), share: row.fard ? sayShare(row.fard, t) : '' }));
  const head = [t('answer.table.heir'), t('answer.table.how'), t('answer.table.group', { n: of.toString() }), t('answer.table.one', { n: tb.corrected.toString() })];
  const rows: string[][] = tb.rows.map((row, i) => [groupName(row.heir, row.count, t, true), how(row), group(row, i).toString(), row.each.toString()]);
  if (tb.treasury > 0n) {
    const tre = fits ? (r.ownTreasury.n * last) / r.ownTreasury.d : (r.ownTreasury.n * tb.working) / r.ownTreasury.d;
    rows.push([t('answer.treasury'), '', tre.toString(), tb.treasury.toString()]);
  }
  // Copied out of its columns, one person's number says whose it is: «32 لكل واحدة» for the daughters (IR21).
  const said = rows.map((x, i) => (tb.rows[i]?.count > 1 ? [...x.slice(0, 3), `${x[3]} ${t(`answer.each_${sexOf(tb.rows[i].heir)}`)}`] : x));
  const text = [t('answer.table.title'), sentence, applies ?? '', head.join(' | '), ...said.map((x) => x.join(' | '))].filter(Boolean).join('\n');
  return { sentence, applies, head, rows, text };
}
