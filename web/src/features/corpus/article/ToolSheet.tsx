import { cloneElement, isValidElement } from 'react';
import { useTranslation } from 'react-i18next';
import type { ArticleItem, TextDetail } from '../corpus.api';
import { AR, articleName } from '../format';
import { textName } from '../names';
import { Sheet } from '@/shared/components/Sheet';
import { ArticleMore } from './ArticleActions';

/** A phone's «⋯» for an article (P13 of the polish review): its label, the name of its text and where its words were
 *  printed, then «حفظ» (RD19: the sheet is how a reader reaches an article that is not in focus) and the tools beyond
 *  the row: its voice, following it, the printed page, an error to report, the code for another site. Sharing has its
 *  own sheet. */
export function ToolSheet({ a, d, frenchFirst, stamp, label, onClose }: {
  a: ArticleItem;
  d: TextDetail;
  frenchFirst: boolean;
  stamp: React.ReactNode;
  label: string;
  onClose: () => void;
}) {
  const { t, i18n } = useTranslation();
  // A copy's page is its file's, and the stamp says whose: «الصفحة 14 من ملف بوابة عدالة» (RD5 of
  // the readers review: under the family code «الصفحة 14» read as the Bulletin's). Said here, where the pages' strings have come:
  // the law's own code, loaded first, has no room for them.
  const file = d.version && ['adala', 'sgg', 'dgi'].includes(d.version.consolidation) ? d.version.consolidation : null;
  if (file && a.page && isValidElement<{ pageWords?: string }>(stamp) && i18n.exists(`pages:corpus.pageOfFile.${file}`)) {
    stamp = cloneElement(stamp, { pageWords: t(`pages:corpus.pageOfFile.${file}`, { page: a.page }) });
  }
  return (
    <Sheet label={label} onClose={onClose} half closeButton>
      <div className="mb-2 flex flex-wrap items-center gap-3 border-b border-rule pb-3">
        <div className="flex min-w-0 flex-1 flex-col">
          <span {...AR} className="font-law text-h2 font-bold leading-tight">{articleName(a.label, t)}</span>
          <span dir="auto" className="text-meta text-ink-soft">{textName(d, i18n.language)}</span>
        </div>
        {stamp}
      </div>
      <ArticleMore a={a} d={d} frenchFirst={frenchFirst} save />
    </Sheet>
  );
}
