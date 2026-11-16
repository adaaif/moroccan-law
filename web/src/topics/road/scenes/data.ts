/** The road's scenes (R8 of the road plan), each an article you can see: the rule in the decree on the rules of the
 *  road (2.10.420, as Adala consolidated it to 24 August 2026) and what a breach costs in the code (52.05: the class,
 *  art. 219's price, art. 99's points). Shown before a specialist's review by an editorial call (Q2), and said so. */
import type { Key, Named, SceneDef } from './engine';
import { SHAPES } from './signs';

/** A scene asks before it shows (S1 of the road tools review): its question on the still frame, the choices, and for
 *  a wrong choice what would happen — the actors' other paths, where they meet, what is said there. */
export type Ask = {
  q: Named;
  choices: { label: Named; right?: boolean; actor?: number }[];
  wrong?: { actors: Record<number, { d?: string; keys: Key[] }>; clash: [number, number]; at: number; dur: number; says: Named;
            flags?: SceneDef['flags'] };
  /** Said after a wrong choice that has nothing to show (a figure, not a move). */
  because?: Named;
};
/** A scene: the rule, the articles, and what a breach costs — the fine tool's offence, whose price and points the page
 *  works out from the rates (S4), or a line where the breach has no fine of its own here. */
export type Scene = SceneDef & { key: string; title: Named; rule: Named; cites: string[]; offence?: string; costNote?: Named; ask?: Ask };

const YOU = { ar: 'أنت', fr: 'Vous' };
const rules = (n: number) => `/ma/decret/2-10-420/art_${n}`;
const code = (n: number) => `/ma/loi/52-05/art_${n}`;

export const SCENES: Scene[] = [
  {
    key: 'priority', title: { ar: 'الأسبقية لليمين', fr: 'La priorité à droite' },
    rule: { ar: 'في تقاطع طريقين لهما نفس الأولوية، يسمح القادم من اليسار بمرور الآخر (المادة 36 من مرسوم قواعد السير).', fr: 'À l’intersection de deux routes de même priorité, celui qui vient de gauche laisse passer l’autre (art. 36 du décret 2-10-420).' },
    offence: 'priority',
    ask: {
      q: { ar: 'تقاطع بلا علامة ولا ضوء. من يمر أولا؟', fr: 'Carrefour sans panneau ni feu. Qui passe d’abord ?' },
      choices: [{ label: { ar: 'أنا', fr: 'Moi' }, actor: 0 }, { label: { ar: 'القادم من يميني', fr: 'Celui qui vient de ma droite' }, actor: 1, right: true }],
      wrong: { actors: { 0: { keys: [[0, 0], [1700, 0.285], [2600, 0.52]] }, 1: { keys: [[0, 0], [600, 0.06], [2600, 0.45]] } }, clash: [195, 105], at: 2600, dur: 3800,
               says: { ar: 'هنا تلتقيان. الأسبقية كانت للقادم من يمينك.', fr: 'Vous vous rencontrez ici. La priorité était à celui de votre droite.' } },
    },
    cites: [rules(36), code(185), code(219), code(99)],
    road: 'crossroads', dur: 7600, still: 1900,
    guides: [['M195 236 V178', 'var(--s-you)'], ['M352 105 H232', 'var(--s-other)']],
    actors: [
      { d: 'M195 265 V-40', colour: 'var(--s-you)', label: YOU, tagAt: [30, 0], keys: [[0, 0], [1700, 0.285], [4300, 0.285], [7600, 1]] },
      { d: 'M395 105 H-40', colour: 'var(--s-other)', glow: [[1700, 4300]], label: { ar: 'من يمينك', fr: 'à votre droite' }, keys: [[0, 0], [600, 0.06], [4200, 0.86], [5200, 1]] },
    ],
    steps: [
      { t: 0, ar: 'تقاطع بلا علامة ولا ضوء: من يمر أولا؟', fr: 'Un carrefour sans panneau ni feu : qui passe d’abord ?' },
      { t: 1700, ar: 'القادم من يمينك له الأسبقية: توقف ودعه يمر.', fr: 'Celui qui vient de votre droite a la priorité : arrêtez-vous, laissez-le passer.' },
      { t: 4300, ar: 'الطريق خالية: مر الآن.', fr: 'La voie est libre : passez.' },
    ],
  },
  {
    key: 'stop', title: { ar: 'علامة قف', fr: 'Le stop' },
    rule: { ar: 'عند علامة «قف»، يتوقف السائق في حدود القارعة، ثم يسمح بالمرور للمركبات الأخرى (المادة 38).', fr: 'Au stop, le conducteur s’arrête à la limite de la chaussée, puis laisse passer les autres véhicules (art. 38).' },
    offence: 'redLight',
    ask: {
      q: { ar: 'علامة «قف» والطريق تبدو خالية. ماذا تفعل؟', fr: 'Un stop, et la voie semble libre. Que faites-vous ?' },
      choices: [{ label: { ar: 'أتوقف تماما عند الخط', fr: 'Je m’arrête complètement à la ligne' }, right: true }, { label: { ar: 'أمر ببطء', fr: 'Je passe doucement' } }],
      wrong: { actors: { 0: { keys: [[0, 0], [1800, 0.26], [2700, 0.43]] }, 1: { keys: [[0, 0], [2700, 0.53]] } }, clash: [195, 135], at: 2700, dur: 3800,
               says: { ar: 'السيارة الأخرى كانت قادمة. الوقوف التام هو ما يجعلك تراها.', fr: 'L’autre voiture arrivait. C’est l’arrêt complet qui vous la fait voir.' } },
    },
    cites: [rules(38), code(184), code(219), code(99)],
    road: 'crossroads', dur: 7400, still: 2100,
    decor: [(svg, el, sign) => { el('path', { d: 'M181 157 H209', stroke: 'var(--s-line)', 'stroke-width': 4 }, svg); sign(svg, 'stop', 240, 180, 34); }],
    guides: [['M195 236 V182', 'var(--s-you)']],
    actors: [
      { d: 'M195 265 V-40', colour: 'var(--s-you)', label: YOU, tagAt: [-34, 0], keys: [[0, 0], [1800, 0.285], [4600, 0.285], [7400, 1]] },
      { d: 'M-40 135 H400', colour: 'var(--s-third)', keys: [[0, 0], [2300, 0.08], [4300, 0.82], [5000, 1]] },
    ],
    steps: [
      { t: 0, ar: 'علامة «قف»: توقف تماما عند الخط، ولو بدت الطريق خالية.', fr: 'Stop : arrêt complet à la ligne, même si la voie semble libre.' },
      { t: 1800, ar: 'توقفت. انظر إلى اليسار وإلى اليمين.', fr: 'Vous êtes arrêté : regardez à gauche et à droite.' },
      { t: 4600, ar: 'حين تخلو الطريق، انطلق.', fr: 'Quand la voie est libre, repartez.' },
    ],
  },
  {
    key: 'roundabout', title: { ar: 'الملتقى الدائري', fr: 'Le giratoire' },
    rule: { ar: 'قبل التوغل في ملتقى دائري معلن عنه بالعلامة الملائمة، يفسح السائق المجال لمن هو داخله (المادة 78)؛ وتغيير المسلك داخله يخضع لقواعد الأسبقية (المادة 37).', fr: 'Avant d’entrer dans un giratoire signalé par le panneau approprié, on cède le passage à ceux qui y circulent (art. 78) ; changer de voie à l’intérieur suit les règles de priorité (art. 37).' },
    offence: 'priority',
    ask: {
      q: { ar: 'سيارة تدور داخل الملتقى. من يمر أولا؟', fr: 'Une voiture tourne dans l’anneau. Qui passe d’abord ?' },
      choices: [{ label: { ar: 'أنا', fr: 'Moi' }, actor: 0 }, { label: { ar: 'التي داخل الملتقى', fr: 'Celle qui est dans l’anneau' }, actor: 1, right: true }],
      wrong: { actors: { 0: { keys: [[0, 0], [1500, 0.168], [2600, 0.306]] }, 1: { keys: [[0, 0.02], [2600, 0.495]] } }, clash: [195, 172], at: 2600, dur: 3800,
               says: { ar: 'هنا تلتقيان. من داخل الملتقى له الأسبقية.', fr: 'Vous vous rencontrez ici. Celui qui est dans l’anneau a la priorité.' } },
    },
    cites: [rules(78), rules(37), code(185), code(99)],
    road: 'roundabout', dur: 8200, still: 2700,
    decor: [(svg, _el, sign) => sign(svg, 'yield', 238, 214, 30)],
    guides: [['M195 236 V200', 'var(--s-you)']],
    actors: [
      { d: 'M195 270 V172 A54 54 0 0 0 232 135 H400', colour: 'var(--s-you)', label: YOU, tagAt: [-34, 0], keys: [[0, 0], [1500, 0.168], [4700, 0.168], [8200, 1]] },
      { d: 'M-30 135 H128 A54 54 0 0 0 180 174 A54 54 0 0 0 234 120 A54 54 0 0 0 195 68 V-40', colour: 'var(--s-other)', glow: [[1500, 4400]], keys: [[0, 0.02], [5200, 0.8], [6400, 1]] },
    ],
    steps: [
      { t: 0, ar: 'عند مدخل الملتقى علامة «فسح المرور».', fr: 'À l’entrée du giratoire, un panneau « cédez le passage ».' },
      { t: 1500, ar: 'من يدور داخل الملتقى له الأسبقية: توقف عند الخط المتقطع.', fr: 'Ceux qui sont dans l’anneau passent d’abord : arrêtez-vous à la ligne.' },
      { t: 4700, ar: 'ادخل ودر إلى يمينك، وأشر قبل الخروج.', fr: 'Entrez, tournez à droite, mettez le clignotant avant de sortir.' },
    ],
  },
  {
    key: 'overtaking', title: { ar: 'التجاوز', fr: 'Le dépassement' },
    rule: { ar: 'لا يقطع السائق الخط المتصل (المادة 6)؛ يتجاوز من اليسار (المادة 24) بعد أن يتأكد أنه يستطيع ذلك دون خطر، ويبتعد بمتر على الأقل (المادة 27)؛ ويلزم المتجاوَز أقصى اليمين دون أن يسرع (المادة 32).', fr: 'On ne franchit pas la ligne continue (art. 6) ; on dépasse par la gauche (art. 24) après s’être assuré de pouvoir le faire sans danger, en s’écartant d’un mètre au moins (art. 27) ; le dépassé serre à droite sans accélérer (art. 32).' },
    offence: 'overtaking',
    ask: {
      q: { ar: 'الشاحنة أمامك بطيئة. هل تتجاوزها الآن؟', fr: 'Le camion devant est lent. Le dépassez-vous maintenant ?' },
      choices: [{ label: { ar: 'نعم، الآن', fr: 'Oui, maintenant' } }, { label: { ar: 'لا، حتى يصير الخط متقطعا', fr: 'Non, quand la ligne devient discontinue' }, right: true }],
      wrong: { actors: { 0: { keys: [[0, 0.173], [1100, 0.319], [2600, 0.5]] } }, clash: [110, 120], at: 1100, dur: 3000,
               says: { ar: 'قطعت الخط المتصل: لا ترى ما يأتي من الأمام.', fr: 'Vous avez franchi la ligne continue : vous ne voyez pas ce qui vient en face.' } },
    },
    cites: [rules(6), rules(24), rules(27), rules(32), code(184), code(99)],
    road: 'road', roadOpts: { solidTo: 112 }, dur: 7800, guidesTill: 0, still: 3700,
    flags: [{ at: [3300, 4600], draw: (g, el) => { el('path', { d: 'M226 111 V129 M221 111 H231 M221 129 H231', stroke: 'var(--s-amber)', 'stroke-width': 2.5 }, g); } }],
    actors: [
      { d: 'M-30 140 H105 C130 140 135 100 160 100 H260 C285 100 290 140 315 140 H420', colour: 'var(--s-you)', label: YOU, tagAt: [0, -23],
        signal: { left: [[2000, 3300]], right: [[4500, 5600]] }, keys: [[0, 0.173], [2500, 0.281, 'lin'], [5500, 0.78], [7800, 1]] },
      { d: 'M120 140 H420', colour: 'var(--s-third)', kind: 'truck', keys: [[0, 0], [7800, 0.546, 'lin']] },
    ],
    steps: [
      { t: 0, ar: 'الخط المتصل لا يقطع: لا تجاوز هنا.', fr: 'Ligne continue : interdit de la franchir, donc de dépasser ici.' },
      { t: 2000, ar: 'صار الخط متقطعا والطريق أمامك خالية: أشر.', fr: 'La ligne devient discontinue, la voie en face est libre : clignotant.' },
      { t: 3300, ar: 'تجاوز من اليسار، مع مسافة جانبية كافية.', fr: 'Dépassez par la gauche avec un écart latéral suffisant.' },
      { t: 4500, ar: 'ارجع إلى يمينك بعد أن تبتعد عنه، مع الإشارة.', fr: 'Revenez à droite une fois assez loin devant, clignotant mis.' },
    ],
  },
  {
    key: 'crossing', title: { ar: 'ممر الراجلين', fr: 'Le passage piétons' },
    rule: { ar: 'يخفض السائق السرعة قرب ممرات الراجلين، وللراجلين الذين دخلوا الممر أسبقية المرور (المادتان 87 و126).', fr: 'Le conducteur ralentit à l’approche des passages piétons ; les piétons engagés ont la priorité (art. 87 et 126).' },
    offence: 'pedestrians',
    ask: {
      q: { ar: 'راجل يدخل الممر. من يمر أولا؟', fr: 'Un piéton s’engage. Qui passe d’abord ?' },
      choices: [{ label: { ar: 'أنا', fr: 'Moi' }, actor: 0 }, { label: { ar: 'الراجل', fr: 'Le piéton' }, actor: 1, right: true }],
      wrong: { actors: { 0: { keys: [[0, 0], [2400, 0.533]] }, 1: { keys: [[0, 0], [1100, 0], [2400, 0.667, 'lin']] } }, clash: [210, 140], at: 2400, dur: 3600,
               says: { ar: 'الراجل الذي دخل الممر له أسبقية المرور.', fr: 'Le piéton engagé sur le passage a la priorité.' } },
    },
    cites: [rules(87), rules(126), code(185), code(219)],
    road: 'road', roadOpts: { zebraAt: 210 }, dur: 7600, still: 3100,
    decor: [(svg, _el, sign) => sign(svg, 'walkers', 150, 56, 28)],
    guides: [['M210 70 V170', 'var(--s-third)']],
    actors: [
      { d: 'M-30 140 H420', colour: 'var(--s-you)', label: YOU, tagAt: [0, -24], keys: [[0, 0], [2100, 0.42], [5100, 0.42], [7600, 1]] },
      { d: 'M210 64 V178', colour: 'var(--s-third)', kind: 'walker', glow: [[2100, 4700]], keys: [[0, 0], [1100, 0], [4700, 1, 'lin']] },
    ],
    steps: [
      { t: 0, ar: 'راجل يدخل ممر الراجلين.', fr: 'Un piéton s’engage sur le passage.' },
      { t: 2100, ar: 'توقف قبل الممر ودعه يعبر.', fr: 'Arrêtez-vous avant le passage et laissez-le traverser.' },
      { t: 5100, ar: 'بعد أن يعبر، واصل طريقك.', fr: 'Une fois qu’il a traversé, repartez.' },
    ],
  },
  {
    key: 'breakdown', title: { ar: 'العطب في الطريق', fr: 'La panne sur la route' },
    rule: { ar: 'عند العطب أو سقوط الحمولة: أضواء الاستغاثة، ومعدة التشوير القبلي على 50 مترا على الأقل (المادة 94 المكررة، منذ 24 غشت 2026).', fr: 'En panne ou si le chargement tombe : feux de détresse, et le dispositif de pré-signalisation à 50 mètres au moins (art. 94 bis, depuis le 24 août 2026).' },
    costNote: { ar: 'قاعدة جديدة منذ 24 غشت 2026.', fr: 'Règle nouvelle depuis le 24 août 2026.' },
    ask: {
      q: { ar: 'تعطلت سيارتك. أين تضع معدة التشوير؟', fr: 'Votre voiture est en panne. Où posez-vous le triangle ?' },
      choices: [{ label: { ar: 'قرب السيارة', fr: 'Près de la voiture' } }, { label: { ar: 'على 50 مترا على الأقل خلفها', fr: 'À 50 mètres au moins derrière' }, right: true }],
      wrong: { actors: { 1: { keys: [[0, 0], [1300, 0], [2000, 0.15, 'lin']] }, 2: { d: 'M-50 140 H420', keys: [[0, 0], [1600, 0], [3200, 0.664]] } }, clash: [262, 140], at: 3200, dur: 4200,
               flags: [{ at: [2000, 4200], draw: (g, el) => { el('path', { d: 'M232 139 L242 157 H222 Z', fill: 'none', stroke: 'var(--g-red)', 'stroke-width': 3.5, 'stroke-linejoin': 'round' }, g); } }],
               says: { ar: 'رآه القادم متأخرا. على 50 مترا يراه من بعيد.', fr: 'Celui qui arrive l’a vu trop tard. À 50 mètres, il le voit de loin.' } },
    },
    cites: [rules(94), `${rules(94)}-bis`],
    road: 'road', dur: 8600, still: 3800,
    flags: [
      { at: [3000, 8600], draw: (g, el) => { el('path', { d: 'M64 139 L74 157 H54 Z', fill: 'none', stroke: 'var(--g-red)', 'stroke-width': 3.5, 'stroke-linejoin': 'round' }, g); } },
      { at: [3400, 8600], draw: (g, el) => {
        el('path', { d: 'M64 182 H262 M64 177 V187 M262 177 V187', stroke: 'var(--s-dark)', 'stroke-width': 1.5 }, g);
        el('text', { x: 163, y: 198, 'text-anchor': 'middle', 'font-size': 12, 'font-weight': 700, fill: 'var(--s-dark)' }, g).textContent = '≥ 50 m';
      } },
    ],
    actors: [
      { d: 'M-40 140 H284', colour: 'var(--s-you)', label: YOU, tagAt: [0, -24], hazard: [[1100, 8600]], keys: [[0, 0.62], [1100, 1]] },
      { d: 'M262 158 H62', colour: 'var(--s-you)', kind: 'walker', show: [1300, 8600], keys: [[0, 0], [1300, 0], [3000, 1, 'lin']] },
      { d: 'M-50 140 H40 C80 140 90 100 130 100 H300 C330 100 340 140 370 140 H420', colour: 'var(--s-other)', keys: [[0, 0], [4200, 0], [5600, 0.2], [8600, 1]] },
    ],
    steps: [
      { t: 0, ar: 'تعطلت سيارتك في الطريق: شغل أضواء الاستغاثة.', fr: 'Votre voiture tombe en panne sur la chaussée : feux de détresse.' },
      { t: 1300, ar: 'ضع معدة التشوير على 50 مترا على الأقل خلف السيارة.', fr: 'Posez le triangle à 50 mètres au moins en arrière.' },
      { t: 4200, ar: 'يراها القادم من بعيد، فيخفف ويتجاوزك.', fr: 'Ceux qui arrivent le voient de loin, ralentissent et vous contournent.' },
    ],
  },
  {
    key: 'scooter', title: { ar: 'التروتينيت بمحرك', fr: 'La trottinette à moteur' },
    rule: { ar: 'لا تتجاوز مركبة التنقل الشخصي بمحرك 25 كلم/س (المادة 19)، وخارج التجمعات العمرانية لا تسير إلا في ممرات الدراجات (المادة 112)، وسائقها يضع خوذة (المادة 110).', fr: 'L’engin de déplacement personnel motorisé ne dépasse pas 25 km/h (art. 19), hors agglomération il ne roule que sur les pistes cyclables (art. 112), et son conducteur porte un casque (art. 110).' },
    costNote: { ar: 'قواعد جديدة منذ 24 غشت 2026.', fr: 'Règles nouvelles depuis le 24 août 2026.' },
    ask: {
      q: { ar: 'خارج المدينة، أين تسير التروتينيت بمحرك؟', fr: 'Hors agglomération, où roule la trottinette à moteur ?' },
      choices: [{ label: { ar: 'في ممر الدراجات', fr: 'Sur la piste cyclable' }, right: true }, { label: { ar: 'في الطريق مع السيارات', fr: 'Sur la chaussée avec les voitures' } }],
      wrong: { actors: { 0: { d: 'M-30 42 H390', keys: [[0, 0], [3000, 0.45, 'lin']] }, 1: { keys: [[0, 0], [3000, 0.44]] } }, clash: [158, 42], at: 3000, dur: 4000,
               says: { ar: 'خارج المدينة لا تسير إلا في ممرات الدراجات (المادة 112).', fr: 'Hors agglomération, elle ne roule que sur les pistes cyclables (art. 112).' } },
    },
    cites: [rules(19), rules(112), rules(110)],
    road: 'street', height: 150, dur: 9000, loop: true,
    decor: [(svg, _el, sign) => sign(svg, 'cyclelane', 330, 12, 20)],
    actors: [
      { d: 'M-30 107 H390', colour: 'var(--s-you)', kind: 'rider', label: { ar: '25 كلم/س', fr: '25 km/h' }, tagAt: [0, -16], keys: [[0, 0], [9000, 1, 'lin']] },
      { d: 'M-50 42 H420', colour: 'var(--s-other)', keys: [[0, 0], [3600, 1, 'lin']] },
      { d: 'M-50 42 H420', colour: 'var(--s-third)', keys: [[0, 0], [4400, 0], [8000, 1, 'lin']] },
    ],
    steps: [{ t: 0, ar: 'التروتينيت في ممر الدراجات، 25 كلم/س على الأكثر، والخوذة على الرأس.', fr: 'La trottinette sur la piste cyclable, à 25 km/h au plus, casque sur la tête.' }],
  },
  {
    key: 'redlight', title: { ar: 'الضوء الأحمر', fr: 'Le feu rouge' },
    rule: { ar: 'الضوء الأحمر منع مطلق للمرور: يتوقف السائق عند خط الوقوف أو قبل ممر الراجلين. والأصفر يعلن الأحمر ويفرض الوقوف، إلا إذا تعذر بأمان (المادة 69).', fr: 'Le feu rouge interdit absolument de passer : on s’arrête à la ligne d’arrêt ou avant le passage piétons. Le jaune annonce le rouge et impose l’arrêt, sauf s’il est impossible en sécurité (art. 69).' },
    cites: [rules(69), rules(41), code(184), code(99)], offence: 'redLight',
    road: 'crossroads', dur: 8000, still: 2700,
    decor: [(svg, el) => {
      el('rect', { x: 226, y: 160, width: 16, height: 40, rx: 4, fill: 'var(--s-dark)' }, svg);
      for (const y of [168, 180, 192]) el('circle', { cx: 234, cy: y, r: 4.5, fill: '#555' }, svg);
      el('path', { d: 'M181 157 H209', stroke: 'var(--s-line)', 'stroke-width': 4 }, svg);
    }],
    flags: [
      { at: [0, 1400], draw: (g, el) => { el('circle', { cx: 234, cy: 192, r: 4.5, fill: '#2fbf5b' }, g); } },
      { at: [1401, 2400], draw: (g, el) => { el('circle', { cx: 234, cy: 180, r: 4.5, fill: '#f0b400' }, g); } },
      { at: [2401, 5600], draw: (g, el) => { el('circle', { cx: 234, cy: 168, r: 4.5, fill: '#e0352b' }, g); } },
      { at: [5601, 8000], draw: (g, el) => { el('circle', { cx: 234, cy: 192, r: 4.5, fill: '#2fbf5b' }, g); } },
    ],
    actors: [
      { d: 'M195 265 V-40', colour: 'var(--s-you)', label: YOU, tagAt: [-34, 0], keys: [[0, 0], [2600, 0.285], [6000, 0.285], [8000, 1]] },
      { d: 'M-40 135 H400', colour: 'var(--s-third)', keys: [[0, 0], [3000, 0.06], [5200, 1]] },
    ],
    steps: [
      { t: 0, ar: 'الضوء أخضر، ثم أصفر: الأصفر يعلن الأحمر.', fr: 'Le feu est vert, puis jaune : le jaune annonce le rouge.' },
      { t: 2400, ar: 'الضوء أحمر: توقف عند خط الوقوف.', fr: 'Le feu est rouge : arrêtez-vous à la ligne.' },
      { t: 5600, ar: 'صار أخضر: مر بعد التأكد من خلو التقاطع.', fr: 'Il passe au vert : passez une fois le carrefour libre.' },
    ],
    ask: {
      q: { ar: 'الضوء صار أحمر. ماذا تفعل؟', fr: 'Le feu passe au rouge. Que faites-vous ?' },
      choices: [{ label: { ar: 'أتوقف عند الخط', fr: 'Je m’arrête à la ligne' }, right: true }, { label: { ar: 'أمر بسرعة', fr: 'Je passe vite' } }],
      wrong: { actors: { 0: { keys: [[0, 0], [2700, 0.426]] }, 1: { keys: [[0, 0], [2700, 0.534]] } }, clash: [195, 135], at: 2700, dur: 3800,
               says: { ar: 'الطريق الأخرى كان ضوؤها أخضر: هنا تلتقيان.', fr: 'L’autre route avait le vert : vous vous rencontrez ici.' } },
    },
  },
  {
    key: 'walker', title: { ar: 'العبور راجلا', fr: 'Traverser à pied' },
    rule: { ar: 'يستعمل الراجل الممر المخصص له إذا وجد على أقل من 50 مترا (المادة 118)، ولا يعبر إلا بالإشارة التي تسمح بذلك (المادة 121). ويخفض السائق السرعة قرب الممر، وللراجل الذي دخله الأسبقية (المادة 126).', fr: 'Le piéton emprunte le passage prévu s’il y en a un à moins de 50 mètres (art. 118) et ne traverse qu’au signal qui le permet (art. 121). Le conducteur ralentit près du passage, et le piéton engagé a la priorité (art. 126).' },
    cites: [rules(116), rules(118), rules(121), rules(126), code(187)], offence: 'walk',
    road: 'road', roadOpts: { zebraAt: 300 }, dur: 7400, still: 2500,
    actors: [
      { d: 'M150 70 H300 V178', colour: 'var(--s-you)', kind: 'walker', label: YOU, tagAt: [0, -16], glow: [[2500, 4400]], keys: [[0, 0], [2500, 0.568, 'lin'], [5000, 1, 'lin']] },
      { d: 'M-30 140 H420', colour: 'var(--s-other)', keys: [[0, 0], [2300, 0.62], [4900, 0.62], [7400, 1]] },
    ],
    steps: [
      { t: 0, ar: 'تريد أن تعبر. ممر الراجلين على بعد خطوات.', fr: 'Vous voulez traverser. Le passage est à quelques pas.' },
      { t: 2500, ar: 'في الممر، السيارة تتوقف لك: لك الأسبقية فيه.', fr: 'Sur le passage, la voiture s’arrête : vous y avez la priorité.' },
      { t: 5000, ar: 'عبرت. تواصل السيارة طريقها.', fr: 'Vous avez traversé. La voiture repart.' },
    ],
    ask: {
      q: { ar: 'تريد أن تعبر. أين؟', fr: 'Vous voulez traverser. Où ?' },
      choices: [{ label: { ar: 'في ممر الراجلين القريب', fr: 'Au passage piétons tout proche' }, right: true }, { label: { ar: 'هنا مباشرة', fr: 'Ici, directement' } }],
      wrong: { actors: { 0: { d: 'M150 64 V178', keys: [[0, 0], [2400, 0.667, 'lin']] }, 1: { keys: [[0, 0], [2400, 0.4]] } }, clash: [150, 140], at: 2400, dur: 3600,
               says: { ar: 'السائق لم يكن ينتظرك هنا. الممر على أقل من 50 مترا.', fr: 'Le conducteur ne vous attendait pas ici. Le passage est à moins de 50 mètres.' } },
    },
  },
  {
    key: 'sirens', title: { ar: 'سيارة الإسعاف', fr: 'L’ambulance' },
    rule: { ar: 'يجب على كل سائق أن يسمح بالمرور لمركبات الشرطة والدرك الملكي ومركبات التدخل الاستعجالي التي تعلن عن اقترابها بإشارات خاصة (المادة 39).', fr: 'Tout conducteur laisse passer les véhicules de police, de la gendarmerie et d’intervention urgente qui annoncent leur approche par des signaux spéciaux (art. 39).' },
    cites: [rules(39), code(185)], offence: 'sirens',
    road: 'road', dur: 7600, still: 1800,
    actors: [
      { d: 'M-30 140 H150 C175 140 185 154 210 154 H420', colour: 'var(--s-you)', label: YOU, tagAt: [0, -24], signal: { right: [[1600, 2600]] },
        keys: [[0, 0.1], [1600, 0.3], [3000, 0.535], [5200, 0.535], [7600, 1]] },
      { d: 'M-80 140 H40 C70 140 80 104 110 104 H420', colour: 'var(--g-white)', kind: 'ambulance', siren: [[0, 7600]], keys: [[0, 0], [2800, 0.2], [5200, 1]] },
    ],
    steps: [
      { t: 0, ar: 'سيارة إسعاف خلفك، أضواؤها ومنبهها يعملان.', fr: 'Une ambulance derrière vous, gyrophares et sirène allumés.' },
      { t: 1600, ar: 'أشر، وأفسح لها الطريق إلى جانبك الأيمن.', fr: 'Clignotant, et laissez-lui la voie en serrant à droite.' },
      { t: 5200, ar: 'مرت. عد إلى مكانك وواصل.', fr: 'Elle est passée. Reprenez votre place.' },
    ],
    ask: {
      q: { ar: 'سيارة إسعاف خلفك بأضوائها ومنبهها. ماذا تفعل؟', fr: 'Une ambulance derrière vous, sirène allumée. Que faites-vous ?' },
      choices: [{ label: { ar: 'أفسح لها الطريق', fr: 'Je lui laisse le passage' }, right: true }, { label: { ar: 'أواصل كما أنا', fr: 'Je continue comme avant' } }],
      wrong: { actors: { 0: { d: 'M-30 140 H420', keys: [[0, 0.07], [3600, 0.4, 'lin']] }, 1: { d: 'M-80 140 H420', keys: [[0, 0], [2400, 0.32], [3600, 0.42, 'lin']] } }, clash: [120, 140], at: 2600, dur: 3800,
               says: { ar: 'بقيت أمامها: تتأخر عن من ينتظرها.', fr: 'Vous restez devant elle : elle arrive en retard là où on l’attend.' } },
    },
  },
  {
    key: 'moped', title: { ar: 'الدراجة بمحرك في المدينة', fr: 'Le cyclomoteur en ville' },
    rule: { ar: 'لا تتجاوز الدراجة بمحرك 40 كلم/س داخل المدينة و60 خارجها (المادة 19)، وتستعمل مسالك الدراجات حيث وجدت (المادة 112). يضع سائقها وراكبها خوذة مربوطة ومصادقا عليها (المادة 110)، ولا يستعمل السماعات (المادة 9).', fr: 'Le cyclomoteur ne dépasse pas 40 km/h en ville et 60 hors agglomération (art. 19) et emprunte les pistes cyclables là où il y en a (art. 112). Conducteur et passager portent un casque attaché et homologué (art. 110), sans écouteurs (art. 9).' },
    cites: [rules(19), rules(112), rules(110), rules(9)],
    costNote: { ar: 'الخوذة واجبة على السائق والراكب كليهما.', fr: 'Le casque est obligatoire pour le conducteur comme pour le passager.' },
    road: 'street', height: 150, dur: 8000, loop: true,
    decor: [(svg, _el, sign) => sign(svg, 'cyclelane', 330, 12, 20)],
    actors: [
      { d: 'M-30 107 H390', colour: 'var(--s-you)', kind: 'rider', label: { ar: '40 كلم/س', fr: '40 km/h' }, tagAt: [0, -16], keys: [[0, 0], [8000, 1, 'lin']] },
      { d: 'M-50 42 H420', colour: 'var(--s-other)', keys: [[0, 0], [4200, 1, 'lin']] },
    ],
    steps: [{ t: 0, ar: 'الدراجة بمحرك في مسلك الدراجات، 40 كلم/س على الأكثر في المدينة، والخوذة مربوطة.', fr: 'Le cyclomoteur sur la piste cyclable, 40 km/h au plus en ville, casque attaché.' }],
    ask: {
      q: { ar: 'ما السرعة القصوى للدراجة بمحرك داخل المدينة؟', fr: 'Quelle est la vitesse maximale d’un cyclomoteur en ville ?' },
      choices: [{ label: { ar: '40 كلم/س', fr: '40 km/h' }, right: true }, { label: { ar: '60 كلم/س', fr: '60 km/h' } }],
      because: { ar: '60 كلم/س هي حدها خارج المدينة. داخلها 40 (المادة 19).', fr: '60 km/h, c’est hors agglomération. En ville, 40 (art. 19).' },
    },
  },
];
/** The signs the scenes use and the code gives their duty, each with its code in joint order 2805.14 (BO 6332, French
 *  edition pp. 774–777, read on its page images on 20 Oct 2026; 3106.19 in BO 6832 changed some) and the article it
 *  makes a duty. */
export type SignCard = { key: string; code: string; name: Named; says: Named; cites: string[]; scene?: string; offence?: string };
export const SIGN_CARDS: SignCard[] = [
  { key: 'stop', code: '201', name: { ar: 'قف', fr: 'Stop' }, says: { ar: 'توقف تام في حدود القارعة، ثم المرور لمن في الطريق الأخرى.', fr: 'Arrêt complet à la limite de la chaussée, puis laisser passer.' }, cites: [rules(38), code(184)], scene: 'stop', offence: 'redLight' },
  { key: 'yield', code: '202.1', name: { ar: 'فسح المرور', fr: 'Cédez le passage' }, says: { ar: 'يفسح المرور لمن في الطريق الأخرى، ولا يتوقف إلا إذا كان أحد قادما.', fr: 'Laisser passer ceux de l’autre route ; s’arrêter seulement si quelqu’un arrive.' }, cites: [rules(78), code(185)], scene: 'roundabout', offence: 'priority' },
  { key: 'roundaboutAhead', code: '205', name: { ar: 'ملتقى دائري', fr: 'Carrefour à sens giratoire' }, says: { ar: 'الأسبقية لمن هو داخل الملتقى، أيا كانت الطريق التي تأتي منها.', fr: 'Priorité à ceux qui sont dans le giratoire, quelle que soit la route d’où l’on vient.' }, cites: [rules(78), rules(37)], scene: 'roundabout' },
  { key: 'priority', code: '206', name: { ar: 'طريق ذات أسبقية', fr: 'Route prioritaire' }, says: { ar: 'على هذه الطريق الأسبقية لك في التقاطعات حتى علامة نهايتها.', fr: 'Sur cette route, vous avez la priorité aux intersections jusqu’au panneau de fin.' }, cites: [rules(36)], scene: 'priority' },
  { key: 'walkers', code: '112', name: { ar: 'ممر الراجلين', fr: 'Passage pour piétons' }, says: { ar: 'خطر: ممر للراجلين أمامك. خفف السرعة، ولمن دخل الممر الأسبقية.', fr: 'Danger : passage pour piétons. Ralentir ; priorité au piéton engagé.' }, cites: [rules(126), rules(87)], scene: 'crossing', offence: 'pedestrians' },
  { key: 'noentry', code: '301', name: { ar: 'اتجاه ممنوع', fr: 'Sens interdit' }, says: { ar: 'ممنوع الدخول. السير في اتجاه ممنوع: الدرجة الأولى، 700 درهم، وأربع نقط.', fr: 'Entrée interdite. Sens interdit : 1re classe, 700 DH, quatre points.' }, cites: [code(184), code(99)], offence: 'wrongWay' },
  { key: 'nopass', code: '322.1', name: { ar: 'ممنوع التجاوز', fr: 'Interdiction de dépasser' }, says: { ar: 'ممنوع تجاوز المركبات ذات المحرك. التجاوز غير القانوني: أربع نقط.', fr: 'Interdit de dépasser les véhicules à moteur. Dépassement irrégulier : quatre points.' }, cites: [code(184), code(99)], scene: 'overtaking', offence: 'overtaking' },
  { key: 'speed60', code: '323', name: { ar: 'تحديد السرعة', fr: 'Limitation de vitesse' }, says: { ar: 'لا تتجاوز السرعة المكتوبة. بـ20 إلى أقل من 30 فوقها: الدرجة الثانية ونقطتان؛ بـ30 إلى أقل من 50: الدرجة الأولى وأربع نقط؛ بـ50 فأكثر: جنحة.', fr: 'Ne pas dépasser la vitesse indiquée. De 20 à moins de 30 au-dessus : 2e classe, deux points ; de 30 à moins de 50 : 1re classe, quatre points ; 50 et plus : délit.' }, cites: [code(185), code(184), code(175)], offence: 'speed' },
];

/** The families the order sorts signs into, by their shape (G1 of the road tools review): what a sign does is said by
 *  its shape before its picture. */
export const FAMILIES: { key: string; name: Named; says: Named; shape: string }[] = [
  { key: 'danger', name: { ar: 'التحذير', fr: 'Le danger' }, says: { ar: 'مثلث بإطار أحمر: خطر أمامك، خفف وانتبه.', fr: 'Un triangle bordé de rouge : un danger devant, ralentissez.' }, shape: SHAPES.danger },
  { key: 'priority', name: { ar: 'الأسبقية', fr: 'La priorité' }, says: { ar: 'من يمر أولا: قف، فسح المرور، الطريق ذات الأسبقية.', fr: 'Qui passe d’abord : stop, cédez le passage, route prioritaire.' }, shape: SHAPES.priority },
  { key: 'ban', name: { ar: 'المنع', fr: 'L’interdiction' }, says: { ar: 'دائرة بإطار أحمر: ممنوع ما تراه فيها.', fr: 'Un cercle bordé de rouge : interdit ce qu’il montre.' }, shape: SHAPES.ban },
  { key: 'must', name: { ar: 'الإلزام', fr: 'L’obligation' }, says: { ar: 'دائرة زرقاء: واجب ما تراه فيها.', fr: 'Un cercle bleu : obligatoire ce qu’il montre.' }, shape: SHAPES.must },
];
export const SIGN_FAMILY: Record<string, string> = {
  stop: 'priority', yield: 'priority', priority: 'priority', roundaboutAhead: 'danger', walkers: 'danger',
  noentry: 'ban', nopass: 'ban', speed60: 'ban', cyclelane: 'must',
};
