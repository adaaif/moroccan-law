import type { CSSProperties, ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Note } from '@/shared/components/ui';
import { sexOf, type Case } from '../case';
import type { Cite, Line } from '../engine';
import { ONE, div, q } from '../frac';
import { inMillions } from '../money';
import Cites from '../parts/Cites';
import { RulesContext, treasuryCites } from '../parts/rules';
import { percent, sayShare } from '../parts/say';
import type { Share } from '../solve';
import { DeceasedContext, useT } from '../strings';
import {
  BEQUEST_ARTS, CHOICES, branchName, outWords, colourOf, groupName, laterName, lineName, money, partsOf, shareWords, swatchKey,
  type Ok, type Part,
} from './words';

/** The answer for the family (IR18, IR4, IR5, IR21 of the inheritance review): what was left and what leaves it
 *  first, the estate as one bar read left to right with every part named, the compulsory bequest said once before the
 *  heirs, a will and a «تنزيل», then one line a person: who, the share in words and out of the one number, the
 *  dirhams, the percentage, the reason under it. The total adds up to the estate shared, to the centime. */
export default function Family({ c, a }: { c: Case; a: Ok }) {
  const { t, i18n } = useT();
  const lang = i18n.language;
  const r = a.result;
  const m = money(a, t, lang);
  // The fixed shares add up to more than the estate; the Akdariyya says its own shares (art. 361).
  const shrunk = Boolean(r.awl) && r.named !== 'akdariyya';
  const parts = partsOf(a, c, t, i18n.language);
  const colours = colourOf(parts);
  const swatch = (s: Share) => colours[swatchKey(s)];
  const heirs = a.shares.filter((s) => s.group === 'heir' || s.group === 'treasury');
  const lineOf = (s: Share): Line | undefined => r.lines.find((l) => l.heir === s.heir);
  const leftWhole = r.left.n === r.left.d;
  // One heir alone, who takes the rest too (art. 349 §6: «فإذا وجد وارث واحد بالفرض رد عليه الباقي»).
  const alone = r.lines.length === 1 && r.lines[0].count === 1 ? r.lines[0] : null;
  return (
    <div className="flex flex-col gap-5">
      {a.money ? <Estate a={a} /> : null}
      {parts.length > 1 ? <Bar parts={parts} colours={colours} /> : null}

      {r.bequest.length ? (
        <Block title={t('answer.bequest.heading')}>
          {r.bequest.map((b, n) => (
            <div key={n} className="flex flex-col gap-2 border-s-[3px] ps-4" style={{ borderColor: 'var(--t)' }}>
              <p className="m-0 text-body font-semibold">{branchName(b, n, r.bequest, c.deceased, t)}</p>
              <p className="m-0 text-body">{t(`answer.bequest.parent_${b.sex}`, { share: sayShare(b.parent, t), money: m.paren(b.parent) })}</p>
              <p className="m-0 text-body">{t(`answer.bequest.part_${b.sex}`, { part: sayShare(b.part, t), share: sayShare(b.share, t), money: m.paren(b.share) })}</p>
              <Rows>
                {a.shares.filter((s) => s.group === 'bequest' && s.key.startsWith(`b${n}.`)).map((s) => (
                  <Row key={s.key} s={s} a={a} swatch={swatch(s)} />
                ))}
              </Rows>
            </div>
          ))}
          {r.capped ? <p className="m-0 text-body">{t('answer.bequest.capped')}</p> : null}
          <p className="m-0 text-meta text-ink-soft">{t('answer.bequest.court')}</p>
          {r.otherBequest ? (
            <p className="m-0 text-meta text-ink-soft">
              {t('answer.bequest.other', { share: sayShare(r.otherBequest, t), money: m.paren(r.otherBequest) })}{' '}
              <Link to={`${CHOICES}#bequest`} className="font-medium">{t('answer.bequest.why')}</Link>
            </p>
          ) : null}
          <Cites today={BEQUEST_ARTS} />
        </Block>
      ) : null}

      {r.will || a.willWaits ? <Will a={a} c={c} swatch={swatch} /> : null}
      {r.tanzil ? <Tanzil a={a} swatch={swatch} /> : null}
      {!leftWhole ? <p className="m-0 text-body">{t('answer.bequest.left', { share: sayShare(r.left, t), money: m.paren(r.left) })}</p> : null}

      {r.radd ? (
        <Note tone="law" quiet>
          <p className="m-0 text-body">{r.raddSpouse ? t(`answer.radd.spouse_${r.raddSpouse.heir}`) : alone ? t(`answer.radd.one_${sexOf(alone.heir)}`) : t('answer.radd.plain')}</p>
          {r.raddSpouse ? (
            <p className="m-0 text-body">
              {t(`answer.radd.other_${r.raddSpouse.heir}`, { share: sayShare(r.raddSpouse.fixed, t), money: m.paren(r.raddSpouse.fixed) })}{' '}
              <Link to={`${CHOICES}#radd`} className="font-medium">{t('answer.radd.why')}</Link>
            </p>
          ) : null}
          <Cites today={[[349, 6]]} />
        </Note>
      ) : null}

      {shrunk ? (
        <Note tone="law" quiet>
          <p className="m-0 text-body">{t('answer.awl')}</p>
          <Cites today={[367, 368]} />
        </Note>
      ) : null}

      {heirs.length ? (
        <Block title={r.bequest.length || r.will || r.tanzil ? t('answer.heirs') : null}>
          <Rows>
            {heirs.map((s) => {
              const l = lineOf(s);
              // With a bequest, a will or a «تنزيل» out first, an heir's share is said of what is left to the heirs:
              // «الثمن مما بقي للورثة», not a bare «الثمن» beside 9,4 % of the estate.
              // When the fixed shares shrank («العول»), the share the code names is said as it stood before: «النصف
              // قبل العول · 3 من 8», not a bare «3 من 8» under «الزوج كياخد النصف».
              const own = l && !leftWhole ? t('answer.ofLeft', { share: sayShare(div(l.own, q(l.count)), t) })
                : l && shrunk && l.fard ? t('answer.awlShare', { share: sayShare(div(l.fard, q(l.count)), t) }) : undefined;
              return <Row key={s.key} s={s} a={a} swatch={swatch(s)} why={l ? t(`why.${l.why}`) : t('answer.treasuryWhy')} cites={l ? l.cites : treasuryCites(r.rules.code)} own={own} />;
            })}
          </Rows>
        </Block>
      ) : null}

      {a.later.map((la, n) => {
        const sex = sexOf(la.later.heir);
        const lines = a.shares.filter((s) => s.group === 'later' && s.later === n);
        const whole = lines.length === 1 && lines[0].key === `l${n}`;
        const theirs = la.result && la.result.ok ? la.result : null;
        return (
          <div key={n} className="flex flex-col gap-2 border-s-[3px] ps-4" style={{ borderColor: 'var(--t)' }}>
            <p className="m-0 text-body font-semibold">{laterName(a, n, c.deceased, t)}</p>
            {la.gone ? <p className="m-0 text-body">{t(`answer.later.gone_${sex}`)}</p>
              : whole ? <p className="m-0 text-body">{t(`answer.later.undecided_${sex}`, { share: sayShare(la.share, t), money: m.paren(la.share) })}</p>
                : (
                  <>
                    <p className="m-0 text-body">{t(`answer.later.passes_${sex}`, { share: sayShare(la.share, t), money: m.paren(la.share) })}</p>
                    {/* Their estate is counted by today's code: an older first death says so, and the articles are today's. */}
                    {r.rules.code === '1958' ? <p className="m-0 text-meta text-ink-soft">{t('answer.later.today')}</p> : null}
                    {/* Their heirs are their own relatives: the names agree with them, not with who died first. */}
                    <RulesContext.Provider value="70-03"><DeceasedContext.Provider value={sex}><Rows>
                      {lines.map((s) => {
                        const l = theirs?.lines.find((x) => x.heir === s.heir);
                        const own = l ? t(`answer.ofTheirs_${sex}`, { share: sayShare(l.each, t) }) : undefined;
                        return <Row key={s.key} s={s} a={a} swatch={swatch(s)} why={l ? t(`why.${l.why}`) : undefined} cites={l?.cites} own={own} />;
                      })}
                    </Rows></DeceasedContext.Provider></RulesContext.Provider>
                  </>
                )}
          </div>
        );
      })}

      {a.shares.length > 1 || (a.paid?.rest ?? 0n) > 0n ? <Total a={a} /> : null}

      {r.excluded.length ? <Excluded a={a} /> : null}
    </div>
  );
}

function Block({ title, children }: { title: string | null; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-3">
      {title ? <h3 className="m-0 text-body font-semibold text-ink-soft">{title}</h3> : null}
      {children}
    </div>
  );
}

const Rows = ({ children }: { children: ReactNode }) => <ul className="m-0 flex list-none flex-col gap-3 p-0">{children}</ul>;

/** One person, or each of several: «كل بنت (3)», the dirhams at the line's end, the share and the percentage under
 *  it, then why, with its articles. */
export function Row({ s, a, swatch, why, cites, own }: { s: Share; a: Ok; swatch?: CSSProperties; why?: string; cites?: Cite[]; own?: string }) {
  const { t, i18n } = useT();
  const m = money(a, t, i18n.language);
  const w = shareWords(s.each, a.common, t);
  const paid = m.paid(s);
  // A French line starts with a capital: «Le huitième …», though the share alone is said «le huitième».
  const capital = (x: string) => (i18n.language === 'fr' ? x.charAt(0).toUpperCase() + x.slice(1) : x);
  return (
    <li className="flex flex-col gap-1 border-t border-rule pt-3 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="flex min-w-0 items-baseline gap-2">
          {swatch ? <span aria-hidden="true" className="size-3 shrink-0 self-center rounded-sm" style={swatch} /> : null}
          <span className="text-body font-semibold">{lineName(s, t)}</span>
        </span>
        {paid ? <span className="text-lead font-bold tabular-nums">{paid}</span> : null}
      </div>
      <p className="m-0 text-body tabular-nums">{capital([own ?? w.words, w.of ?? (own ? w.words : null), percent(s.each)].filter(Boolean).join(' · '))}</p>
      {why || cites?.length ? (
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
          {why ? <p className="m-0 text-meta text-ink-soft">{why}</p> : null}
          {cites?.length ? <Cites cites={cites} /> : null}
        </div>
      ) : null}
    </li>
  );
}

/** What was left, what leaves it first (art. 322), and what is shared: a ledger, the amount said again in «مليون». */
function Estate({ a }: { a: Ok }) {
  const { t, i18n } = useT();
  const mo = a.money;
  if (!mo) return null;
  const m = money(a, t, i18n.language);
  const out = ([['funeral', mo.funeral], ['debts', mo.debts], ['dowry', mo.dowry]] as const).filter(([, v]) => v > 0n);
  const millions = inMillions(mo.net);
  const row = (label: string, value: string, strong = false, minus = false) => (
    <div className={`flex items-baseline justify-between gap-3 ${strong ? 'border-t border-rule pt-2 font-semibold' : ''}`}>
      <span className="text-body">{label}</span>
      <bdi className="text-body tabular-nums">{minus ? '− ' : ''}{value}</bdi>
    </div>
  );
  return (
    <div className="flex flex-col gap-1.5">
      {out.length ? (
        <>
          {row(t('answer.estate.left'), m.dh(mo.gross))}
          {out.map(([k, v]) => <div key={k}>{row(t(`answer.estate.${k}`), m.dh(v), false, true)}</div>)}
          {row(t('answer.estate.net'), m.dh(mo.net), true)}
          <Cites today={[322]} />
        </>
      ) : row(t('answer.estate.only'), m.dh(mo.net), true)}
      {millions ? <p className="m-0 text-meta text-ink-soft">{t('answer.millions', { m: millions })}</p> : null}
    </div>
  );
}

/** The estate as one bar, left to right whatever the page's direction (the charts' rule), each part a
 *  shade of the topic's colour; the legend names every part in the bar's order with its percentage. */
function Bar({ parts, colours }: { parts: Part[]; colours: Record<string, CSSProperties> }) {
  const { t, i18n } = useT();
  const dir = i18n.language === 'fr' ? 'ltr' : 'rtl';
  const weight = (p: Part) => Number((p.share.n * 100000n) / p.share.d) / 1000;
  return (
    <figure className="m-0 flex flex-col gap-2" aria-label={t('answer.bar')}>
      <div dir="ltr" aria-hidden="true" className="flex h-9 gap-0.5 overflow-hidden rounded-control">
        {parts.map((p) => <span key={p.key} className="h-full" style={{ ...colours[p.key], flex: `${weight(p)} 1 0`, minWidth: 3 }} />)}
      </div>
      <ul dir="ltr" className="m-0 flex list-none flex-wrap gap-x-4 gap-y-1 p-0">
        {parts.map((p) => (
          <li key={p.key} dir={dir} className="flex items-center gap-1.5 text-meta">
            <span aria-hidden="true" className="size-3 shrink-0 rounded-sm" style={colours[p.key]} />
            <span>{p.name}</span>
            <bdi className="whitespace-nowrap tabular-nums text-ink-soft">{percent(p.share)}</bdi>
          </li>
        ))}
      </ul>
    </figure>
  );
}

function Will({ a, c, swatch }: { a: Ok; c: Case; swatch: (s: Share) => CSSProperties }) {
  const { t, i18n } = useT();
  const r = a.result;
  const m = money(a, t, i18n.language);
  const w = r.will;
  const share = a.shares.find((s) => s.group === 'will');
  const granted = w && w.granted.n * w.asked.d === w.asked.n * w.granted.d;
  return (
    <Block title={t('answer.will.heading')}>
      {a.willWaits ? <p className="m-0 text-body">{t('answer.will.waits')}</p> : null}
      {w ? (
        <>
          <p className="m-0 text-body">
            {t('answer.will.asked', { share: sayShare(w.asked, t), money: m.paren(w.asked) })}{' '}
            {granted ? t('answer.will.whole') : w.granted.n === 0n ? t('answer.will.none') : t('answer.will.granted', { share: sayShare(w.granted, t), money: m.paren(w.granted) })}
          </p>
          {c.will?.agreed ? <p className="m-0 text-meta text-ink-soft">{t('answer.will.agreed')}</p> : null}
          {w.cut ? (
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <p className="m-0 text-meta text-ink-soft">{t(`answer.will.${w.cut}`)}</p>
              <Cites today={w.cut === 'heir' ? [280] : [277, 303]} />
            </div>
          ) : null}
          {share ? <Rows><Row s={share} a={a} swatch={swatch(share)} /></Rows> : null}
        </>
      ) : null}
    </Block>
  );
}

function Tanzil({ a, swatch }: { a: Ok; swatch: (s: Share) => CSSProperties }) {
  const { t } = useT();
  const z = a.result.tanzil;
  const share = a.shares.find((s) => s.group === 'tanzil');
  if (!z) return null;
  return (
    <Block title={t('answer.tanzil.heading')}>
      {share ? <Rows><Row s={share} a={a} swatch={swatch(share)} /></Rows> : null}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <p className="m-0 text-meta text-ink-soft">{t(`answer.tanzil.${z.by}`)}{z.cut ? ` ${t('answer.tanzil.cut')}` : ''}</p>
        <Cites today={z.by === 'rise' ? [[317, 1]] : [[317, 2], 318]} />
      </div>
    </Block>
  );
}

/** The total: the lines add up to what is shared, and a centime that cannot be split equally is said. */
function Total({ a }: { a: Ok }) {
  const { t, i18n } = useT();
  const m = money(a, t, i18n.language);
  const rest = a.paid?.rest ?? 0n;
  const sum = a.paid ? a.shares.reduce((x, s) => x + (a.paid as NonNullable<typeof a.paid>).each[s.key] * BigInt(s.count), 0n) : null;
  const whole = a.common && a.common > 1n ? t('answer.of', { n: a.common.toString(), d: a.common.toString() }) : null;
  return (
    <div className="flex flex-col gap-1 border-t-2 border-ink pt-3">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3">
        <span className="text-body font-semibold">{t('answer.total')}</span>
        {sum !== null ? <span className="text-lead font-bold tabular-nums">{m.dh(sum)}</span> : null}
      </div>
      <p className="m-0 text-body tabular-nums">{[whole, t('answer.totalAll'), percent(ONE)].filter(Boolean).join(' · ')}</p>
      {rest > 0n ? <p className="m-0 text-meta text-ink-soft">{t('answer.rest', { count: Number(rest) })}</p> : null}
    </div>
  );
}

/** Those who take nothing, by name with the plain reason and the article; a dead son's children shut out as heirs
 *  are said to take by the bequest above. */
function Excluded({ a }: { a: Ok }) {
  const { t, i18n } = useT();
  const r = a.result;
  return (
    <Block title={t('answer.out.heading')}>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {r.excluded.map((e) => {
          return (
            <li key={e.heir} className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <p className="m-0 text-body">
                <span className="font-semibold">{groupName(e.heir, e.count, t)}</span>{t('answer.colon')}{outWords(e, r, t, i18n.language)}
              </p>
              <Cites cites={e.cites} />
            </li>
          );
        })}
      </ul>
    </Block>
  );
}

