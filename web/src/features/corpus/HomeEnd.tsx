import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { BlogLinks } from '@/features/blog/BlogLinks';

/** The home's end, a moment after the page (1 Nov 2026): «قانون بالأرقام», its three newest posts (without links from the
 *  pages people read, nobody would find them), then the library and who makes the site. Its code left the
 *  first load to make room for the posts. */
export default function HomeEnd() {
  const { t } = useTranslation();
  return (
    <>
      <BlogLinks big />
      <Link to="/library" className="flex min-h-14 items-center gap-4 rounded-card bg-sheet px-5 py-5 text-ink no-underline ring-1 ring-transparent hover:ring-stamp-line sm:px-12">
        <span className="grid size-12 shrink-0 place-items-center rounded-card bg-wash text-stamp"><Books /></span>
        <span className="flex min-w-0 flex-col">
          <span className="text-lead font-semibold">{t('nav.library')}</span>
          <span className="text-body text-ink-soft">{t('home.libraryLead')}</span>
        </span>
      </Link>
      {/* Who makes the site, at the end of the home (P18 of the polish review). */}
      <Link to="/about" className="-mt-4 inline-flex min-h-11 items-center self-center text-body font-medium no-underline">{t('nav.about')}</Link>
    </>
  );
}

const Books = () => (
  <svg aria-hidden="true" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round">
    <path d="M5 4h4v16H5zM10 4h4v16h-4zM15.5 5.2l3.4-.9 3.6 15.5-3.4.9z" />
  </svg>
);
