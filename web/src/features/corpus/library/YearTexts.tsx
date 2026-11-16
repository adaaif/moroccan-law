import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { LinesSkeleton } from '@/shared/components/ui';
import { AR } from '../format';
import { useNum, useYearTexts, type YearText } from './library.api';
import { fold, stem } from './read';
import '@/shared/locales/pages';

const LAWS = ['law', 'organic_law', 'decree_law', 'constitution'];
const STEP = 60;

/** A year's laws and dahirs (W8 of the library-search review): the texts other texts cite most first, then every law and
 *  dahir signed that year, by day, with a filter. Decrees and orders are counted, and searched. A reader who knows «a
 *  dahir of 1958» reads its dahirs by name instead of opening 54 issues one by one. */
export function YearTexts({ year }: { year: number }) {
  const { t, i18n } = useTranslation();
  const num = useNum();
  const q = useYearTexts(year);
  const [filter, setFilter] = useState('');
  const [shown, setShown] = useState(40);
  if (q.isLoading) return <LinesSkeleton lines={8} />;
  const d = q.data;
  if (!d) return <p className="lb-note">{t('pages:landing.failed')}</p>;
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const laws = LAWS.reduce((n, k) => n + (d.counts[k] ?? 0), 0), dahirs = d.counts.dahir ?? 0;
  const decrees = d.counts.decree ?? 0, orders = (d.counts.order ?? 0) + (d.counts.decision ?? 0);
  const by = new Map(d.texts.map((x) => [x.path, x]));
  const top = d.most_cited.map((p) => by.get(p)).filter(Boolean) as YearText[];
  const wanted = fold(filter).split(' ').filter(Boolean).map(stem);
  const all = wanted.length
    ? d.texts.filter((x) => { const hay = ` ${fold(`${x.name?.ar ?? ''} ${x.name?.fr ?? ''} ${x.subject}`).split(' ').map(stem).join(' ')} ${fold(x.number)} `; return wanted.every((w) => hay.includes(` ${w}`)); })
    : d.texts;
  const what = [laws ? t('pages:lib4.bo.lawsN', { count: laws, n: num(laws) }) : '', dahirs ? t('pages:lib4.bo.dahirsN', { count: dahirs, n: num(dahirs) }) : ''].filter(Boolean).join(t('pages:lib4.bo.and'));
  const row = (x: YearText) => {
    const name = (lang === 'fr' && x.name?.fr) || x.name?.ar || x.subject;
    const kind = x.type === 'law' && /^1\.\d/.test(x.number) ? t('pages:lib4.k.dahirLaw') : t(`corpus.types.${x.type}`);
    return (
      <li key={x.path}>
        <Link to={x.path} className="lb-yt">
          <span className="n">{kind}{x.number ? <> <bdi dir="ltr">{x.number}</bdi></> : x.signed_on ? <> <bdi dir="ltr">{x.signed_on.slice(8, 10)}/{x.signed_on.slice(5, 7)}</bdi></> : null}</span>
          <span className="m"><b {...(lang === 'fr' && x.name?.fr ? {} : AR)}>{name}</b>
            {x.status === 'repealed' ? <small className="gone">{t('pages:lib4.text.repealed')}</small> : x.status === 'partly_repealed' ? <small>{t('pages:lib4.text.partly')}</small> : null}
            {x.cited >= 20 ? <small>{t('pages:lib4.text.cited', { count: x.cited, n: num(x.cited) })}</small> : null}</span>
          {x.issue ? <span className="lb-stp">{t('pages:lib4.text.issue', { n: x.issue.number + (x.issue.suffix ? ` ${t(`corpus.suffix.${x.issue.suffix}`)}` : '') })}</span> : null}
        </Link>
      </li>
    );
  };
  return (
    <div className="lb-yts">
      {what ? <p className="lb-note">{t('pages:lib4.bo.signed', { what })}</p> : <p className="lb-note">{t('pages:lib4.bo.noTexts')}</p>}
      {top.length && !wanted.length ? (
        <>
          <h3>{t('pages:lib4.bo.mostCited', { year })}</h3>
          <ul className="cols">{top.map(row)}</ul>
        </>
      ) : null}
      {d.texts.length ? (
        <>
          <h3>{t('pages:lib4.bo.all', { year, n: num(d.texts.length) })}</h3>
          <input type="search" className="lb-ytf" dir="auto" value={filter} onChange={(e) => { setFilter(e.target.value); setShown(40); }}
                 placeholder={t('pages:lib4.bo.filter')} aria-label={t('pages:lib4.bo.filter')} />
          <ul className="cols">{all.slice(0, shown).map(row)}</ul>
          {all.length > shown ? <button type="button" className="lb-ytmore" onClick={() => setShown((n) => n + STEP)}>
            {t('pages:lib4.bo.more', { n: num(Math.min(STEP, all.length - shown)), rest: num(all.length - shown) })}</button> : null}
          {!all.length ? <p className="lb-note">{t('pages:lib4.bo.none')}</p> : null}
        </>
      ) : null}
      {decrees + orders ? <p className="lb-note">{t('pages:lib4.bo.others', { year, decrees: t('pages:lib4.bo.decreesN', { count: decrees, n: num(decrees) }), orders: t('pages:lib4.bo.ordersN', { count: orders, n: num(orders) }) })}{' '}
        <Link to={`/search?year=${year}&type=decree`}>{t('pages:lib4.bo.searchThem')}</Link></p> : null}
    </div>
  );
}
