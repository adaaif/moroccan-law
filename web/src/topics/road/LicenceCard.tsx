import { useRoadT } from './strings';

/** The licence as its points (P1 of the road tools review): one dot a point, ten to a row. The points a stop takes
 *  fall out one after the other; those time brings back return in green; art. 100's ceiling is a ring on the dot
 *  where a stop's loss stops. At zero the card goes grey. Under reduced motion every change is instant. */
export function LicenceCard({ max, after, now, cap, title }: {
  max: number;
  /** The balance right after the stops. */
  after: number;
  /** The balance shown: after the stops, plus what the years and the course bring back. */
  now: number;
  /** The dot where art. 100 stopped a stop's loss, counted from the full licence. */
  cap: number | null;
  title: string;
}) {
  const { t } = useRoadT();
  return (
    <div className={`flex flex-col gap-3 rounded-card border border-rule bg-[linear-gradient(135deg,var(--color-wash),var(--color-sheet))] px-4 py-4 transition-[filter] duration-500 motion-reduce:transition-none ${now === 0 ? 'grayscale' : ''}`}>
      <div className="flex items-baseline justify-between gap-3">
        <span className="text-body font-semibold">{title}</span>
        <span className="text-meta text-ink-soft">{t('points.ofMax', { max })}</span>
      </div>
      <div aria-hidden="true" className="grid grid-cols-10 gap-1.5">
        {Array.from({ length: max }, (_, i) => {
          const lost = i >= now, back = !lost && i >= after;
          return (
            <span key={i} style={{ transitionDelay: `${Math.abs(i - after) * 22}ms` }}
                  className={`aspect-square rounded-full transition-[transform,opacity,background-color] duration-300 motion-reduce:transition-none ${
                    lost ? 'scale-50 bg-ink-soft opacity-25' : back ? 'bg-in-force' : 'bg-[var(--t)]'} ${cap !== null && i === cap ? 'ring-2 ring-amended ring-offset-1' : ''}`} />
          );
        })}
      </div>
    </div>
  );
}
