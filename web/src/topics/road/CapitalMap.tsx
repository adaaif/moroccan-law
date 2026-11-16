import type { Result, Table } from './rules/compensation';
import { useRoadT } from './strings';

/** The capital table as a map (C1 of the road tools review): earnings up, age across, each cell's shade its capital,
 *  the reader's cell lit, the two rows art. 5's formula reads between joined by a line, and the cells the BO
 *  misprinted marked. A drawing of a table, so it never mirrors; the numbers are the page's, one tap away. */
export function CapitalMap({ table, result, age }: { table: Table; result: Result; age: number }) {
  const { t } = useRoadT();
  const rows = table.earnings, cols = table.ages;
  const W = 320, H = 220, cw = W / cols.length, rh = H / rows.length;
  const all = rows.flatMap((e) => table.capital[String(e)] ?? []);
  const lo = Math.min(...all), hi = Math.max(...all);
  const col = cols.indexOf(Math.min(Math.max(age, cols[0]), cols[cols.length - 1]));
  const rowOf = (e: number) => rows.findIndex((x) => x >= e);
  const y = (i: number) => H - (i + 1) * rh;
  const marks = result.rows.map((r) => rowOf(r.earnings)).filter((i) => i >= 0);
  return (
    <figure className="m-0 flex flex-col gap-2">
      <svg viewBox={`-46 -8 ${W + 52} ${H + 32}`} role="img" aria-label={t('compensation.mapAlt')} style={{ direction: 'ltr' }} className="w-full">
        {rows.map((e, i) => (table.capital[String(e)] ?? []).map((c, j) => (
          <rect key={`${i}-${j}`} x={j * cw} y={y(i)} width={cw + 0.3} height={rh + 0.3}
                fill="var(--t)" opacity={0.12 + 0.78 * ((c - lo) / Math.max(1, hi - lo))} />
        )))}
        {table.misprints.map((m) => {
          const i = rows.indexOf(m.earnings), j = cols.indexOf(m.age);
          return i < 0 || j < 0 ? null : <rect key={`${m.earnings}-${m.age}`} x={j * cw} y={y(i)} width={cw} height={rh} fill="none" stroke="var(--color-repealed)" strokeWidth={1.4} />;
        })}
        {marks.length > 1 ? <line x1={(col + 0.5) * cw} x2={(col + 0.5) * cw} y1={y(marks[0]) + rh / 2} y2={y(marks[1]) + rh / 2} stroke="var(--color-ink)" strokeWidth={2} /> : null}
        {marks.map((i) => (
          <circle key={i} cx={(col + 0.5) * cw} cy={y(i) + rh / 2} r={5} fill="var(--color-sheet)" stroke="var(--color-ink)" strokeWidth={2.5}
                  className="motion-safe:animate-[rise_220ms_ease-out_both]" />
        ))}
        <text x={-4} y={H} textAnchor="end" fontSize={15} fill="var(--color-ink-soft)">{Math.round(rows[0] / 1000)}k</text>
        <text x={-4} y={12} textAnchor="end" fontSize={15} fill="var(--color-ink-soft)">{Math.round(rows[rows.length - 1] / 1000)}k</text>
        <text x={0} y={H + 18} fontSize={15} fill="var(--color-ink-soft)">{cols[0]}</text>
        <text x={W} y={H + 18} textAnchor="end" fontSize={15} fill="var(--color-ink-soft)">{cols[cols.length - 1]}</text>
      </svg>
      <figcaption className="text-meta text-ink-soft">{t('compensation.mapCaption')}</figcaption>
    </figure>
  );
}
