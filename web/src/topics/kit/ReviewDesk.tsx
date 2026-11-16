import { Suspense, useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AR } from '@/features/corpus/format';
import { Button, Note, Page, PageSkeleton } from '@/shared/components/ui';
import { markStaff } from '@/shared/analytics/device';
import { api, ApiError } from '@/shared/services/api';
import { REVIEW_EXTRAS } from '../registry';
import { pick, refPath, useKitT, type Cite, type Named } from './api';

type Item = {
  ref: string; kind: string; key: string; title: Named | null; state: 'draft' | 'stale' | 'checked'; open?: boolean;
  checked: { by: string; on: string } | null; wave: number | null; item: Record<string, unknown> | null;
  /** Times its page was shown in the last 28 days; null for an item without a page of its own. */
  readers: number | null;
};
type Desk = { slug: string; items: Item[]; bodies: Record<string, string> };
type Unit = { label: string; text: Named[]; cites: Cite[] };

/** The sentences of an item a reviewer checks one by one, each with the articles it rests on. */
function units(it: Item, lang: string): Unit[] {
  const x = it.item as Record<string, never> | null;
  if (!x) return [];
  const named = (v: unknown) => (v && typeof v === 'object' && 'ar' in (v as object) ? [v as Named] : []);
  const out: Unit[] = [];
  if (x.lead) out.push({ label: '·', text: named(x.lead), cites: (x.cites as Cite[]) ?? [] });
  (x.steps as Record<string, unknown>[] | undefined)?.forEach((s, i) => out.push({
    label: `${i + 1} · ${pick(s.title as Named, lang)}`, text: [...named(s.answer), ...named(s.body)], cites: (s.cites as Cite[]) ?? [] }));
  (x.sections as Record<string, unknown>[] | undefined)?.forEach((s) => (s.facts as Record<string, unknown>[] | undefined)?.forEach((f, i) => out.push({
    label: `${pick(s.title as Named, lang)} · ${i + 1}`, text: named(f.text), cites: (f.cites as Cite[]) ?? [] })));
  (x.items as Record<string, unknown>[] | undefined)?.forEach((f, i) => out.push({
    label: `${i + 1}`, text: [...named(f.label), ...named(f.note), ...named(f.when)], cites: (f.cites as Cite[]) ?? [] }));
  (x.timeline as Record<string, unknown>[] | undefined)?.forEach((f) => out.push({
    label: String(f.date), text: named(f.text), cites: (f.cites as Cite[]) ?? [] }));
  if (x.line) out.push({ label: '·', text: named(x.line), cites: [] });
  (x.notes as unknown[] | undefined)?.forEach((n, i) => out.push({ label: `${i + 1}`, text: named(n), cites: [] }));
  return out;
}

const KEY = (slug: string, ref: string) => `law.review.${slug}.${ref}`;
const readTicks = (slug: string, ref: string): number[] => { try { return JSON.parse(localStorage.getItem(KEY(slug, ref)) ?? '[]'); } catch { return []; } };

/** The reviewer's desk (R1, R2 of the road tools review): every item of the topic by wave, drafts included, each
 *  sentence beside the words of the articles it cites; a tick per sentence, kept on this device; once every sentence
 *  passes, the check is recorded for the item as `manage.py approve_topic` records it (who, when, the articles'
 *  digests), under the signed-in account's name: the server takes no name from the page. Each wave lists its items
 *  most read first, an item's readings of the last 28 days quietly beside it. Staff only: the server says so to anyone
 *  else. */
export default function ReviewDesk({ slug }: { slug: string }) {
  const { t, i18n } = useKitT();
  const lang = i18n.language;
  const qc = useQueryClient();
  // The desk answers staff alone (MayReview): this device is a team's, never counted by the site's measures.
  const q = useQuery({ queryKey: ['review', slug], queryFn: () => api<Desk>(`/topics/${slug}/review/`).then((d) => { markStaff(); return d; }), retry: false });
  const [wave, setWave] = useState<number | 'all'>(1);
  const [open, setOpen] = useState<string | null>(null);
  const [ticks, setTicks] = useState<Record<string, number[]>>({});
  const approve = useMutation({
    mutationFn: (refs: string[]) => api(`/topics/${slug}/review/`, { method: 'POST', json: { refs } }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ['review', slug] }); void qc.invalidateQueries({ queryKey: ['topic'] }); },
  });
  if (q.isLoading) return <Page width="reading"><PageSkeleton /></Page>;
  if (q.error) {
    const status = q.error instanceof ApiError ? q.error.status : 0;
    return (
      <Page width="reading">
        <Note tone="warn"><p className="m-0 text-body">{t(status === 401 ? 'review.signIn' : status === 403 ? 'review.staff' : 'review.failed')}</p></Note>
        {status === 401 ? <Button to={`/login?next=${encodeURIComponent(`/topics/${slug}/review`)}`}>{t('review.signInButton')}</Button> : null}
      </Page>
    );
  }
  const desk = q.data!;
  const Extra = REVIEW_EXTRAS[slug];
  const waves = [...new Set(desk.items.map((i) => i.wave).filter((w): w is number => w !== null))].sort();
  const shown = desk.items.filter((i) => wave === 'all' || i.wave === wave);
  const tick = (ref: string, n: number) => {
    const cur = ticks[ref] ?? readTicks(slug, ref);
    const next = cur.includes(n) ? cur.filter((x) => x !== n) : [...cur, n];
    setTicks({ ...ticks, [ref]: next });
    try { localStorage.setItem(KEY(slug, ref), JSON.stringify(next)); } catch { /* private window */ }
  };
  return (
    <Page width="wide" className="gap-5">
      <header className="flex flex-col gap-1">
        <Link to={`/topics/${slug}`} className="text-body text-ink-soft no-underline">{t('review.back')}</Link>
        <h1 className="m-0 text-h1 font-bold">{t('review.title')}</h1>
        <p className="m-0 text-lead text-ink-soft">{t('review.lead')}</p>
      </header>
      <div role="tablist" className="flex flex-wrap gap-2">
        {[...waves, 'all' as const].map((w) => {
          const here = desk.items.filter((i) => w === 'all' || i.wave === w);
          return (
            <button key={w} type="button" role="tab" aria-selected={wave === w} onClick={() => setWave(w)}
                    className={`min-h-11 rounded-full border px-4 text-body ${wave === w ? 'border-ink bg-ink text-sheet' : 'border-rule bg-sheet'}`}>
              {w === 'all' ? t('review.all') : t('review.wave', { n: w })} · {here.filter((i) => i.state === 'checked').length}/{here.length}
            </button>
          );
        })}
      </div>
      <ul className="m-0 flex list-none flex-col gap-2 p-0">
        {shown.map((it) => {
          const us = units(it, lang);
          const done = ticks[it.ref] ?? readTicks(slug, it.ref);
          const ready = it.kind === 'tools' || (us.length > 0 && us.every((_, n) => done.includes(n)));
          return (
            <li key={it.ref} className="rounded-card bg-sheet">
              <button type="button" aria-expanded={open === it.ref} onClick={() => setOpen(open === it.ref ? null : it.ref)}
                      className="flex w-full flex-wrap items-center gap-3 px-5 py-4 text-start">
                <span className={`rounded-full px-2.5 py-0.5 text-meta ${it.state === 'checked' ? 'bg-[color-mix(in_srgb,var(--color-in-force)_14%,var(--color-sheet))] text-in-force' : it.state === 'stale' ? 'bg-amended-wash text-amended' : 'bg-paper text-ink-soft'}`}>
                  {t(`review.states.${it.state}`)}{it.open ? ` · ${t('review.open')}` : ''}
                </span>
                <span lang={lang} className="min-w-0 flex-1 text-lead font-semibold">{pick(it.title ?? undefined, lang) || it.ref}</span>
                <span className="text-meta text-ink-soft" dir="ltr">{it.ref}</span>
                {it.readers ? <span className="text-meta text-ink-soft">{t('review.readers', { count: it.readers })}</span> : null}
                {us.length ? <span className="text-meta text-ink-soft">{done.length}/{us.length}</span> : null}
              </button>
              {open === it.ref ? (
                <div className="flex flex-col gap-3 border-t border-rule px-5 py-4">
                  {it.checked ? <p className="m-0 text-meta text-ink-soft">{t('checked', { by: it.checked.by, date: it.checked.on })}</p> : null}
                  {it.kind === 'tools' ? <Link to={refPath(slug, it.ref)} className="text-body">{t('review.openTool')}</Link> : null}
                  {us.map((u, n) => (
                    <div key={n} className={`grid gap-3 rounded-control border px-3 py-3 lg:grid-cols-2 ${done.includes(n) ? 'border-in-force' : 'border-rule'}`}>
                      <div className="flex flex-col gap-1.5">
                        <span className="text-meta font-semibold text-ink-soft">{u.label}</span>
                        {u.text.map((x, k) => <p key={k} className="m-0 text-body">{x.ar}<br /><span className="text-meta text-ink-soft" lang="fr" dir="ltr">{x.fr}</span></p>)}
                        <label className="flex min-h-11 items-center gap-2">
                          <input type="checkbox" checked={done.includes(n)} onChange={() => tick(it.ref, n)} className="size-5 accent-[var(--color-in-force)]" />
                          <span className="text-body">{t('review.right')}</span>
                        </label>
                      </div>
                      <div className="flex flex-col gap-2">
                        {u.cites.length ? u.cites.map((c) => (
                          <details key={c.path} open={u.cites.length === 1}>
                            <summary className="cursor-pointer text-meta font-semibold text-stamp"><bdi {...AR}>{c.label}</bdi> · {pick(c.text, lang)}</summary>
                            <p {...AR} className="m-0 mt-1 max-h-64 overflow-y-auto whitespace-pre-line font-law text-body">{desk.bodies[c.path] ?? t('review.noBody')}</p>
                          </details>
                        )) : <span className="text-meta text-ink-soft">{t('review.noCites')}</span>}
                      </div>
                    </div>
                  ))}
                  <div className="flex flex-wrap items-center gap-3">
                    <Button variant="primary" disabled={!ready || approve.isPending} onClick={() => approve.mutate([it.ref])}>{t('review.approve')}</Button>
                    {!ready ? <span className="text-meta text-ink-soft">{t('review.notReady')}</span> : null}
                  </div>
                </div>
              ) : null}
            </li>
          );
        })}
      </ul>
      {Extra ? <Suspense fallback={null}><Extra slug={slug} /></Suspense> : null}
    </Page>
  );
}
