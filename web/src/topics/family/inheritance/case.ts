/** A family's case as the calculator holds it, and its code (IR12, IR16 of the inheritance review): short enough to
 *  read aloud, kept in the address after «#», which a browser never sends, so the page's promise that nothing leaves
 *  the phone holds for a link too. The code starts with the engine's version: a link made before a correction says so
 *  when it opens. Pure: the page and `node --test` read the same file. */
import { HEIRS, SINGLE, type Branch, type Counts, type Heir, type Tanzil } from './engine.ts';

/** The engine's version, said on every result. 2.0: the bequest in the Court of Cassation's reading (14 Nov 2026). */
export const ENGINE = '2.0';
const MAJOR = ENGINE.split('.')[0];

/** A will: an amount in centimes, or a part of the estate («1/3»). */
export type WillCase = { kind: 'amount' | 'part'; value: string; heir: boolean; agreed: boolean };
/** An heir who died after the deceased and before the division, with their own family (IR26). */
export type Later = { heir: Heir; counts: Counts; branches: Branch[] };

export type Case = {
  deceased: 'm' | 'f';
  /** '' for a death since 5 Feb 2004 (the rules in force); else the day (yyyy-mm-dd) or the year of an older death. */
  died: string;
  counts: Counts;
  branches: Branch[];
  /** Amounts in centimes as digits, '' when not given: what was left, then what leaves it first (art. 322). */
  estate: string; funeral: string; debts: string; dowry: string;
  will: WillCase | null;
  tanzil: Tanzil | null;
  later: Later[];
  /** The two answers that stop the tool (IR7): a child to be born; someone missing, of another religion, not
   *  recognised by the father, or who killed the deceased. */
  unborn: boolean; other: boolean;
};

export const EMPTY: Case = {
  deceased: 'm', died: '', counts: {}, branches: [], estate: '', funeral: '', debts: '', dowry: '', will: null, tanzil: null,
  later: [], unborn: false, other: false,
};

const CODE: Record<Heir, string> = {
  husband: 'h', wife: 'w', son: 's', daughter: 'd', sonsSon: 'ss', sonsDaughter: 'sd', father: 'fa', mother: 'mo',
  grandfather: 'gf', grandmotherM: 'gm', grandmotherF: 'gp', fullBrother: 'fb', fullSister: 'fs', patBrother: 'pb',
  patSister: 'ps', matBrother: 'mb', matSister: 'ms', fullNephew: 'fn', patNephew: 'pn', fullUncle: 'fu', patUncle: 'pu',
  fullCousin: 'fc', patCousin: 'pc',
};
const HEIR = Object.fromEntries(Object.entries(CODE).map(([h, c]) => [c, h])) as Record<string, Heir>;
const FEMALE: Heir[] = ['wife', 'daughter', 'sonsDaughter', 'mother', 'grandmotherM', 'grandmotherF', 'fullSister', 'patSister', 'matSister'];
export const sexOf = (h: Heir): 'm' | 'f' => (FEMALE.includes(h) ? 'f' : 'm');
/** The most there can be of a relative. */
export const most = (h: Heir): number => (SINGLE.includes(h) ? 1 : h === 'wife' ? 4 : 20);

const digits = (s: string) => (/^\d{1,15}$/.test(s) ? s : '');

function family(counts: Counts, branches: Branch[]): string[] {
  const out: string[] = [];
  for (const h of HEIRS) {
    const n = Math.min(most(h), Math.max(0, Math.floor(counts[h] ?? 0)));
    if (n) out.push(SINGLE.includes(h) ? CODE[h] : `${CODE[h]}${n}`);
  }
  for (const b of branches) out.push(`x${b.sex}${b.sons}a${b.daughters}${b.spouse ? 'w' : ''}${b.parent ? 'p' : ''}`);
  return out;
}

/** The case as its code: «v2~m~w1~d3~fb2~e80000000». An empty case has no code. */
export function encode(c: Case): string {
  const t = [`v${MAJOR}`, c.deceased, ...family(c.counts, c.branches)];
  if (c.died) t.push(`t${c.died.replaceAll('-', '')}`);
  if (c.estate) t.push(`e${c.estate}`);
  if (c.funeral) t.push(`of${c.funeral}`);
  if (c.debts) t.push(`od${c.debts}`);
  if (c.dowry) t.push(`os${c.dowry}`);
  if (c.will?.value) t.push(`${c.will.kind === 'part' ? 'op' : 'ow'}${c.will.value.replace('/', 'j')}${c.will.heir ? 'h' : ''}${c.will.agreed ? 'a' : ''}`);
  if (c.tanzil?.count) t.push(`z${c.tanzil.as === 'son' ? 's' : 'd'}${c.tanzil.count}${c.tanzil.equal ? 'e' : ''}${c.tanzil.agreed ? 'a' : ''}`);
  for (const l of c.later) t.push(['l' + CODE[l.heir], ...family(l.counts, l.branches)].join('!'));
  if (c.unborn) t.push('u');
  if (c.other) t.push('o');
  return t.length > 2 ? t.join('~') : '';
}

function readFamily(tokens: string[], counts: Counts, branches: Branch[]) {
  for (const tok of tokens) {
    const b = /^x([mf])(\d{1,2})a(\d{1,2})(w?)(p?)$/.exec(tok);
    if (b) {
      branches.push({ sex: b[1] as 'm' | 'f', sons: Math.min(20, +b[2]), daughters: Math.min(20, +b[3]), spouse: b[4] === 'w', parent: b[5] === 'p' });
      continue;
    }
    const m = /^([a-z]{1,2})(\d{0,2})$/.exec(tok);
    const h = m && HEIR[m[1]];
    if (h) counts[h] = Math.min(most(h), Math.max(1, +(m[2] || 1)));
  }
}

/** A code back into its case, with the engine's version it was made by; null when it is not one. What it does not
 *  know it leaves out: an old link opens on what it can still read. */
export function decode(code: string): { case: Case; version: string } | null {
  const tokens = code.replace(/^#/, '').split('~');
  const v = /^v(\d+)$/.exec(tokens[0] ?? '');
  if (!v || (tokens[1] !== 'm' && tokens[1] !== 'f')) return null;
  const c: Case = { ...EMPTY, deceased: tokens[1], counts: {}, branches: [], later: [] };
  const rest = tokens.slice(2);
  readFamily(rest.filter((t) => !t.includes('!')), c.counts, c.branches);
  for (const tok of rest) {
    let m: RegExpExecArray | null;
    if (tok.includes('!')) {
      const [head, ...fam] = tok.split('!');
      const h = HEIR[head.slice(1)];
      if (head[0] === 'l' && h) {
        const later: Later = { heir: h, counts: {}, branches: [] };
        readFamily(fam, later.counts, later.branches);
        c.later.push(later);
      }
    } else if ((m = /^t(\d{4})(\d{2})?(\d{2})?$/.exec(tok))) c.died = m[2] && m[3] ? `${m[1]}-${m[2]}-${m[3]}` : m[1];
    else if ((m = /^e(\d+)$/.exec(tok))) c.estate = digits(m[1]);
    else if ((m = /^of(\d+)$/.exec(tok))) c.funeral = digits(m[1]);
    else if ((m = /^od(\d+)$/.exec(tok))) c.debts = digits(m[1]);
    else if ((m = /^os(\d+)$/.exec(tok))) c.dowry = digits(m[1]);
    else if ((m = /^ow(\d+)(h?)(a?)$/.exec(tok))) c.will = { kind: 'amount', value: digits(m[1]), heir: m[2] === 'h', agreed: m[3] === 'a' };
    else if ((m = /^op(\d)j(\d{1,2})(h?)(a?)$/.exec(tok))) c.will = { kind: 'part', value: `${m[1]}/${m[2]}`, heir: m[3] === 'h', agreed: m[4] === 'a' };
    else if ((m = /^z([sd])(\d{1,2})(e?)(a?)$/.exec(tok))) c.tanzil = { as: m[1] === 's' ? 'son' : 'daughter', count: Math.min(20, +m[2]), equal: m[3] === 'e', agreed: m[4] === 'a' };
    else if (tok === 'u') c.unborn = true;
    else if (tok === 'o') c.other = true;
  }
  // A man leaves no husband, a woman no wife.
  if (c.deceased === 'm') delete c.counts.husband; else delete c.counts.wife;
  return { case: c, version: v[1] };
}

/** Whether a link was made by an older engine than this one: its figures may have changed since (IR12). */
export const older = (version: string) => Number(version) < Number(MAJOR);

/** Nobody entered yet. */
export const nobody = (c: Case) => !Object.values(c.counts).some((n) => n) && !c.branches.length;
