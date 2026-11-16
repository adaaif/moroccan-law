/** «الثمن اللي حددات الدولة» (T7 of the consumer plan, K4): sugar's maximum ex-factory price per kilogram by
 *  presentation, from the orders that restate order 1964.06's article 1, and the most a wholesaler and a retailer may
 *  add on it, each a share of the ex-factory price (article 2 as order 3243.23 wrote it). A copy of rates.yaml ships with
 *  the tool so it answers offline; back/apps/topics/tests/test_consumer.py fails when the two part ways. */
export type RateRow = { from: string; to?: string; values: Record<string, number> };
/** The row in force on a day (as kit/api's inForce, kept here so the rules run without the app). */
export const inForce = (rows: RateRow[], on: string): RateRow | undefined =>
  rows.filter((r) => r.from <= on && (!r.to || on < r.to)).sort((a, b) => b.from.localeCompare(a.from))[0];

export type Presentation = 'loaf' | 'lump' | 'bulk50' | 'g5' | 'g2' | 'g1';
export const PRESENTATIONS: { key: Presentation; block: boolean }[] = [
  { key: 'g1', block: false }, { key: 'g2', block: false }, { key: 'g5', block: false },
  { key: 'loaf', block: true }, { key: 'lump', block: true }, { key: 'bulk50', block: false },
];

export const SUGAR: RateRow[] = [
  { from: '2020-04-23', to: '2024-01-01', values: { loaf: 5.008, lump: 5.008, bulk50: 4.118, g5: 4.174, g2: 4.178, g1: 4.218 } },
  { from: '2024-01-01', to: '2025-01-01', values: { loaf: 5.0548, lump: 5.0548, bulk50: 4.1565, g5: 4.2130, g2: 4.2171, g1: 4.2574,
    wholesale_block: 236, wholesale_granulated: 235, retail_block: 377, retail_granulated: 357 } },
  { from: '2025-01-01', to: '2026-01-01', values: { loaf: 5.1016, lump: 5.1016, bulk50: 4.1950, g5: 4.2520, g2: 4.2561, g1: 4.2968,
    wholesale_block: 236, wholesale_granulated: 235, retail_block: 377, retail_granulated: 357 } },
  { from: '2026-01-01', values: { loaf: 5.1484, lump: 5.1484, bulk50: 4.2335, g5: 4.2910, g2: 4.2951, g1: 4.3363,
    wholesale_block: 236, wholesale_granulated: 235, retail_block: 377, retail_granulated: 357 } },
];

/** The order that set each row, for the line under the price. */
export const SUGAR_ORDERS: Record<string, { order: string; issue: string; path: string }> = {
  '2020-04-23': { order: '1071.20', issue: '6876', path: '/ma/arrete/1071-20/art_1' },
  '2024-01-01': { order: '3243.23', issue: '7261', path: '/ma/arrete/3243-23/art_1' },
  '2025-01-01': { order: '2900.24', issue: '7363', path: '/ma/arrete/2900-24/art_1' },
  '2026-01-01': { order: '2889.25', issue: '7469', path: '/ma/arrete/2889-25/art_1' },
};
export const MARGINS_PATH = '/ma/arrete/3243-23/art_1';

const r4 = (n: number) => Math.round(n * 10000) / 10000;

export type SugarPrice = { factory: number; wholesale: number | null; retail: number | null; total: number | null; from: string };

/** A presentation's prices on a day: the ex-factory maximum, and in dirhams what each margin adds, when the row has them. */
export function sugarOn(rows: RateRow[], day: string, p: Presentation): SugarPrice | null {
  const row = inForce(rows, day);
  if (!row || row.values[p] === undefined) return null;
  const factory = row.values[p];
  const block = PRESENTATIONS.find((x) => x.key === p)?.block ?? false;
  const w = row.values[block ? 'wholesale_block' : 'wholesale_granulated'];
  const r = row.values[block ? 'retail_block' : 'retail_granulated'];
  if (w === undefined || r === undefined) return { factory, wholesale: null, retail: null, total: null, from: row.from };
  const wholesale = r4(factory * w / 10000), retail = r4(factory * r / 10000);
  return { factory, wholesale, retail, total: r4(factory + wholesale + retail), from: row.from };
}
