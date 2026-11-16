import { addMonths, addYears } from '../../papers/rules/dates.ts';

/** What the texts say of what happens online (the digital review): for each situation, the offences the penal
 *  code, the press code 88.13 or law 09.08 name, their penalties as printed (prison in months, fines in dirhams), the
 *  aggravation they write, whether the victim's complaint is needed, the prescription and where to complain. It names the
 *  texts; the court qualifies the facts and decides. Pure. */
export type Situation = 'hacked' | 'altered' | 'scam' | 'extortion' | 'intimate' | 'montage' | 'harassment' | 'defamation' | 'insult' | 'data';
export const SITUATIONS: Situation[] = ['extortion', 'intimate', 'montage', 'harassment', 'hacked', 'altered', 'scam', 'defamation', 'insult', 'data'];

export type Range = [number, number];
export type Offence = {
  key: Situation; path: string;
  /** Prison in months, when the text sets it. */
  prison?: Range;
  fine: Range;
  /** «or one of these penalties only». */
  either?: boolean;
  /** The heavier penalty a text writes, and when. */
  aggravated?: { path: string; prison?: Range; fine?: Range; doubled?: boolean; when: 'partner' | 'colleague' };
  /** The victim's complaint starts the prosecution (88.13 art. 99). */
  complaint?: string;
  prescription: { years?: number; months?: number; path: string };
  where: 'prosecutor' | 'cndp';
  wherePath: string;
};

const DELIT = { years: 4, path: '/ma/loi/22-01/art_5' };
const PRESS = { months: 6, path: '/ma/loi/88-13/art_101' };
const PROSECUTOR = { where: 'prosecutor' as const, wherePath: '/ma/loi/22-01/art_40' };

export const OFFENCES: Record<Situation, Offence> = {
  hacked: { key: 'hacked', path: '/ma/dahir/1-59-413/art_607-3', prison: [1, 3], fine: [2_000, 10_000], either: true, prescription: DELIT, ...PROSECUTOR },
  altered: { key: 'altered', path: '/ma/dahir/1-59-413/art_607-6', prison: [12, 36], fine: [10_000, 200_000], either: true, prescription: DELIT, ...PROSECUTOR },
  scam: { key: 'scam', path: '/ma/dahir/1-59-413/art_540', prison: [12, 60], fine: [500, 5_000], prescription: DELIT, ...PROSECUTOR },
  extortion: { key: 'extortion', path: '/ma/dahir/1-59-413/art_538', prison: [12, 60], fine: [200, 2_000], prescription: DELIT, ...PROSECUTOR },
  intimate: {
    key: 'intimate', path: '/ma/dahir/1-59-413/art_447-1', prison: [6, 36], fine: [2_000, 20_000], prescription: DELIT, ...PROSECUTOR,
    aggravated: { path: '/ma/dahir/1-59-413/art_447-3', prison: [12, 60], fine: [5_000, 50_000], when: 'partner' },
  },
  montage: {
    key: 'montage', path: '/ma/dahir/1-59-413/art_447-2', prison: [12, 36], fine: [2_000, 20_000], prescription: DELIT, ...PROSECUTOR,
    aggravated: { path: '/ma/dahir/1-59-413/art_447-3', prison: [12, 60], fine: [5_000, 50_000], when: 'partner' },
  },
  harassment: {
    key: 'harassment', path: '/ma/dahir/1-59-413/art_503-1-1', prison: [1, 6], fine: [2_000, 10_000], either: true, prescription: DELIT, ...PROSECUTOR,
    aggravated: { path: '/ma/dahir/1-59-413/art_503-1-1', doubled: true, when: 'colleague' },
  },
  defamation: { key: 'defamation', path: '/ma/loi/88-13/art_85', fine: [10_000, 100_000], complaint: '/ma/loi/88-13/art_99', prescription: PRESS, ...PROSECUTOR },
  insult: { key: 'insult', path: '/ma/loi/88-13/art_85', fine: [10_000, 50_000], complaint: '/ma/loi/88-13/art_99', prescription: PRESS, ...PROSECUTOR },
  data: { key: 'data', path: '/ma/loi/9-08/art_53', fine: [20_000, 200_000], prescription: DELIT, where: 'cndp', wherePath: '/ma/loi/9-08/art_28' },
};

/** The last day the public action stands, from the day of the facts (or the publication): four years for these délits
 *  (22.01 art. 5), six months for the press code's (88.13 art. 101), unless an act of prosecution interrupts it. */
export function lapses(o: Offence, facts: string): string {
  return o.prescription.months ? addMonths(facts, o.prescription.months) : addYears(facts, o.prescription.years!);
}

/** «6 months – 3 years» as months, for words: [6, 36] → { from: [6, 'months'], to: [3, 'years'] }. */
export function spell(months: number): [number, 'months' | 'years'] {
  return months >= 12 && months % 12 === 0 ? [months / 12, 'years'] : [months, 'months'];
}
