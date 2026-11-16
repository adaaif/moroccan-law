/** The plain reading of «وزارة التعليم» (post 26), kept apart from the drawing so it can be tested: which strand a name
 *  belongs to (the schools, higher education, or both at once). */
export type Strand = 'school' | 'higher' | 'both';

export function strand(name: string): Strand {
  const higher = /التعليم العالي|العالي/.test(name);
  const school = /التربية|التهذيب|الابتدائي|الثانوي/.test(name);
  return higher && school ? 'both' : higher ? 'higher' : 'school';
}
