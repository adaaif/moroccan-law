import { useQuery } from '@tanstack/react-query';
import { useMemo } from 'react';

/** The world in Equal Earth and Morocco alone, drawn once from Natural Earth's Morocco edition (it draws the Kingdom
 *  whole; manage.py draw_maps writes public/geo/*.json). A place is projected here with the same constants. */
type WorldGeo = { w: number; h: number; scale: number; top: number; countries: Record<string, string> };
type MoroccoGeo = { w: number; h: number; lon0: number; lat1: number; k: number; scale: number; shapes: Record<string, string> };

const A1 = 1.340264, A2 = -0.081106, A3 = 0.000893, A4 = 0.003796, M = Math.sqrt(3) / 2;

function equalEarth(lon: number, lat: number): [number, number] {
  const l = (lon * Math.PI) / 180, t = Math.asin(M * Math.sin((lat * Math.PI) / 180));
  const t2 = t * t, t6 = t2 * t2 * t2;
  return [(l * Math.cos(t)) / (M * (A1 + 3 * A2 * t2 + t6 * (7 * A3 + 9 * A4 * t2))), t * (A1 + A2 * t2 + t6 * (A3 + A4 * t2))];
}

const useGeo = <T,>(name: 'world' | 'morocco') => useQuery({
  queryKey: ['geo', name],
  queryFn: async () => (await fetch(`/geo/${name}.json`)).json() as Promise<T>,
  staleTime: Infinity,
  gcTime: Infinity,
});

/** A place on a map: its size the share or the count it stands for. */
export type Dot = {
  slug: string;
  ar: string;
  fr: string;
  lat: number;
  lon: number;
  value: number;
  /** A state that is gone, drawn dashed on its successor (PL10). */
  gone?: boolean;
  /** Grown or shrunk over the years (the posts colour them). */
  tone?: 'rise' | 'fall' | null;
};

type Placed = Dot & { x: number; y: number; r: number };

/** Names drawn only where they do not sit on each other. */
function labels(dots: Placed[], size: number, most: number, rtl: boolean) {
  const boxes: number[][] = [];
  const out: { x: number; y: number; text: string; anchor: 'middle' | 'end' | 'start' }[] = [];
  for (const d of dots) {
    if (out.length >= most) break;
    const text = rtl ? d.ar : d.fr;
    const w = text.length * size * 0.56 + 4;
    const b = [d.x - w / 2, d.y - d.r - 4 - size, d.x + w / 2, d.y - d.r - 1];
    if (boxes.some((o) => !(b[2] < o[0] || b[0] > o[2] || b[3] < o[1] || b[1] > o[3]))) continue;
    boxes.push(b);
    out.push({ x: d.x, y: d.y - d.r - 4, text, anchor: 'middle' });
  }
  return out;
}

function Marks({ placed, picked, onPick, size, most, rtl, city }: {
  placed: Placed[]; picked?: string | null; onPick?: (slug: string) => void; size: number; most: number; rtl: boolean; city?: boolean;
}) {
  const names = useMemo(() => labels(placed, size, most, rtl), [placed, size, most, rtl]);
  return (
    <>
      <g>
        {placed.map((d) => (
          <g key={d.slug} className={`pl-pm${d.gone ? ' gone' : ''}${d.slug === picked ? ' on' : ''}${d.tone ? ` ${d.tone}` : ''}${city ? ' city' : ''}`}
             transform={`translate(${d.x.toFixed(1)},${d.y.toFixed(1)})`} onClick={onPick ? () => onPick(d.slug) : undefined}>
            <circle className="o" r={d.r.toFixed(1)} />
            {!city && d.r > 6 ? <circle className="i" r={(d.r * 0.72).toFixed(1)} /> : null}
            <title>{rtl ? d.ar : d.fr}</title>
          </g>
        ))}
      </g>
      <g aria-hidden="true">
        {names.map((n) => <text key={`${n.x},${n.y}`} className="pl-lbl" x={n.x} y={n.y} textAnchor={n.anchor} fontSize={size}>{n.text}</text>)}
      </g>
    </>
  );
}

/** The world in postmarks (PL7): each state a postmark of the stamp's violet on its place, its area its value. A
 *  coloured map would hide Belgium, Tunisia and Bahrain and give Russia and Canada the screen by their size. */
export function WorldMap({ dots, picked, onPick, label, rtl, most = 7, max }: {
  dots: Dot[]; picked?: string | null; onPick?: (slug: string) => void; label: string; rtl: boolean; most?: number; max?: number;
}) {
  const geo = useGeo<WorldGeo>('world');
  const placed = useMemo(() => {
    const g = geo.data;
    if (!g) return [];
    const top = max ?? Math.max(1, ...dots.map((d) => d.value));
    return dots.filter((d) => d.value > 0).map((d) => {
      const [x, y] = equalEarth(d.lon, d.lat);
      return { ...d, x: x * g.scale + g.w / 2, y: (g.top - y) * g.scale, r: Math.max(1.8, 34 * Math.sqrt(d.value / top)) };
    }).sort((a, b) => b.r - a.r);
  }, [geo.data, dots, max]);
  const g = geo.data;
  return (
    <svg className="pl-map" viewBox={g ? `0 0 ${g.w} ${g.h}` : '0 0 1000 437'} role="img" aria-label={label}>
      {g ? Object.entries(g.countries).map(([a3, d]) => <path key={a3} d={d} className={a3 === 'MAR' ? 'pl-land ma' : 'pl-land'} />) : null}
      <Marks placed={placed} picked={picked} onPick={onPick} size={13} most={most} rtl={rtl} />
    </svg>
  );
}

/** Morocco whole, its cities as dots (PL13). */
export function MoroccoMap({ dots, picked, onPick, label, rtl, most = 8, max }: {
  dots: Dot[]; picked?: string | null; onPick?: (slug: string) => void; label: string; rtl: boolean; most?: number; max?: number;
}) {
  const geo = useGeo<MoroccoGeo>('morocco');
  const placed = useMemo(() => {
    const g = geo.data;
    if (!g) return [];
    const top = max ?? Math.max(1, ...dots.map((d) => d.value));
    return dots.filter((d) => d.value > 0).map((d) => ({
      ...d, x: (d.lon - g.lon0) * g.k * g.scale, y: (g.lat1 - d.lat) * g.scale, r: Math.max(1.6, 19 * Math.sqrt(d.value / top)),
    })).sort((a, b) => b.r - a.r);
  }, [geo.data, dots, max]);
  const g = geo.data;
  return (
    <svg className="pl-map ma" viewBox={g ? `0 0 ${g.w} ${g.h}` : '0 0 400 421'} role="img" aria-label={label}>
      {g ? ['DZA', 'MRT', 'ESP', 'PRT'].map((a) => g.shapes[a] ? <path key={a} d={g.shapes[a]} className="pl-land" /> : null) : null}
      {g ? <path d={g.shapes.MAR} className="pl-land ma" /> : null}
      <Marks placed={placed} picked={picked} onPick={onPick} size={10} most={most} rtl={rtl} city />
    </svg>
  );
}
