import { useEffect } from 'react';

/** D9: discussions, people's pages and the open questions stay out of search engines at first, so a case someone
 *  wrote about does not follow them on Google. robots.txt says so too. */
export function useNoIndex() {
  useEffect(() => {
    const meta = document.createElement('meta');
    meta.name = 'robots';
    meta.content = 'noindex, nofollow';
    document.head.appendChild(meta);
    return () => meta.remove();
  }, []);
}
