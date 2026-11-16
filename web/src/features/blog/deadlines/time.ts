/** The plain arithmetic of «15 يوما: الأجل المفضل» (post 23), kept apart from the drawing so it can be tested: a deadline's
 *  place on a scale of time that runs from an hour to decades (logarithmic, so an hour and ten years both show), and the
 *  noun after a number as Arabic agrees it. */

export const MIN_DAYS = 1 / 24, MAX_DAYS = 365.25 * 75;

/** Where a duration in days stands between 0 and 1 on the logarithmic scale. */
export function place(days: number): number {
  const d = Math.min(MAX_DAYS, Math.max(MIN_DAYS, days));
  return (Math.log(d) - Math.log(MIN_DAYS)) / (Math.log(MAX_DAYS) - Math.log(MIN_DAYS));
}

/** The noun after a number: 1 its own word, 2 the dual, 3–10 the plural, 11 and more the singular. */
export function arabicKey(n: number): 'one' | 'two' | 'few' | 'many' {
  if (n === 1) return 'one';
  if (n === 2) return 'two';
  const r = n % 100;
  return r >= 3 && r <= 10 ? 'few' : 'many';
}
