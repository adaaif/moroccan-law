import { Fragment, type ReactNode } from 'react';
import { pick, type Named } from '../api';

/** A figure as the reader's language writes it: the bill's «60.000» is «60 000» in French. */
export const local = (v: string, lang: string) => (lang === 'fr' && /^\d{1,3}(\.\d{3})+%?$/.test(v) ? v.replace(/\./g, '\u202f') : v);
export const words = (v: Named | string | undefined, lang: string) => (typeof v === 'string' ? local(v, lang) : pick(v, lang));
/** Each figure kept left to right inside a right-to-left line: «35% ولا 25%» had shown its last as «%25». */
export function iso(s: string): ReactNode {
  return s.split(/(\d[\d.,\u202f]*(?:\s?%)?)/).map((part, i) => (i % 2 ? <bdi key={i} dir="ltr">{part}</bdi> : <Fragment key={i}>{part}</Fragment>));
}
