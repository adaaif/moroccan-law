/** The scene engine (R8, R18 of the road plan): a road drawn once in SVG, actors moving along paths by keyframes
 *  [ms, share of the path, 'lin'?], captions changing at their moment. The first still frame explains by itself; play
 *  runs the scene once; the steps go through it, the only way under reduced motion. Traffic keeps to the right in both
 *  languages: the drawing never mirrors with the page. The browser's own animation frames, no library. */
import { SIGNS } from './signs';
import { reducedMotion } from '../../kit/motion';

const NS = 'http://www.w3.org/2000/svg';
type Attrs = Record<string, string | number>;
export type El = (name: string, attrs?: Attrs, parent?: Element) => SVGElement;
export type Sign = (svg: Element, key: string, x: number, y: number, size?: number) => void;
export type Key = [number, number, 'lin'?];
export type Named = { ar: string; fr: string };
export type Actor = {
  d: string; colour: string; kind?: 'car' | 'truck' | 'walker' | 'rider' | 'ambulance'; label?: Named; tagAt?: [number, number];
  keys: Key[]; glow?: [number, number][]; signal?: { left?: [number, number][]; right?: [number, number][] };
  hazard?: [number, number][]; show?: [number, number];
  /** An emergency vehicle's blue lamps, flashing while its signals are on (decree 2.10.420 art. 39). */
  siren?: [number, number][];
};
export type SceneDef = {
  road: keyof typeof ROADS; roadOpts?: { solidTo?: number; zebraAt?: number }; height?: number; dur: number; still?: number;
  loop?: boolean; guidesTill?: number; decor?: ((svg: Element, el: El, sign: Sign) => void)[];
  guides?: [string, string][]; flags?: { at: [number, number]; draw: (g: Element, el: El) => void }[];
  actors: Actor[];
  /** A step's caption; `zoom` eases the camera onto a part of the drawing ([x, y, w, h]) while it is told. */
  steps: ({ t: number; hold?: number; zoom?: [number, number, number, number] } & Named)[];
};

export const el: El = (name, attrs = {}, parent) => {
  const e = document.createElementNS(NS, name);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, String(v));
  parent?.appendChild(e);
  return e;
};

const sign: Sign = (svg, key, x, y, size = 30) => {
  el('g', { transform: `translate(${x - size / 2},${y - size / 2}) scale(${size / 100})` }, svg).innerHTML = SIGNS[key]();
};

type Lamps = { g: SVGElement; left: SVGElement[]; right: SVGElement[]; brake: SVGElement[]; blue: SVGElement[] };

/** A vehicle seen from above, pointing along +x; in its own frame +y is its right-hand side. */
function vehicle(parent: Element, colour: string, truck: boolean, ambulance = false): Lamps {
  const g = el('g', {}, parent);
  const L = truck ? 58 : 40, W = truck ? 24 : 20;
  if (truck) {
    el('rect', { x: -L / 2, y: -W / 2, width: L - 16, height: W, rx: 3, fill: colour }, g);
    el('rect', { x: L / 2 - 15, y: -W / 2 + 1, width: 15, height: W - 2, rx: 4, fill: colour, opacity: 0.85 }, g);
  } else {
    el('rect', { x: -L / 2, y: -W / 2, width: L, height: W, rx: 6, fill: colour }, g);
    el('rect', { x: -L / 2 + 5, y: -W / 2 + 3, width: 6, height: W - 6, rx: 2, fill: 'var(--s-glass)' }, g);
  }
  el('rect', { x: L / 2 - (truck ? 8 : 15), y: -W / 2 + (truck ? 4 : 3), width: truck ? 5 : 7, height: W - (truck ? 8 : 6), rx: 2, fill: 'var(--s-glass)' }, g);
  for (const y of [-W / 2 + 3, W / 2 - 3]) el('circle', { cx: L / 2 - 1, cy: y, r: 2, fill: 'var(--s-head)' }, g);
  if (ambulance) {
    el('rect', { x: -6, y: -2, width: 12, height: 4, fill: 'var(--g-red)' }, g);
    el('rect', { x: -2, y: -6, width: 4, height: 12, fill: 'var(--g-red)' }, g);
  }
  const lamp = (x: number, y: number) => el('circle', { cx: x, cy: y, r: 3, fill: 'var(--s-amber)', opacity: 0 }, g);
  // Brake lamps at the back, lit while the vehicle slows or waits (S3 of the road tools review): drivers read them first.
  const brake = [-W / 2 + 3, W / 2 - 3].map((y) => el('rect', { x: -L / 2 - 1, y: y - 2.5, width: 3, height: 5, rx: 1, fill: 'var(--s-brake)', opacity: 0 }, g));
  const blue = ambulance ? [-4, 4].map((y) => el('circle', { cx: 0, cy: y, r: 3.2, fill: 'var(--s-siren)', opacity: 0 }, g)) : [];
  return { g, left: [lamp(L / 2 - 2, -W / 2 + 1), lamp(-L / 2 + 2, -W / 2 + 1)], right: [lamp(L / 2 - 2, W / 2 - 1), lamp(-L / 2 + 2, W / 2 - 1)], brake, blue };
}

function person(parent: Element, colour: string, rides: boolean): Lamps {
  const g = el('g', {}, parent);
  if (rides) {
    const r = el('g', { transform: 'scale(1.5)' }, g);
    el('rect', { x: -12, y: -2.5, width: 24, height: 5, rx: 2.5, fill: 'var(--s-dark)' }, r);
    el('ellipse', { cx: -2, cy: 0, rx: 5, ry: 7, fill: colour }, r);
    el('circle', { cx: -1, cy: 0, r: 4, fill: 'var(--s-helmet)' }, r);
  } else {
    el('ellipse', { cx: 0, cy: 0, rx: 5.5, ry: 8, fill: colour }, g);
    el('circle', { cx: 0, cy: 0, r: 3.8, fill: 'var(--s-skin)' }, g);
  }
  return { g, left: [], right: [], brake: [], blue: [] };
}

export const ROADS = {
  crossroads(svg: Element) {
    el('rect', { x: 0, y: 82, width: 360, height: 76, fill: 'var(--s-walk)' }, svg);
    el('rect', { x: 142, y: 0, width: 76, height: 240, fill: 'var(--s-walk)' }, svg);
    el('rect', { x: 0, y: 90, width: 360, height: 60, fill: 'var(--s-asphalt)' }, svg);
    el('rect', { x: 150, y: 0, width: 60, height: 240, fill: 'var(--s-asphalt)' }, svg);
    el('path', { d: 'M0 120 H146 M214 120 H360 M180 0 V86 M180 154 V240', stroke: 'var(--s-line)', 'stroke-width': 2, 'stroke-dasharray': '10 9' }, svg);
  },
  roundabout(svg: Element) {
    el('rect', { x: 0, y: 90, width: 360, height: 60, fill: 'var(--s-asphalt)' }, svg);
    el('rect', { x: 150, y: 0, width: 60, height: 240, fill: 'var(--s-asphalt)' }, svg);
    el('circle', { cx: 180, cy: 120, r: 72, fill: 'var(--s-asphalt)' }, svg);
    el('circle', { cx: 180, cy: 120, r: 38, fill: 'var(--s-island)', stroke: 'var(--s-line)', 'stroke-width': 2 }, svg);
    el('path', { d: 'M0 120 H104 M256 120 H360 M180 0 V44 M180 196 V240', stroke: 'var(--s-line)', 'stroke-width': 2, 'stroke-dasharray': '10 9' }, svg);
    for (const d of ['M182 194 H208', 'M152 46 H178', 'M106 92 V118', 'M254 122 V148'])
      el('path', { d, stroke: 'var(--s-line)', 'stroke-width': 3, 'stroke-dasharray': '4 4' }, svg);
  },
  street(svg: Element) {
    el('rect', { x: 0, y: 24, width: 360, height: 70, fill: 'var(--s-asphalt)' }, svg);
    el('path', { d: 'M0 59 H360', stroke: 'var(--s-line)', 'stroke-width': 2, 'stroke-dasharray': '12 10' }, svg);
    el('rect', { x: 0, y: 94, width: 360, height: 26, fill: 'var(--s-cycle)' }, svg);
    el('path', { d: 'M0 94 H360', stroke: 'var(--s-line)', 'stroke-width': 2 }, svg);
    el('rect', { x: 0, y: 120, width: 360, height: 30, fill: 'var(--s-walk)' }, svg);
  },
  road(svg: Element, { solidTo = 0, zebraAt = 0 }: { solidTo?: number; zebraAt?: number } = {}) {
    el('rect', { x: 0, y: 72, width: 360, height: 96, fill: 'var(--s-walk)' }, svg);
    el('rect', { x: 0, y: 80, width: 360, height: 80, fill: 'var(--s-asphalt)' }, svg);
    if (solidTo) el('path', { d: `M0 120 H${solidTo}`, stroke: 'var(--s-line)', 'stroke-width': 3 }, svg);
    el('path', { d: `M${solidTo} 120 H360`, stroke: 'var(--s-line)', 'stroke-width': 2.5, 'stroke-dasharray': '12 10' }, svg);
    if (zebraAt) for (let y = 84; y < 158; y += 12) el('rect', { x: zebraAt - 12, y, width: 24, height: 7, fill: 'var(--s-zebra)' }, svg);
  },
};

const ease = (t: number) => (t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2);
function shareAt(keys: Key[], t: number): number {
  if (t <= keys[0][0]) return keys[0][1];
  for (let i = 1; i < keys.length; i++) {
    const [t1, s1, how] = keys[i], [t0, s0] = keys[i - 1];
    if (t <= t1) {
      const f = (t - t0) / Math.max(1, t1 - t0);
      return s0 + (s1 - s0) * (how === 'lin' ? f : ease(f));
    }
  }
  return keys[keys.length - 1][1];
}
const within = (spans: [number, number][] | undefined, t: number) => (spans ?? []).some(([a, b]) => t >= a && t <= b);

export type Controller = {
  show: (t: number) => void; play: (rate?: number) => void; halt: () => void; stepAt: (i: number) => number; dur: number;
  playing: () => boolean;
  /** Where an actor is drawn now, in the drawing's units: a tap on it answers the scene's question. */
  where: (i: number) => { x: number; y: number } | null;
};

/** Draws `def` into `svg` and returns what moves it; `onStep` hears the caption's index, `onEnd` the end. */
export function mount(svg: SVGSVGElement, def: SceneDef, lang: 'ar' | 'fr', onStep: (i: number) => void, onEnd: () => void,
                      onTime?: (t: number) => void): Controller {
  svg.replaceChildren();
  svg.setAttribute('viewBox', `0 0 360 ${def.height ?? 240}`);
  el('rect', { width: 360, height: def.height ?? 240, fill: 'var(--s-verge)' }, svg);
  ROADS[def.road](svg, def.roadOpts);
  def.decor?.forEach((d) => d(svg, el, sign));
  const guides = el('g', {}, svg);
  def.guides?.forEach(([d, c]) => el('path', { d, stroke: c, 'stroke-width': 2.5, 'stroke-dasharray': '3 5', fill: 'none', opacity: 0.6 }, guides));
  const flags = (def.flags ?? []).map((f) => { const g = el('g', { opacity: 0 }, svg); f.draw(g, el); return { g, at: f.at }; });
  const layer = el('g', {}, svg);
  const actors = def.actors.map((a) => {
    const path = el('path', { d: a.d, fill: 'none' }, svg) as SVGPathElement;
    const halo = a.glow ? el('circle', { r: 31, fill: 'none', stroke: 'var(--s-amber)', 'stroke-width': 3, opacity: 0 }, layer) : null;
    const trail = a.kind === 'walker' ? null : el('path', { fill: 'none', stroke: a.colour, 'stroke-width': 7, 'stroke-linecap': 'round', opacity: 0.18 }, layer);
    const v = a.kind === 'walker' || a.kind === 'rider' ? person(layer, a.colour, a.kind === 'rider') : vehicle(layer, a.colour, a.kind === 'truck', a.kind === 'ambulance');
    let tag: SVGElement | null = null;
    const label = a.label?.[lang];
    if (label) {
      tag = el('g', {}, layer);
      const w = 14 + label.length * (lang === 'fr' ? 5.6 : 6.4);
      el('rect', { x: -w / 2, y: -10, width: w, height: 19, rx: 9.5, fill: a.colour }, tag);
      el('text', { x: 0, y: 4, 'text-anchor': 'middle', 'font-size': 11, 'font-weight': 600, fill: '#fff' }, tag).textContent = label;
    }
    return { a, path, v, tag, halo, trail, seen: [] as string[], len: path.getTotalLength() };
  });
  let raf = 0, t0 = 0, now = 0, k = -1, rate = 1, playing = false;
  const full: [number, number, number, number] = [0, 0, 360, def.height ?? 240];
  let view = full, viewRaf = 0;
  /** The camera eases onto a step's part of the drawing (S3): the viewBox, over half a second. */
  function aim(to: [number, number, number, number]) {
    cancelAnimationFrame(viewRaf);
    const from = view, t1 = performance.now(), d = reducedMotion() ? 0 : 520;
    const go = (ts: number) => {
      const f = d ? Math.min(1, (ts - t1) / d) : 1, e = ease(f);
      view = from.map((x, i) => x + (to[i] - x) * e) as typeof view;
      svg.setAttribute('viewBox', view.map((x) => x.toFixed(1)).join(' '));
      if (f < 1) viewRaf = requestAnimationFrame(go);
    };
    viewRaf = requestAnimationFrame(go);
  }
  function show(t: number, jumped = true) {
    now = t;
    for (const actor of actors) {
      const { a, path, v, tag, halo, len, trail } = actor;
      const at = (x: number) => Math.min(Math.max(shareAt(a.keys, x), 0), 1);
      const l = at(t) * len;
      // Slowing or waiting after having moved: the brake lamps are lit.
      const before = at(t - 180), after = at(t + 180), moved = at(t) - at(0) > 0.001 || t < (a.keys[a.keys.length - 1]?.[0] ?? 0);
      const braking = moved && at(t) < 1 && (after - at(t) < (at(t) - before) * 0.8 - 0.0004 || (after - at(t) < 0.0003 && t > a.keys[0][0]));
      v.brake.forEach((c) => c.setAttribute('opacity', braking ? '1' : '0'));
      v.blue.forEach((c, i) => c.setAttribute('opacity', within(a.siren, t) && Math.floor(t / 220) % 2 === i ? '1' : '0.15'));
      const p = path.getPointAtLength(l), q = path.getPointAtLength(Math.min(len, l + 0.6)), r = path.getPointAtLength(Math.max(0, l - 0.6));
      v.g.setAttribute('transform', `translate(${p.x.toFixed(1)},${p.y.toFixed(1)}) rotate(${((Math.atan2(q.y - r.y, q.x - r.x) * 180) / Math.PI).toFixed(1)})`);
      tag?.setAttribute('transform', `translate(${(p.x + (a.tagAt?.[0] ?? 0)).toFixed(1)},${(p.y + (a.tagAt?.[1] ?? -24)).toFixed(1)})`);
      if (halo) { halo.setAttribute('cx', p.x.toFixed(1)); halo.setAttribute('cy', p.y.toFixed(1)); halo.setAttribute('opacity', within(a.glow, t) ? '1' : '0'); }
      v.left.forEach((c) => c.setAttribute('opacity', within(a.signal?.left, t) || within(a.hazard, t) ? '1' : '0'));
      v.right.forEach((c) => c.setAttribute('opacity', within(a.signal?.right, t) || within(a.hazard, t) ? '1' : '0'));
      if (a.show) { const o = within([a.show], t) ? '1' : '0'; v.g.setAttribute('opacity', o); tag?.setAttribute('opacity', o); }
      // A short trail behind what moves while the scene plays; a jump on the scrubber clears it.
      if (trail) {
        if (jumped || reducedMotion()) actor.seen = [];
        else if (after > before) actor.seen = [...actor.seen.slice(-7), `${p.x.toFixed(1)} ${p.y.toFixed(1)}`];
        trail.setAttribute('d', actor.seen.length > 1 ? `M${actor.seen.join(' L')}` : '');
      }
    }
    guides.setAttribute('opacity', t < (def.guidesTill ?? 900) || t === (def.still ?? 0) ? '1' : '0');
    for (const f of flags) f.g.setAttribute('opacity', within([f.at], t) ? '1' : '0');
    const step = def.steps.reduce((acc, s, i) => (t >= s.t ? i : acc), 0);
    if (step !== k) { k = step; onStep(step); aim(def.steps[step].zoom ?? full); }
    onTime?.(t);
  }
  function frame(ts: number) {
    if (!t0) t0 = ts - now / rate;
    const t = (ts - t0) * rate;
    show(Math.min(t, def.dur), false);
    if (t < def.dur) raf = requestAnimationFrame(frame);
    else if (def.loop) { now = 0; t0 = 0; raf = requestAnimationFrame(frame); }
    else { raf = 0; playing = false; onEnd(); }
  }
  const halt = () => { cancelAnimationFrame(raf); raf = 0; t0 = 0; playing = false; };
  show(def.still ?? 0);
  return {
    show: (t) => { halt(); show(t); },
    play: (r = 1) => { halt(); rate = r; playing = true; if (now >= def.dur || now === (def.still ?? 0)) now = 0; raf = requestAnimationFrame(frame); },
    halt,
    stepAt: (i) => def.steps[i].t + (def.steps[i].hold ?? 300),
    dur: def.dur,
    playing: () => playing,
    where: (i) => {
      const x = actors[i];
      if (!x) return null;
      const pt = x.path.getPointAtLength(Math.min(Math.max(shareAt(x.a.keys, now), 0), 1) * x.len);
      return { x: pt.x, y: pt.y };
    },
  };
}
