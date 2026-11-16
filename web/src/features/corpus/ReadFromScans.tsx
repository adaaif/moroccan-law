import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import type { TextDetail } from './corpus.api';

/** A text whose words a model read from the images of an archive issue's pages keeps its printed page a tap away (UX3
 *  of the phone-test review): the Bulletin prevails, and a reading of it is not the Bulletin. Since 15 Nov 2026 it
 *  no longer says who read it or that the reading may be wrong in a few words: «عن «قانون»» says it once (#ab-who), and
 *  the row under each article still says «خطأ في القراءة؟». Nothing when there is no page to open. */
export default function ReadFromScans({ d }: { d: TextDetail }) {
  const { t } = useTranslation();
  if (!d.version?.read_from_scans) return null;
  const page = d.issue?.document_id && d.page_index !== null && d.page_index !== undefined
    ? `/pages/${d.issue.document_id}/${d.page_index}` : null;
  if (!page) return null;
  return (
    <p className="m-0 max-w-[64ch] text-meta text-ink-soft">
      <Link to={page} className="font-medium">{t('corpus.seePrinted')}</Link>
    </p>
  );
}
