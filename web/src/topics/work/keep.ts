/** The reader's CNSS days, kept on the phone once the days tool has them (E15 of the work-counted review), so the page's
 *  instrument shows them. Nothing else about the reader is kept. */
const KEY = 'law.topic.work.days';

export function readDays(): number | null {
  try {
    const v = localStorage.getItem(KEY);
    return v === null || Number.isNaN(Number(v)) ? null : Number(v);
  } catch { return null; }
}

export function writeDays(days: number): void {
  try { localStorage.setItem(KEY, String(days)); } catch { /* private window */ }
}
