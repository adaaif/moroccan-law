import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button, Page } from '@/shared/components/ui';
import { usePageTitle } from '@/shared/services/title';
import '@/shared/locales/pages';
import { TERMS_DATE } from './access';
import { dateOf } from './said';
import '@/features/corpus/library.css';
import './access.css';

const ODBL = 'https://opendatacommons.org/licenses/odbl/1-0/';

/**
 * /data/terms: the terms of access, dated (the date is their version, the one a request records), as short numbered
 * lines in plain words, in Arabic and in French. They govern the service; the database's licence, ODbL 1.0, stands
 * whole beside them.
 */
export default function TermsPage() {
  const { t, i18n } = useTranslation();
  usePageTitle([t('pages:access.terms.title')]);
  const lines = t('pages:access.terms.lines', { returnObjects: true }) as string[];
  return (
    <Page width="reading" className="lb ax">
      <header className="lb-head">
        <div>
          <h1>{t('pages:access.terms.title')}</h1>
          <p className="ax-line"><time dateTime={TERMS_DATE}>{t('pages:access.terms.version', { date: dateOf(TERMS_DATE, i18n.language) })}</time></p>
          <p className="lead">{t('pages:access.terms.lead')}</p>
        </div>
      </header>
      <ol className="ax-terms">
        {lines.map((line, i) => <li key={i} id={`term-${i + 1}`}>{line}</li>)}
      </ol>
      <p className="ax-small ax-links">
        <a href={ODBL} target="_blank" rel="noreferrer">{t('pages:access.terms.odbl')}</a>
        <Link to="/privacy#write">{t('pages:access.form.privacy')}</Link>
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <Button variant="primary" to="/data/request">{t('pages:access.door.ask')}</Button>
        <Link to="/data" className="inline-flex min-h-11 items-center">{t('pages:access.form.back')}</Link>
      </div>
    </Page>
  );
}
