/** The plain arithmetic of «على كل قانون يصوّت عليه البرلمان» (post 21), kept apart from the drawing so it can be tested:
 *  how long words take to read at a pace and a time a day, said in years, months and days as each language says them;
 *  and the years a hand made more laws than Parliament. */

/** Calendar days to read `words` at `wpm` words a minute for `minutes` a day. */
export function daysToRead(words: number, wpm: number, minutes: number): number {
  return Math.ceil(words / wpm / minutes);
}

/** A number of days as years, months and days (a year of 365 days, a month of 30), the smaller parts dropped once the
 *  larger is two or more: «11 years», «2 years and 9 months», «2 months and 3 days». */
export function span(days: number): { y: number; m: number; d: number } {
  const y = Math.floor(days / 365);
  const rest = days - y * 365;
  const m = Math.floor(rest / 30);
  const d = rest - m * 30;
  if (y >= 10) return { y: Math.round(days / 365), m: 0, d: 0 };
  if (y >= 1) return { y, m, d: 0 };
  if (m >= 2) return { y: 0, m, d: 0 };
  return { y: 0, m, d };
}

/** The noun after a number, as Arabic agrees it: 1 its own word, 2 the dual, 3–10 the plural, 11 and more the singular. */
export function arabicKey(n: number): 'one' | 'two' | 'few' | 'many' {
  if (n === 1) return 'one';
  if (n === 2) return 'two';
  const r = n % 100;
  return r >= 3 && r <= 10 ? 'few' : 'many';
}

/** The years in which a hand other than Parliament made more texts of the law's rank than Parliament voted. */
export function withoutParliament(years: { year: number; voted: number; dfl: number; rdl: number }[]): number[] {
  return years.filter((y) => y.dfl + y.rdl > y.voted).map((y) => y.year);
}
