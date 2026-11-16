/** Dirhams for the inheritance calculator (IR5 of the inheritance review): an amount read the ways Moroccans write
 *  it, and shares paid out to the centime so that the lines add up to the estate. Pure, over BigInt centimes. */
import type { Q } from './frac.ts';

/** A dirham, or the «مليون» prices are said in: a million centimes, 10,000 DH. */
export type Unit = 'dh' | 'million';

const EASTERN = '٠١٢٣٤٥٦٧٨٩';

/** An amount as typed, in centimes; null when it is not one. «800000», «800 000», «800.000», «800,000», «1.200.000»,
 *  «800.000,50», «800000.5», «٨٠٠٠٠٠» are all read; a separator followed by exactly three digits groups thousands, and
 *  a last separator followed by one or two digits is the decimal mark. */
export function parseAmount(raw: string, unit: Unit = 'dh'): bigint | null {
  // «80 مليون» says its own unit; «درهم», «DH» and the like are words around the number.
  if (/مليون|ملايين|million/i.test(raw)) unit = 'million';
  const s = raw.replace(/[٠-٩]/g, (d) => String(EASTERN.indexOf(d))).replace(/٫/g, ',').replace(/[^\d.,]/g, '');
  if (!/^\d[\d.,]*$/.test(s)) return null;
  const last = Math.max(s.lastIndexOf('.'), s.lastIndexOf(','));
  let whole = s, frac = '';
  if (last >= 0) {
    const tail = s.slice(last + 1);
    // One or two digits after the last mark: a decimal. Three: a group of thousands, like every mark before it.
    if (tail.length >= 1 && tail.length <= 2) [whole, frac] = [s.slice(0, last), tail];
    else if (tail.length !== 3) return null;
  }
  const groups = whole.split(/[.,]/);
  if (groups.some((g, i) => g === '' || (i > 0 && g.length !== 3) || (i === 0 && groups.length > 1 && g.length > 3))) return null;
  const centimes = BigInt(groups.join('')) * 100n + BigInt((frac + '00').slice(0, 2));
  return unit === 'million' ? centimes * 10000n : centimes;
}

/** Centimes as «800.000» or «177.777,78»: the dot groups thousands, the comma is the decimal mark, as the page prints. */
export function formatAmount(centimes: bigint, lang: string): string {
  const whole = (centimes / 100n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, lang === 'fr' ? ' ' : '.');
  const cents = centimes % 100n;
  return cents ? `${whole},${cents.toString().padStart(2, '0')}` : whole;
}

/** An amount in «مليون سنتيم», for the line that says it back («80 مليون»): a whole number, or one decimal. */
export function inMillions(centimes: bigint): string | null {
  if (centimes < 1000000n) return null;
  const tenths = (centimes * 10n) / 1000000n;
  return tenths % 10n ? `${tenths / 10n},${tenths % 10n}` : `${tenths / 10n}`;
}

export type Payee = { key: string; count: number; each: Q };
/** `each`: one person's centimes, by the payee's key. `rest`: the centimes that cannot be shared out equally. */
export type Paid = { each: Record<string, bigint>; rest: bigint };

/** Each person's amount to the centime. Every share is first cut down to the centime; the centimes left over go, one
 *  each, to the groups whose people lost the most, a whole group at a time so that equals stay equal. What still cannot
 *  be shared equally is returned as `rest` and said on the page: the lines and the rest make the estate exactly. */
export function allot(total: bigint, payees: Payee[]): Paid {
  const each: Record<string, bigint> = {};
  const lost: { key: string; count: number; num: bigint; den: bigint }[] = [];
  let paid = 0n;
  for (const p of payees) {
    const exact = total * p.each.n;              // over p.each.d
    each[p.key] = exact / p.each.d;
    paid += each[p.key] * BigInt(p.count);
    lost.push({ key: p.key, count: p.count, num: exact % p.each.d, den: p.each.d });
  }
  let rest = total - paid;
  // The largest loss first; a tie goes to the larger group, then to the earlier line.
  const order = lost.map((l, i) => ({ ...l, i })).filter((l) => l.num > 0n)
    .sort((a, b) => { const x = b.num * a.den - a.num * b.den; return x > 0n ? 1 : x < 0n ? -1 : b.count - a.count || a.i - b.i; });
  for (const l of order) {
    if (BigInt(l.count) > rest) continue;
    each[l.key] += 1n;
    rest -= BigInt(l.count);
  }
  return { each, rest };
}
