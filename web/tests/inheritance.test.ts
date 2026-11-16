// The inheritance engine against its cases (F6 of the family plan): `node --test tests/`. No package: Node's own
// runner reads the TypeScript as it is.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { compute, type Heir, type Input } from '../src/topics/family/inheritance/engine.ts';
import { eq, q, sum, type Q } from '../src/topics/family/inheritance/frac.ts';

type Case = {
  name: string; deceased: 'm' | 'f'; died?: string; counts: Input['counts']; predeceased?: Input['predeceased'];
  each: Record<string, string>; out?: string[]; base?: number; awl?: number; tashih?: number; named?: string;
  radd?: boolean; treasury?: string; bequest?: { son?: string; daughter?: string }[]; capped?: boolean; before?: boolean;
  /** The mixed forms of arts 362–363: the engine stops. */
  stop?: boolean;
  /** The bequest's total by the other reading of art. 370. */
  other?: string;
  /** The reason a line carries, by heir. */
  why?: Record<string, string>;
  /** The spouse's share without the return, or null when no spouse shares in it. */
  raddSpouse?: string | null;
};
const { cases } = JSON.parse(readFileSync(new URL('./inheritance.cases.json', import.meta.url), 'utf8')) as { cases: Case[] };
const frac = (s: string): Q => {
  const [n, d = '1'] = s.split('/');
  return q(BigInt(n), BigInt(d));
};

for (const c of cases) {
  test(c.name, () => {
    const r = compute({ deceased: c.deceased, died: c.died ?? '2026-10-12', counts: c.counts, predeceased: c.predeceased });
    if (c.before) {
      assert.equal(r.ok, false);
      return;
    }
    if (c.stop) {
      assert.ok(!r.ok && r.reason === 'mixed', 'the mixed forms of arts 362–363 are not computed');
      return;
    }
    assert.ok(r.ok);
    const got = Object.fromEntries(r.lines.map((l) => [l.heir, l.each]));
    for (const [heir, share] of Object.entries(c.each))
      assert.ok(got[heir] && eq(got[heir], frac(share)), `${heir}: ${got[heir]?.n}/${got[heir]?.d}, not ${share}`);
    assert.deepEqual(Object.keys(got).sort(), Object.keys(c.each).sort(), 'the heirs who take');
    for (const h of c.out ?? []) assert.ok(r.excluded.some((e) => e.heir === (h as Heir)), `${h} should take nothing`);
    if (c.base) assert.equal(r.base, BigInt(c.base), 'base');
    if (c.awl) assert.equal(r.awl, BigInt(c.awl), 'awl');
    if (c.tashih) assert.equal(r.tashih, BigInt(c.tashih), 'tashih');
    if (c.named) assert.equal(r.named, c.named);
    if (c.radd !== undefined) assert.equal(r.radd, c.radd, 'radd');
    if (c.treasury) assert.ok(eq(r.treasury, frac(c.treasury)), 'treasury');
    if (c.bequest) {
      assert.equal(r.bequest.length, c.bequest.length, 'bequest branches');
      c.bequest.forEach((b, i) => {
        if (b.son) assert.ok(eq(r.bequest[i].son, frac(b.son)), `bequest son ${r.bequest[i].son.n}/${r.bequest[i].son.d}`);
        if (b.daughter) assert.ok(eq(r.bequest[i].daughter, frac(b.daughter)), 'bequest daughter');
      });
    }
    if (c.capped !== undefined) assert.equal(r.capped, c.capped, 'capped');
    if (c.other) assert.ok(r.otherBequest && eq(r.otherBequest, frac(c.other)), `the other reading: ${r.otherBequest?.n}/${r.otherBequest?.d}`);
    for (const [heir, why] of Object.entries(c.why ?? {})) assert.equal(r.lines.find((l) => l.heir === heir)?.why, why, `${heir}'s reason`);
    if (c.raddSpouse === null) assert.equal(r.raddSpouse, null);
    else if (c.raddSpouse) assert.ok(r.raddSpouse && eq(r.raddSpouse.fixed, frac(c.raddSpouse)), 'the spouse without the return');
    // Everything is shared out: the heirs, the bequest and the Treasury make the whole.
    const whole = sum([
      ...r.lines.map((l) => l.share), r.treasury, ...r.bequest.map((b) => b.share),
    ]);
    assert.ok(eq(whole, q(1)), `the whole: ${whole.n}/${whole.d}`);
  });
}
