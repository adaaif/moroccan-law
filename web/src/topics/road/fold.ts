/** The words a reader may type folded the same way as the offences' words: no short vowels, one alef, ه for ة. */
const MARKS = /[ً-ٟ]|ٰ|ـ|[̀-ͯ]/g;
export const fold = (s: string) => s.toLowerCase().normalize('NFKD').replace(MARKS, '')
  .replace(/[أإآٱ]/g, 'ا').replace(/ة/g, 'ه').replace(/ى/g, 'ي')
  .replace(/ؤ/g, 'و').replace(/ئ/g, 'ي').trim();
