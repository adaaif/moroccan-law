import type { Week, WeekIssue, WeekSeries, WeekText } from '@/features/explain/explain.api';

/** The Bulletin prints its texts in this order of kinds. */
export const KINDS = ['constitution', 'organic_law', 'law', 'dahir', 'decree_law', 'decree', 'order', 'decision', 'circular',
  'convention', 'bill', 'other'];
export const kindOf = (x: WeekText) => (KINDS.includes(x.type) ? x.type : 'other');

/** What the week shows in a row: a text alone, or a series of texts of one form (the backend's `series`), placed where
 *  its first member stands. */
export type Unit = { kind: 'text'; text: WeekText } | { kind: 'series'; id: string; series: WeekSeries; texts: WeekText[] };

export function units(rows: WeekText[], series: Week['series']): Unit[] {
  const out: Unit[] = [];
  const seen = new Map<string, Extract<Unit, { kind: 'series' }>>();
  for (const x of rows) {
    const s = x.series ? series[x.series] : undefined;
    if (!x.series || !s) { out.push({ kind: 'text', text: x }); continue; }
    const u = seen.get(x.series);
    if (u) u.texts.push(x);
    else {
      const made = { kind: 'series' as const, id: x.series, series: s, texts: [x] };
      seen.set(x.series, made);
      out.push(made);
    }
  }
  return out;
}

/** The units of the general section under the kinds the Bulletin prints them by, in its order. */
export function byKind(rows: WeekText[], series: Week['series']): { kind: string; units: Unit[]; count: number }[] {
  const all = units(rows, series);
  return KINDS.map((kind) => {
    // A series sits under its first member's kind (one member may be filed as another).
    const list = all.filter((u) => kindOf(u.kind === 'text' ? u.text : u.texts[0]) === kind);
    return { kind, units: list, count: list.reduce((n, u) => n + (u.kind === 'text' ? 1 : u.texts.length), 0) };
  }).filter((g) => g.units.length);
}

/** How the week's paper is spent, class by class: what makes law, decrees, orders and decisions, the special section. */
export type PaperClass = 'law' | 'decree' | 'order' | 'special' | 'front';
export const PAPER: PaperClass[] = ['law', 'decree', 'order', 'special', 'front'];
const RANK: Record<PaperClass, number> = { law: 4, decree: 3, order: 2, special: 1, front: 0 };

export function paperClass(x: WeekText): PaperClass {
  if (x.section === 'special') return 'special';
  if (['constitution', 'organic_law', 'law', 'dahir', 'decree_law'].includes(x.type)) return 'law';
  return x.type === 'decree' ? 'decree' : 'order';
}

/** An issue's pages as runs of one class, first page first: each page takes the highest class of a text that starts on
 *  it, a page where none starts continues the one before, the pages before the first text are its front and contents. */
export function paperOf(issue: WeekIssue, texts: WeekText[]): { cls: PaperClass; from: number; to: number }[] {
  if (!issue.first_page || !issue.pages) return [];
  const first = issue.first_page;
  const last = first + issue.pages - 1;
  const starts = new Map<number, PaperClass>();
  for (const x of texts) {
    if (x.issue.key !== issue.key || x.page == null || x.page < first || x.page > last) continue;
    const c = paperClass(x);
    const had = starts.get(x.page);
    if (!had || RANK[c] > RANK[had]) starts.set(x.page, c);
  }
  const runs: { cls: PaperClass; from: number; to: number }[] = [];
  let cls: PaperClass = 'front';
  for (let p = first; p <= last; p++) {
    cls = starts.get(p) ?? cls;
    const run = runs.at(-1);
    if (run && run.cls === cls) run.to = p;
    else runs.push({ cls, from: p, to: p });
  }
  return runs;
}

/** The first and last page a series' members start on, and in which issues. */
export function spanOf(texts: WeekText[]): { issues: string[]; from: number | null; to: number | null } {
  const pages = texts.map((x) => x.page).filter((p): p is number => p != null);
  return { issues: [...new Set(texts.map((x) => x.issue.key))], from: pages.length ? Math.min(...pages) : null,
           to: pages.length ? Math.max(...pages) : null };
}
