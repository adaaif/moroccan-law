import { P } from './iconPaths';

/** A light's three lamps are drawn apart: the top one in red. */
export function KitIcon({ name, size = 26, className = '' }: { name: string; size?: number; className?: string }) {
  const d = P[name] ?? P.rules;
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"
         strokeLinecap="round" strokeLinejoin="round" className={`shrink-0 ${className}`}>
      <path d={d} />
      {name === 'light' ? <><circle cx="12" cy="7.5" r="1.8" fill="#C8102E" stroke="none" /><circle cx="12" cy="12" r="1.8" fill="currentColor" stroke="none" opacity=".35" /><circle cx="12" cy="16.5" r="1.8" fill="currentColor" stroke="none" opacity=".35" /></> : null}
    </svg>
  );
}

/** The road's name for them. */
export const RoadIcon = KitIcon;
