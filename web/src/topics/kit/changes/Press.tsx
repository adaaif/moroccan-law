import { Link } from 'react-router-dom';
import { longDate } from '@/features/corpus/format';
import { pick, useKitItem, useKitT, type InfoPage as Info, type Named } from '../api';
import { KitPage, NextLinks } from '../parts';
import { useRefTitles } from '../share';
import { BillBand } from './BillBand';
import './words';
import './changes.css';

/** One thing said about a law or a bill outside its text (the bill-story review, Y8–Y10; docs/rules.md, «What
 *  people say is linked, never the law»): who, where, when, the headline as printed, one sentence of ours, a proposal said as
 *  one; the article itself a link away. What a named person said is `quotes[].says`: our sentence in reported speech
 *  («كيقول بلي …», «estime que …»), drawn after the name as one sentence, never as «Name: words» (the person spoke
 *  none of our words). */
export type PressItem = {
  key: string; type: 'government' | 'parliament' | 'unions' | 'employers' | 'experts' | 'press'; outlet: Named; date: string;
  lang: 'ar' | 'fr'; title: string; url: string; said?: Named;
  quotes?: { who: Named; says: Named; proposal?: boolean }[];
};
export type PressPage = Info & { items: PressItem[]; checked_on?: string };
const ORDER: PressItem['type'][] = ['government', 'parliament', 'unions', 'employers', 'experts', 'press'];

/** The items grouped by who speaks, newest first in each group; `most` keeps the page's short version. */
export function PressList({ items, most }: { items: PressItem[]; most?: number }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const shown = most ? [...items].sort((a, b) => b.date.localeCompare(a.date)).slice(0, most) : items;
  return (
    <div className="pr-list">
      {ORDER.map((type) => {
        const here = shown.filter((i) => i.type === type).sort((a, b) => b.date.localeCompare(a.date));
        if (!here.length) return null;
        return (
          <section key={type} className="pr-group" aria-label={t(`press.types.${type}`)}>
            <h3 className="pr-type">{t(`press.types.${type}`)}</h3>
            <ul>
              {here.map((i) => (
                <li key={i.key} className="pr-item">
                  <span className="pr-who"><b>{pick(i.outlet, lang)}</b><time dateTime={i.date}>{longDate(i.date, lang)}</time></span>
                  <span className="pr-body">
                    <a href={i.url} target="_blank" rel="noreferrer" lang={i.lang} dir={i.lang === 'ar' ? 'rtl' : 'ltr'} className="pr-title">{i.title}</a>
                    {i.said ? <span className="pr-said">{pick(i.said, lang)}</span> : null}
                    {(i.quotes ?? []).map((q, k) => (
                      <span key={k} className="pr-said">
                        <b>{pick(q.who, lang)}</b>{lang === 'fr' ? ', ' : '، '}{pick(q.says, lang)}
                        {q.proposal ? <span className="pr-prop">{t('press.proposal')}</span> : null}
                      </span>
                    ))}
                  </span>
                </li>
              ))}
            </ul>
          </section>
        );
      })}
    </div>
  );
}

/** «شنو كيقولو» on a page (Y8): the four newest, and the way to them all. */
export function PressPanel({ slug, page }: { slug: string; page: string }) {
  const { t, i18n } = useKitT();
  const q = useKitItem<PressPage>(slug, 'pages', page);
  if (!q.data?.items?.length) return null;
  return (
    <section className="pr-panel" aria-labelledby="pr-panel">
      <h2 id="pr-panel" className="ch-sec-h">{t('press.title')}</h2>
      <p className="pr-lead">{t('press.lead')}</p>
      <PressList items={q.data.items} most={4} />
      <p className="ch-foot"><span>{q.data.checked_on ? t('press.checked', { date: longDate(q.data.checked_on, i18n.language) }) : null}</span>
        <Link to={`/topics/${slug}/pages/${page}`}>{t('press.all', { count: q.data.items.length })}</Link></p>
    </section>
  );
}

/** The whole page of what is said (Y8). */
export default function PressView({ slug, p }: { slug: string; p: PressPage }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const titles = useRefTitles(slug);
  return (
    <KitPage slug={slug} item={p} title={pick(p.title, lang)} lead={pick(p.lead, lang)}>
      {p.bill ? <BillBand slug={slug} bill={p.bill} reform={p.reform} /> : null}
      <PressList items={p.items ?? []} />
      <p className="pr-lead">{p.checked_on ? t('press.checked', { date: longDate(p.checked_on, lang) }) : null} {t('press.rule')}</p>
      <NextLinks slug={slug} refs={p.next} titles={titles} />
    </KitPage>
  );
}

/** Under a claim (Y9): the outlets that printed it, each a link. */
export function Repeated({ items, keys }: { items: PressItem[]; keys?: string[] }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const found = (keys ?? []).map((k) => items.find((i) => i.key === k)).filter((i): i is PressItem => Boolean(i));
  if (!found.length) return null;
  return (
    <p className="pr-repeat">
      <span>{t('press.repeated')}</span>
      {found.map((i) => (
        <a key={i.key} href={i.url} target="_blank" rel="noreferrer"><bdi>{pick(i.outlet, lang)}</bdi>{t('press.sep')}<bdi>{longDate(i.date, lang)}</bdi></a>
      ))}
    </p>
  );
}
