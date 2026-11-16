import { iconPath } from './iconPaths';
import { KitIcon } from './icons';
import { pick, useKitT, type Door, type Named } from './api';
import { PlotMark } from './Plot';

export type SignKind = NonNullable<Door['sign']>;

/** A door's sign (A5 of the road-signposted review; G1 of the family-papers review). On the road, the family's shape and
 *  colours as order 2805.14 gives them, so the shape says the kind of moment before the words do (a triangle, something
 *  happened; a red ring, a penalty; a blue disc, a duty; a blue square, a procedure), the door's pictogram inside. Signs
 *  keep their colours at night, as on the road. In the family, the mark of the office where the passage ends, in the
 *  topic's colour: the adouls' act, the civil-status booklet, the courthouse, the consulate; protection has no paper,
 *  only a shield in ink, so the row draws no eye. A topic without signs draws its icon on a tile of its colour. */
export function Sign({ kind, icon, size = 40, mark, card = false, shape = 'punch', plot }: {
  kind?: SignKind; icon?: string; size?: number; mark?: { value: string; unit: Named } | null; card?: boolean;
  /** The object a topic's numbers are drawn on: the work's punch card, the consumer's price tag, the land's plot, the
   *  tax's fiscal stamp. */
  shape?: 'punch' | 'tag' | 'plot' | 'stamp' | 'vignette' | 'card' | 'cachet' | 'file' | 'bubble' | 'receipt';
  /** The land's drawing of the door's plot (the land review, M2). */
  plot?: string;
}) {
  // The land draws every door as its plot, the law's number written on it where a plan writes the area.
  if (shape === 'plot' && (plot || mark)) return <PlotMark plot={plot} mark={mark ?? null} />;
  // A topic counted in numbers (E1 of the work-counted review) draws its doors on punch cards: the number, or the paper; the
  // consumer on price tags (the consumer-receipt review).
  if (mark || (card && icon)) {
    if (shape === 'tag') return <PriceTag mark={mark ?? null} icon={icon} />;
    if (shape === 'stamp') return <FiscalStamp mark={mark ?? null} icon={icon} />;
    if (shape === 'vignette') return <Vignette mark={mark ?? null} icon={icon} />;
    if (shape === 'card') return <IdCard mark={mark ?? null} icon={icon} />;
    if (shape === 'cachet') return <Cachet mark={mark ?? null} icon={icon} />;
    if (shape === 'file') return <Dossier mark={mark ?? null} icon={icon} />;
    if (shape === 'bubble') return <Bubble mark={mark ?? null} icon={icon} />;
    if (shape === 'receipt') return <RentReceipt mark={mark ?? null} icon={icon} />;
    return <PunchCard mark={mark ?? null} icon={icon} />;
  }
  // A door with neither draws nothing: the same glyph down a list says nothing.
  if (!kind && !icon) return null;
  if (kind && kind in OFFICES) {
    return (
      <svg aria-hidden="true" width={size} height={size} viewBox="0 0 40 40"
           className={`shrink-0 ${kind === 'shield' ? 'text-ink' : 'text-[color:var(--t)]'}`}>
        {OFFICES[kind as keyof typeof OFFICES]}
      </svg>
    );
  }
  if (!kind) {
    return (
      <span aria-hidden="true" style={{ width: size, height: size }}
            className="grid shrink-0 place-items-center rounded-full bg-[color-mix(in_srgb,var(--t)_14%,var(--color-sheet))] text-[color:var(--t)]">
        <KitIcon name={icon!} size={Math.round(size * 0.6)} />
      </span>
    );
  }
  const blue = kind === 'disc' || kind === 'square';
  // The pictogram sits where the shape leaves the most room: low in the triangle, centred elsewhere.
  const box = kind === 'tri' ? { x: 12, y: 15.5, s: 16 } : { x: 10, y: 10, s: 20 };
  return (
    <svg aria-hidden="true" width={size} height={size} viewBox="0 0 40 40" className="shrink-0">
      {kind === 'tri' ? <path d="M20 4.5 36.5 34h-33z" fill="#fff" stroke="var(--color-sign-red)" strokeWidth="3.6" strokeLinejoin="round" /> : null}
      {kind === 'ring' ? <circle cx="20" cy="20" r="16.6" fill="#fff" stroke="var(--color-sign-red)" strokeWidth="4.2" /> : null}
      {kind === 'disc' ? <circle cx="20" cy="20" r="18.5" fill="var(--color-sign-blue)" /> : null}
      {kind === 'square' ? <rect x="2" y="2" width="36" height="36" rx="6" fill="var(--color-sign-blue)" /> : null}
      <svg x={box.x} y={box.y} width={box.s} height={box.s} viewBox="0 0 24 24" fill="none" stroke={blue ? '#fff' : '#1e1b2c'}
           strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d={iconPath(icon ?? 'rules')} />
      </svg>
    </svg>
  );
}

/** The offices' marks, 40 × 40, in the colour around them; their inner lines in the sheet's colour. */
const OFFICES = {
  // The adouls' act: a tall sheet, its lines, two signatures at its foot.
  act: (
    <>
      <rect x="10" y="3" width="20" height="34" rx="2.5" fill="currentColor" />
      <path d="M14 9.5h12M14 13.5h12M14 17.5h12M14 21.5h8" stroke="var(--color-sheet)" strokeWidth="1.8" strokeLinecap="round" />
      <path d="M13.5 31.5c1.6-3.2 2.6 2 4.4-1M22 31.5c1.6-3.2 2.6 2 4.4-1" stroke="var(--color-sheet)" strokeWidth="1.6" fill="none" strokeLinecap="round" />
    </>
  ),
  // The civil-status booklet: a small book, its spine, its label.
  record: (
    <>
      <rect x="8" y="4" width="24" height="32" rx="3" fill="currentColor" />
      <rect x="26" y="4" width="6" height="32" rx="2" fill="var(--color-ink)" opacity=".22" />
      <rect x="11.5" y="10" width="11" height="8" rx="1.5" fill="var(--color-sheet)" />
      <path d="M11.5 23.5h11M11.5 28h8" stroke="var(--color-sheet)" strokeWidth="1.8" strokeLinecap="round" />
    </>
  ),
  // The family court: a courthouse front.
  court: (
    <g fill="currentColor">
      <path d="M20 3.5 36.5 12.5h-33z" />
      <rect x="5" y="14.5" width="30" height="2.5" rx="1" />
      <rect x="7" y="18.5" width="4" height="12" rx="1" /><rect x="14" y="18.5" width="4" height="12" rx="1" />
      <rect x="22" y="18.5" width="4" height="12" rx="1" /><rect x="29" y="18.5" width="4" height="12" rx="1" />
      <rect x="3.5" y="32" width="33" height="4.5" rx="1.2" />
    </g>
  ),
  // The consulate: a globe.
  consul: (
    <>
      <circle cx="20" cy="20" r="16" fill="currentColor" />
      <ellipse cx="20" cy="20" rx="6.5" ry="16" fill="none" stroke="var(--color-sheet)" strokeWidth="1.8" />
      <path d="M4.5 15h31M4.5 25h31M20 4v32" stroke="var(--color-sheet)" strokeWidth="1.8" />
    </>
  ),
  // The land registry: the title's ledger, open, its plan on the right page (the land review).
  registry: (
    <>
      <path d="M3 9c5-2 11-2 17 1 6-3 12-3 17-1v24c-5-2-11-2-17 1-6-3-12-3-17-1z" fill="currentColor" />
      <path d="M20 10v24" stroke="var(--color-sheet)" strokeWidth="1.6" />
      <path d="M7 15h9M7 19h9M7 23h7" stroke="var(--color-sheet)" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M24 16l9-1 1 10-9 1z" fill="none" stroke="var(--color-sheet)" strokeWidth="1.6" strokeLinejoin="round" />
    </>
  ),
  // The commune: its hall, the flag on its roof.
  // The police's service where an identity card is asked for and collected (the papers review): a badge, its star.
  police: (
    <g fill="currentColor">
      <path d="M20 3 33 8v10c0 8.5-5.6 15.4-13 19-7.4-3.6-13-10.5-13-19V8z" />
      <path d="m20 11 2.3 4.8 5.2.6-3.9 3.6 1.1 5.2L20 22.6l-4.7 2.6 1.1-5.2-3.9-3.6 5.2-.6z" fill="var(--color-sheet)" />
    </g>
  ),
  commune: (
    <g fill="currentColor">
      <rect x="6" y="15" width="28" height="19" rx="1.5" />
      <path d="M4 16 20 7l16 9z" />
      <path d="M20 7V2.5" stroke="currentColor" strokeWidth="1.6" /><path d="M20 2.5h7l-2 2 2 2h-7z" />
      <rect x="17" y="24" width="6" height="10" fill="var(--color-sheet)" />
      <rect x="9.5" y="19" width="5" height="4" fill="var(--color-sheet)" /><rect x="25.5" y="19" width="5" height="4" fill="var(--color-sheet)" />
      <rect x="3" y="34" width="34" height="3" rx="1" />
    </g>
  ),
  // The trusteeship council: a table and its seats.
  council: (
    <g fill="currentColor">
      <rect x="6" y="17" width="28" height="6" rx="2" />
      <circle cx="10" cy="11" r="3.2" /><circle cx="20" cy="9.5" r="3.2" /><circle cx="30" cy="11" r="3.2" />
      <rect x="9" y="23" width="3" height="11" rx="1" /><rect x="28" y="23" width="3" height="11" rx="1" />
      <circle cx="14" cy="30" r="3" /><circle cx="26" cy="30" r="3" />
    </g>
  ),
  // The insurance fund (the health review): the insured's card, its chip and its number line.
  fund: (
    <>
      <rect x="3" y="9" width="34" height="23" rx="3.5" fill="currentColor" />
      <rect x="7.5" y="14" width="7" height="5.5" rx="1.2" fill="var(--color-sheet)" />
      <path d="M7.5 25.5h18M28 16h4.5" stroke="var(--color-sheet)" strokeWidth="1.8" strokeLinecap="round" />
    </>
  ),
  // The hospital or the clinic: its front, the cross over its door.
  hospital: (
    <g fill="currentColor">
      <rect x="6" y="11" width="28" height="23" rx="1.5" />
      <rect x="3" y="34" width="34" height="3" rx="1" />
      <rect x="17" y="26" width="6" height="8" fill="var(--color-sheet)" />
      <path d="M18 14.5h4v3h3v4h-3v3h-4v-3h-3v-4h3z" fill="var(--color-sheet)" />
      <path d="M20 3v6M17 6h6" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
    </g>
  ),
  // Barid Al-Maghrib, where the auto-entrepreneur's register is kept (the business review): an envelope.
  post: (
    <>
      <rect x="3" y="9" width="34" height="23" rx="2.5" fill="currentColor" />
      <path d="M5 11.5 20 23l15-11.5" fill="none" stroke="var(--color-sheet)" strokeWidth="2" strokeLinejoin="round" />
    </>
  ),
  // The bank a cheque is drawn on: the cheque, its amount box and the drawer's signature.
  bank: (
    <>
      <rect x="2.5" y="10" width="35" height="20" rx="2" fill="currentColor" />
      <path d="M6.5 15.5h15M6.5 20h10" stroke="var(--color-sheet)" strokeWidth="1.8" strokeLinecap="round" />
      <rect x="25" y="13.5" width="9" height="5" rx="1" fill="var(--color-sheet)" />
      <path d="M22 26c1.6-3 2.8 1.8 4.6-.8s2.6 1.6 4.4-.4" fill="none" stroke="var(--color-sheet)" strokeWidth="1.6" strokeLinecap="round" />
    </>
  ),
  // The bar (هيئة المحامين), where the bâtonnier names a lawyer and settles fees (the justice review): the lawyer's
  // robe at the neck, its two white bands.
  bar: (
    <>
      <path d="M7 36V17c0-4 3-7 7-8l6 6 6-6c4 1 7 4 7 8v19z" fill="currentColor" />
      <path d="M14 9l6 6 6-6" fill="none" stroke="var(--color-sheet)" strokeWidth="1.8" strokeLinejoin="round" />
      <rect x="16.4" y="16" width="3" height="10" rx="1" fill="var(--color-sheet)" />
      <rect x="20.6" y="16" width="3" height="10" rx="1" fill="var(--color-sheet)" />
    </>
  ),
  // The CNDP, where a refused data right ends (the digital review): a page under a padlock.
  privacy: (
    <>
      <rect x="7" y="4" width="22" height="28" rx="2" fill="currentColor" />
      <path d="M11 11h14M11 16h10M11 21h12" stroke="var(--color-sheet)" strokeWidth="1.8" strokeLinecap="round" />
      <rect x="22" y="22" width="15" height="13" rx="2" fill="currentColor" stroke="var(--color-sheet)" strokeWidth="1.6" />
      <path d="M25.5 22v-3a4 4 0 0 1 8 0v3" fill="none" stroke="currentColor" strokeWidth="2.2" />
      <circle cx="29.5" cy="28.5" r="1.6" fill="var(--color-sheet)" />
    </>
  ),
  // Protection: a shield, outlined.
  shield: (
    <>
      <path d="M20 4l13 5v9.5c0 8.4-5.6 14.4-13 17.8C12.6 32.9 7 26.9 7 18.5V9z" fill="none" stroke="currentColor" strokeWidth="3" strokeLinejoin="round" />
      <path d="M20 12v14" stroke="currentColor" strokeWidth="3" strokeLinecap="round" />
    </>
  ),
};

/** The punch card a worker slides into the clock at the gate (E1 of the work-counted review): the one number the law sets for
 *  a door with its unit under it, or the paper that decides the door, in the topic's colour; the notch at its top is
 *  the clock's slot. 74 × 56, the same for every door, so the rows' words line up. */
export function PunchCard({ mark, icon }: { mark: { value: string; unit: Named } | null; icon?: string }) {
  const { i18n } = useKitT();
  return (
    <span aria-hidden="true" style={CARD} className="relative flex h-14 shrink-0 flex-col items-center justify-center pt-2 text-[color:var(--t)]">
      <span style={SLOT} className="absolute -translate-x-1/2 bg-sheet" />
      {mark ? (
        <>
          <span dir="ltr" style={{ fontSize: 18 }} className="font-bold leading-none tabular-nums">{mark.value}</span>
          <span lang={i18n.language} className="mt-0.5 whitespace-nowrap text-meta font-medium leading-tight">{pick(mark.unit, i18n.language)}</span>
        </>
      ) : <KitIcon name={icon!} size={26} />}
    </span>
  );
}

/** The card's colours and the slot's cut, in styles: one-off values that the shared stylesheet need not carry. */
const EDGE = '1.5px solid color-mix(in srgb, var(--t) 45%, transparent)';
const CARD: React.CSSProperties = { width: 74, borderRadius: 9, border: EDGE, background: 'color-mix(in srgb, var(--t) 10%, var(--color-sheet))' };
const SLOT: React.CSSProperties = { top: -1.5, left: '50%', width: 12, height: 7, border: EDGE, borderTop: 0, borderRadius: '0 0 7px 7px' };

/** The price tag a shop ties to what it sells (the consumer-receipt review): the number the law sets for a door (7
 *  days, a year, 3,000 dirhams, 4 %) with its unit, or the door's pictogram, in the topic's colour; its point and its
 *  hole toward the row's start, as a tag hangs from its string. 74 × 56, the same for every door. */
export function PriceTag({ mark, icon }: { mark: { value: string; unit: Named } | null; icon?: string }) {
  const { i18n } = useKitT();
  return (
    <span aria-hidden="true" className="relative flex h-14 shrink-0 flex-col items-center justify-center text-[color:var(--t)]"
          style={{ width: 74, paddingInlineStart: 12 }}>
      <svg viewBox="0 0 74 56" className="absolute inset-0 size-full rtl:-scale-x-100" aria-hidden="true">
        <path d="M17 1.5H69a3.5 3.5 0 0 1 3.5 3.5v46a3.5 3.5 0 0 1-3.5 3.5H17L1.8 28Z" strokeWidth="1.5" strokeLinejoin="round"
              style={{ fill: 'color-mix(in srgb, var(--t) 10%, var(--color-sheet))', stroke: 'color-mix(in srgb, var(--t) 50%, transparent)' }} />
        <circle cx="14" cy="28" r="3.4" strokeWidth="1.5" style={{ fill: 'var(--color-sheet)', stroke: 'color-mix(in srgb, var(--t) 50%, transparent)' }} />
      </svg>
      {mark ? (
        <>
          <span dir="ltr" style={{ fontSize: 18 }} className="relative font-bold leading-none tabular-nums">{mark.value}</span>
          <span lang={i18n.language} className="relative mt-0.5 whitespace-nowrap text-meta font-medium leading-tight">{pick(mark.unit, i18n.language)}</span>
        </>
      ) : <span className="relative"><KitIcon name={icon!} size={24} /></span>}
    </span>
  );
}

/** The fiscal stamp (the tax review, T6): the perforated edge everyone knows tax by, bought for a passport or a
 *  certificate, around the one figure the law sets for a door (a rate, an amount, a deadline) with its unit, or the
 *  door's pictogram, in the topic's colour; a fine frame inside the teeth, as a stamp prints its value. 74 × 56, the
 *  same for every door. */
export function FiscalStamp({ mark, icon }: { mark: { value: string; unit: Named } | null; icon?: string }) {
  const { i18n } = useKitT();
  return (
    <span aria-hidden="true" className="relative flex h-14 shrink-0 flex-col items-center justify-center text-[color:var(--t)]" style={{ width: 74 }}>
      <svg viewBox="0 0 74 56" className="absolute inset-0 size-full" aria-hidden="true">
        <rect x="1" y="1" width="72" height="54" style={{ fill: 'color-mix(in srgb, var(--t) 16%, var(--color-sheet))' }} />
        {/* The teeth: bites of the row's colour along every edge, as the stamp was torn from its sheet's perforations. */}
        {TEETH.map(([cx, cy]) => <circle key={`${cx}-${cy}`} cx={cx} cy={cy} r="2.6" style={{ fill: 'var(--color-sheet)' }} />)}
        <rect x="6.5" y="6.5" width="61" height="43" fill="none" strokeWidth="1.2" style={{ stroke: 'color-mix(in srgb, var(--t) 55%, transparent)' }} />
      </svg>
      {mark ? (
        <>
          <span dir="ltr" style={{ fontSize: 18 }} className="relative font-bold leading-none tabular-nums">{mark.value}</span>
          <span lang={i18n.language} className="relative mt-0.5 whitespace-nowrap text-meta font-medium leading-tight">{pick(mark.unit, i18n.language)}</span>
        </>
      ) : <span className="relative"><KitIcon name={icon!} size={24} /></span>}
    </span>
  );
}

/** The stamp's perforations: a bite every 6 units along the 74 × 56 edge, the corners included. */
const TEETH: [number, number][] = [
  ...Array.from({ length: 13 }, (_, i) => [1 + i * 6, 1] as [number, number]),
  ...Array.from({ length: 13 }, (_, i) => [1 + i * 6, 55] as [number, number]),
  ...Array.from({ length: 8 }, (_, i) => [1, 8 + i * 6.5] as [number, number]),
  ...Array.from({ length: 8 }, (_, i) => [73, 8 + i * 6.5] as [number, number]),
];

/** The vignette (the health review, S8): the label people cut from a box of medicine, its barcode and public
 *  price, which the CNSS asks for with the feuille de soins. A cut edge inside its frame, the one figure the law sets for
 *  a door (3 months, 0 cheque, 48 hours) with its unit, or the door's pictogram, in the topic's colour; the barcode along
 *  its foot in ink. 74 × 56, the same for every door. */
export function Vignette({ mark, icon }: { mark: { value: string; unit: Named } | null; icon?: string }) {
  const { i18n } = useKitT();
  return (
    <span aria-hidden="true" className="relative flex h-14 shrink-0 flex-col items-center justify-center pb-2 text-[color:var(--t)]" style={{ width: 74 }}>
      <svg viewBox="0 0 74 56" className="absolute inset-0 size-full" aria-hidden="true">
        <rect x="0.75" y="0.75" width="72.5" height="54.5" rx="3" strokeWidth="1.5"
              style={{ fill: 'var(--color-sheet)', stroke: 'color-mix(in srgb, var(--t) 60%, transparent)' }} />
        {/* The cut line a pair of scissors follows, just inside the edge. */}
        <rect x="4" y="4" width="66" height="48" rx="2" fill="none" strokeWidth="1" strokeDasharray="3 2.5"
              style={{ stroke: 'color-mix(in srgb, var(--t) 45%, transparent)' }} />
        {/* The barcode: bars of the text's ink, uneven as a code is. */}
        {BARS.map(([x, w]) => <rect key={x} x={x} y="44" width={w} height="5" style={{ fill: 'var(--color-ink-soft)' }} />)}
      </svg>
      {mark ? (
        <>
          <span dir="ltr" style={{ fontSize: 18 }} className="relative font-bold leading-none tabular-nums">{mark.value}</span>
          <span lang={i18n.language} className="relative mt-0.5 whitespace-nowrap text-meta font-medium leading-tight">{pick(mark.unit, i18n.language)}</span>
        </>
      ) : <span className="relative"><KitIcon name={icon!} size={24} /></span>}
    </span>
  );
}

/** The vignette's barcode: its bars' starts and widths, centred along the foot. */
const BARS: [number, number][] = [
  [18, 1.2], [20.5, 0.8], [22.5, 2], [26, 0.8], [28, 1.4], [30.8, 0.8], [33, 2.2], [36.6, 0.8], [38.6, 1.2], [41, 2],
  [44.4, 0.8], [46.4, 1.4], [49, 0.8], [51, 2.2], [54.6, 0.8],
];

/** The national identity card (the papers review): the card everyone carries, drawn small, its photo at its left as
 *  on the card, the law's figure beside it, and its machine-readable line of chevrons along its foot (law 04.20, art.
 *  5). An object, so never mirrored: the card reads the same on an Arabic page. 74 × 56, the same for every door. */
export function IdCard({ mark, icon }: { mark: { value: string; unit: Named } | null; icon?: string }) {
  const { i18n } = useKitT();
  return (
    <span aria-hidden="true" className="relative block h-14 shrink-0 text-[color:var(--t)]" style={{ width: 74 }}>
      <svg viewBox="0 0 74 56" className="absolute inset-0 size-full" aria-hidden="true">
        <rect x="0.75" y="4.75" width="72.5" height="46.5" rx="5" strokeWidth="1.5"
              style={{ fill: 'color-mix(in srgb, var(--t) 9%, var(--color-sheet))', stroke: 'color-mix(in srgb, var(--t) 50%, transparent)' }} />
        {/* The photo: a head and shoulders in its frame. */}
        <rect x="5.5" y="10" width="13" height="17" rx="1.5" style={{ fill: 'color-mix(in srgb, var(--t) 20%, var(--color-sheet))' }} />
        <circle cx="12" cy="16" r="3.2" style={{ fill: 'color-mix(in srgb, var(--t) 55%, transparent)' }} />
        <path d="M6.5 27c.6-3.6 2.8-5.4 5.5-5.4s4.9 1.8 5.5 5.4z" style={{ fill: 'color-mix(in srgb, var(--t) 55%, transparent)' }} />
        {/* The machine-readable line: chevrons, as «IDMAR<<<<» runs across the card's back. */}
        <path d={CHEVRONS} fill="none" strokeWidth="1" strokeLinecap="round" strokeLinejoin="round" style={{ stroke: 'var(--color-ink-soft)' }} />
      </svg>
      <span className="absolute flex flex-col items-center justify-center" style={{ left: 20, right: 2, top: 5, bottom: 15 }}>
        {mark ? (
          <>
            <span dir="ltr" style={{ fontSize: 17 }} className="font-bold leading-none tabular-nums">{mark.value}</span>
            <span lang={i18n.language} style={{ lineHeight: 1.15 }} className="whitespace-nowrap text-meta font-medium">{pick(mark.unit, i18n.language)}</span>
          </>
        ) : <KitIcon name={icon!} size={24} />}
      </span>
    </span>
  );
}

/** Twelve chevrons «<» from the card's start to its end, along its foot. */
const CHEVRONS = Array.from({ length: 12 }, (_, i) => `M${9 + i * 5} 43.5l-2.2 1.8 2.2 1.8`).join('');

/** The company's rubber stamp (the business review): the rectangle every Moroccan business presses on its invoices
 *  and letters, its name, RC and ICE in two lines around the middle, here the one figure the law sets for a door (3
 *  months, 60 days, 41 trades) with its unit, or the door's pictogram, in the topic's ink, pressed a little askew as a
 *  hand presses it. An object, so never mirrored. 74 × 56, the same for every door. */
export function Cachet({ mark, icon }: { mark: { value: string; unit: Named } | null; icon?: string }) {
  const { i18n } = useKitT();
  return (
    <span aria-hidden="true" className="relative block h-14 shrink-0 text-[color:var(--t)]" style={{ width: 74 }}>
      <span className="absolute inset-0 flex flex-col items-center justify-center" style={{ transform: 'rotate(-3deg)' }}>
        <svg viewBox="0 0 74 56" className="absolute inset-0 size-full" aria-hidden="true">
          <rect x="2" y="4" width="70" height="48" rx="4" fill="none" strokeWidth="2" style={{ stroke: 'color-mix(in srgb, var(--t) 80%, transparent)' }} />
          <rect x="5.5" y="7.5" width="63" height="41" rx="2" fill="none" strokeWidth="0.9" style={{ stroke: 'color-mix(in srgb, var(--t) 60%, transparent)' }} />
          {/* The name line over the figure and the RC · ICE line under it, as dashes of ink. */}
          <path d="M14 13h46M18 43.5h10M32 43.5h24" strokeWidth="1.6" strokeLinecap="round" strokeDasharray="3 1.6"
                style={{ stroke: 'color-mix(in srgb, var(--t) 45%, transparent)' }} />
        </svg>
        {mark ? (
          <>
            <span dir="ltr" style={{ fontSize: 17 }} className="relative font-bold leading-none tabular-nums">{mark.value}</span>
            <span lang={i18n.language} style={{ lineHeight: 1.15 }} className="relative whitespace-nowrap text-meta font-medium">{pick(mark.unit, i18n.language)}</span>
          </>
        ) : <span className="relative"><KitIcon name={icon!} size={22} /></span>}
      </span>
    </span>
  );
}

/** The court file (the justice review): the folder every Moroccan who went to court carries a number home for, its
 *  tab at the top, the label where the registry writes «number / code / year» drawn as dashes and slashes, and on its
 *  cover the one figure the law sets for a door (48 hours, 30 days, 5.000 DH) with its unit, or the door's pictogram,
 *  in the topic's ink. An object, so never mirrored. 74 × 56, the same for every door. */
export function Dossier({ mark, icon }: { mark: { value: string; unit: Named } | null; icon?: string }) {
  const { i18n } = useKitT();
  return (
    <span aria-hidden="true" className="relative block h-14 shrink-0 text-[color:var(--t)]" style={{ width: 74 }}>
      <svg viewBox="0 0 74 56" className="absolute inset-0 size-full" aria-hidden="true">
        {/* The tab, then the cover a little in front of it. */}
        <path d="M3 9.5V5.5Q3 3 5.5 3h17l4 5" strokeWidth="1.4" strokeLinejoin="round"
              style={{ fill: 'color-mix(in srgb, var(--t) 18%, var(--color-sheet))', stroke: 'color-mix(in srgb, var(--t) 55%, transparent)' }} />
        <rect x="1.75" y="7.75" width="70.5" height="46.5" rx="3" strokeWidth="1.5"
              style={{ fill: 'color-mix(in srgb, var(--t) 7%, var(--color-sheet))', stroke: 'color-mix(in srgb, var(--t) 55%, transparent)' }} />
        {/* The registry's label: «… / … / …». */}
        <path d="M44 12.5h3.5M50 15l1.6-4M54 12.5h3.5M60 15l1.6-4M64 12.5h4" strokeWidth="1.5" strokeLinecap="round"
              style={{ stroke: 'color-mix(in srgb, var(--t) 50%, transparent)' }} />
      </svg>
      <span className="absolute flex flex-col items-center justify-center" style={{ left: 2, right: 2, top: 16, bottom: 2 }}>
        {mark ? (
          <>
            <span dir="ltr" style={{ fontSize: 17 }} className="font-bold leading-none tabular-nums">{mark.value}</span>
            <span lang={i18n.language} style={{ lineHeight: 1.15 }} className="whitespace-nowrap text-meta font-medium">{pick(mark.unit, i18n.language)}</span>
          </>
        ) : <KitIcon name={icon!} size={24} />}
      </span>
    </span>
  );
}

/** The message bubble (the digital review): the shape every Moroccan's online life runs through, its tail at the
 *  top corner where a received message starts and the two read ticks at its foot, here the one figure the law sets for
 *  a door (10 days, 20 working days, 5 years of prison) with its unit, or the door's pictogram, in the topic's ink. An
 *  object, so never mirrored. 100 × 56, the same for every door: wider than the stamp and the file, for «200.000 درهم»
 *  and «سنين حبس». */
export function Bubble({ mark, icon }: { mark: { value: string; unit: Named } | null; icon?: string }) {
  const { i18n } = useKitT();
  return (
    <span aria-hidden="true" className="relative block h-14 shrink-0 text-[color:var(--t)]" style={{ width: 100 }}>
      <svg viewBox="0 0 100 56" className="absolute inset-0 size-full" aria-hidden="true">
        <path d="M9 3h83a6 6 0 0 1 6 6v36a6 6 0 0 1-6 6H14a6 6 0 0 1-6-6V11L2 3.6Q1.2 3 2.6 3z" strokeWidth="1.5" strokeLinejoin="round"
              style={{ fill: 'color-mix(in srgb, var(--t) 9%, var(--color-sheet))', stroke: 'color-mix(in srgb, var(--t) 50%, transparent)' }} />
        {/* The two read ticks in its foot's corner, under the words. */}
        <path d="M84 47.5l1.6 1.6 3.2-3.6M87.4 49.1l3.2-3.6" fill="none" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"
              style={{ stroke: 'color-mix(in srgb, var(--t) 70%, transparent)' }} />
      </svg>
      <span className="absolute flex flex-col items-center justify-center" style={{ left: 11, right: 6, top: 3, bottom: 11 }}>
        {mark ? (
          <>
            <span dir="ltr" style={{ fontSize: 17 }} className="font-bold leading-none tabular-nums">{mark.value}</span>
            <span lang={i18n.language} style={{ lineHeight: 1.15 }} className="whitespace-nowrap text-meta font-medium">{pick(mark.unit, i18n.language)}</span>
          </>
        ) : <KitIcon name={icon!} size={24} />}
      </span>
    </span>
  );
}

/** The rent receipt's counterfoil (HM19 of the hard-moment review): the carnet every tenant is handed a slip from
 *  each month (67.12 art. 12: a signed receipt for the rent), its stub kept by the landlord behind a perforated line and
 *  the slip's ruled field «…» where the amount is written, here the one figure the law sets for a door (2 months, 8%,
 *  15 days) with its unit, or the door's pictogram, in the topic's ink. An object, so never mirrored; 110 × 56, for
 *  «شهور على الأقل». */
export function RentReceipt({ mark, icon }: { mark: { value: string; unit: Named } | null; icon?: string }) {
  const { i18n } = useKitT();
  return (
    <span aria-hidden="true" className="relative block h-14 shrink-0 text-[color:var(--t)]" style={{ width: 110 }}>
      <svg viewBox="0 0 110 56" preserveAspectRatio="none" className="absolute inset-0 size-full" aria-hidden="true">
        {/* The stub, then the slip, a perforated line between them. */}
        <rect x="1.75" y="1.75" width="106.5" height="52.5" rx="3" strokeWidth="1.5"
              style={{ fill: 'color-mix(in srgb, var(--t) 7%, var(--color-sheet))', stroke: 'color-mix(in srgb, var(--t) 55%, transparent)' }} />
        <rect x="1.75" y="1.75" width="15" height="52.5" rx="3"
              style={{ fill: 'color-mix(in srgb, var(--t) 16%, var(--color-sheet))' }} />
        <path d="M17 4v48" strokeWidth="1.4" strokeDasharray="2 2.6"
              style={{ stroke: 'color-mix(in srgb, var(--t) 60%, transparent)' }} />
        {/* The stub's own lines: the month and the number. */}
        <path d="M5.5 12h7.5M5.5 18h5M5.5 24h7" strokeWidth="1.5" strokeLinecap="round"
              style={{ stroke: 'color-mix(in srgb, var(--t) 45%, transparent)' }} />
      </svg>
      <span className="absolute flex flex-col items-center justify-center gap-0.5" style={{ left: 20, right: 4, top: 2, bottom: 2 }}>
        {mark ? (
          <>
            <span dir="ltr" style={{ fontSize: 17 }} className="font-bold leading-none tabular-nums">{mark.value}</span>
            <span lang={i18n.language} style={{ lineHeight: 1.1 }} className="text-balance text-center text-meta font-medium">{pick(mark.unit, i18n.language)}</span>
          </>
        ) : <KitIcon name={icon!} size={24} />}
      </span>
    </span>
  );
}
