import { useTranslation } from 'react-i18next';
import type { OutlineEntry } from '../corpus.api';
import { Drawer, FindInText, JumpField, OutlineTree } from './Navigator';

/** The phone's panels from the reading bar: the outline with the jump by number, or the search in the text. */
export default function Panel({ kind, index, textPath, current, asked, onClose }: {
  kind: 'outline' | 'find';
  index: OutlineEntry[];
  textPath: string;
  current: string;
  asked: string;
  onClose: () => void;
}) {
  const { t } = useTranslation();
  if (kind === 'outline') {
    return (
      <Drawer label={t('reading.outline')} onClose={onClose}>
        <div className="border-b border-rule-soft px-4 py-3"><JumpField articles={index} textPath={textPath} onGo={onClose} /></div>
        <nav data-scroll aria-label={t('reading.outline')} className="min-h-0 flex-1 overflow-y-auto overscroll-contain p-2">
          <OutlineTree articles={index} textPath={textPath} current={current} onGo={onClose} />
        </nav>
      </Drawer>
    );
  }
  return (
    <Drawer label={t('reading.find')} onClose={onClose}>
      <div className="flex min-h-0 flex-1 flex-col p-3"><FindInText textPath={textPath} initial={asked} autoFocus={!asked} onGo={onClose} /></div>
    </Drawer>
  );
}
