import { Suspense, lazy, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import NotFound from '@/features/corpus/NotFound';
import { Note, Page, PageSkeleton } from '@/shared/components/ui';
import { KitPage } from '../../kit/parts';
import { underTool } from '../../registry';
import type { Area, Open } from './area';
import { solve } from './solve';
import { DeceasedContext, useT } from './strings';
import { useCase } from './useCase';
import LANDINGS from './landings.json';

// «اختيارات الحاسبة», at the tool's own address + /choices, loaded only there (IR11).
const ChoicesPage = lazy(() => import('./choices/ChoicesPage'));
import Ask from './ask/Ask';
import Tree from './ask/Tree';
import Estate from './after/Estate';
import After from './after/After';
import AnswerView from './answer/Answer';
import { RulesContext } from './parts/rules';
import Office from './office/Office';

/** «حاسبة الإرث» (the inheritance review, 14 Nov 2026). The family is asked a question at a time, in the order of
 *  the law and only what can change the answer (ask/); the tree draws itself and stays the expert's way in. Then what
 *  the estate is and what leaves it first (after/Estate), an heir who died since or a «تنزيل» (office/), the answer at
 *  two depths with its sheet (answer/), and what comes after the shares: the house, the papers (after/After).
 *  The case lives in the address after «#» (useCase): nothing of it is sent. The engine, the solver and the table are
 *  pure files beside this one; the screens only draw what they return. On a desk the answer is held beside the
 *  questions: KitPage puts the child that carries `data-answer` in the second column. */
export default function InheritancePage({ slug }: { slug: string }) {
  // What follows the tool's own address: nothing, or one of the common families that have an address of their own
  // (IR28: «…/inheritance/zawja-3-banat-akhawan» opens answered, with its own title for a search engine).
  const under = underTool(useLocation().pathname, 'inheritance');
  if (under === 'choices') return <Suspense fallback={<Page width="reading"><PageSkeleton /></Page>}><ChoicesPage slug={slug} /></Suspense>;
  const landing = LANDINGS.find((l) => l.slug === under);
  if (under && !landing) return <NotFound />;
  return <Calculator slug={slug} landing={landing} />;
}

function Calculator({ slug, landing }: { slug: string; landing?: (typeof LANDINGS)[number] }) {
  const kept = useCase(landing?.code);
  // Every name on the page agrees with who died (strings.ts).
  return <DeceasedContext.Provider value={kept.c.deceased}><Body slug={slug} landing={landing} kept={kept} /></DeceasedContext.Provider>;
}

function Body({ slug, landing, kept }: { slug: string; landing?: (typeof LANDINGS)[number]; kept: ReturnType<typeof useCase> }) {
  const { t, i18n } = useT();
  const { c, set, reset, load, code, stale } = kept;
  const answer = useMemo(() => solve(c), [c]);
  const [open, setOpenState] = useState<Open>(() => ({ later: c.later.length > 0, will: Boolean(c.will), tanzil: Boolean(c.tanzil), tree: false }));
  const setOpen = (o: Partial<Open>) => setOpenState((x) => ({ ...x, ...o }));
  const area: Area = { c, set, answer, open, setOpen };
  // The code this death is counted by: every citation on the page names its articles (IR27).
  const rules = answer.state === 'ok' ? answer.result.rules.code : '70-03';
  return (
    <KitPage slug={slug} title={landing ? landing.title[i18n.language === 'fr' ? 'fr' : 'ar'] : t('shell.title')}
             lead={landing ? landing.lead[i18n.language === 'fr' ? 'fr' : 'ar'] : t('shell.lead')}>
      <RulesContext.Provider value={rules}>
      {stale ? <Note tone="warn" quiet><p className="m-0 text-meta">{t('shell.older')}</p></Note> : null}
      {rules === '1958' ? <Note tone="law" quiet><p className="m-0 text-meta">{t('shell.old')}</p></Note> : null}
      <Ask {...area} reset={reset} load={load} code={code} />
      <Tree {...area} />
      <Estate {...area} />
      <Office {...area} />
      <AnswerView c={c} answer={answer} code={code} />
      <After c={c} answer={answer} />
      </RulesContext.Provider>
    </KitPage>
  );
}
