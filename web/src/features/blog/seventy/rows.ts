import type { SeventyFigures } from '../blog.api';

/** A year of the post's table, its columns named as the figures name them. */
export type YearRow = {
  year: number; issues: number; bis: number; pages: number; texts: number; words: number; dahir: number; law: number;
  decree: number; order: number; decision: number; other: number; report_issues: number; report_pages: number; printed: number;
};

export function yearRows(f: SeventyFigures): YearRow[] {
  return f.years.map((r) => Object.fromEntries(f.year_fields.map((name, k) => [name, r[k]])) as YearRow);
}

/** The decades as the post groups them: 1956–1959 first, the last one up to the post's last year. */
export function decades(rows: YearRow[]): { from: number; to: number; rows: YearRow[] }[] {
  const out: { from: number; to: number; rows: YearRow[] }[] = [];
  for (const r of rows) {
    const d = Math.floor(r.year / 10) * 10;
    const cur = out[out.length - 1];
    if (cur && Math.floor(cur.from / 10) * 10 === d) { cur.rows.push(r); cur.to = r.year; } else out.push({ from: r.year, to: r.year, rows: [r] });
  }
  return out;
}
