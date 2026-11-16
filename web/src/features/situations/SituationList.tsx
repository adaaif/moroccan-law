import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useSituations } from '@/features/corpus/corpus.api';
import { topicColour } from '@/features/topics/colour';
import { SituationArt } from './SituationArt';
import { situationPath, situationTopic } from './to';

/** The situations as a list of doors, each its title (the home shows the first ones). Drafts reach only a
 *  developer's page, and say so once, under the list. */
export function SituationList({ limit, tiles = false }: { limit?: number; tiles?: boolean }) {
  const { i18n } = useTranslation();
  const situations = useSituations();
  const list = (situations.data ?? []).slice(0, limit);
  if (!list.length) return null;
  const lang = i18n.language === 'fr' ? 'fr' : 'ar';
  if (tiles) {
    // The home's guides as picture tiles, two by three (P15, P19 of the polish review), each in its topic's colour.
    return (
      <div className="flex flex-col gap-3">
        <ul className="m-0 grid list-none gap-2 p-0 sm:grid-cols-2 lg:grid-cols-3">
          {list.map((s) => (
            <li key={s.slug} style={topicColour(situationTopic(s.slug, s.topic))}>
              <Link to={situationPath(s.slug)} lang={lang}
                    className="flex h-full min-h-14 items-center gap-3 rounded-card bg-[color-mix(in_srgb,var(--t)_9%,var(--color-sheet))] p-2.5 text-ink no-underline hover:text-stamp sm:p-3">
                <SituationArt slug={s.slug} topic={situationTopic(s.slug, s.topic)} size={36} />
                <span className="min-w-0 text-body font-semibold leading-snug">{s.title[lang]}</span>
              </Link>
            </li>
          ))}
        </ul>
      </div>
    );
  }
  return (
    <div className="flex flex-col gap-3">
      <ul className="m-0 grid list-none gap-x-10 border-b border-rule p-0 sm:grid-cols-2 lg:grid-cols-3">
        {list.map((s) => (
          <li key={s.slug} className="border-t border-rule">
            <Link to={situationPath(s.slug)} lang={lang}
                  className="flex min-h-14 items-center py-3 text-lead leading-snug text-ink no-underline hover:text-stamp">
              {s.title[lang]}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
