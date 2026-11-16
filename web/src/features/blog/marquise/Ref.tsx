import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Stamp } from '@/features/corpus/article/Stamp';
import type { MarquisePost } from '../blog.api';
import { day } from '../clock/names';

/** A text the post names: its name (to its address when the site has cut it, else to its printed page) and its issue and
 *  page as the site's stamp, or as a short violet chip in a narrow place. */
export function Ref({ k, post, lang, compact = false }: { k: string; post: MarquisePost; lang: string; compact?: boolean }) {
  const { t } = useTranslation('blog');
  const f = post.figures.texts[k];
  if (!f) return null;
  const name = refName(k, post, lang, t);
  const issue = f.issue.replace(' bis', lang === 'fr' ? ' bis' : ' مكرر');
  const to = f.path ?? f.viewer;
  return (
    <span className={`mq-ref${compact ? ' is-compact' : ''}`}>
      {to ? <Link to={to}>{name}</Link> : name}{' '}
      {compact ? (f.viewer ? <Link to={f.viewer} className="mq-ref-page">{t('clock.pageShort', { issue, page: f.page })}</Link> : null)
               : <Stamp issue={issue} page={f.page} to={f.viewer} className="mq-ref-stamp" />}
    </span>
  );
}

function refName(k: string, post: MarquisePost, lang: string, t: (key: string, o?: Record<string, unknown>) => string): string {
  const fr = lang === 'fr';
  const dash = (n: string) => (fr ? n.replace(/\./g, '-') : n);
  const order = (n?: string, date?: string) => (n ? t('marquise.ref.order', { n: dash(n) }) : t('marquise.ref.orderOf', { day: day(date!, lang) }));
  if (k.startsWith('p')) {
    const p = post.prices.find((x) => `p${x.date}` === k)!;
    return order(p.number, p.date);
  }
  if (k === 'renamed') return order(post.renamed.number, post.renamed.date);
  if (k === 'approve') return order(post.approve.number, post.approve.date);
  if (k === 'applied') return order(post.palestine.applied.number, post.palestine.applied.date);
  if (k === 'delegate') return t('marquise.ref.decree', { n: dash(post.delegate.number ?? '') });
  if (k === 'levy') return t('marquise.ref.dahir', { n: dash('1.70.16') });
  const c = post.palestine.changed.find((x) => `changed${x.date}` === k);
  return c?.law ? t('marquise.ref.financeLaw', { n: dash(c.law), year: c.date.slice(0, 4) }) : t('marquise.ref.issue', { day: day(c?.date ?? '', lang) });
}
