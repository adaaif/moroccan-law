import type { CSSProperties } from 'react';

/** Road signs drawn from their specification (R9 of the road plan): a shape, its border and fill, and a pictogram in a
 *  100 × 100 box, as joint order 2805.14 describes them (BO 6332, French edition pp. 774–777; changed by 3106.19, BO
 *  6832). Nothing is a copied picture. Sizes and exact colours are in an «instruction générale» never published: the
 *  proportions here are approximate. Markup for an SVG's inside, built from constants only. */
const RED = 'var(--g-red)', BLUE = 'var(--g-blue)', INK = 'var(--g-ink)', WHITE = 'var(--g-white)', YEL = 'var(--g-yellow)';

const danger = (p: string) => `<path d="M50 8 L94 86 Q96 90 91 90 L9 90 Q4 90 6 86 Z" fill="${WHITE}" stroke="${RED}" stroke-width="9" stroke-linejoin="round"/>${p}`;
const ban = (p: string) => `<circle cx="50" cy="50" r="43" fill="${WHITE}" stroke="${RED}" stroke-width="9"/>${p}`;
const must = (p: string) => `<circle cx="50" cy="50" r="46" fill="${BLUE}"/>${p}`;

/** A roundabout's three arrows, turning the way traffic does on the right (counter-clockwise on screen). */
function arrows(c: string, r: number, cy: number): string {
  let out = '';
  for (let i = 0; i < 3; i++) {
    const a0 = ((-90 + i * 120 + 18) * Math.PI) / 180, a1 = ((-90 + i * 120 + 92) * Math.PI) / 180;
    const x0 = 50 + r * Math.cos(a0), y0 = cy + r * Math.sin(a0), x1 = 50 + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
    const w = r > 16 ? 7 : 5.5, s = r > 16 ? 8 : 6.5, dx = Math.sin(a0), dy = -Math.cos(a0);
    const tx = x0 + dx * s * 0.45, ty = y0 + dy * s * 0.45, bx = x0 - dx * s * 0.75, by = y0 - dy * s * 0.75;
    out += `<path d="M${x1.toFixed(1)} ${y1.toFixed(1)} A${r} ${r} 0 0 0 ${x0.toFixed(1)} ${y0.toFixed(1)}" fill="none" stroke="${c}" stroke-width="${w}" stroke-linecap="round"/>`
      + `<path d="M${(bx - dy * s * 0.85).toFixed(1)} ${(by + dx * s * 0.85).toFixed(1)} L${tx.toFixed(1)} ${ty.toFixed(1)} L${(bx + dy * s * 0.85).toFixed(1)} ${(by - dx * s * 0.85).toFixed(1)}" fill="none" stroke="${c}" stroke-width="${w - 1}" stroke-linejoin="round" stroke-linecap="round"/>`;
  }
  return out;
}

const walker = `<g fill="${INK}"><circle cx="52" cy="40" r="5.5"/><path d="M50 47 l-6 14 l-7 17 h6 l6 -14 l5 7 l2 13 h6 l-3 -16 l-5 -8 l3 -8 l6 6 h8 v-5 h-6 l-8 -10 z"/></g>`;
const speed = (n: number) => `<text x="50" y="62" text-anchor="middle" font-size="${n > 99 ? 34 : 40}" font-weight="700" fill="${INK}" font-family="Arial, sans-serif">${n}</text>`;

/** Each family's bare shape, for the signs page's heads. */
export const SHAPES = {
  danger: danger(''), ban: ban(''), must: must(''),
  priority: `<path d="M31 4 H69 L96 31 V69 L69 96 H31 L4 69 V31 Z" fill="${RED}" stroke="${WHITE}" stroke-width="4"/>`,
};

/** A limit sign for any speed (the speed tool's chips): the red ring and the number. */
export const speedSign = (n: number) => ban(speed(n));

export const SIGNS: Record<string, () => string> = {
  stop: () => `<path d="M31 4 H69 L96 31 V69 L69 96 H31 L4 69 V31 Z" fill="${RED}" stroke="${WHITE}" stroke-width="4"/>`
    + `<text x="50" y="64" text-anchor="middle" font-size="40" font-weight="700" fill="${WHITE}" font-family="var(--font-ui)">قف</text>`,
  yield: () => `<path d="M9 12 L91 12 Q96 12 94 16 L52 90 Q50 93 48 90 L6 16 Q4 12 9 12 Z" fill="${WHITE}" stroke="${RED}" stroke-width="9" stroke-linejoin="round"/>`,
  priority: () => `<rect x="17" y="17" width="66" height="66" transform="rotate(45 50 50)" fill="${WHITE}" stroke="${INK}" stroke-width="2"/>`
    + `<rect x="27" y="27" width="46" height="46" transform="rotate(45 50 50)" fill="${YEL}"/>`,
  roundaboutAhead: () => danger(arrows(INK, 13, 62)),
  walkers: () => danger(walker),
  speed60: () => ban(speed(60)),
  nopass: () => ban(`<rect x="25" y="38" width="20" height="28" rx="6" fill="${RED}"/><rect x="55" y="38" width="20" height="28" rx="6" fill="${INK}"/>`),
  noentry: () => `<circle cx="50" cy="50" r="46" fill="${RED}"/><rect x="18" y="41" width="64" height="18" rx="2" fill="${WHITE}"/>`,
  cyclelane: () => must(`<g fill="none" stroke="${WHITE}" stroke-width="5"><circle cx="31" cy="62" r="12"/><circle cx="69" cy="62" r="12"/><path d="M31 62 L44 40 H60 L69 62 M44 40 L52 62 H31" stroke-linejoin="round"/></g>`),
};

/** The colours the signs and scenes are drawn in, as the order gives them in words (red, blue, white, black, yellow). */
const SIGN_COLOURS = { '--g-red': '#c8102e', '--g-blue': '#1f5fae', '--g-ink': '#151320', '--g-white': '#ffffff', '--g-yellow': '#f6b800' };

/** The scenes' colours: the road, its lines and verge, and the three road users told apart. Fixed in both themes, as
 *  a drawing of the road is. */
export const SCENE_COLOURS = {
  '--s-asphalt': '#46434f', '--s-line': '#f4f1ea', '--s-verge': '#dfe6d6', '--s-walk': '#d9d3c9', '--s-island': '#c9dbbd',
  '--s-glass': '#cfe0ef', '--s-head': '#fff7d6', '--s-amber': '#f0a21b', '--s-skin': '#e3b48a', '--s-dark': '#2a2833',
  '--s-helmet': '#e4512f', '--s-you': '#5b3a9e', '--s-other': '#b86e00', '--s-third': '#126b60', '--s-zebra': '#f4f1ea',
  '--s-cycle': '#b9d3a8', '--s-brake': '#e0352b', '--s-siren': '#2b6fe0', ...SIGN_COLOURS,
} as CSSProperties;
