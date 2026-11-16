import type { CSSProperties, ReactNode } from 'react';
import { topicColour } from './colour';

/* The topics' covers (P19 of the polish review): one flat style, each topic's colour in tones, people where the topic is
   about people. Drawn on a 320 × 160 grid in code, so they come with their page and follow the night; a first set,
   until an illustrator draws the real one. */

const tone = (share: number, base = 'var(--color-sheet)'): CSSProperties => ({ fill: `color-mix(in srgb, var(--t) ${share}%, ${base})` });
const PALE = tone(16);
const MID = tone(42);
const FULL: CSSProperties = { fill: 'var(--t)' };
const DEEP = tone(62, 'var(--color-ink)');
const SHEET: CSSProperties = { fill: 'var(--color-sheet)' };

/** A person standing, feet at (x, y), `s` their size: a head and shoulders, nothing more. */
function Person({ x, y, s = 1, look = DEEP }: { x: number; y: number; s?: number; look?: CSSProperties }) {
  return (
    <g style={look}>
      <circle cx={x} cy={y - 40 * s} r={8 * s} />
      <path d={`M${x - 11 * s} ${y}v${-18 * s}a${11 * s} ${11 * s} 0 0 1 ${22 * s} 0v${18 * s}z`} />
    </g>
  );
}

const Ground = ({ look = MID }: { look?: CSSProperties }) => <path style={look} d="M0 130q80-16 160-4t160-8v42H0z" />;

const SCENES: Record<string, ReactNode> = {
  family: (
    <>
      <Ground />
      <path style={MID} d="M96 130V78l64-42 64 42v52z" />
      <path style={SHEET} d="M150 130v-24a10 10 0 0 1 20 0v24z" opacity="0.6" />
      <Person x={124} y={132} s={1.35} />
      <Person x={198} y={132} s={1.25} look={FULL} />
      <Person x={161} y={134} s={0.8} look={FULL} />
      <path style={FULL} d="M160 52c-4-6-14-4-12 4 2 5 12 11 12 11s10-6 12-11c2-8-8-10-12-4z" />
    </>
  ),
  work: (
    <>
      <Ground />
      <path style={MID} d="M192 130V44h88v86z" />
      {[0, 1, 2].map((r) => [0, 1, 2].map((c) => <rect key={`${r}${c}`} style={PALE} x={204 + c * 26} y={56 + r * 22} width="14" height="12" rx="2" />))}
      <Person x={112} y={132} s={1.5} />
      <rect style={FULL} x="128" y="98" width="34" height="26" rx="4" />
      <path d="M138 98v-6h14v6" fill="none" stroke="var(--t)" strokeWidth="4" strokeLinejoin="round" />
    </>
  ),
  housing: (
    <>
      <Ground />
      <rect style={MID} x="40" y="40" width="74" height="90" rx="3" />
      {[0, 1, 2].map((r) => [0, 1].map((c) => <rect key={`${r}${c}`} style={PALE} x={52 + c * 32} y={52 + r * 24} width="18" height="14" rx="2" />))}
      <path style={FULL} d="M150 130V82l50-38 50 38v48z" />
      <rect style={DEEP} x="188" y="98" width="24" height="32" rx="3" />
      <g style={DEEP}>
        <circle cx="276" cy="70" r="14" />
        <path d="M268 80h8v36l-4 4-4-4z" />
      </g>
      <circle style={PALE} cx="276" cy="66" r="5" />
    </>
  ),
  // The road itself running away to the sun (A6 of the road-signposted review: through the arch, the car's front had read as a
  // chest), its centre line dashed, a warning sign at its side.
  road: (
    <>
      <circle style={MID} cx="160" cy="70" r="20" />
      <path style={PALE} d="M0 96q60-10 120-4h80q60-6 120 4v64H0z" />
      <path style={DEEP} d="M148 92h24l116 68H32z" />
      <path style={SHEET} d="M159.3 98h1.4l.5 6h-2.4zM158.6 110h2.8l.8 9h-4.4zM157.5 127h5l1.3 15h-7.6zM156.2 150h7.6l.8 10h-9.2z" />
      <rect style={DEEP} x="252" y="70" width="6" height="58" rx="2" />
      <path style={FULL} d="M255 36l24 40h-48z" />
      <path style={SHEET} d="M255 50l12 20h-24z" />
    </>
  ),
  consumer: (
    <>
      <Ground />
      <rect style={MID} x="40" y="56" width="140" height="74" />
      <path style={FULL} d="M32 42h156l-8 22H40z" />
      {[0, 1, 2, 3].map((i) => <path key={i} style={PALE} d={`M${48 + i * 34} 42h17l-2 22h-15z`} />)}
      <rect style={PALE} x="58" y="78" width="40" height="30" rx="3" />
      <path d="M206 72h12l12 40h44l10-30h-60" fill="none" stroke="var(--color-ink)" strokeOpacity="0.7" strokeWidth="5" strokeLinejoin="round" strokeLinecap="round" />
      <circle style={DEEP} cx="236" cy="124" r="6" />
      <circle style={DEEP} cx="268" cy="124" r="6" />
      <path style={FULL} d="M236 84h40l-6 22h-30z" />
    </>
  ),
  // The land (the land review, M2): a plot on the hill as a surveyor draws it, its outline in the decrees' red and
  // its stones at the corners; a tree at its edge.
  land: (
    <>
      <circle style={MID} cx="262" cy="40" r="18" />
      <path style={MID} d="M0 116q70-30 150-10t170-12v66H0z" />
      <path style={FULL} d="M0 140q90-20 170-6t150-6v32H0z" />
      <path d="M112 80 192 72 206 120 104 128Z" strokeWidth="3" strokeLinejoin="round" style={{ ...tone(30), stroke: 'var(--color-sign-red)' }} />
      {[[112, 80], [192, 72], [206, 120], [104, 128]].map(([x, y]) => <circle key={x} cx={x} cy={y} r="5.5" strokeWidth="3" style={{ ...SHEET, stroke: 'var(--color-sign-red)' }} />)}
      <rect style={DEEP} x="238" y="88" width="6" height="34" rx="3" />
      <circle style={FULL} cx="241" cy="80" r="16" />
    </>
  ),
  tax: (
    <>
      <Ground />
      <path style={SHEET} d="M70 24h110v106l-11-7-11 7-11-7-11 7-11-7-11 7-11-7-11 7-11-7z" />
      <path d="M70 24h110v106l-11-7-11 7-11-7-11 7-11-7-11 7-11-7-11 7-11-7-11 7z" fill="none" stroke="var(--t)" strokeWidth="3" strokeLinejoin="round" />
      {[0, 1, 2, 3].map((i) => <rect key={i} style={i === 3 ? FULL : MID} x="86" y={42 + i * 18} width={i === 3 ? 50 : 78} height="7" rx="3.5" />)}
      {[0, 1, 2, 3].map((i) => <ellipse key={i} style={i % 2 ? MID : FULL} cx="240" cy={120 - i * 12} rx="34" ry="10" />)}
      <ellipse style={DEEP} cx="240" cy="84" rx="34" ry="10" />
      <text x="240" y="89" textAnchor="middle" fontSize="14" fontWeight="700" style={PALE}>%</text>
    </>
  ),
  health: (
    <>
      <Ground />
      {/* The health review (S8): a box of medicine, its cross, and the label people cut from it for the feuille de
          soins: the cut edge dashed, the barcode under the price. */}
      <path style={PALE} d="M162 62l14-14h108l-14 14z" />
      <path style={MID} d="M270 62l14-14v70l-14 14z" />
      <rect style={MID} x="162" y="62" width="108" height="70" rx="3" />
      <path style={FULL} d="M176 70h8v8h8v8h-8v8h-8v-8h-8v-8h8z" />
      <rect style={SHEET} x="200" y="78" width="60" height="44" rx="3" />
      <rect x="204" y="82" width="52" height="36" rx="2" fill="none" stroke="var(--t)" strokeWidth="1.6" strokeDasharray="4 3" />
      <rect style={FULL} x="210" y="88" width="30" height="5" rx="2" />
      {[212, 216, 219, 224, 227, 231, 236, 239, 244].map((x, i) => <rect key={x} style={FULL} x={x} y="100" width={i % 3 === 0 ? 2.4 : 1.4} height="12" />)}
      <Person x={96} y={132} s={1.45} />
      <path style={FULL} d="M96 44c-6-9-22-6-18 6 3 8 18 17 18 17s15-9 18-17c4-12-12-15-18-6z" />
    </>
  ),
  papers: (
    <>
      <Ground />
      <rect style={SHEET} x="168" y="22" width="96" height="112" rx="6" />
      <rect x="168" y="22" width="96" height="112" rx="6" fill="none" stroke="var(--t)" strokeWidth="3" />
      {[0, 1, 2, 3].map((i) => <rect key={i} style={MID} x="182" y={40 + i * 16} width={i === 3 ? 40 : 68} height="6" rx="3" />)}
      <circle cx="238" cy="112" r="14" fill="none" stroke="var(--t)" strokeWidth="3" />
      <rect style={FULL} x="48" y="56" width="130" height="80" rx="10" />
      <circle style={PALE} cx="82" cy="90" r="16" />
      <path style={PALE} d="M66 122a16 16 0 0 1 32 0z" />
      {[0, 1, 2].map((i) => <rect key={i} style={PALE} x="110" y={78 + i * 14} width={i === 2 ? 34 : 54} height="6" rx="3" />)}
    </>
  ),
  business: (
    <>
      <Ground />
      <rect style={MID} x="96" y="58" width="168" height="72" />
      <path style={FULL} d="M88 40h184v20H88z" />
      <path style={FULL} d="M88 60h184l-2 4a12 12 0 0 1-22 0 12 12 0 0 1-23 0 12 12 0 0 1-23 0 12 12 0 0 1-23 0 12 12 0 0 1-23 0 12 12 0 0 1-23 0 12 12 0 0 1-23 0 12 12 0 0 1-23 0z" />
      <rect style={DEEP} x="164" y="88" width="32" height="42" rx="3" />
      <rect style={PALE} x="112" y="86" width="38" height="28" rx="3" />
      <rect style={PALE} x="210" y="86" width="38" height="28" rx="3" />
      <Person x={56} y={132} s={1.3} look={FULL} />
    </>
  ),
  justice: (
    <>
      <Ground />
      <path style={MID} d="M60 58 160 22l100 36z" />
      <rect style={MID} x="60" y="58" width="200" height="10" />
      {[0, 1, 2, 3, 4].map((i) => <rect key={i} style={PALE} x={74 + i * 40} y="72" width="14" height="52" />)}
      <rect style={MID} x="52" y="122" width="216" height="10" />
      <g style={DEEP}>
        <rect x="157" y="38" width="6" height="58" rx="3" />
        <rect x="118" y="44" width="84" height="5" rx="2.5" />
        <path d="M120 49 108 76h24zM200 49l-12 27h24z" opacity="0.35" />
      </g>
      <path style={FULL} d="M104 76h32a16 9 0 0 1-32 0zM184 76h32a16 9 0 0 1-32 0z" />
    </>
  ),
  digital: (
    <>
      <Ground />
      <rect style={DEEP} x="70" y="34" width="150" height="92" rx="8" />
      <rect style={FULL} x="80" y="44" width="130" height="72" rx="3" />
      <path style={DEEP} d="M56 126h178l-10 8H66z" />
      <rect style={MID} x="236" y="58" width="44" height="76" rx="8" />
      <rect style={PALE} x="242" y="66" width="32" height="56" rx="3" />
      <path d="M133 74v-8a12 12 0 0 1 24 0v8" fill="none" stroke="var(--color-sheet)" strokeWidth="5" />
      <rect style={SHEET} x="126" y="72" width="38" height="30" rx="5" />
      <circle style={FULL} cx="145" cy="86" r="5" />
    </>
  ),
};

/** A topic's scene on its pale tone, on the 320 × 160 grid (the cover's band, and the arch's window: U1). */
export function Scene({ slug }: { slug: string }) {
  return (
    <>
      <rect width="320" height="160" style={PALE} />
      {SCENES[slug] ?? SCENES.papers}
    </>
  );
}

/** A topic's cover: its scene, in a band as wide as its place (`className` sets the height). */
export function TopicCover({ slug, className = '' }: { slug: string; className?: string }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 320 160" preserveAspectRatio="xMidYMax slice" style={topicColour(slug)}
         className={`block w-full ${className}`}>
      <Scene slug={slug} />
    </svg>
  );
}
