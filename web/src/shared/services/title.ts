import { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

/** The browser tab's name for a page (P1 of the polish review): its own words first, then the site's name. In-app navigation
 *  used to keep the first page's name on every later page, in history, bookmarks and the tab switcher. Parts that
 *  are empty are left out; no parts at all is the site's name alone. */
/** The name the page drawn last gave itself where no effect runs (the prerender, in Node): scripts/prerender.mjs heads the
 *  pages it writes with it, so a page's name is written once, in the page. */
export const drawn = { title: '' };

export function usePageTitle(parts: (string | null | undefined)[]) {
  const { t } = useTranslation();
  const title = [...parts.filter((p): p is string => Boolean(p && p.trim())), t('app.name')].join(' — ');
  if (typeof document === 'undefined') drawn.title = title;
  useEffect(() => {
    if (typeof document !== 'undefined') document.title = title;
  }, [title]);
}
