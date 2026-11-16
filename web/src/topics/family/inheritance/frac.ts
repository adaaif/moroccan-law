/** Exact fractions over BigInt: a share is never a decimal (F6 of the family plan). Plain functions over {n, d}, so
 *  Node's own test runner reads this file as it is. */
export type Q = { n: bigint; d: bigint };

const abs = (a: bigint) => (a < 0n ? -a : a);

export function gcd(a: bigint, b: bigint): bigint {
  a = abs(a);
  b = abs(b);
  while (b) [a, b] = [b, a % b];
  return a;
}

export const lcm = (a: bigint, b: bigint): bigint => (a && b ? abs(a * b) / gcd(a, b) : a || b);

export function q(n: bigint | number, d: bigint | number = 1n): Q {
  let nn = BigInt(n);
  let dd = BigInt(d);
  if (dd === 0n) throw new RangeError('zero denominator');
  if (dd < 0n) [nn, dd] = [-nn, -dd];
  const g = gcd(nn, dd) || 1n;
  return { n: nn / g, d: dd / g };
}

export const ZERO = q(0);
export const ONE = q(1);
export const add = (a: Q, b: Q): Q => q(a.n * b.d + b.n * a.d, a.d * b.d);
export const sub = (a: Q, b: Q): Q => q(a.n * b.d - b.n * a.d, a.d * b.d);
export const mul = (a: Q, b: Q): Q => q(a.n * b.n, a.d * b.d);
export const div = (a: Q, b: Q): Q => q(a.n * b.d, a.d * b.n);
export const cmp = (a: Q, b: Q): number => {
  const x = a.n * b.d - b.n * a.d;
  return x < 0n ? -1 : x > 0n ? 1 : 0;
};
export const isZero = (a: Q) => a.n === 0n;
export const sum = (xs: Q[]): Q => xs.reduce(add, ZERO);
export const max = (...xs: Q[]): Q => xs.reduce((m, x) => (cmp(x, m) > 0 ? x : m));
export const eq = (a: Q, b: Q) => cmp(a, b) === 0;
export const show = (a: Q) => (a.d === 1n ? `${a.n}` : `${a.n}/${a.d}`);
