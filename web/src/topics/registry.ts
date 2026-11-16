import { lazy, type ComponentType, type LazyExoticComponent } from 'react';
import type { Door, Module } from './kit/api';

/** One page of a topic whose tools share a chunk. */
const named = <M,>(load: () => Promise<M>, name: keyof M) =>
  lazy(() => load().then((m) => ({ default: m[name] as ComponentType<{ slug: string }> })));

/** The topics with code of their own (F16 of the family plan): each tool loads only on its page, so the first load
 *  stays at its budget. A topic without a module keeps the kit's pages and its hub. */
export const TOOLS: Record<string, Record<string, LazyExoticComponent<ComponentType<{ slug: string }>>>> = {
  family: {
    inheritance: lazy(() => import('./family/inheritance/InheritancePage')),
    dates: lazy(() => import('./family/dates/DatesPage')),
    support: lazy(() => import('./family/support/SupportPage')),
  },
  consumer: {
    receipt: lazy(() => import('./consumer/ReceiptPage')),
    return: lazy(() => import('./consumer/ReturnPage')),
    guarantee: lazy(() => import('./consumer/GuaranteePage')),
    late: lazy(() => import('./consumer/LatePage')),
    credit: lazy(() => import('./consumer/CreditPage')),
    where: lazy(() => import('./consumer/WherePage')),
    clause: lazy(() => import('./consumer/ClausePage')),
    prices: lazy(() => import('./consumer/PricesPage')),
    letters: lazy(() => import('./consumer/LettersPage')),
  },
  housing: {
    rent: lazy(() => import('./housing/RentPage')),
    eviction: lazy(() => import('./housing/EvictionPage')),
    offplan: lazy(() => import('./housing/OffplanPage')),
    aid: lazy(() => import('./housing/AidPage')),
  },
  road: {
    fine: lazy(() => import('./road/FinePage')),
    speed: lazy(() => import('./road/SpeedPage')),
    now: lazy(() => import('./road/NowPage')),
    points: lazy(() => import('./road/PointsPage')),
    compensation: lazy(() => import('./road/CompensationPage')),
    scenes: lazy(() => import('./road/ScenesPage')),
    signs: lazy(() => import('./road/SignsPage')),
    practice: lazy(() => import('./road/PracticePage')),
  },
  land: {
    clock: lazy(() => import('./land/ClockPage')),
    permit: lazy(() => import('./land/PermitPage')),
    before: lazy(() => import('./land/BeforePage')),
    find: lazy(() => import('./land/FindPage')),
  },
  tax: {
    salary: lazy(() => import('./tax/SalaryPage')),
    bill: lazy(() => import('./tax/BillPage')),
    pension: lazy(() => import('./tax/PensionPage')),
    rent: lazy(() => import('./tax/RentPage')),
    local: lazy(() => import('./tax/LocalPage')),
    car: lazy(() => import('./tax/CarPage')),
    sell: lazy(() => import('./tax/SellPage')),
    buy: lazy(() => import('./tax/BuyPage')),
    own: lazy(() => import('./tax/OwnPage')),
    late: lazy(() => import('./tax/LatePage')),
  },
  health: {
    refund: lazy(() => import('./health/RefundPage')),
    clock: lazy(() => import('./health/ClockPage')),
    illness: lazy(() => import('./health/IllnessPage')),
  },
  papers: {
    card: lazy(() => import('./papers/CardPage')),
    clock: lazy(() => import('./papers/ClockPage')),
    counter: lazy(() => import('./papers/CounterPage')),
    names: lazy(() => import('./papers/NamesPage')),
    rehab: lazy(() => import('./papers/RehabPage')),
  },
  digital: {
    offence: named(() => import('./digital/tools'), 'OffencePage'),
    info: named(() => import('./digital/tools'), 'InfoToolPage'),
    letter: named(() => import('./digital/tools'), 'LetterPage'),
    copyright: named(() => import('./digital/tools'), 'CopyrightPage'),
  },
  justice: {
    deadline: named(() => import('./justice/tools'), 'DeadlinePage'),
    custody: named(() => import('./justice/tools'), 'CustodyPage'),
    court: named(() => import('./justice/tools'), 'CourtPage'),
    alternative: named(() => import('./justice/tools'), 'AlternativePage'),
  },
  business: {
    form: lazy(() => import('./business/FormPage')),
    cheque: lazy(() => import('./business/ChequePage')),
    late: lazy(() => import('./business/LatePage')),
    year: lazy(() => import('./business/YearPage')),
  },
  work: {
    end: lazy(() => import('./work/EndPage')),
    pay: lazy(() => import('./work/PayPage')),
    dates: lazy(() => import('./work/DatesPage')),
    cnss: lazy(() => import('./work/CnssPage')),
  },
};

/** A journey step's tool worked out in place (J3 of the road tools review), by the step's `tool` reference; it gets the
 *  day the journey asked and the journey's key. */
export const STEP_WIDGETS: Record<string, Record<string, LazyExoticComponent<ComponentType<{ slug: string; day: string; journey: string }>>>> = {
  road: {
    'tools/fine': lazy(() => import('./road/FineInline')),
  },
};

/** What a topic adds to its reviewer's desk (Q1 of the road tools review): the road's practice-card workshop. */
/** A page's own drawings, by the name its folder gives them (the bill-page review, V6, V8): the bill's gain
 *  calculator and its scale through the years, loaded with the page that names them. */
export const PAGE_WIDGETS: Record<string, Record<string, LazyExoticComponent<ComponentType<{ slug: string }>>>> = {
  tax: {
    'bill-gain': named(() => import('./tax/BillWidgets'), 'BillGain'),
    'bill-scales': named(() => import('./tax/BillWidgets'), 'ScaleYears'),
    // The bill-story review: the guess and the curve with its steps, four people, the road to 2031, the method.
    'bill-story': named(() => import('./tax/story/BillStory'), 'BillStory'),
    'bill-people': named(() => import('./tax/story/StoryParts'), 'People'),
    'bill-road': named(() => import('./tax/story/StoryParts'), 'Road'),
    'bill-method': named(() => import('./tax/story/StoryParts'), 'Method'),
    // «لك» under each change of the salaried section (a row's `you`): the reader's own figure from the page's salary.
    'bill-you-expenses': named(() => import('./tax/BillRows'), 'YouExpenses'),
    'bill-you-top': named(() => import('./tax/BillRows'), 'YouTop'),
    'bill-you-allowance': named(() => import('./tax/BillRows'), 'YouAllowance'),
    'bill-you-declare': named(() => import('./tax/BillRows'), 'YouDeclare'),
  },
};

export const REVIEW_EXTRAS: Record<string, LazyExoticComponent<ComponentType<{ slug: string }>>> = {
  road: lazy(() => import('./road/CardWorkshop')),
};

/** The tools a topic draws as instruments on its page (A8 of the road-signposted review): their keys, known without loading
 *  anything, and the one component that draws them, loaded with the topic's page. */
export const INSTRUMENTS: Record<string, { keys: Record<string, true>; component: LazyExoticComponent<ComponentType<{ slug: string; tools: Door[]; side: boolean }>> }> = {
  road: { keys: { fine: true, speed: true, points: true }, component: lazy(() => import('./road/Instruments')) },
  family: { keys: { years: true, inheritance: true, dates: true }, component: lazy(() => import('./family/Instruments')) },
  work: { keys: { end: true, pay: true, cnss: true }, component: lazy(() => import('./work/Instruments')) },
  consumer: { keys: { receipt: true, return: true, guarantee: true }, component: lazy(() => import('./consumer/Instruments')) },
  land: { keys: { clock: true, permit: true, before: true }, component: lazy(() => import('./land/Instruments')) },
  tax: { keys: { salary: true, local: true, car: true }, component: lazy(() => import('./tax/Instruments')) },
  health: { keys: { refund: true, clock: true, illness: true }, component: lazy(() => import('./health/Instruments')) },
  papers: { keys: { card: true, clock: true, counter: true }, component: lazy(() => import('./papers/Instruments')) },
  business: { keys: { form: true, cheque: true, late: true }, component: lazy(() => import('./business/Instruments')) },
  justice: { keys: { deadline: true, custody: true, court: true }, component: lazy(() => import('./justice/Instruments')) },
  digital: { keys: { offence: true, info: true, letter: true }, component: lazy(() => import('./digital/Instruments')) },
};

/** The tools that open without a network (A17 of the road-signposted review): the accident's «دابا». Their page renders
 *  even when the topic cannot be asked for, from what `KEEP` put on the phone. */
/** The tools that answer addresses under their own: the inheritance calculator's common families, each opening on its
 *  answer, and the page of its readings (IR11, IR28 of the inheritance review). The tool's page reads the rest of
 *  the address itself. */
export const UNDER: Record<string, string[]> = { family: ['inheritance'] };
/** What an address says after a tool's own: «zawja-ibn-bint» in «/topics/family/tools/inheritance/zawja-ibn-bint»,
 *  '' on the tool's page. Read from the address itself: the router's own remainder is the topic's, not the tool's. */
export const underTool = (pathname: string, key: string): string =>
  (pathname.split(`/tools/${key}`)[1] ?? '').replace(/^\/+|\/+$/g, '');

export const OFFLINE: Record<string, string[]> = { road: ['now'] };

/** What a topic keeps on the phone once its page has been opened, in the browser's idle time. */
export const KEEP: Record<string, (module: Module) => Promise<void>> = {
  road: (module) => import('./road/keep').then((m) => m.keep(module)),
  family: () => import('./family/keep').then((m) => m.keep()),
  health: () => import('./health/keep').then((m) => m.keep()),
};
