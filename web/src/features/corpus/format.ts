/** Gregorian dates the way Moroccan readers write them; ar-MA and fr-MA both keep Western digits. */
/** An issue's date as the BO's masthead prints it (U13 of the Moroccan-design review): the Hijri date, then the
 *  Gregorian in brackets, «30 ربيع الآخر 1448 (12 أكتوبر 2026)»; in French the Gregorian, the Hijri after it in Arabic.
 *  The Gregorian alone where the masthead was not read. */
export function issueDate(iso: string, hijri: string | undefined, lang: string): string {
  const day = longDate(iso, lang);
  if (!hijri) return day;
  // A French page names the Hijri month as the French edition does (PX29 of the where-it-trips review: it was in Arabic).
  return lang === 'fr' ? `${day} (${hijriFr(hijri)})` : `${hijri} (${day})`;
}

/** A Hijri date with its month named as the French edition names it. */
export const hijriFr = (hijri: string) => hijri.replace(/[\u0600-\u06FF]+(?:\s[\u0600-\u06FF]+)?/, (m) => HIJRI_FR[m] ?? m);

const HIJRI_FR: Record<string, string> = {
  'محرم': 'moharram', 'صفر': 'safar', 'ربيع الأول': 'rabia I', 'ربيع الآخر': 'rabia II', 'ربيع الثاني': 'rabia II',
  'جمادى الأولى': 'joumada I', 'جمادى الآخرة': 'joumada II', 'جمادى الثانية': 'joumada II', 'رجب': 'rejeb', 'شعبان': 'chaabane',
  'رمضان': 'ramadan', 'شوال': 'chaoual', 'ذو القعدة': 'kaada', 'ذي القعدة': 'kaada', 'ذو الحجة': 'hija', 'ذي الحجة': 'hija',
};

export function longDate(iso: string | null | undefined, lang: string): string {
  if (!iso) return '';
  return new Intl.DateTimeFormat(lang === 'fr' ? 'fr-MA' : 'ar-MA', { dateStyle: 'long', timeZone: 'UTC' }).format(
    new Date(`${iso}T00:00:00Z`),
  );
}

/** The article's body as paragraphs: one per line the source kept. */
export function paragraphs(body: string): string[] {
  return body
    .split(/\n+/)
    .map((p) => p.trim())
    .filter(Boolean);
}

export type Row = { cells: string[]; strong: boolean };
/** How a line of the law is set (the review of 18 Oct 2026): `mark` is the enumerator it opens with, printed
 *  apart in a hanging column («1 -», «أ -», «-»), or a part's «أولا:» set in bold; `depth` is its place in the
 *  article's lists (0: a paragraph); `hang` aligns a line without a mark with the text of the item it belongs to.
 *  A paragraph keeps where its words start in the body (`at`), so the article's marks (body offsets) land in it. */
export type ListMark = 'num' | 'letter' | 'dash' | 'ordinal' | '';
export type Para = { kind: 'p'; text: string; at: number; marker: string; mark: ListMark; depth: number; hang: boolean };
export type Block = Para | { kind: 'table'; rows: Row[] };

// The enumerators an article's lines open with, as printed: never «1.58.376» (a number) nor «2026» (a year).
const ENUMERATORS: [Exclude<ListMark, ''>, RegExp][] = [
  ['ordinal', /^((?:أولا|ثانيا|ثالثا|رابعا|خامسا|سادسا|سابعا|ثامنا|تاسعا|عاشرا)\s*[:\-–])\s*/],
  ['num', /^(\d{1,3}\s*[-–—)]|\d{1,3}[°º]|\d{1,3}\.(?=\s))\s*(?=[^\d\s])/],
  ['letter', /^([ء-ي]\s*[-–—)]|[a-z]\))\s*(?=[^\d\s])/],
  ['dash', /^([-–—•])\s*(?=[^\d\s-])/],
];

function enumerator(line: string): { mark: Exclude<ListMark, ''>; marker: string; length: number } | null {
  for (const [mark, re] of ENUMERATORS) {
    const m = re.exec(line);
    if (m) return { mark, marker: m[1].replace(/\s+/g, ' '), length: m[0].length };
  }
  return null;
}

/** The sign a line ends on, past closing quotes and brackets: «:» opens points, «؛» goes on to the next. */
const ending = (text: string) => text.replace(/[\s»)"*]+$/, '').at(-1) ?? '';

/** A body as paragraphs, list items and tables: the OCR writes tables in Markdown, one row a line. A list's
 *  items nest by their kind of mark (a «أ -» under a «7 -»); lines after an item that ends on «:» are its points;
 *  lines between two items belong to the first; anything else ends the list. */
export function blocks(body: string): Block[] {
  const out: Block[] = [];
  for (const m of body.matchAll(/[^\n]+/g)) {
    const raw = m[0];
    const line = raw.trim();
    if (!line) continue;
    const at = (m.index ?? 0) + (raw.length - raw.trimStart().length);
    if (line.startsWith('|')) {
      const raw = line.replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
      if (raw.every((c) => /^:?-{2,}:?$/.test(c))) continue; // the header's rule
      const row = { cells: raw.map((c) => c.replace(/\*\*/g, '')), strong: raw.some((c) => c.startsWith('**')) };
      const last = out.at(-1);
      if (last?.kind === 'table') last.rows.push(row);
      else out.push({ kind: 'table', rows: [row] });
    } else {
      out.push({ kind: 'p', text: line, at, marker: '', mark: '', depth: 0, hang: false });
    }
  }
  const paras = out.filter((b): b is Para => b.kind === 'p');
  const itemAhead = (from: number) => {
    for (const p of paras.slice(from)) {
      const e = enumerator(p.text);
      if (e) return e.mark !== 'ordinal';
    }
    return false;
  };
  let stack: ListMark[] = [];
  let points = false; // inside the points an «…:» opened
  paras.forEach((p, i) => {
    const prev = paras[i - 1];
    const e = enumerator(p.text);
    if (e) {
      points = false;
      if (e.mark === 'ordinal') stack = [];
      else stack = stack.includes(e.mark) ? stack.slice(0, stack.indexOf(e.mark) + 1) : [...stack, e.mark];
      Object.assign(p, { text: p.text.slice(e.length), at: p.at + e.length, marker: e.marker, mark: e.mark, depth: stack.length });
    } else if (prev && ending(prev.text) === ':') {
      points = true;
      Object.assign(p, { depth: prev.depth + 1, hang: true });
    } else if (points && prev && '؛;،,'.includes(ending(prev.text))) {
      Object.assign(p, { depth: prev.depth, hang: true });
    } else if (stack.length && itemAhead(i + 1)) {
      points = false;
      Object.assign(p, { depth: stack.length, hang: true });
    } else {
      points = false;
      stack = [];
    }
  });
  return out;
}

/** Numbers as the BO prints them in a table («1 234 567», «1.234.567,50», «(12 000)» negative), or null. */
export function tableNumber(cell: string): number | null {
  const c = cell.replace(/[\s\u00a0\u202f]/g, '');
  const m = /^(\()?(-)?(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d+))?(\))?$/.exec(c);
  if (!m) return null;
  const value = Number(`${m[3].replace(/\./g, '')}.${m[4] ?? '0'}`);
  return m[1] || m[2] ? -value : value;
}

/** The law's own words are Arabic, set right to left whatever the interface's language. */
export const AR = { lang: 'ar', dir: 'rtl' } as const;

/** An issue's number as printed: «7533», «7465 مكرر» / «7465 bis». */
export function issueNo(issue: { number: number; suffix?: string; edition?: string }, t: (key: string) => string): string {
  const n = issue.suffix ? `${issue.number} ${t(`corpus.suffix.${issue.suffix}`)}` : String(issue.number);
  // The French edition's numbers are another series (Arabic BO 190 and French BO 190 are two issues of 1916).
  return issue.edition === 'translation_fr' ? `${n} ${t('article.extras.french').toLowerCase()}` : n;
}

/** /ma/loi/50-25/art_6 → the text's address and the article it opens on. */
export function splitAddress(pathname: string): { textPath: string; focus: string } {
  const parts = pathname.replace(/\/+$/, '').split('/');
  const last = parts.at(-1) ?? '';
  const focus = last.startsWith('art_') || last === 'annex' ? last : '';
  return { textPath: focus ? parts.slice(0, -1).join('/') : parts.join('/'), focus };
}

/** A table whose last row is its total («المجموع…», «Total…»), the rows above it plain amounts: true when each
 *  amount column adds up (to the unit), false when one does not, null when there is nothing to check. */
export function totalCheck(rows: Row[]): boolean | null {
  const label = (r: Row) => (r.cells.find((c) => tableNumber(c) === null) ?? '').replace(/\u0640/g, '');
  const isTotal = (r: Row) => /^(?:\*\*)?\s*(?:المجموع|مجموع|Total)/i.test(label(r));
  const last = rows.at(-1);
  if (!last || !isTotal(last) || rows.slice(1, -1).some(isTotal) || rows.length < 3) return null;
  let compared = 0;
  for (let c = 0; c < last.cells.length; c++) {
    const total = tableNumber(last.cells[c]);
    if (total === null) continue;
    const parts = rows.slice(1, -1).map((r) => tableNumber(r.cells[c] ?? ''));
    if (parts.some((p) => p === null)) continue;
    compared++;
    const sum = parts.reduce<number>((a, b) => a + (b ?? 0), 0);
    if (Math.abs(sum - total) >= 1) return false;
  }
  return compared ? true : null;
}

/** An article's name: its label as printed, or «النص» for a text printed in one piece with no label of its own
 *  (a Constitutional Court decision, an opinion, a licence). */
export function articleName(label: string, t: (key: string) => string): string {
  return label || t('article.whole');
}

/** «المادة 419» as a margin sets it: the word small, the number large («مادة فريدة» whole). */
export function splitLabel(label: string): [string, string] {
  const m = label.match(/^(المادة|الفصل|Article|Art\.)\s+(.+)$/);
  return m ? [m[1], m[2]] : ['', label];
}

/** The words that open a division of a code («الباب الأول: …», «Titre II»): a heading that does not open with one is
 *  no part (P12 of the polish review: the end of a title or of an article, cut off by a reading, is not a part).
 *  A lookahead, not `\b`: in a JavaScript pattern `\b` never falls after an Arabic letter. */
export const DIVISION = /^(الكتاب|القسم|الباب|باب|الجزء|الفرع|الفصل|المبحث|الشطر|Livre|Titre|Chapitre|Section|Partie)(?=[\s:،.-]|$)/;

/** An article's first words, for the outline: «يبرم عقد الكراء وجوبا بمحرر كتابي…». */
export function firstWords(body: string, most = 8): string {
  const words = body.replace(/\*\*|\||-{3,}|^#+\s*/gm, ' ').split(/\s+/).filter(Boolean);
  return words.slice(0, most).join(' ') + (words.length > most ? '…' : '');
}
