export type Seat = { x: number; y: number; angle: number };

/** A chamber's seats, as its rows of benches: each row an arc, the longer rows holding more, every seat the same
 *  step from its neighbours; returned in the order a sweep from the left edge to the right meets them. `lift` (radians)
 *  carries each row's ends below the diameter: 0 draws a hemicycle, about half a radian the horseshoe arch of a
 *  Moroccan door, its feet turned in. `hollow` is the clear floor's share of the radius (the count is written there). */
export function hemicycle(total: number, width = 360, lift = 0, hollow = 0.45): { seats: Seat[]; r: number; height: number; cx: number; cy: number; inner: number } {
  const outer = width / 2 - 7, inner = outer * hollow;
  const mean = (outer + inner) / 2;
  const span = Math.PI + 2 * lift;
  // As many rows as keep a seat's step along its row and the step between rows nearest each other.
  const fit = (rows: number) => Math.abs((outer - inner) / (rows - 1) - (span * mean * rows) / total);
  let rows = 3;
  for (let n = 4; n <= 14; n += 1) if (fit(n) < fit(rows)) rows = n;
  const radius = (i: number) => inner + (i * (outer - inner)) / (rows - 1);
  const sum = rows * mean;
  const exact = Array.from({ length: rows }, (_, i) => (total * radius(i)) / sum);
  const counts = exact.map(Math.floor);
  // The seats the rounding left over go to the rows that lost the most.
  exact.map((e, i) => ({ i, lost: e - counts[i] })).sort((a, b) => b.lost - a.lost)
    .slice(0, total - counts.reduce((a, b) => a + b, 0)).forEach(({ i }) => { counts[i] += 1; });
  const cx = width / 2, cy = outer + 7;
  const seats: Seat[] = [];
  counts.forEach((n, i) => {
    for (let j = 0; j < n; j += 1) {
      const angle = Math.PI + lift - ((j + 0.5) / n) * span;
      seats.push({ x: cx + radius(i) * Math.cos(angle), y: cy - radius(i) * Math.sin(angle), angle });
    }
  });
  seats.sort((a, b) => b.angle - a.angle);
  const step = Math.min((outer - inner) / (rows - 1), (span * mean * rows) / total);
  // A small chamber's seats stay dots, never discs.
  return { seats, r: Math.min(6, step * 0.4), height: cy + outer * Math.sin(lift) + 7, cx, cy, inner };
}
