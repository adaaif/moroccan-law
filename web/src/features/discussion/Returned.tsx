import { ruleNo, useT } from './strings';

/** What the check answered when it returned the words (29 Oct 2026): the rule in the site's own words, a
 *  way to fix it, and a way to send it as it is to a person. */
export function Returned({ rule, busy, onInsist }: { rule: string; busy: boolean; onInsist: () => void }) {
  const { t } = useT();
  return (
    <div role="alert" className="flex flex-col gap-2 rounded-control bg-amended-wash px-3 py-2.5 text-meta text-amended">
      <span>{t('check.returned', { n: ruleNo(rule), rule: t(`rules.${rule}`) })}</span>
      <span className="text-ink-soft">{t(`rulesLong.${rule}`)}</span>
      <span className="flex flex-wrap items-center gap-3">
        <span>{t('check.fix')}</span>
        <button type="button" disabled={busy} onClick={onInsist}
                className="h-10 rounded-control border border-amended bg-sheet px-3 font-medium text-amended hover:bg-paper">
          {t('check.insist')}
        </button>
      </span>
    </div>
  );
}
