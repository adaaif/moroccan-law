import { Link } from 'react-router-dom';
import type { OutlineEntry } from '@/features/corpus/corpus.api';
import { AR } from '@/features/corpus/format';
import { useCounts } from './discussion.api';
import { useT } from './strings';

/** On a text's profile (R4, R12 of the for-everyone review): its articles the topics' posts cite most, by name, each a door
 *  to the posts about it. The same request as the articles' counts. */
export default function TextTalk({ textPath, outline }: { textPath: string; outline: OutlineEntry[] }) {
  const { t } = useT();
  const counts = useCounts(textPath);
  const all = Object.entries(counts.data?.articles ?? {});
  if (!all.length) return null;
  const label = new Map(outline.map((o) => [o.eid, o.label]));
  const top = all.filter(([eid]) => label.has(eid)).sort((x, y) => y[1].count - x[1].count).slice(0, 3);
  // A desk's side column and, since U4 of the Moroccan-design review, a phone under the parts: one line that scrolls
  // sideways, so article 1 starts on the first screen.
  return (
    <section className="flex flex-col gap-1.5" data-noprint>
      <h2 className="m-0 text-meta font-semibold text-ink-soft">{t('textTalkTop')}</h2>
      <ul className="m-0 -mx-5 flex list-none gap-1.5 overflow-x-auto px-5 pb-1 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:px-0">
        {top.map(([eid, a]) => (
          <li key={eid} className="shrink-0">
            <Link to={`/discussion${textPath}/${eid}`}
                  className="inline-flex min-h-11 items-center gap-1.5 rounded-full bg-talk-wash px-3 text-meta text-ink no-underline hover:text-talk">
              <bdi {...AR} className="font-semibold">{label.get(eid)}</bdi>
              <span className="text-talk">{a.count}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
