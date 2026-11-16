import { useCallback, useMemo, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { corpusApi, outlineOf, type ArticleItem, type TextDetail } from './corpus.api';

const MORE = 40;
type Place = 'after' | 'before' | 'instead';

/** The articles on the page of a long text (row 7): the window the API sent, more after it as the reader nears
 *  the end, the ones before it on request, and a new window when the outline or a link asks for an article that
 *  is not loaded. A short text is all there from the start. */
export function useArticleWindow(d: TextDetail | undefined, textPath: string, on: string) {
  const fresh = (x: TextDetail | undefined) => ({ src: x, from: x?.range?.[0] ?? 0, items: x?.articles ?? [] as ArticleItem[] });
  // Kept with the answer it came from: a new answer (another version, another text) starts again from it.
  const [state, setState] = useState(() => fresh(d));
  if (state.src !== d) setState(fresh(d));
  // The answer a load was asked for: one that comes back for another text or version is dropped (PX23 of
  // the where-it-trips review: law A's articles were appended to law B's).
  const src = useRef(d);
  src.current = d;
  const [busy, setBusy] = useState(false);
  // A load that failed (offline, an error): said under the articles with a way to try again, never silent (PX23).
  const [failed, setFailed] = useState<null | (() => void)>(null);
  // A long text's outline comes from its own address, once a version (S15 of the performance audit).
  const url = d && !d.outline ? d.outline_url : null;
  const sent = useQuery({ queryKey: ['outline', url], queryFn: () => corpusApi.outline(url!), enabled: Boolean(url), staleTime: Infinity });
  const outline = useMemo(() => (d ? outlineOf(d, sent.data?.outline) : []), [d, sent.data]);
  const asked = useRef('');

  const total = d?.total_articles ?? 0;
  const to = state.from + state.items.length;

  // One request at a time, held in a ref: two scroll frames in a row must not both ask for the same articles.
  const inflight = useRef(false);
  const load = useCallback(async (from: number, count: number, place: Place): Promise<void> => {
    if (inflight.current) return;
    inflight.current = true;
    setBusy(true);
    setFailed(null);
    const asker = src.current;
    try {
      const r = await corpusApi.articles(textPath, from, count, on);
      if (src.current !== asker) return;
      setState((s) => place === 'after' ? { ...s, items: [...s.items, ...r.articles] }
        : place === 'before' ? { ...s, from: r.range[0], items: [...r.articles, ...s.items] }
          : { ...s, from: r.range[0], items: r.articles });
    } catch {
      if (src.current === asker) setFailed(() => () => void load(from, count, place));
    } finally {
      inflight.current = false;
      setBusy(false);
    }
  }, [textPath, on]);

  const more = useCallback(() => { if (to < total) void load(to, MORE, 'after'); }, [load, to, total]);
  const earlier = useCallback(() => {
    const from = Math.max(0, state.from - MORE);
    if (state.from > 0) void load(from, state.from - from, 'before');
  }, [load, state.from]);
  /** The text from its first article (PX2): «من البداية» and a code reopened after reading it deep. */
  const start = useCallback(() => { if (state.from > 0) void load(0, MORE, 'instead'); }, [load, state.from]);
  /** An article by its anchor: loaded around it when it is not on the page. Resolves once it is. */
  const reach = useCallback(async (eid: string) => {
    if (state.items.some((a) => a.eid === eid) || asked.current === eid) return;
    const at = outline.findIndex((o) => o.eid === eid);
    if (at < 0) return;
    asked.current = eid;
    try {
      await load(Math.max(0, at - 2), MORE, 'instead');
    } finally {
      asked.current = '';
    }
  }, [state.items, outline, load]);

  // Whether the outline is in: an article missing from it is missing from the text (PX20), not still on its way.
  const known = !url || sent.isSuccess;
  return { articles: state.items, from: state.from, to, total, outline, known, busy, failed, more, earlier, start, reach };
}
