import { useTranslation } from 'react-i18next';
import { longDate } from './format';

export type RibbonMark = { date: string; label: string };

const DAY = 86_400_000;

/** The design's signature: a text's life as a ruler read in the page's direction, from its first
 *  publication to today, one segment per version. Recent segments keep a minimum width so a change made
 *  last month stays visible beside decades of stability. */
export function VersionRibbon({ start, startLabel, changes }: { start: string; startLabel: string; changes: RibbonMark[] }) {
  const { t, i18n } = useTranslation();
  const marks = [{ date: start, label: startLabel }, ...[...changes].sort((a, b) => a.date.localeCompare(b.date))];
  const now = Date.now();
  const spans = marks.map((m, i) => {
    const from = Date.parse(m.date);
    const to = i + 1 < marks.length ? Date.parse(marks[i + 1].date) : now;
    return Math.max(to - from, DAY);
  });
  const total = spans.reduce((a, b) => a + b, 0);
  const widths = spans.map((s) => Math.max((s / total) * 100, 14));
  const scale = 100 / widths.reduce((a, b) => a + b, 0);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-end gap-[3px]">
        {marks.map((m, i) => {
          const current = i === marks.length - 1;
          return (
            <div key={m.date + i} className="flex min-w-0 flex-col gap-1.5" style={{ width: `${widths[i] * scale}%` }}>
              <span className="flex flex-col leading-tight">
                <span className={`font-law text-law font-semibold ${current ? 'text-stamp' : ''}`}>
                  {longDate(m.date, i18n.language)}
                </span>
                <span className={`truncate text-meta ${current ? 'text-stamp' : 'text-ink-soft'}`}>{m.label}</span>
              </span>
              <span
                className={`flex h-10 items-center justify-center rounded-control text-meta font-medium ${
                  current ? 'bg-stamp text-on-stamp' : 'bg-chip text-ink-soft'
                }`}
              >
                {current ? t('corpus.currentVersion') : ''}
              </span>
            </div>
          );
        })}
      </div>
      <span className="self-end text-meta text-ink-soft">{t('corpus.today')}</span>
    </div>
  );
}
