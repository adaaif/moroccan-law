/** A life topic's line icon (24 grid, 1.8 stroke, like the bar's), in its colour (`t-<slug>`). */
const PATHS: Record<string, string> = {
  family: 'M8 10.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6ZM16.5 11.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5ZM2.5 20a5.5 5.5 0 0 1 11 0M12.5 20a4.5 4.5 0 0 1 9 0',
  work: 'M3 7.5h18v12H3zM8.5 7.5V5h7v2.5M3 13h18',
  housing: 'M4 11 12 4l8 7v9H4zM10 20v-5h4v5',
  road: 'M5 16h14v-4l-2-5H7l-2 5zM5 16v2.5M19 16v2.5M8 12.5h.01M16 12.5h.01',
  consumer: 'M3 4h2l2.5 11h11L21 7H6.2M9 20h.01M18 20h.01',
  land: 'M12 21V11M12 11c0-4 3-6 7-6 0 4-3 6-7 6ZM12 14c0-3-2-5-6-5 0 3 2 5 6 5ZM4 21h16',
  tax: 'M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6M9 16h3',
  health: 'M12 20s-7-4.5-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.5-7 10-7 10ZM9 11h2l1-2 1.5 4 1-2H16',
  papers: 'M3 6h18v12H3zM7 10h4M7 14h6M15.5 10h2',
  business: 'M3 21h18M5 21V8l7-4 7 4v13M9 21v-5h6v5M9 11h.01M15 11h.01',
  justice: 'M12 4v16M5 8h14M7 8l-3 6a3 3 0 0 0 6 0zM17 8l-3 6a3 3 0 0 0 6 0zM8 20h8',
  digital: 'M4 5h16v11H4zM9 20h6M12 16v4M9.5 10.5l1.8 1.8 3.4-3.6',
};

export function TopicIcon({ slug, size = 24 }: { slug: string; size?: number }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round" className="shrink-0">
      <path d={PATHS[slug] ?? PATHS.papers} />
    </svg>
  );
}

