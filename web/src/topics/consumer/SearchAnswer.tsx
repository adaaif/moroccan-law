import { Link } from 'react-router-dom';
import { askedIn } from './answer';
import { articleLabel, useConsumerT } from './strings';

const TOOLS = { return: 'return', guarantee: 'guarantee', late: 'late' } as const;
const ART = { return: '/ma/loi/31-08/art_36', guarantee: '/ma/loi/31-08/art_65', late: '/ma/loi/31-08/art_13' } as const;

/** A consumer question answered by the topic's own rules (S2 of the consumer plan): the period in words, its
 *  article, and the tool that works out the reader's own day. Nothing for any other question. */
export default function SearchAnswer({ q }: { q: string }) {
  const { t } = useConsumerT();
  const asked = askedIn(q);
  if (!asked) return null;
  return (
    <section className="flex flex-col gap-2 rounded-card bg-sheet px-5 py-4" style={{ ['--t' as string]: 'var(--color-t-consumer)' }}>
      <p className="m-0 text-meta text-ink-soft">{t(`answer.${asked}.over`)}</p>
      <p className="m-0 text-h3 font-bold text-[color:var(--t)]">{t(`answer.${asked}.value`)}</p>
      <p className="m-0 text-body">{t(`answer.${asked}.line`)}{' · '}<Link to={ART[asked]} lang="ar">{articleLabel(ART[asked])}</Link></p>
      <Link to={`/topics/consumer/tools/${TOOLS[asked]}`} className="inline-flex min-h-11 items-center self-start text-body font-semibold">{t(`answer.${asked}.open`)}</Link>
    </section>
  );
}
