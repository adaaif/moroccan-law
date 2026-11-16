import { ending } from '../../kit/dates.ts';
import type { Holiday } from '../../kit/holidays.ts';
import { addYears } from '../../papers/rules/dates.ts';

/** The limits to attack a decision or to complain, each with its article (the civil procedure 58.25, in force since 23 Aug
 *  2026; the criminal procedure 22.01 with law 03.23). A court's limit is complete: neither the day it starts from nor
 *  its last day counts, and a last day off moves to the next working day (58.25 art. 602, 22.01 art. 750). The
 *  prescription of a complaint is counted in calendar years from the day of the facts (22.01 art. 5). Pure. */
export type Kind =
  | 'appeal' | 'opposition' | 'urgent' | 'payment' | 'payment-appeal' | 'civil-status' | 'annul' | 'cassation'
  | 'crim-appeal' | 'crim-opposition' | 'crim-cassation'
  | 'crime' | 'delit' | 'contravention';

export type Group = 'civil' | 'criminal' | 'complaint';
/** What starts the limit: the notification, the pronouncement (or the decision), the facts. */
export type From = 'notice' | 'pronounced' | 'facts';

export type Rule = { kind: Kind; group: Group; days?: number; years?: number; from: From; path: string; complete: boolean };

export const RULES: Rule[] = [
  { kind: 'appeal', group: 'civil', days: 30, from: 'notice', path: '/ma/loi/58-25/art_204', complete: true },
  { kind: 'opposition', group: 'civil', days: 15, from: 'notice', path: '/ma/loi/58-25/art_200', complete: true },
  { kind: 'urgent', group: 'civil', days: 15, from: 'notice', path: '/ma/loi/58-25/art_230', complete: true },
  { kind: 'payment', group: 'civil', days: 15, from: 'notice', path: '/ma/loi/58-25/art_239', complete: true },
  { kind: 'payment-appeal', group: 'civil', days: 15, from: 'notice', path: '/ma/loi/58-25/art_242', complete: true },
  { kind: 'civil-status', group: 'civil', days: 15, from: 'notice', path: '/ma/loi/58-25/art_279', complete: true },
  { kind: 'annul', group: 'civil', days: 15, from: 'notice', path: '/ma/loi/58-25/art_32', complete: true },
  { kind: 'cassation', group: 'civil', days: 30, from: 'notice', path: '/ma/loi/58-25/art_380', complete: true },
  { kind: 'crim-appeal', group: 'criminal', days: 10, from: 'pronounced', path: '/ma/loi/22-01/art_400', complete: true },
  { kind: 'crim-opposition', group: 'criminal', days: 10, from: 'notice', path: '/ma/loi/22-01/art_393', complete: true },
  { kind: 'crim-cassation', group: 'criminal', days: 10, from: 'pronounced', path: '/ma/loi/22-01/art_527', complete: true },
  { kind: 'crime', group: 'complaint', years: 15, from: 'facts', path: '/ma/loi/22-01/art_5', complete: false },
  { kind: 'delit', group: 'complaint', years: 4, from: 'facts', path: '/ma/loi/22-01/art_5', complete: false },
  { kind: 'contravention', group: 'complaint', years: 1, from: 'facts', path: '/ma/loi/22-01/art_5', complete: false },
];

export const COUNTING = { civil: '/ma/loi/58-25/art_602', criminal: '/ma/loi/22-01/art_750' } as const;

export const rule = (kind: Kind) => RULES.find((r) => r.kind === kind)!;

/** The criminal appeal runs from the pronouncement only for a party present or told the day; else from the
 *  notification (22.01 art. 400). The cassation likewise from the decision, or its notification (art. 527). */
export function startsFrom(r: Rule, present: boolean): From {
  return r.from === 'pronounced' && !present ? 'notice' : r.from;
}

export type Last = {
  /** The last day one may still act. */
  date: string;
  /** The day after the start, the first counted; the last counted day (a complete limit leaves the day after it). */
  first: string; counted: string;
  /** The days off the end was moved past. */
  moved: Holiday[];
  rule: Rule;
};

export function lastDay(kind: Kind, start: string): Last {
  const r = rule(kind);
  if (r.years) {
    const date = addYears(start, r.years);
    return { date, first: start, counted: date, moved: [], rule: r };
  }
  const counted = ending(start, { key: kind, path: r.path, label: '', days: r.days }).date;
  const end = ending(start, { key: kind, path: r.path, label: '', days: r.days, complete: true });
  const first = ending(start, { key: kind, path: r.path, label: '', days: 1 }).date;
  return { date: end.date, first, counted, moved: end.moved, rule: r };
}

/** The days a month grid shows for a limit: from the start's week to the last day's, each marked. */
export type Cell = { day: string; mark: 'start' | 'counted' | 'uncounted' | 'off' | 'last' | 'outside' };
export function cells(start: string, last: Last, offDays: (day: string) => boolean): Cell[] {
  const at = (d: string) => new Date(`${d}T12:00:00Z`);
  const iso = (x: Date) => x.toISOString().slice(0, 10);
  const monday = (d: string) => { const x = at(d); x.setUTCDate(x.getUTCDate() - ((x.getUTCDay() + 6) % 7)); return x; };
  const from = monday(start);
  const to = at(last.date);
  const out: Cell[] = [];
  for (let x = from; x <= to || (out.length % 7) !== 0; x = new Date(x.getTime() + 864e5)) {
    const day = iso(x);
    const mark: Cell['mark'] = day < start ? 'outside' : day === start ? 'start' : day === last.date ? 'last'
      : day <= last.counted ? 'counted' : day > last.date ? 'outside' : offDays(day) ? 'off' : 'uncounted';
    out.push({ day, mark });
  }
  return out;
}
