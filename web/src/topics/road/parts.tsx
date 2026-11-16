import { Link } from 'react-router-dom';
import { articleLabel } from './strings';

/** The articles a result rests on, as chips leading to them; the law's names stay Arabic. */
export function Arts({ paths }: { paths: string[] }) {
  return (
    <span className="flex flex-wrap gap-1.5">
      {[...new Set(paths)].map((p) => (
        <Link key={p} to={p} lang="ar" dir="rtl" className="inline-flex min-h-11 items-center rounded-full bg-wash px-2.5 text-meta text-stamp no-underline hover:underline">
          {articleLabel(p)}
        </Link>
      ))}
    </span>
  );
}

export const FIELD = 'h-12 w-full min-w-0 rounded-control border border-field bg-sheet px-3 text-body';
export const CARD = 'flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7';
