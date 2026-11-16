import { Fragment } from 'react';
import { Link } from 'react-router-dom';

/** A chapter of the constitutions' short history (C4), its links written «[(الفصل 5)](art_5)» to the constitution at
 *  `path` («()» the text itself): every claim leads to the article that shows it. */
export function Story({ words, path }: { words: string; path: string }) {
  const parts = words.split(/(\[[^\]]+\]\([^)]*\))/);
  return (
    <>
      {parts.map((p, i) => {
        const m = /^\[([^\]]+)\]\(([^)]*)\)$/.exec(p);
        if (!m) return <Fragment key={i}>{p}</Fragment>;
        return <Link key={i} to={m[2] ? `${path}/${m[2]}` : path} className="whitespace-nowrap underline underline-offset-4">{m[1]}</Link>;
      })}
    </>
  );
}
