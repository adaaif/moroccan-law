/** «اختيارات الحاسبة» (IR11 of the inheritance review): where the code can be read two ways, what the engine does,
 *  the other reading, who holds each, and since when. A result that rests on one of these says so and links here.
 *  And the calculator's record of changes (IR12): what moved, when, and why. Data only; choices/ draws it.
 *
 *  Every sentence here is a draft until an adoul or a family judge has read it. The decisions and the guide named
 *  under «bequest» were read through the judge's article, not in their own pages: the source line says so. */
import type { Cite } from './engine';

export type Text = { ar: string; fr: string };
export type Choice = {
  /** The address of the choice on its page: «#bequest». */
  key: 'bequest' | 'stage2' | 'nothingLeft' | 'radd' | 'mixed' | 'third' | 'tanzil';
  title: Text;
  cites: Cite[];
  /** The article's own words that are read two ways, in Arabic as the code has them. */
  words: string;
  /** What the engine does, and on what it rests. */
  does: Text;
  /** The other reading, and who holds it. */
  other: Text;
  /** Where to read more: a decision, a book, a page; shown as printed. */
  sources: string[];
  since: string;
};
export type Change = { version: string; on: string; what: Text };

export const CHOICES: Choice[] = [
  {
    key: 'bequest',
    title: { ar: 'مقدار الوصية الواجبة للأحفاد', fr: 'Le montant du legs obligatoire des petits-enfants' },
    cites: [370],
    words: 'الوصية الواجبة لهؤلاء الأحفاد تكون بمقدار حصتهم مما يرثه أبوهم أو أمهم عن أصله المتوفى على فرض موت موروثهم إثر وفاة أصله المذكور على أن لا يتجاوز ذلك ثلث التركة.',
    does: {
      ar: 'تعطي الحاسبة الأحفاد نصيبهم هم من نصيب أبيهم أو أمهم، لا ذلك النصيب كله. يفرض الولد المتوفى حيا يوم وفاة أصله فيأخذ نصيبه، ثم يقسم ذلك النصيب على ورثته هو، وما ينوب أولاده هو الوصية الواجبة؛ وما بقي يعود إلى التركة. هذه قراءة المجلس الأعلى (محكمة النقض اليوم) في قراره عدد 805، ووزارة العدل في كتابها عدد 20396 وفي الدليل العملي لمدونة الأسرة.',
      fr: 'Le calculateur donne aux petits-enfants leur propre part dans ce que leur père ou leur mère aurait hérité, non cette part entière. L’enfant prédécédé est supposé vivant au décès et prend sa part ; cette part est ensuite partagée entre ses propres héritiers, et ce qui revient à ses enfants est le legs obligatoire ; le reste retourne à la succession. C’est la lecture de la Cour suprême (aujourd’hui Cour de cassation) dans son arrêt n° 805, et du ministère de la Justice dans sa lettre n° 20396 et dans le Guide pratique du Code de la famille.',
    },
    other: {
      ar: 'قراءة أخرى تعطي الأحفاد نصيب أبيهم أو أمهم كاملا في حدود الثلث، وترى عبارة «حصتهم» زائدة؛ قال بها جلول النقاشي ومحمد رياض. تعرض الحاسبة رقمها بجانب الأول متى اختلفا.',
      fr: 'Une autre lecture donne aux petits-enfants la part entière de leur père ou de leur mère, dans la limite du tiers, et tient le mot « leur part » pour superflu ; elle est soutenue par Jelloul Naqqachi et Mohamed Riad. Le calculateur affiche son chiffre à côté du premier quand ils diffèrent.',
    },
    sources: [
      'حسن منصف، رئيس غرفة بمحكمة النقض: «الوصية الواجبة علما وعملا وفي تزاحمها مع باقي الوصايا» (ومنه نقلنا ما يلي)',
      'قرار المجلس الأعلى عدد 805 بتاريخ 28 ماي 1985، مجلة قضاء المجلس الأعلى، العددان 37 و38، ص 122: «نصيب الطاعنة باعتبارها الوارث الوحيد لوالدها هو النصف فيما يرثه من والده وليس جميع الحصة»',
      'كتاب وزير العدل عدد 20396 بتاريخ 25 يناير 1980',
      'دليل عملي لمدونة الأسرة، وزارة العدل، 2004، ص 217 وما بعدها',
      'الغازي الحسيني، مختصر الفرائض والحقوق الإرثية، 1982، ص 151',
      'محمد رياض، أحكام المواريث بين النظر الفقهي والتطبيق العملي، 1998، ص 248 إلى 251 (القراءة الأخرى)',
    ],
    since: '2.0',
  },
  {
    key: 'stage2',
    title: { ar: 'من يرث الولد المتوفى قبل أصله، وهل يرد على أولاده', fr: 'Qui hérite de l’enfant prédécédé, et le reste revient-il à ses enfants' },
    cites: [370, 372],
    words: 'على فرض موت موروثهم إثر وفاة أصله المذكور',
    does: {
      ar: 'في مسألة الولد المتوفى تعد الحاسبة من يأخذ قبل أولاده: زوجه إن بقي حيا، وأمه أو أباه إن كان هو زوج المتوفى الباقي، وجده وجدته من جهة المتوفى. ولا ترد على أولاده شيئا: البنت الواحدة تأخذ نصف نصيب أبيها، والبنتان فأكثر الثلثين، ومع الابن يأخذون ما بقي بعد أصحاب الفروض؛ وما زاد يعود إلى ورثة الأصل.',
      fr: 'Dans la succession supposée de l’enfant prédécédé, le calculateur compte ceux qui prennent avant ses enfants : son conjoint survivant, sa mère ou son père si c’est le conjoint survivant du défunt, son grand-père et sa grand-mère du côté du défunt. Rien ne revient en plus à ses enfants : une fille seule prend la moitié de la part de son père, deux filles ou plus les deux tiers, et avec un fils ils prennent ce qui reste après les parts fixes ; le surplus retourne aux héritiers du défunt.',
    },
    other: {
      ar: 'منذ 2004 تعرف المدونة الرد (المادة 349)، وإعماله في مسألة الولد المتوفى يعطي البنت الوحيدة التي لا عاصب معها أكثر من النصف. القرار عدد 805 صدر قبل ذلك. والحاسبة لا تعرف والدي زوج المتوفاة، وهما جدا الولد لأبيه.',
      fr: 'Depuis 2004 le Code connaît le retour (article 349) ; appliqué dans la succession de l’enfant prédécédé, il donnerait plus de la moitié à une fille seule sans agnat. L’arrêt n° 805 est antérieur. Le calculateur ne connaît pas les parents du mari de la défunte, grands-parents paternels de l’enfant.',
    },
    sources: [
      'قرار المجلس الأعلى عدد 805 بتاريخ 28 ماي 1985 (نقلا عن مقال حسن منصف)',
      'الغازي الحسيني، مختصر الفرائض، ص 155: «ونصف حظه إلى الحفيدة عند انفرادها، وما بقي يضاف كله إلى ورثة الأصل»',
    ],
    since: '2.0',
  },
  {
    key: 'nothingLeft',
    title: { ar: 'أولاد الابن الذين لم يبق لهم شيء', fr: 'Les enfants du fils à qui il ne reste rien' },
    cites: [371],
    words: 'لا يستحق هؤلاء الأحفاد وصية، إذا كانوا وارثين لأصل موروثهم جدا كان أو جدة',
    does: {
      ar: 'أولاد الابن المتوفى عصبة عند عدم الابن، لكن الفروض قد تستغرق التركة فلا يبقى لهم شيء. الحاسبة تعطيهم حينئذ الوصية الواجبة، لأنهم لم يرثوا شيئا في الواقع.',
      fr: 'Les enfants d’un fils prédécédé héritent par taâsib en l’absence de fils, mais les parts fixes peuvent épuiser la succession. Le calculateur leur donne alors le legs obligatoire, puisqu’ils n’ont en fait rien hérité.',
    },
    other: {
      ar: 'قد تقرأ «وارثين» بمعنى غير محجوبين، فلا وصية لمن كان عاصبا ولو لم يبق له شيء. لم نقف على قرار في ذلك؛ يحسمه العدلان أو المحكمة.',
      fr: 'On peut lire « héritiers » au sens de « non exclus » : pas de legs pour un héritier par taâsib même s’il ne lui reste rien. Nous n’avons pas trouvé de décision sur ce point ; les adouls ou le tribunal tranchent.',
    },
    sources: [],
    since: '1.0',
  },
  {
    key: 'radd',
    title: { ar: 'الرد على الزوج أو الزوجة', fr: 'Le retour au mari ou à l’épouse' },
    cites: [[349, 6]],
    words: 'فإذا وجد وارث واحد بالفرض رد عليه الباقي، وإذا تعدد الورثة بالفرض، ولم تستغرق الفروض التركة رد عليهم الباقي حسب نسبهم في الإرث.',
    does: {
      ar: 'إذا بقي شيء بعد الفروض ولا عاصب، ترده الحاسبة على جميع أصحاب الفروض حسب أنصبتهم، والزوج أو الزوجة منهم، كما هو نص المادة: لم تستثن أحدا.',
      fr: 'S’il reste quelque chose après les parts fixes et qu’aucun héritier par taâsib ne le prend, le calculateur le rend à tous les héritiers à part fixe selon leurs parts, mari ou épouse compris, comme l’article est écrit : il n’excepte personne.',
    },
    other: {
      ar: 'جمهور الفقهاء لا يرد على الزوجين، فيبقى للزوجة فرضها ويرد الباقي على غيرها؛ والمذهب المالكي قبل المدونة يجعل الباقي لبيت المال. تعرض الحاسبة نصيب الزوج أو الزوجة بغير رد بجانب الأول.',
      fr: 'La majorité des juristes ne rend rien aux époux : l’épouse garde sa part fixe et le reste revient aux autres ; le rite malékite, avant le Code, l’attribuait au Trésor. Le calculateur affiche à côté la part du conjoint sans retour.',
    },
    sources: [],
    since: '1.0',
  },
  {
    key: 'mixed',
    title: { ar: 'المالكية وشبه المالكية مع أخت أو مع أخ من نوع آخر', fr: 'La Malikiyya et la quasi-Malikiyya avec une sœur, ou avec un frère d’une autre sorte' },
    cites: [362, 363],
    words: 'إذا اجتمع مع الجد زوج وأم أو جدة وأخ للأب فأكثر وأخوان لأم فأكثر فرض للزوج النصف وللأم السدس وللجد ما بقي ولا يأخذ الإخوة للأم شيئا لأن الجد يحجبهم ولا يأخذ الأخ للأب شيئا.',
    does: {
      ar: 'تطبق الحاسبة المادتين كما كتبتا: إخوة لأب وحدهم (362) أو أشقاء وحدهم (363). فإن كانت مع الأخ أخت، أو مع الشقيق أخ لأب، توقفت ولم تحسب، وأحالت على العدلين.',
      fr: 'Le calculateur applique les deux articles tels qu’ils sont écrits : des frères consanguins seuls (362) ou des frères germains seuls (363). Si une sœur accompagne le frère, ou un frère consanguin le frère germain, il s’arrête sans calculer et renvoie aux adouls.',
    },
    other: {
      ar: 'علة المادتين («لأن الجد يحجبهم») تقتضي ألا يأخذ هؤلاء شيئا كذلك؛ وقواعد الجد مع الإخوة (المادة 354) تعطيهم نصيبا. بين القراءتين سدس التركة.',
      fr: 'La raison des deux articles (« car le grand-père les exclut ») voudrait qu’ils ne prennent rien non plus ; les règles du grand-père avec les frères et sœurs (article 354) leur donneraient une part. Un sixième de la succession sépare les deux lectures.',
    },
    sources: [],
    since: '2.0',
  },
  {
    key: 'third',
    title: { ar: 'الثلث: الوصية الواجبة أولا، ثم الوصية والتنزيل', fr: 'Le tiers : le legs obligatoire d’abord, puis le testament et le tanzil' },
    cites: [277, 280, 302, 303],
    words: 'الوصية عقد يوجب حقا في ثلث مال عاقده يلزم بموته.',
    does: {
      ar: 'تخرج الوصية الواجبة من الثلث أولا، كما قضت محكمة النقض؛ ثم تتحاص الوصية الإرادية والتنزيل فيما بقي منه (المادة 302)، إلا أن يجيز الورثة أكثر (المادة 303). والوصية لوارث لا تنفذ إلا بإجازة الباقين (المادة 280).',
      fr: 'Le legs obligatoire sort du tiers en premier, comme l’a jugé la Cour de cassation ; le testament et le tanzil se partagent ensuite ce qui en reste, au prorata (article 302), sauf si les héritiers consentent à davantage (article 303). Un legs à un héritier ne vaut qu’avec l’accord des autres (article 280).',
    },
    other: {
      ar: 'رأي يقدم الوصية الإرادية (محمد رياض)، ورأي يسوي بين الوصايا كلها فيتحاص أصحابها في الثلث (وإليه يميل القاضي منصف).',
      fr: 'Un avis fait passer le testament d’abord (Mohamed Riad) ; un autre met tous les legs au même rang, partagés au prorata dans le tiers (le juge Mansif y incline).',
    },
    sources: [
      'قرار المجلس الأعلى عدد 1175 بتاريخ 27 دجنبر 2001، ملف 43962-1-97 (نقلا عن مقال حسن منصف)',
      'قرار المجلس الأعلى عدد 155 بتاريخ 14 مارس 2007، ملف 510-2-1-2006 (نقلا عن المقال نفسه)',
    ],
    since: '2.0',
  },
  {
    key: 'tanzil',
    title: { ar: 'التنزيل: طريقتان في الحساب', fr: 'Le tanzil : deux manières de compter' },
    cites: [[317, 1], [317, 2], 318, 316],
    words: 'إذا كان في مسألة المنزل – كسرا – ذو فرض وكانت عبارته صريحة في تسوية الملحق بالملحق به، حسبت المسألة بطريقة العول حيث يدخل بها ضرر التنزيل على الجميع.',
    does: {
      ar: 'إن صرح المنزل بالتسوية، أخذ المنزل مثل سهام من ألحق به وزيد ذلك على أصل المسألة (طريقة العول). وإلا حسبت المسألة والمنزل من الورثة فأعطي مثل نصيب من ألحق به، ثم قسم الباقي على الورثة كأن لا تنزيل. وهو كالوصية: في حدود الثلث إلا بإجازة الورثة.',
      fr: 'Si les termes établissent l’égalité, la personne instituée prend autant de parts que l’héritier auquel elle est assimilée, ajoutées à la base (méthode du ’awl). Sinon le cas est compté avec elle parmi les héritiers, elle reçoit ce que reçoit cet héritier, puis le reste est partagé entre les héritiers comme s’il n’y avait pas de tanzil. Comme un testament : dans la limite du tiers, sauf accord des héritiers.',
    },
    other: {
      ar: 'لم نقف على قرار يفصل طريقة الحساب؛ هذه قراءتنا لنص المادتين 317 و318، وتعرض على العدلين.',
      fr: 'Nous n’avons pas trouvé de décision détaillant le calcul ; c’est notre lecture des articles 317 et 318, à soumettre aux adouls.',
    },
    sources: [],
    since: '2.0',
  },
];

export const CHANGES: Change[] = [
  {
    version: '2.0', on: '2026-11-14',
    what: {
      ar: 'الوصية الواجبة تحسب بقراءة محكمة النقض: نصيب الأحفاد من نصيب أبيهم أو أمهم، لا النصيب كله؛ وكانت الحاسبة تعطيهم النصيب كله. الأحفاد يدخلون من ولدهم المتوفى وحده، فلا تسقط وصيتهم. فروع «المالكية» و«شبه المالكية» التي لم تحسمها المدونة لا تحسب. المبالغ تجمع التركة بالسنتيم. كل نتيجة تحمل نسختها ورمز حالتها.',
      fr: 'Le legs obligatoire est compté selon la lecture de la Cour de cassation : la part des petits-enfants dans la part de leur père ou de leur mère, non la part entière, que le calculateur leur donnait. Les petits-enfants ne se saisissent que par leur parent prédécédé, pour que leur legs ne soit jamais omis. Les formes de la « Malikiyya » et de la « quasi-Malikiyya » que le Code ne tranche pas ne sont plus calculées. Les montants font la succession au centime. Chaque résultat porte sa version et le code de son cas.',
    },
  },
  {
    version: '1.0', on: '2026-10-20',
    what: {
      ar: 'النسخة الأولى: الكتاب السادس من مدونة الأسرة بكسور صحيحة، وكل نصيب بمادته.',
      fr: 'Première version : le livre VI du Code de la famille en fractions exactes, chaque part avec son article.',
    },
  },
];
