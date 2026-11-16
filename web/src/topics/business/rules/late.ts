import { addDays, addMonths } from '../../papers/rules/dates.ts';

/** A late invoice between traders (the commerce code's chapter on payment terms, as law 69.21 wrote it). Pure. */
export const ARTICLES = {
  who: '/ma/loi/15-95/art_1-78',
  term: '/ma/loi/15-95/art_2-78',
  fine: '/ma/loi/15-95/art_3-78',
  declare: '/ma/loi/15-95/art_4-78',
  sanction: '/ma/loi/15-95/art_6-78',
} as const;

/** The chapter spares whoever turns over 2,000,000 DH a year or less, without VAT (art. 78-1). */
export const SPARED = 2_000_000;
/** 60 days without an agreement, 120 at most with one (art. 78-2). */
export const DEFAULT_TERM = 60;
export const MAX_TERM = 120;
/** The fine's rate past the first month, per month or part of a month (art. 78-3). */
export const MONTHLY = 0.0085;

const endOfMonth = (day: string) => {
  const [y, m] = day.split('-').map(Number);
  return new Date(Date.UTC(y, m, 0, 12)).toISOString().slice(0, 10);
};

/** The day the term runs from: the invoice's date, or the end of the delivery's month when the invoice came later. */
export function start(invoice: string, delivered: string | null): string {
  if (!delivered) return invoice;
  const last = endOfMonth(delivered);
  return invoice <= last ? invoice : last;
}

/** The last day to pay: the agreed term, never past 120 days (art. 78-2). */
export function due(invoice: string, delivered: string | null, agreed: number | null): string {
  const days = agreed == null ? DEFAULT_TERM : Math.min(Math.max(agreed, 0), MAX_TERM);
  return addDays(start(invoice, delivered), days);
}

/** The months of delay begun between the last day and the payment: the first, then each further month or part. */
export function monthsLate(dueDay: string, paid: string): number {
  if (paid <= dueDay) return 0;
  let k = 1;
  while (addMonths(dueDay, k) < paid) k += 1;
  return k;
}

/** The fine owed to the Treasury: Bank Al-Maghrib's key rate for the first month, 0.85 % for each further month or
 *  part, on the unpaid sum with tax (art. 78-3). `keyRate` in percent (2.25 for 2.25 %). */
export function fine(amount: number, months: number, keyRate: number): { first: number; rest: number; total: number } {
  if (months <= 0 || amount <= 0) return { first: 0, rest: 0, total: 0 };
  const first = Math.round(amount * (keyRate / 100) * 100) / 100;
  const rest = Math.round(amount * MONTHLY * (months - 1) * 100) / 100;
  return { first, rest, total: Math.round((first + rest) * 100) / 100 };
}
