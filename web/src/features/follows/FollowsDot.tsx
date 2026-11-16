import { useTranslation } from 'react-i18next';
import '@/shared/locales/pages';
import { useNews } from './follows.api';
import { useFollows } from './store';

/** A dot on «أنا» when something one follows changed since one last looked (R13). Loaded only for a device that
 *  follows something. */
export default function FollowsDot() {
  const { t } = useTranslation();
  const follows = useFollows();
  const news = useNews(follows.map((f) => f.path));
  const fresh = news.data?.news.some((n) => {
    const seen = follows.find((f) => f.path === n.path)?.seen ?? [];
    return n.items.some((i) => !seen.includes(i.key));
  });
  if (!fresh) return null;
  return <span role="status" aria-label={t('pages:follow.fresh')} className="absolute -top-0.5 end-[calc(50%-16px)] size-2.5 rounded-full bg-people-fill ring-2 ring-sheet" />;
}
