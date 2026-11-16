import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { longDate } from '@/features/corpus/format';
import type { HolidaysPost } from '../blog.api';
import { Figure, Table } from '../kit';
import { Head } from '../Head';
import Lines from './Lines';
import '@/shared/design/french.css';
import '../post.css';
import './holidays.css';

/**
 * «أعيادنا بمرسوم، كيف كبرت لائحة العطل» (the blog's seventh post): the private employers' paid holidays as lines from the
 * decree that brought each in; then the oldest list (1958, with the Jewish feasts), the list decree by decree, and the
 * administration's list beside the employers'. The lists are the meta's, read in each text; the counts are computed.
 */
export default function Holidays({ post }: { post: HolidaysPost }) {
  const { t, i18n } = useTranslation('blog');
  const lang = i18n.language;
  const fr = lang === 'fr';
  const names = useMemo<Record<string, string>>(() => ({ ...Object.fromEntries(post.holidays.map((h) => [h.key, fr ? h.fr : h.ar])), jan1: fr ? post.jan1.fr : post.jan1.ar }),
    [post, fr]);
  const priv = post.private;
  const byYear = (y: string) => priv.find((l) => post.figures.texts[l.text]?.published.startsWith(y))!;
  // The administration's list today: the 2000 decree's, with what came after.
  const admin = useMemo(() => {
    const base = post.administration.find((a) => a.days && a.text.startsWith('2-00'))!;
    const days = [...base.days!];
    for (const a of post.administration) if (a.adds && (post.figures.texts[a.text]?.published ?? '') > '2000') days.push(...a.adds.filter((d) => !days.includes(d)));
    return { days, two: base.two_days ?? [] };
  }, [post]);
  const current = priv[priv.length - 1].days;
  const order = [...post.holidays.map((h) => h.key).filter((k) => admin.days.includes(k) || current.includes(k))];
  if (admin.days.includes('jan1')) order.unshift('jan1');
  const src = t('fig.source', { from: 1958, to: 2026 });
  const p = (key: string, values: Record<string, unknown> = {}) => <p className="bp-p">{t(key, values)}</p>;

  return (
    <article className="bp" lang={lang}>
      <Head post={post} />

      <figure className="bp-hero" aria-labelledby="hl-q">
        <div className="bp-hero-words">
          <p className="bp-q" id="hl-q">{t('holidays.hero.q')}</p>
          <p className="bp-unit">{t('holidays.hero.how')}</p>
        </div>
        <Lines post={post} />
        <div className="bp-hero-foot">
          <p className="bp-so"><b>{t('fig.so')}</b> {t('holidays.hero.so', { first: priv[0].days.length, last: current.length })}</p>
          <p className="bp-src">{src}</p>
        </div>
      </figure>

      <section className="bp-sec" aria-labelledby="hl-s1">
        <h2 id="hl-s1">{t('holidays.s1.h')}</h2>
        {p('holidays.s1.p1')}
        {p('holidays.s1.p2')}
      </section>

      <section className="bp-sec" aria-labelledby="hl-s2">
        <h2 id="hl-s2">{t('holidays.s2.h')}</h2>
        {p('holidays.s2.p1', { y2000: byYear('2000').days.length })}
        {p('holidays.s2.p2', { y2026: current.length })}
      </section>

      <section className="bp-sec" aria-labelledby="hl-s3">
        <h2 id="hl-s3">{t('holidays.s3.h')}</h2>
        {p('holidays.s3.p1')}
        <Figure id="two-lists" q={t('holidays.s3.q')} unit={t('holidays.s3.unit')} source={src} so={t('holidays.s3.so')}
                table={<Table head={['', t('holidays.s3.admin'), t('holidays.s3.private')]}
                              rows={order.map((k) => [names[k], admin.days.includes(k) ? (admin.two.includes(k) ? t('holidays.s3.twoDays') : '✓') : '–', current.includes(k) ? '✓' : '–'])} />}>
          <div className="hl-two" role="table">
            <div className="hl-two-row hl-two-head" role="row">
              <span role="columnheader" /><span role="columnheader">{t('holidays.s3.admin')}</span><span role="columnheader">{t('holidays.s3.private')}</span>
            </div>
            {order.map((k) => (
              <div key={k} className={`hl-two-row${admin.days.includes(k) !== current.includes(k) ? ' is-diff' : ''}`} role="row">
                <span role="rowheader">{names[k]}</span>
                <span role="cell">{admin.days.includes(k) ? <i role="img" className={admin.two.includes(k) ? 'two' : ''} aria-label={admin.two.includes(k) ? t('holidays.s3.twoDays') : t('holidays.s3.on')}>{admin.two.includes(k) ? t('holidays.s3.twoDays') : ''}</i> : '–'}</span>
                <span role="cell">{current.includes(k) ? <i role="img" aria-label={t('holidays.s3.on')} /> : '–'}</span>
              </div>
            ))}
          </div>
        </Figure>
      </section>

      <section className="bp-method" aria-labelledby="hl-method">
        <h2 id="hl-method">{t('holidays.method.h')}</h2>
        <ul>
          {(['read', 'missing', 'defect', 'check'] as const).map((k) => <li key={k}>{t(`holidays.method.${k}`)}</li>)}
          <li>{t('holidays.method.on', { on: longDate(post.counted_on, lang) })}</li>
        </ul>
      </section>
    </article>
  );
}
