import { useTranslation } from 'react-i18next';
import type { TextDetail } from './corpus.api';
import { longDate } from './format';

/** How far the site has read the Bulletin for this text, in one line on its first screen (N4 of
 *  the read-and-trusted review): a reader's first question about a law is whether it is today's. The long sentence, with the issues
 *  missing, stays in «حول هذا النص». */
export function ReadTo({ d }: { d: TextDetail }) {
  const { t, i18n } = useTranslation();
  const c = d.version ? d.standing?.coverage : null;
  const latest = c?.latest;
  if (!latest) return null;
  return (
    <p className="m-0 text-meta text-ink-soft">
      {t('corpus.readTo', { number: latest.key.replace('-bis', ` ${t('corpus.suffix.bis')}`), date: longDate(latest.date, i18n.language) })}
      {/* An archive text: how many issues since it are unread, beside «لم نجد ما ينسخه» (UX3). */}
      {c.partial ? t('corpus.notRead', { count: c.missing_count ?? c.missing.length }) : null}
    </p>
  );
}
