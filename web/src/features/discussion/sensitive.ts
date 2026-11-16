// Where questions are often personal (R12 of the for-everyone review): the family code, the labour code, the penal code and
// criminal procedure, the housing lease, the law on violence against women; and the topics that hold them (29 Oct
// 2026). They offer help nearby, and asking without a name before the question is written.
const SENSITIVE = ['/ma/loi/70-03', '/ma/loi/65-99', '/ma/dahir/1-59-413', '/ma/loi/22-01', '/ma/loi/67-12', '/ma/loi/103-13',
                   '/talk/family', '/talk/work', '/talk/justice', '/talk/housing', '/talk/health', '/talk/digital'];

export const isSensitive = (path: string) => SENSITIVE.some((p) => path === p || path.startsWith(`${p}/`));
