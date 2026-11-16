import { useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useLocation } from 'react-router-dom';
import { SearchBox } from '@/features/search/SearchBox';
import { Sheet } from '@/shared/components/Sheet';

/** The search one tap away on every page (UX5 of the phone-test review): the home's box, focused, with the last
 *  searches kept on this device and the suggestions as one types. It closes once a search or a suggestion takes the
 *  reader somewhere. Its code loads on the first tap: the first load has no room. */
export default function SearchSheet({ onClose }: { onClose: () => void }) {
  const { t } = useTranslation();
  const where = useLocation();
  const opened = useRef(where.key);
  useEffect(() => {
    if (where.key !== opened.current) onClose();
  }, [where.key, onClose]);
  return (
    <Sheet label={t('nav.search')} onClose={onClose} closeButton centered>
      {/* Tall enough for the suggestions, which open under the box, to stay inside the sheet (a style, not a class:
          the stylesheet has no room either). */}
      <div className="flex flex-col gap-3 pb-2" style={{ minHeight: '70vh' }}>
        <SearchBox autoFocus />
      </div>
    </Sheet>
  );
}
