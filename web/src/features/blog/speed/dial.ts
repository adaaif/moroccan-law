/** The plain geometry of «السرعة في الجريدة الرسمية» (post 22), kept apart from the drawing so it can be tested: where a
 *  speed stands on the dial, and where each order's dot sits when several share a year and a speed. */

export const DIAL_MAX = 140;

/** The angle of a speed on the dial, in degrees: 0 km/h at the left end (-120°), the dial's top at 70 km/h, 140 at the
 *  right end (+120°). Clamped to the dial. */
export function angle(kmh: number): number {
  const k = Math.min(DIAL_MAX, Math.max(0, kmh));
  return -120 + (k / DIAL_MAX) * 240;
}

/** A point on a circle of radius r around (cx, cy) at a dial angle (0° straight up, clockwise). */
export function polar(cx: number, cy: number, r: number, deg: number): [number, number] {
  const rad = (deg * Math.PI) / 180;
  return [cx + r * Math.sin(rad), cy - r * Math.cos(rad)];
}

/** The orders as dots: each order's year and speed, and its rank among those sharing both (to sit side by side). */
export function stack(orders: { year: number; kmh: number }[]): { year: number; kmh: number; k: number }[] {
  const seen = new Map<string, number>();
  return orders.map((o) => {
    const key = `${o.year}-${o.kmh}`;
    const k = seen.get(key) ?? 0;
    seen.set(key, k + 1);
    return { ...o, k };
  });
}
