import { useQuery } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { api } from '@/shared/services/api';
import { go } from '@/shared/services/motion';
import { todayIso } from '@/shared/services/today';
import '@/shared/locales/pages';
import { ArchDoor } from './Arch';
import { useOpenTopic } from './open';
import { useTopics } from './topics.api';

type Calendar = { ahead: { date: string; topic: { slug: string } }[]; behind: { date: string; topic: { slug: string } }[] };
const DAY = 86_400_000;

/** The life topics as doors (U1, U3 of the Moroccan-design review): twelve horseshoe arches, four a row on a phone so
 *  all of them are on the home's first screen, six on a desk; each named by its short name. A door whose law changed in
 *  the last month, or changes in the next three, carries people's saffron mark (30 Oct 2026, the law's calendar). */
export function TopicRow() {
  const { t: tr, i18n } = useTranslation();
  const topics = useTopics();
  const cal = useQuery({ queryKey: ['topics', 'calendar'], queryFn: () => api<Calendar>('/topics/calendar/'), staleTime: 600_000 });
  const now = Date.parse(`${todayIso()}T00:00:00Z`);
  const near = (d: string, days: number) => Math.abs(Date.parse(`${d}T00:00:00Z`) - now) <= days * DAY;
  const marked = new Set([...(cal.data?.ahead ?? []).filter((e) => near(e.date, 92)), ...(cal.data?.behind ?? []).filter((e) => near(e.date, 31))]
    .map((e) => e.topic.slug));
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  const navigate = useNavigate();
  const { pending, warm, open } = useOpenTopic();
  if (!topics.data) return <DoorsSpace />;
  return (
    <ul className="m-0 grid list-none grid-cols-4 gap-x-2 gap-y-3 p-0 sm:grid-cols-6 sm:gap-x-6 sm:gap-y-5">
      {topics.data.map((t) => (
        <li key={t.slug} className="min-w-0">
          <Link to={`/topics/${t.slug}`} lang={lang} aria-busy={pending === t.slug || undefined}
                onPointerEnter={() => warm(t.slug)} onPointerDown={() => warm(t.slug)} onFocus={() => warm(t.slug)}
                onClick={(e) => {
                  if (e.metaKey || e.ctrlKey || e.shiftKey) return;
                  e.preventDefault();
                  // The door grows into the topic's window (U7), once the window is there to grow into.
                  const door = e.currentTarget.querySelector<HTMLElement>('[data-door]');
                  open(t.slug, () => go(navigate, `/topics/${t.slug}`, door, 'topic-arch'));
                }}
                className="group flex flex-col items-center gap-1 text-center text-meta leading-tight text-ink no-underline active:scale-[0.97] motion-reduce:active:scale-100"
                style={pending === t.slug ? { color: 'var(--color-stamp)' } : undefined}>
            <span className="relative block w-full max-w-[74px]">
              <ArchDoor slug={t.slug} className="w-full transition-transform group-hover:-translate-y-0.5 group-aria-busy:motion-safe:animate-pulse motion-reduce:transition-none" />
              {marked.has(t.slug) ? <span aria-hidden="true" style={MARK} /> : null}
            </span>
            {/* A word longer than its door is hyphenated where the phone can, else broken (HM44: «Consommation» ran into
                «Immobilier»). */}
            <span className="line-clamp-2 min-h-[2.5em] [overflow-wrap:anywhere]" style={{ hyphens: 'auto' }}>{(t.short ?? t.name)[lang]}</span>
            {marked.has(t.slug) ? <span className="sr-only">{tr('pages:home2.changing')}</span> : null}
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** People's saffron dot at the arch's top corner: the law of this door changed lately or changes soon. */
const MARK: React.CSSProperties = { position: 'absolute', top: 4, insetInlineEnd: 2, width: 14, height: 14, borderRadius: '50%',
  background: 'var(--color-people-fill)', boxShadow: '0 0 0 3px var(--color-paper)' };

/** The doors' place while they come: three rows on a phone, two on a desk, so nothing below moves. */
export function DoorsSpace() {
  return <div aria-hidden="true" className="aspect-[4/3.3] w-full sm:aspect-[6/2.6]" />;
}
