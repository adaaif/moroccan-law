import { PATH, RULES, type MeasureName } from '@/shared/analytics/measures';

/** The registry's rules applied before a batch leaves (the analytics review, 15 Nov 2026): the door refuses a whole
 *  batch for one value outside them, so each event is made to fit here, never sent to be refused. A property the
 *  registry does not list for the name, or whose value its rule refuses, is left out; a number outside its range is
 *  held at its end (the top band reads as that much or more). The rules are measures.ts's, written from the registry. */

type Rule =
  | { type: 'bool' }
  | { type: 'choice'; values: readonly string[] }
  | { type: 'number'; lo: number; hi: number; step: number }
  | { type: 'pattern'; pattern: string; most: number; lower: boolean };

const patterns = new Map<string, RegExp>();
function re(source: string): RegExp {
  let compiled = patterns.get(source);
  if (!compiled) patterns.set(source, (compiled = new RegExp(source)));
  return compiled;
}

/** A value as its rule keeps it, or undefined when the rule refuses it. */
function kept(rule: Rule, value: unknown): unknown {
  switch (rule.type) {
    case 'bool':
      return typeof value === 'boolean' ? value : undefined;
    case 'choice':
      return typeof value === 'string' && rule.values.includes(value) ? value : undefined;
    case 'number':
      return typeof value === 'number' && Number.isFinite(value) ? Math.min(rule.hi, Math.max(rule.lo, value)) : undefined;
    case 'pattern': {
      if (typeof value !== 'string') return undefined;
      const v = rule.lower ? value.toLowerCase() : value;
      return v.length > 0 && v.length <= rule.most && re(rule.pattern).test(v) ? v : undefined;
    }
  }
}

/** A measure's properties as the door accepts them. */
export function fit(name: MeasureName, props: Record<string, unknown> | undefined): Record<string, unknown> {
  const rules = RULES[name] as Record<string, Rule>;
  const out: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(props ?? {})) {
    const v = Object.hasOwn(rules, key) ? kept(rules[key], value) : undefined;
    if (v !== undefined) out[key] = v;
  }
  return out;
}

/** An address as the door accepts it: without its query and fragment, then cut back a segment at a time until it
 *  reads (an address with letters the pattern has no room for, «/places/%D8%…», counts as its page above). */
export function fitPath(path: string): string {
  let p = path.split(/[?#]/)[0];
  while (p.length > 1 && !re(PATH).test(p)) p = p.slice(0, p.lastIndexOf('/')) || '/';
  return re(PATH).test(p) ? p : '/';
}
