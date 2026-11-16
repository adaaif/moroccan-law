import { useQuery } from '@tanstack/react-query';
import { api } from '@/shared/services/api';

export type IssueRef = { edition: string; key: string; number: number; suffix: string; date: string; document_id: number };

export type LawRef = {
  year: number;
  kind: 'bill' | 'law' | 'amending' | 'settlement';
  number: string;
  title: string;
  text_id: number | null;
  issue: IssueRef | null;
  /** A bill: the day it was filed, its file (the ministry's) and its page (the finance-bill review, P4). */
  filed: { on: string; document_id: number | null; path: string } | null;
};

export type Figure = { amount: string; page: number | null };

export type Headline = { revenue: string; spending: string; deficit: string; borrowing: string | null; posts: number | null };
export type LawSummary = LawRef & { headline: Headline | null };

export type Ministry = {
  code: string;
  name: string;
  state: '' | 'common' | 'contingencies' | 'tax_refunds';
  running: string;
  investment: string;
  commitment: string;
  posts: number | null;
  chapters: { code: string; label: string; amount: string; page: number | null }[];
  pages: number[];
};

export type Check = {
  name: string;
  id: string;
  args: Record<string, string>;
  expected: string | null;
  found: string | null;
  ok: boolean;
  tables: string[];
  source: string;
};

export type BudgetDetail = LawRef & {
  page_index: Record<string, number>;
  articles: Record<string, { eid: string; page: number | null }>;
  balance: Record<string, Figure> | null;
  posts: { label: string; count: number; total: boolean }[] | null;
  ministries: Ministry[];
  stated: Record<string, string[] | undefined>;
  sources: Record<string, string | undefined>;
  contents: {
    articles: { number: string; eid: string; label: string; subject: string; part: string; page: number | null }[];
    changes: { id: number; title: string; type: string; number: string | null; count: number }[];
  };
  dahir: string;
  signed_on: string | null;
  checks: { count: number; passed: number; shown: string[]; items: Check[]; checked_at: string | null };
};

export const budgetApi = {
  laws: () => api<LawSummary[]>('/budget/laws/'),
  law: (year: string) => api<BudgetDetail>(`/budget/laws/${year}/`),
};

export const useBudgetLaws = () => useQuery({ queryKey: ['budget', 'laws'], queryFn: budgetApi.laws });
export const useBudget = (year: string) =>
  useQuery({ queryKey: ['budget', 'law', year], queryFn: () => budgetApi.law(year), enabled: Boolean(year) });
