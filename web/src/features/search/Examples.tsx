import { useState, useTransition } from 'react';
import { useTranslation } from 'react-i18next';
import { Link, useNavigate } from 'react-router-dom';
import { useQueryClient } from '@tanstack/react-query';
import { AR } from '@/features/corpus/format';
import { chipClass } from '@/shared/components/buttons';
import { EXAMPLES, EXAMPLES_FR } from './examples';
import { askEarly } from './search.api';

/** Searches a reader can tap, to see what the box understands; `line` keeps them on one line that scrolls sideways
 *  (the home), rather than rows of chips. */
export function Examples({ size = 'small', line = false }: { size?: 'small' | 'big'; line?: boolean }) {
  const { i18n } = useTranslation();
  const french = i18n.language === 'fr';
  const client = useQueryClient();
  const navigate = useNavigate();
  // As the box (HM7): the question leaves with the tap and the chip pulses until the search page shows.
  const [going, start] = useTransition();
  const [chosen, setChosen] = useState('');
  return (
    <ul className={`m-0 flex min-w-0 list-none gap-2 p-0 ${line ? '-me-4 flex-nowrap overflow-x-auto pe-4 sm:me-0 sm:pe-0 [mask-image:linear-gradient(to_right,black_calc(100%-2.5rem),transparent)] [scrollbar-width:none] rtl:[mask-image:linear-gradient(to_left,black_calc(100%-2.5rem),transparent)]' : 'flex-wrap'}`}>
      {(french ? EXAMPLES_FR : EXAMPLES).map((x) => (
        <li key={x} className="shrink-0">
          <Link {...(french ? { lang: 'fr', dir: 'ltr' as const } : AR)} to={`/search?q=${encodeURIComponent(x)}`}
                onClick={(e) => {
                  if (e.metaKey || e.ctrlKey || e.shiftKey) return;
                  e.preventDefault();
                  askEarly(client, x, i18n.language);
                  setChosen(x);
                  start(() => navigate(`/search?q=${encodeURIComponent(x)}`));
                }}
                className={chipClass(going && chosen === x, `whitespace-nowrap ${going && chosen === x ? 'motion-safe:animate-pulse' : ''} ${size === 'big' ? 'h-11 text-body' : ''}`)}>
            {x}
          </Link>
        </li>
      ))}
    </ul>
  );
}
