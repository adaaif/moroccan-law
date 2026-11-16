import { Link } from 'react-router-dom';
import { pick, refPath, useKitT, type Claim, type InfoPage as Info } from '../api';
import { Cites, KitPage, NextLinks } from '../parts';
import { useRefTitles } from '../share';
import { BillBand } from './BillBand';
import { Repeated, type PressPage } from './Press';
import { useKitItem } from '../api';
import './words';
import './changes.css';

/** «قالو | مكتوب» (the bill-page review, V13): each sentence as it was said, with its page, beside what the text
 *  gives — its figure first, under a neutral marker (as said, on a condition, later, not in the bill, another figure);
 *  never «كذب» or «خطأ» (C1 of the finance-bill review). Two columns on a desk, one under the other on a phone. */
export default function ClaimsView({ slug, p }: { slug: string; p: Info }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const titles = useRefTitles(slug);
  const claims = (p.sections ?? []) as Claim[];
  const press = useKitItem<PressPage>(slug, 'pages', p.press ?? '').data?.items ?? [];
  return (
    <KitPage slug={slug} item={p} title={pick(p.title, lang)} lead={pick(p.lead, lang)} wide>
      {p.bill ? <BillBand slug={slug} bill={p.bill} reform={p.reform} /> : null}
      <ol className="cl-list">
        <li className="cl-head" aria-hidden="true"><span>{t('claims.said')}</span><span>{t('claims.written')}</span></li>
        {claims.map((c, i) => {
          const quote = pick(c.title, lang).replace(/^[«"]|[»"]$/g, '');
          const link = c.tool ?? c.more;
          return (
            <li key={i} className="cl-row">
              <div className="cl-said">
                <span className="ch-sr">{t('claims.said')}</span>
                <q>{quote}</q>
                {c.source ? <a href={c.source.url} target="_blank" rel="noreferrer">{pick(c.source.name, lang)}</a> : null}
                <Repeated items={press} keys={c.repeated} />
              </div>
              <div className="cl-text">
                <span className="ch-sr">{t('claims.written')}</span>
                <span className={`cl-mark ${c.mark}`}>{pick(c.mark_words, lang)}</span>
                <p className="cl-fig">{pick(c.figure, lang)}</p>
                {(c.facts ?? []).map((f, j) => (
                  <div key={j} style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <p>{pick(f.text, lang)}</p>
                    <Cites cites={f.cites} />
                  </div>
                ))}
                {link && titles[link] ? <Link to={refPath(slug, link)} className="cl-link">{pick(titles[link], lang)}</Link> : null}
              </div>
            </li>
          );
        })}
      </ol>
      <NextLinks slug={slug} refs={p.next} titles={titles} />
    </KitPage>
  );
}
