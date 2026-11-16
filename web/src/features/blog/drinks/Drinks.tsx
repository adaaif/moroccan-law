import { type ReactNode, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import type { DrinksPost } from '../blog.api';
import { Head } from '../Head';
import { Figure } from '../kit';
import { day } from '../clock/names';
import { Fines } from './Fines';
import { groups, hoursOf, hourlyOn } from './fines';
import { Print } from '../Print';
import { shareArticle } from './share';
import '@/shared/design/french.css';
import '../post.css';
import './drinks.css';

/** A sum as the Bulletin prints it: «1.500», «300». */
const money = (v: number, lang: string) => (lang === 'fr' ? v.toLocaleString('fr-FR').replace(/\u202f/g, ' ') : v.toLocaleString('en-US').replace(/,/g, '.'));

/**
 * «الفصل 28، كما طبعته الجريدة الرسمية سنة 1967» (the blog's seventeenth post): the article as printed, framed on its page
 * and read word by word, each marked phrase opening what the order says about it; how an order, not a law, came to carry
 * it; the dahir of 1913 beside it; the order's eighteen fines on one line; the public drunkenness decree of the same year.
 * The text, its date, its penalties, nothing else (the review's C4). Every quote is the meta's, read on its page.
 */
export default function Drinks({ post }: { post: DrinksPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const side = lang === 'fr' ? 'fr' : 'ar';
  const rtl = lang !== 'fr';
  const [note, setNote] = useState('who');
  const [sharing, setSharing] = useState(false);
  const heroRef = useRef<HTMLElement>(null);
  const tx = post.figures.texts;
  const wage = post.figures.wage;
  const fineRows = groups(post.fines);

  /** A text's page as a stamp. */
  const stamp = (key: string) => {
    const f = tx[key];
    return f ? <Stamp issue={f.issue.replace(' bis', rtl ? ' مكرر' : ' bis')} page={f.page} to={f.viewer} className="dr-stamp" /> : null;
  };
  /** An article of the order, opening it on the site. */
  const art = (n: number | string, label?: string): ReactNode => {
    const to = post.figures.articles[String(n)];
    const words = label ?? t('drinks.art', { n });
    return to ? <Link to={to} className="dr-art">{words}</Link> : <span>{words}</span>;
  };
  /** Article numbers as the page says them: «الفصل 28», «الفصلان 29 و30», «الفصول 1 و5 و17…». */
  const arts = (ns: number[]) => {
    const list = ns.join(rtl ? ' و' : ', ').replace(/, (\d+)$/, ' et $1');
    return t(ns.length === 1 ? 'drinks.art' : ns.length === 2 ? 'drinks.artsTwo' : 'drinks.arts', { n: list });
  };

  const h67 = hoursOf(300, wage, post.order.published)!, h26 = hoursOf(300, wage, post.counted_on)!;
  const noteText = (key: string) => t(`drinks.notes.${key}`, { h67, h26 });
  const noteRefs: Record<string, ReactNode[]> = {
    who: [art(3), art(1), art(7), <>{tx['c-walis']?.path ? <Link to={tx['c-walis'].path} className="dr-art">{t('drinks.chain.names.walis', { n: rtl ? '371.02' : '371-02' })}</Link> : null} {stamp('c-walis')}</>],
    what: [],
    whom: [],
    penalty: [art(37)],
    repeat: [art(43), art(37)],
  };

  /** A paragraph of the article with its marked words as buttons, each opening its note. */
  const paragraph = (words: string, p: number) => {
    const marks = post.art28.marks.filter((m) => m.p === p);
    const parts: ReactNode[] = [];
    let rest = words;
    for (const m of marks) {
      const phrase = m[side];
      const at = rest.indexOf(phrase);
      if (at < 0) continue;
      parts.push(rest.slice(0, at));
      const n = post.art28.marks.indexOf(m) + 1;
      parts.push(
        // A span, not a button, so the words wrap with the line like the printed ones; it answers the keys a button does.
        <span key={m.key} role="button" tabIndex={0} className={`dr-mark${note === m.key ? ' is-on' : ''}`} aria-pressed={note === m.key}
              aria-controls={`dr-note-${m.key}`} onClick={() => setNote(m.key)}
              onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); setNote(m.key); } }}>
          {phrase}<sup>{n}</sup>
        </span>,
      );
      rest = rest.slice(at + phrase.length);
    }
    parts.push(rest);
    return <p key={p} className="dr-words">{parts}</p>;
  };

  const doShare = async () => {
    if (!heroRef.current || !tx.art28?.viewer) return;
    setSharing(true);
    try {
      await shareArticle(heroRef.current, {
        dir: rtl ? 'rtl' : 'ltr', over: `${t('name')} ${t('number', { n: post.number })}`, title: t('drinks.share.title'),
        viewer: tx.art28.viewer, crop: post.art28.crop, line: t('drinks.share.line'), source: t('drinks.share.source'), site: t('drinks.share.site'),
      });
    } finally { setSharing(false); }
  };

  const delegation = post.chain.find((c) => c.key === 'delegation')!;
  const w67 = hourlyOn(wage, post.order.published), w26 = hourlyOn(wage, post.counted_on);
  const dec = (v: number | null) => (v === null ? '' : String(v).replace('.', ','));

  return (
    <article className="bp dr" lang={lang}>
      <Head post={post} />

      <figure className="dr-hero" ref={heroRef} aria-labelledby="dr-q">
        <p className="dr-q" id="dr-q">{t('drinks.hero.q')}</p>
        <p className="dr-how">{t('drinks.hero.how')}</p>
        <div className="dr-sheet">
          <p className="dr-order">{t('drinks.hero.order')}</p>
          {tx.art28?.viewer ? <Print viewer={tx.art28.viewer} crop={post.art28.crop} alt={t('drinks.hero.alt')} /> : null}
          <p className="dr-sheet-stamp">{stamp('art28')}</p>
        </div>
        <div className="dr-read">
          <div className="dr-text">
            <p className="dr-art-head">{t('drinks.artHead', { n: 28 })}</p>
            {post.art28[side].map((w, i) => paragraph(w, i))}
            {lang === 'fr' ? <div className="dr-ar" lang="ar" dir="rtl">{post.art28.ar.map((w) => <p key={w}>{w}</p>)}</div> : null}
          </div>
          <section className="dr-notes" aria-labelledby="dr-notes-h">
            <h2 id="dr-notes-h">{t('drinks.hero.notes')}</h2>
            <ol>
              {post.art28.marks.map((m, i) => (
                <li key={m.key} id={`dr-note-${m.key}`} className={note === m.key ? 'is-on' : ''}>
                  <button type="button" className="dr-note-head" aria-expanded={note === m.key} onClick={() => setNote(m.key)}>
                    <span className="dr-note-n">{i + 1}</span><span>{rtl ? `«${m[side]}»` : `« ${m[side]} »`}</span>
                  </button>
                  {note === m.key ? (
                    <div className="dr-note-body">
                      <p>{noteText(m.key)}</p>
                      {noteRefs[m.key]?.length ? <p className="dr-note-refs">{noteRefs[m.key].map((r, k) => <span key={k}>{r}</span>)}</p> : null}
                    </div>
                  ) : null}
                </li>
              ))}
            </ol>
          </section>
        </div>
        <div className="dr-share-row">
          <button type="button" className="dr-share" disabled={sharing} onClick={doShare}>
            <svg aria-hidden="true" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 3v12" /><path d="m7 8 5-5 5 5" /><path d="M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5" /></svg>
            {t('drinks.hero.share')}
          </button>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="dr-s1">
        <h2 id="dr-s1">{t('drinks.chain.h')}</h2>
        <p className="bp-p">{t('drinks.chain.p1')}</p>
        <blockquote className="dr-quote" lang="ar" dir="rtl">«{delegation.words}»</blockquote>
        <p className="bp-p">{t('drinks.chain.p2', { first: post.order.page, last: post.order.last, n: post.order.articles })}</p>
        <ol className="dr-chain">
          {post.chain.map((c) => {
            const f = tx[`c-${c.key}`];
            const name = t(`drinks.chain.names.${c.key}`, { n: rtl ? c.text.number : c.text.number.replace(/\./g, '-') });
            return (
              <li key={c.key} className={c.key === 'order' ? 'is-order' : ''}>
                <span className="dr-year">{c.year}</span>
                <span className="dr-chain-body">
                  <span>{t(`drinks.chain.rows.${c.key}`, { n: post.order.articles })}</span>
                  <span className="dr-chain-src">{f?.path ? <Link to={f.path}>{name}</Link> : name} {stamp(`c-${c.key}`)}</span>
                </span>
              </li>
            );
          })}
        </ol>
        <p className="bp-p">{t('drinks.chain.p3')} {art(44)}</p>
        <blockquote className="dr-quote is-small" lang={rtl ? 'ar' : 'fr'}>«{t('drinks.chain.law1929')}»</blockquote>
      </section>

      <section className="bp-sec" aria-labelledby="dr-s2">
        <h2 id="dr-s2">{t('drinks.first.h')}</h2>
        <p className="bp-p">
          {t('drinks.first.p1', { hijri: post.first.hijri, reason: post.first.reason, vizier: post.first.vizier[side] })}{' '}
          {tx['f-56']?.path ? <Link to={tx['f-56'].path}>{t('drinks.art', { n: rtl ? 'الأول' : '1' })}</Link> : null} {stamp('f-56')}
        </p>
        <blockquote className="dr-quote" lang="ar" dir="rtl">«{post.first.art1}»</blockquote>
        <Figure id="dr-two" q={t('drinks.first.q')} unit={t('drinks.first.unit')} so={t('drinks.first.so')} source={t('fig.source', { from: 1913, to: 1967 })}>
          <div className="dr-two">
            <figure>
              {tx['f-56']?.viewer ? <Print viewer={tx['f-56'].viewer} crop={post.first.crop} alt={t('drinks.first.c1913')} /> : null}
              <figcaption>{t('drinks.first.c1913')}</figcaption>
            </figure>
            <figure>
              {tx.art28?.viewer ? <Print viewer={tx.art28.viewer} crop={post.art28.crop} alt={t('drinks.first.c1967')} /> : null}
              <figcaption>{t('drinks.first.c1967')}</figcaption>
            </figure>
          </div>
        </Figure>
        <p className="bp-p">{t('drinks.first.p2')}</p>
        <table className="dr-pairs">
          <thead><tr>{(t('drinks.first.th', { returnObjects: true }) as string[]).map((h) => <th key={h} scope="col">{h}</th>)}</tr></thead>
          <tbody>
            {post.pairs.map((p) => (
              <tr key={p.key}>
                <th scope="row">{t(`drinks.first.rows.${p.key}`)}</th>
                <td>{tx[`f-${p.p1913}`]?.viewer ? <Link to={tx[`f-${p.p1913}`].viewer!}>{arts(p.a1913.split(', ').map(Number))}</Link> : p.a1913}</td>
                <td>{art(p.n1967, arts(p.a1967.split(', ').map(Number)))}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>

      <section className="bp-sec" aria-labelledby="dr-s3">
        <h2 id="dr-s3">{t('drinks.fines.h')}</h2>
        <p className="bp-p">{t('drinks.fines.p1')}</p>
        <Figure id="dr-fines" q={t('drinks.fines.q')} unit={t('drinks.fines.unit')} so={t('drinks.fines.so')} source={t('fig.source', { from: 1967, to: 1967 })}>
          <Fines rows={fineRows} picked={28}
                 label={(g) => t(`drinks.fines.groups.${g.lo}-${g.hi}`, { arts: arts(g.arts) })}
                 range={(g) => {
                   // The prison the group's articles add: all of them («and» or «or», as they say), or only some.
                   const own = post.fines.filter((f) => g.arts.includes(f.art));
                   const jailed = own.filter((f) => f.prison);
                   const key = !jailed.length ? null : jailed.length < own.length ? 'drinks.fines.prisonSome' : jailed.every((f) => f.or) ? 'drinks.fines.prisonOr' : 'drinks.fines.prison';
                   return [t('drinks.fines.range', { lo: money(g.lo, lang), hi: money(g.hi, lang) }), key && g.prison ? t(key, { a: g.prison[0], b: g.prison[1] }) : null].filter(Boolean).join(' ');
                 }}
                 ticks={[0, 500, 1000, 1500, 2000, 2500].map((v) => money(v, lang))} />
        </Figure>
        <p className="bp-p">{t('drinks.fines.p2')}</p>
        <ul className="dr-also">
          {(['9', '27', '4', '35', '36'] as const).map((k) => <li key={k}>{t(`drinks.fines.also.${k}`)} {art(k)}</li>)}
        </ul>
        <p className="dr-note-small">{t('drinks.fines.minors')} {art(29)} {art(30)} {art(31)}</p>
      </section>

      <section className="bp-sec" aria-labelledby="dr-s4">
        <h2 id="dr-s4">{t('drinks.drunk.h')}</h2>
        <p className="bp-p">{t('drinks.drunk.p1')} {tx.drunk?.path ? <Link to={tx.drunk.path}>{rtl ? 'المرسوم الملكي 724.66' : 'décret royal 724-66'}</Link> : null} {stamp('drunk')}</p>
        <blockquote className="dr-quote" lang="ar" dir="rtl">«{post.drunk.words}»</blockquote>
        <p className="bp-p">{t('drinks.drunk.p2')}</p>
      </section>

      <section className="bp-method" aria-labelledby="dr-method">
        <h2 id="dr-method">{t('drinks.method.h')}</h2>
        <ul>
          {(['read', 'first', 'law1929', 'translation'] as const).map((k) => <li key={k}>{t(`drinks.method.${k}`)}</li>)}
          <li>{t('drinks.method.wage', { w67: dec(w67), w26: dec(w26) })}</li>
          {(['names', 'check'] as const).map((k) => <li key={k}>{t(`drinks.method.${k}`)}</li>)}
          <li>{t('drinks.method.on', { on: day(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
