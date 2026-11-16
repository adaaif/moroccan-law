import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { AR, longDate, paragraphs } from '@/features/corpus/format';
import { forgetArticle, forgetFamily, useFamilies, useSaved, type SavedFamily } from '@/shared/services/saved';
import { usePageTitle } from '@/shared/services/title';
import { Button, EmptyState, Page } from '@/shared/components/ui';
import { EmptyArt } from '@/shared/components/EmptyArt';
import { dayIn } from '@/shared/services/today';
import '@/shared/locales/pages';
import { useT as useInheritanceT } from '@/topics/family/inheritance/strings';

/** /saved, «محفوظاتي»: the articles kept on this device, whole, readable without a connection (row 14), and the
 *  families kept from the inheritance calculator (IR16 of the inheritance review), each opening the calculator on it. */
export default function SavedPage() {
  const { t, i18n } = useTranslation();
  usePageTitle([t('pages:saved.title')]);
  const saved = useSaved();
  const families = useFamilies();
  return (
    <Page width="reading" className="gap-6">
      <header className="flex flex-col gap-2">
        <h1 className="m-0 font-law text-h1 font-semibold">{t('pages:saved.title')}</h1>
        <p className="m-0 max-w-[60ch] text-ink-soft">{t('pages:saved.lead')}</p>
      </header>
      {saved.length ? (
        <ol className="m-0 flex list-none flex-col gap-4 p-0">
          {saved.map((s) => (
            <li key={s.path} className="rounded-control border border-rule bg-sheet px-5 py-5 sm:px-7">
              <p {...AR} className="m-0 text-meta text-ink-soft">
                <Link to={s.textPath} className="text-ink-soft no-underline hover:text-stamp">{s.text}</Link>
              </p>
              <h2 {...AR} className="m-0 mt-1 font-law text-h2 font-semibold">
                <Link to={s.path} className="text-ink no-underline hover:text-stamp">{s.label}</Link>
              </h2>
              {s.source ? <p className="m-0 mt-1 text-meta text-ink-soft">{s.source}</p> : null}
              <details className="mt-3">
                <summary className="flex min-h-11 cursor-pointer items-center text-body font-medium text-stamp">{t('pages:saved.read')}</summary>
                <div {...AR} className="mt-2 max-w-[70ch] font-law text-law leading-[1.85]">
                  {paragraphs(s.body.replace(/\*\*/g, '')).map((p, i) => <p key={i} className="m-0 mt-2 first:mt-0">{p}</p>)}
                </div>
              </details>
              <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-meta text-ink-soft">
                <span>{t('pages:saved.on', { date: longDate(dayIn(new Date(s.savedAt)), i18n.language) })}</span>
                <button type="button" onClick={() => void forgetArticle(s.path)} className="h-11 text-stamp hover:text-stamp-deep">
                  {t('pages:saved.forget')}
                </button>
              </div>
            </li>
          ))}
        </ol>
      ) : families.length ? null : (
        <EmptyState art={<EmptyArt kind="saved" />} title={t('pages:saved.empty')} lead={t('pages:saved.howTo')}>
          <Button variant="primary" to="/codes">{t('pages:saved.first')}</Button>
        </EmptyState>
      )}
      {families.length ? <Families families={families} /> : null}
    </Page>
  );
}

/** The families kept from the inheritance calculator: each a link that opens the calculator on it (the family is its
 *  code, after «#», which never leaves the device), the day it was kept, and a way to forget it. */
function Families({ families }: { families: SavedFamily[] }) {
  const { t, i18n } = useInheritanceT();
  return (
    <section aria-labelledby="saved-families" className="flex flex-col gap-3">
      <header className="flex flex-col gap-1">
        <h2 id="saved-families" className="m-0 text-h3 font-semibold">{t('ask.saved.title')}</h2>
        <p className="m-0 max-w-[60ch] text-meta text-ink-soft">{t('ask.saved.lead')}</p>
      </header>
      <ul className="m-0 flex list-none flex-col gap-4 p-0">
        {families.map((f) => (
          <li key={f.code} className="rounded-control border border-rule bg-sheet px-5 py-4 sm:px-7">
            <h3 className="m-0 text-lead font-semibold">
              <Link to={`/topics/family/tools/inheritance#${f.code}`} dir="auto" className="text-ink no-underline hover:text-stamp">{f.name}</Link>
            </h3>
            <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-2 text-meta text-ink-soft">
              <span>{t('ask.saved.on', { date: longDate(dayIn(new Date(f.savedAt)), i18n.language) })}</span>
              <button type="button" onClick={() => void forgetFamily(f.code)} aria-label={t('ask.keep.forgetNamed', { name: f.name })}
                      className="h-11 text-stamp hover:text-stamp-deep">
                {t('ask.saved.forget')}
              </button>
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
