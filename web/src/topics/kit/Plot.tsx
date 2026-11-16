import type { ReactNode } from 'react';
import { pick, useKitT, type Named } from './api';

/** The plot a surveyor draws (the land review, M2): a cadastral square with its faint grid, the parcel's outline in
 *  the red the BO's decrees name («المرسومة حدودها بلون أحمر»), its boundary stones at the corners. A titled plot is
 *  solid with its stones, an untitled one dashed; what is taken or disputed is washed in red. The one number the law
 *  sets for a door is written where a plan writes the area. 56 × 56, the same for every door, so the rows' words line
 *  up. Colours from the page's tokens, so night redraws it. */
export function PlotMark({ plot, mark, size = 56 }: { plot?: string; mark?: { value: string; unit: Named } | null; size?: number }) {
  const { i18n } = useKitT();
  const drawing = PLOTS[plot ?? ''] ?? PLOTS.buy;
  return (
    <span aria-hidden="true" className="relative grid shrink-0 place-items-center overflow-hidden"
          style={{ width: size, height: size, borderRadius: 9, background: 'var(--color-sheet)', border: '1px solid color-mix(in srgb, var(--t) 30%, transparent)',
                   backgroundImage: GRID, backgroundSize: `${size / 4}px ${size / 4}px` }}>
      <svg viewBox="0 0 56 56" className="absolute inset-0 size-full" style={{ opacity: mark ? 0.5 : 1 }}>{drawing}</svg>
      {mark ? (
        <span className="relative flex flex-col items-center leading-none text-ink">
          <span dir="ltr" className="rounded px-0.5 font-bold tabular-nums" style={{ fontSize: mark.value.length > 3 ? 14 : 18, background: VEIL }}>{mark.value}</span>
          <span lang={i18n.language} className="mt-0.5 whitespace-nowrap rounded px-0.5 text-meta font-semibold" style={{ background: VEIL }}>{pick(mark.unit, i18n.language)}</span>
        </span>
      ) : null}
    </span>
  );
}

const GRID = 'linear-gradient(color-mix(in srgb, var(--t) 16%, transparent) 1px, transparent 1px), linear-gradient(90deg, color-mix(in srgb, var(--t) 16%, transparent) 1px, transparent 1px)';
const VEIL = 'color-mix(in srgb, var(--color-sheet) 80%, transparent)';
const RED = 'var(--color-sign-red)';
const WASH = 'color-mix(in srgb, var(--t) 16%, var(--color-sheet))';
const INK = 'var(--color-ink)';
const SHEET = 'var(--color-sheet)';

/** The parcel, its stones and its outline: one shape for every plot, so the eye compares what changes. */
const PARCEL = 'M9 15 46 9 49 46 12 49Z';
const stones = (points: [number, number][] = [[9, 15], [46, 9], [49, 46], [12, 49]]) => (
  <g fill={SHEET} stroke={RED} strokeWidth="1.6">{points.map(([x, y]) => <circle key={`${x}-${y}`} cx={x} cy={y} r="2.6" />)}</g>
);
const parcel = (dashed = false) => <path d={PARCEL} fill={WASH} stroke={RED} strokeWidth="1.8" strokeDasharray={dashed ? '4 3' : undefined} />;

const PLOTS: Record<string, ReactNode> = {
  // Buying: the deed on the plot.
  buy: (
    <>
      {parcel()}{stones()}
      <g transform="translate(18 16)" fill="none" stroke={INK} strokeWidth="1.7" strokeLinejoin="round" strokeLinecap="round">
        <path d="M1 1h13l4 4v19H1z" fill={SHEET} /><path d="M4.5 8h9M4.5 12h9M4.5 16h5" />
        <circle cx="14" cy="19.5" r="3" fill={SHEET} stroke={RED} />
      </g>
    </>
  ),
  // Held for years: dashed (not titled), its fence posts.
  own: (
    <>
      {parcel(true)}
      <g fill="none" stroke="var(--t)" strokeWidth="1.8" strokeLinecap="round"><path d="M17 40V30M25 40V27M33 40V29M14 33h23" /></g>
    </>
  ),
  // Registering: the stones the surveyor sets, B1 to B4.
  register: (
    <>
      {parcel()}
      <g fill={SHEET} stroke={RED} strokeWidth="1.8">
        <rect x="5.5" y="11.5" width="7" height="7" rx="1" /><rect x="42.5" y="5.5" width="7" height="7" rx="1" />
        <rect x="45.5" y="42.5" width="7" height="7" rx="1" /><rect x="8.5" y="45.5" width="7" height="7" rx="1" />
      </g>
      <g fontSize="7" fontWeight="700" fill={RED} textAnchor="middle" style={{ fontFamily: 'inherit' }}>
        <text x="17" y="24">B1</text><text x="39" y="19">B2</text><text x="40" y="42">B3</text><text x="19" y="43">B4</text>
      </g>
    </>
  ),
  // Someone registers my land: two plots overlapping, the overlap washed.
  oppose: (
    <>
      <path d="M5 18 34 12 37 44 8 47Z" fill={WASH} stroke={RED} strokeWidth="1.8" />
      <path d="M24 10 51 8 50 40 26 43Z" fill="none" stroke={INK} strokeWidth="1.8" strokeDasharray="4 3" />
      <path d="M24 12 35 12 37 43 26 43Z" fill={RED} opacity=".2" />
    </>
  ),
  // Fraud on the title: a line struck across the titled plot.
  fraud: <>{parcel()}{stones()}<path d="M13 44 44 13" stroke={INK} strokeWidth="2" strokeDasharray="3 3" /></>,
  // We inherited: the shares drawn dashed inside one plot.
  heirs: <>{parcel()}{stones()}<path d="M21 13 23 48M34 11 36 47M10 31 48 27" stroke={INK} strokeWidth="1.5" strokeDasharray="3 3" /></>,
  // A co-owner sold: one share shaded.
  preempt: (
    <>
      {parcel()}<path d="M28 12 46 9 49 46 30 48Z" fill={INK} opacity=".16" />
      <path d="M28 12 30 48" stroke={INK} strokeWidth="1.6" strokeDasharray="3 3" />{stones()}
    </>
  ),
  // Dividing: two plots and the new stones between them.
  divide: (
    <>
      <path d="M9 15 26 12 28 48 12 49Z" fill={WASH} stroke={RED} strokeWidth="1.8" />
      <path d="M31 11 46 9 49 46 33 47Z" fill={WASH} stroke={RED} strokeWidth="1.8" />
      {stones([[9, 15], [46, 9], [49, 46], [12, 49], [26, 12], [31, 11], [28, 48], [33, 47]])}
    </>
  ),
  // Building: the footprint.
  build: <>{parcel()}{stones()}<rect x="19" y="20" width="18" height="16" fill={INK} opacity=".22" stroke={INK} strokeWidth="1.4" /></>,
  // Built without a permit: the footprint struck in red.
  nopermit: (
    <>
      {parcel()}{stones()}
      <rect x="17" y="18" width="22" height="20" fill="none" stroke={RED} strokeWidth="1.8" strokeDasharray="3 2.5" />
      <path d="M17 18 39 38" stroke={RED} strokeWidth="1.6" />
    </>
  ),
  // Reserved in the plan: the reservation hatched.
  plan: (
    <>
      {parcel()}
      <clipPath id="plot-plan"><path d="M26 12 46 9 47.3 29 27 31Z" /></clipPath>
      <g clipPath="url(#plot-plan)" stroke={INK} strokeWidth="1.3" opacity=".55">
        {Array.from({ length: 9 }, (_, i) => <path key={i} d={`M${20 + i * 4} 34 ${34 + i * 4} 6`} />)}
      </g>
      <path d="M26 12 27 31 47.3 29" fill="none" stroke={INK} strokeWidth="1.4" />{stones()}
    </>
  ),
  // The state takes it: a road band across the plot.
  expro: (
    <>
      {parcel()}
      <path d="M0 34 56 22 56 32 0 44Z" fill={RED} opacity=".24" />
      <path d="M0 34 56 22M0 44 56 32" stroke={RED} strokeWidth="1.6" />
      <path d="M0 39 56 27" stroke={SHEET} strokeWidth="1.4" strokeDasharray="4 3" />{stones()}
    </>
  ),
  // Collective land: many plots, one community.
  collective: (
    <g fill={WASH} stroke={RED} strokeWidth="1.5">
      {['M4 8 20 6 21 22 5 24Z', 'M22 6 37 5 38 21 23 22Z', 'M39 5 52 6 51 21 40 21Z', 'M5 26 21 24 22 38 6 40Z', 'M23 24 38 23 39 37 24 38Z',
        'M40 23 51 23 50 37 41 37Z', 'M6 42 22 40 23 52 7 52Z', 'M24 40 39 39 40 51 25 52Z', 'M41 39 50 39 49 51 42 51Z'].map((d) => <path key={d} d={d} />)}
    </g>
  ),
};
