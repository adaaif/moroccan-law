import { SHOWN_STATES, type ArticleItem, type TextDetail } from '../corpus.api';

export type Standing = 'in_force' | 'none_found' | 'amended' | 'repealed' | 'partly_repealed' | 'not_yet_in_force' | null;

/** «In force» is said only when the site has read what came after the text as printed: with many issues since it unread
 *  (the archive's), the most it can say is that it found no repeal (UX3 of the phone-test review). */
function unread(d: TextDetail): boolean {
  // `sure`: the server's word that «in force» has a reason (an official portal's copy, or printed since 2019: RD6).
  return d.standing?.sure === false || (d.version?.consolidation === 'as_published' && Boolean(d.standing?.coverage?.partial));
}

/** Where a text stands, at a glance (rows 12 and L5): repealed, partly or not yet in force from what the site read, then
 *  «amended» when changes shown as fact touched it, «in force» when the site read it and found nothing against it. */
export function textStanding(d: TextDetail): Standing {
  const s = d.standing?.status;
  if (s === 'repealed' || s === 'partly_repealed' || s === 'not_yet_in_force') return s;
  if (d.standing?.changes) return 'amended';
  if (s !== 'in_force') return null;
  return unread(d) ? 'none_found' : 'in_force';
}

export function articleStanding(a: ArticleItem, d: TextDetail): Standing {
  const s = d.standing?.status;
  if (s === 'repealed' || s === 'not_yet_in_force') return s;
  const shown = a.changes.filter((c) => SHOWN_STATES.includes(c.state) || (!c.state && c.sources.length));
  if (shown.some((c) => c.verb === 'repealed' && SHOWN_STATES.includes(c.state))) return 'repealed';
  if (shown.length) return 'amended';
  if (s !== 'in_force' && s !== 'partly_repealed') return null;
  return unread(d) ? 'none_found' : 'in_force';
}

/** One colour per standing, the same everywhere. */
export const STANDING_TONE: Record<Exclude<Standing, null>, { dot: string; text: string }> = {
  in_force: { dot: 'bg-in-force', text: 'text-in-force' },
  none_found: { dot: 'bg-ink-soft', text: 'text-ink-soft' },
  amended: { dot: 'bg-amended', text: 'text-amended' },
  partly_repealed: { dot: 'bg-amended', text: 'text-amended' },
  not_yet_in_force: { dot: 'bg-amended', text: 'text-amended' },
  repealed: { dot: 'bg-repealed', text: 'text-repealed' },
};
