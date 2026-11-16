import { todayIso } from '@/shared/services/today';
/** How far the reader got in a topic's tools and journeys (T4, J4 of the road tools review), kept on the phone only:
 *  the scenes answered, the signs and cards learned, a journey's steps ticked. The topic's page reads it back. */
export type Progress = { done: number; total: number };
const key = (slug: string, ref: string) => `law.topic.${slug}.progress.${ref}`;

export function readProgress(slug: string, ref: string): Progress | null {
  try { const v = JSON.parse(localStorage.getItem(key(slug, ref)) ?? 'null'); return v && typeof v.done === 'number' ? v : null; } catch { return null; }
}

export function writeProgress(slug: string, ref: string, p: Progress) {
  try { localStorage.setItem(key(slug, ref), JSON.stringify(p)); } catch { /* private window */ }
}

/** A set of keys kept for one thing (the steps ticked, the scenes answered). */
export function readSet(slug: string, ref: string): string[] {
  try { const v = JSON.parse(localStorage.getItem(`${key(slug, ref)}.set`) ?? '[]'); return Array.isArray(v) ? v : []; } catch { return []; }
}

export function writeSet(slug: string, ref: string, items: string[], total: number) {
  try { localStorage.setItem(`${key(slug, ref)}.set`, JSON.stringify(items)); } catch { /* private window */ }
  writeProgress(slug, ref, { done: items.length, total });
}

/** A journey's day as the reader gave it (G8 of the family-papers review), with the end of its next limit counted
 *  from it: the journey opens on that day again, and its door says the days left. Kept on the phone only. */
/** A journey's day and its limits: `last` the next one, worked out when read from `all` (PX13), so a limit that passed
 *  gives way to the one after it. */
export type Due = { day: string; last: string; all?: string[] };

export function readDue(slug: string, ref: string): Due | null {
  try {
    const v = JSON.parse(localStorage.getItem(`${key(slug, ref)}.due`) ?? 'null') as Due | null;
    if (!v || typeof v.last !== 'string') return null;
    const today = todayIso();
    const next = (v.all ?? []).find((e) => e >= today);
    return next ? { ...v, last: next } : v;
  } catch { return null; }
}

export function writeDue(slug: string, ref: string, due: Due | null) {
  try {
    if (due) localStorage.setItem(`${key(slug, ref)}.due`, JSON.stringify(due));
    else localStorage.removeItem(`${key(slug, ref)}.due`);
  } catch { /* private window */ }
}

/** The child's age the reader last chose on the topic's age line (G10), so the topic's page draws the same age. */
export function readAge(slug: string): number | null {
  try { const v = Number(localStorage.getItem(`law.topic.${slug}.age`)); return localStorage.getItem(`law.topic.${slug}.age`) === null || Number.isNaN(v) ? null : v; } catch { return null; }
}

export function writeAge(slug: string, age: number) {
  try { localStorage.setItem(`law.topic.${slug}.age`, String(age)); } catch { /* private window */ }
}
