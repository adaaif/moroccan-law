import { TopicIcon } from '@/features/topics/TopicIcon';
import { topicColour } from '@/features/topics/colour';

// What each situation adds to its topic's picture, drawn on the same 24 grid (R10 of the for-everyone review).
const MARKS: Record<string, string> = {
  'road-accident': 'M12 4 2.5 20h19zM12 10v4.5M12 17.5h.01',
  'driving-licence': 'M3 6h18v12H3zM7 10h4M7 14h6M15.5 10h2',
  renting: 'M8 14a4 4 0 1 1 3.5-6H21v3h-2v2h-3v-2h-4.5A4 4 0 0 1 8 14z',
  divorce: 'M8 15a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM16 17a4 4 0 1 0 0-8 4 4 0 0 0 0 8z',
  dismissal: 'M10 4H5v16h5M14 8l4 4-4 4M18 12H9',
  birth: 'M12 21s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 5.5-7 10-7 10z',
  consumer: 'M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6',
  'co-ownership': 'M4 21V4h10v17M14 9h6v12M7 8h.01M11 8h.01M7 12h.01M11 12h.01M7 16h.01M11 16h.01M17 13h.01M17 17h.01',
  building: 'M3 21h18M6 21V10l6-5 6 5v11M10 21v-6h4v6',
  expropriation: 'M12 21s-6-5.5-6-11a6 6 0 1 1 12 0c0 5.5-6 11-6 11zM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z',
  copyright: 'M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z',
  property: 'M6 3h9l5 5v13H6zM15 3v5h5M9 13h7M9 17h5',
};

/** A situation's picture: its topic's icon on its colour, the situation's own mark in a badge at the corner. */
export function SituationArt({ slug, topic, size = 88 }: { slug: string; topic?: string; size?: number }) {
  const t = topic || 'papers';
  return (
    <span aria-hidden="true" style={{ ...topicColour(t), width: size, height: size }}
          className="relative grid shrink-0 place-items-center rounded-[28%] bg-[color-mix(in_srgb,var(--t)_15%,var(--color-sheet))] text-[color:var(--t)]">
      <TopicIcon slug={t} size={Math.round(size * 0.42)} />
      <span className="absolute -bottom-1 -end-1 grid place-items-center rounded-full bg-[color:var(--t)] text-sheet ring-4 ring-sheet"
            style={{ width: size * 0.42, height: size * 0.42 }}>
        <svg width={Math.round(size * 0.24)} height={Math.round(size * 0.24)} viewBox="0 0 24 24" fill="none" stroke="currentColor"
             strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={MARKS[slug] ?? MARKS.property} /></svg>
      </span>
    </span>
  );
}
