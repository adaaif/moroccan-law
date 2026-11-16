import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { usePageTitle } from '@/shared/services/title';

export function AuthLayout({ title, children, footer }: { title: string; children: ReactNode; footer?: ReactNode }) {
  const { t } = useTranslation();
  usePageTitle([title]);
  return (
    <main className="mx-auto flex w-full max-w-md flex-col gap-5 px-4 py-10 sm:py-16">
      <section className="rounded-control border border-rule bg-sheet p-6 sm:p-8">
        <p className="mb-1 text-body text-ink-soft">{t('app.tagline')}</p>
        <h1 className="mb-7 font-law text-h1 font-semibold leading-tight">{title}</h1>
        {children}
      </section>
      {footer ? <p className="text-center text-body">{footer}</p> : null}
    </main>
  );
}
