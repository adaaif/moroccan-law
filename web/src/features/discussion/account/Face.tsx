import type { CSSProperties } from 'react';
import './account.css';

/* A person on the site (30 Oct 2026): their face, the first letter of their name, in the colour of the topic they write in
   most; the icons of their menu and their account pages. account.css draws them. */

/** A face: the name's first letter, `size` pixels round (32, or as its place in account.css says). */
export function Face({ name, size, style }: { name?: string | null; size?: number; style?: CSSProperties }) {
  return (
    <span className="ac-face" aria-hidden="true" style={size ? { ['--s' as string]: `${size}px`, ...style } : style}>
      {name ? [...name.trim()][0] : '•'}
    </span>
  );
}

const PATHS = {
  notices: 'M4 13.5 6 5h12l2 8.5V19H4zM4 13.5h5l1 2h4l1-2h5',
  mine: 'M4 5h16v11H9l-5 4zM8 9.5h8M8 12.5h5',
  saved: 'M6.5 3.5h11v17l-5.5-4-5.5 4z',
  following: 'M6 9a6 6 0 1 1 12 0c0 5 2 6.5 2 6.5H4S6 14 6 9ZM10 19a2 2 0 0 0 4 0',
  review: 'M12 3 19 6v5.5c0 4.3-3 7.7-7 9.5-4-1.8-7-5.2-7-9.5V6zM9 12l2 2 4-4',
  settings: 'M4 7h9M17 7h3M4 17h3M11 17h9M15 5v4M9 15v4',
  reading: 'M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z',
  profile: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4.5 20.5a7.5 7.5 0 0 1 15 0',
  out: 'M14 4h5v16h-5M10 8l-4 4 4 4M6 12h10',
  data: 'M12 4v11M7.5 10.5 12 15l4.5-4.5M5 19.5h14',
  reports: 'M5 21V4M5 4h11l-2 4 2 4H5',
  lock: 'M6 11h12v9H6zM8.5 11V8a3.5 3.5 0 0 1 7 0v3M12 14.5v2',
  key: 'M8 20a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9ZM11.2 12.3 19.5 4M16 7.5l2.5 2.5M13.8 9.7l2 2',
} as const;

export function Icon({ name, size = 20 }: { name: keyof typeof PATHS; size?: number }) {
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"
         strokeLinecap="round" strokeLinejoin="round" className={name === 'out' ? 'ac-flip' : undefined}>
      <path d={PATHS[name]} />
    </svg>
  );
}
