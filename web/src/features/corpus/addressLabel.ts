// A site address said in words (R3 of the for-everyone review: no raw address shown to a reader): «/ma/loi/67-12/art_33»
// is «المادة 33» inside law 67.12's page, «القانون 67.12، المادة 33» elsewhere; «/ma/decret/2-26-434» is «مرسوم 2.26.434».
const KINDS: Record<string, [string, string]> = {
  loi: ['القانون', 'Loi'], 'loi-organique': ['القانون التنظيمي', 'Loi organique'], decret: ['المرسوم', 'Décret'],
  'decret-loi': ['المرسوم بقانون', 'Décret-loi'], dahir: ['الظهير', 'Dahir'], arrete: ['القرار', 'Arrêté'],
  decision: ['المقرر', 'Décision'], code: ['المدونة', 'Code'],
};

export function addressLabel(path: string, lang: string, here = ''): string {
  const m = path.match(/^\/ma\/([a-z-]+)\/(?:\d{4}\/)?([^/]+)(?:\/art_([^/]+))?$/);
  if (!m) return path;
  const [, kind, number, article] = m;
  const fr = lang === 'fr';
  const art = article ? (fr ? `article ${article}` : `المادة ${article}`) : '';
  const textPath = path.replace(/\/art_[^/]+$/, '');
  if (article && textPath === here) return art;
  const name = `${(KINDS[kind] ?? ['النص', 'Texte'])[fr ? 1 : 0]} ${number.replace(/-/g, '.')}`;
  return art ? `${name}${fr ? ', ' : '، '}${art}` : name;
}
