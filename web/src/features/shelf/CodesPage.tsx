import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { LinesSkeleton, Page } from '@/shared/components/ui';
import { usePageTitle } from '@/shared/services/title';
import { CardHost, Shelves } from '@/features/corpus/library/Books';
import { Find } from '@/features/corpus/library/Find';
import { useDetail, useLibrary, useNum } from '@/features/corpus/library/library.api';
import '@/features/corpus/library.css';
import '@/shared/locales/pages';

/** /codes, «المدونات والقوانين الأساسية»: the library's codes on a page of their own: the box, then the 67 texts people
 *  ask for by name on their nine shelves, every name in view (W7 of the library-search review; the shelves of 15 Nov 2026). */
export default function CodesPage() {
  const { t } = useTranslation();
  const num = useNum();
  usePageTitle([t('pages:lib3.codes.title')]);
  const library = useLibrary();
  const [hits, setHits] = useState<Set<string> | null>(null);
  const [detail, toggleDetail] = useDetail();
  const books = library.data?.branches.reduce((n, b) => n + b.books.length, 0) ?? 67;
  return (
    <Page width="wide" className="lb">
      <CardHost>
        <header className="lb-head">
          <h1>{t('pages:lib3.codes.title')}</h1>
          <p className="lead">{t('pages:lib5.tabs.codesSub', { texts: t('pages:lib2.textsN', { count: books, n: num(books) }), n: library.data?.branches.length ?? 9 })}</p>
        </header>
        <Find id="codes-find" onBooks={setHits} examples={false} />
        {/* The index's place held while it comes (RD16). */}
        <p className="lb-roomtop">
          <span>{t('pages:lib5.codesLead')}</span>
          <button type="button" className="lb-switch" aria-pressed={detail} onClick={toggleDetail}>{t('pages:lib5.detail')}</button>
        </p>
        {library.data ? <Shelves branches={library.data.branches} most={library.data.most} hits={hits} detail={detail} /> : <div className="min-h-svh"><LinesSkeleton /></div>}
      </CardHost>
    </Page>
  );
}
