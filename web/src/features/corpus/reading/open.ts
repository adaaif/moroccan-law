import type { QueryClient } from '@tanstack/react-query';
import type { NavigateFunction } from 'react-router-dom';
import { go } from '@/shared/services/motion';
import { corpusApi } from '../corpus.api';
import { splitAddress } from '../format';

/* An article opened from a peek (30 Oct 2026: a reader could not tell which article the peek had opened): the peek's
   label becomes the article's number on the law's page, where the article lands lit (reading/landing.css) with the
   way back to the page the peek was opened on. */

/** While the pointer rests on the way to the article: its text and the landing's code, so that the page is there
 *  when the finger lifts and the label has a number to land on. */
export function warmArticle(qc: QueryClient, path: string) {
  const { textPath } = splitAddress(path);
  void qc.prefetchQuery({ queryKey: ['textAt', textPath, ''], queryFn: () => corpusApi.textAt(path), staleTime: 600_000 });
  void import('./Place');
  void import('./landing.css');
}

/** Opens the article, its label flying to its number, and then closes the peek (`close`; an article of the same law
 *  keeps the page, and the peek with it). The page it was opened on is named by its own title (a page that keeps its
 *  title discreet stays so), for the way back. The peek's entry in the history (the phone's back closes a sheet) is
 *  taken over first, so that closing it does not go back: back from the article is the page, not a page whose peek
 *  has gone. */
export function openArticle(navigate: NavigateFunction, path: string, label: HTMLElement | null, close: () => void) {
  const parts = document.title.split(' — ');
  const from = parts.length > 1 ? parts[0] : null;
  const replace = (window.history.state as { sheet?: number } | null)?.sheet !== undefined;
  go((to) => { navigate(to, { state: from ? { from } : null, replace }); close(); }, path, label, 'article-label');
}
