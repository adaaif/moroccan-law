import { useTranslation } from 'react-i18next';
import { Navigate } from 'react-router-dom';
import { useBudgetLaws } from './budget.api';
import { Page } from '@/shared/components/ui';
import './words';

/** «قانون المالية» goes to the latest year's law. */
export default function BudgetIndex() {
  const { t } = useTranslation();
  const laws = useBudgetLaws();
  const latest = laws.data?.filter((l) => l.kind === 'law').sort((a, b) => b.year - a.year)[0];
  if (latest) return <Navigate to={`/budget/${latest.year}`} replace />;
  return (
    <Page width="wide">
      <p className="text-ink-soft">{laws.isLoading ? t('corpus.loading') : t('budget.notFound', { year: '' })}</p>
    </Page>
  );
}
