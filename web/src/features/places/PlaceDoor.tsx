import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import '@/shared/locales/pages';
import { n, named } from './format';
import type { PlaceCard } from './places.api';

/** A state or a Moroccan place a question names whole, above search's results (PL21 of the places review):
 *  how many texts name it since when, and its page of every article that does. In the stamp's violet: the
 *  Bulletin's own record, not a topic's door. */
export default function PlaceDoor({ p }: { p: PlaceCard }) {
  const { t, i18n } = useTranslation();
  const lang = i18n.language;
  return (
    <section className="sa-ans" style={{ '--t': 'var(--color-stamp)', '--t-wash': 'var(--color-wash)' } as React.CSSProperties} aria-labelledby="sa-place">
      <div className="top">
        <span className="sit"><span>{t('pages:places.title')} · {t(`pages:places.kind.${p.kind}`)}</span></span>
        <h2 id="sa-place" className="lead">{named(p, lang)}{lang === 'fr' ? ', ' : '، '}{t('pages:places.doorCount', { count: p.texts, texts: n(p.texts, lang) })}</h2>
        <span className="acts"><Link to={p.path} className="go">{t('pages:places.open', { count: p.texts })}</Link></span>
      </div>
    </section>
  );
}
