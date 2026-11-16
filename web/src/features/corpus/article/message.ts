import type { ArticleItem, TextDetail } from '../corpus.api';
import { issueNo } from '../format';

/** A text's name short enough for a message or a line: its title up to «الصادر بتنفيذه» and the date. */
export function shortName(title: string, max = 110): string {
  // «Dahir n° 1-26-71 du … portant promulgation de la loi n° 46-26 relative à …» is known by its law.
  const law = /promulgation\s+de\s+la\s+(loi\b.*)$/i.exec(title);
  if (law) title = law[1][0].toUpperCase() + law[1].slice(1);
  const cut = title.split(/\s+(?:الصادر(?:ة)?\s+بتنفيذه|الصادر(?:ة)?\s+في|بتاريخ|بيان\s+الأسباب|promulguée\s+par|du\s+\d)/)[0].trim();
  const name = cut.replace(/[.\s]+$/, '');
  return name.length <= max ? name : `${name.slice(0, max).replace(/\s+\S*$/, '')}…`;
}

/** An article's words without the reading's Markdown (bold marks, table pipes), on one line each. */
export function plainBody(body: string): string {
  return body.replace(/\*\*/g, '').replace(/^\|?\s*:?-{3,}.*$/gm, '').replace(/\|/g, ' ').replace(/[ \t]+/g, ' ')
    .replace(/\n{2,}/g, '\n').trim();
}

/** Where an article was printed, as people cite it: «الجريدة الرسمية عدد 5824، ص 2168». */
export function sourceLine(a: ArticleItem, d: TextDetail, t: (k: string, o?: Record<string, unknown>) => string): string {
  if (d.version?.consolidation === 'sgg') return t('article.sourceSgg');
  if (d.version?.consolidation === 'adala') return t('article.sourceAdala');
  if (d.version?.consolidation === 'dgi') return t('article.sourceDgi');
  if (!d.issue) return '';
  const issue = t('corpus.issueTitle', { number: issueNo(d.issue, t) });
  return a.page ? `${issue}${t('corpus.listSep')}${t('article.pageShort', { page: a.page })}` : issue;
}

const LIMIT = 700;

/** The message «أرسل» sends (row 13): the article and its text in bold (WhatsApp's *…*), its words up to 700
 *  characters, where it was printed, and its link. In French, the official translation when there is one. */
/** How a message signs (8 Nov 2026): the address people type, after the Arabic name in Arabic, «قانون · 3adala.com»,
 *  and alone in French, where the site's name is the address's own word (15 Nov 2026). Never the ministry's portal
 *  «عدالة». */
export const signature = (lang: string) => {
  const host = typeof location === 'undefined' ? '' : location.hostname.replace(/^www\./, '');
  return lang === 'fr' ? host : `قانون · ${host}`;
};

export function articleMessage(a: ArticleItem, d: TextDetail, origin: string, lang: string,
                               t: (k: string, o?: Record<string, unknown>) => string): string {
  const french = lang === 'fr' && a.french;
  // A constitution's article as people cite it: «الفصل 19 من الدستور», «الفصل 19 من دستور 1996» (C7 of the constitution
  // review).
  const head = french ? `*${a.french!.label} — ${shortName(d.french?.title || d.title)}*`
    : d.constitution ? `*${a.label} من ${d.constitution.cited_as}*` : `*${a.label} — ${shortName(d.title)}*`;
  let body = plainBody(french ? a.french!.body : a.body);
  if (body.length > LIMIT) body = `${body.slice(0, LIMIT).replace(/\s+\S*$/, '')} …`;
  const source = sourceLine(a, d, t);
  return [head, body, french ? t('french.note') : '', source ? t('article.source', { source }) : '', `${origin}${a.path}`,
    signature(lang)].filter(Boolean).join('\n\n');
}
