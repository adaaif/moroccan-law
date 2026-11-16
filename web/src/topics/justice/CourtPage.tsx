import { Button } from '@/shared/components/ui';
import { refPath } from '../kit/api';
import { KitPage } from '../kit/parts';
import { AnswerCard, Chips, SourceFold } from '../kit/tool/parts';
import { useToolState } from '../kit/tool/state';
import { MoneyField } from '../business/parts';
import { CASSATION, COUNTED, FINAL, PROXIMITY, SUBJECTS, court, type Subject } from './rules/court';
import { Ladder, Sheet } from './parts';
import { articleLabel, useJusticeT, useMoney } from './strings';

/** «فين نمشي؟» (the justice review): what the dispute is about and how much → the court that decides it, drawn with
 *  the courts above it as three tiers, the ways up lit only where the law opens them (58.25 arts 29–33, 38, 204, 32,
 *  375, 331), then what the procedure is, what it costs and whether a lawyer is needed. It names the court; it never
 *  says who is right. It waits for a person's check. The inputs live in the address. */
export default function CourtPage({ slug }: { slug: string }) {
  const { t } = useJusticeT();
  const money = useMoney();
  const [s, set] = useToolState({ s: 'debt', m: '4000' });
  const subject = (SUBJECTS.includes(s.s as Subject) ? s.s : 'debt') as Subject;
  const amount = Math.max(0, Number(s.m) || 0);
  const a = court(subject, amount);
  const counted = COUNTED[subject];
  const crime = a.court === 'prosecutor';
  const tiers = crime ? [] : [
    { key: 'first', title: t(`court.courts.${a.court}`), line: t(`court.lines.${a.court}`), on: true },
    a.recourse.kind === 'annul'
      ? { key: 'annul', title: t('court.annulTier'), line: t('court.annulLine'), on: true, way: t('court.wayAnnul', { count: a.recourse.days }) }
      : { key: 'appeal', title: t('court.appealTier'), line: t('court.appealLine'), on: true, way: t('court.wayAppeal', { count: a.recourse.days }) },
    { key: 'cassation', title: t('court.cassationTier'), line: a.cassation.open ? t('court.cassationOpen') : t('court.cassationClosed'), on: a.cassation.open,
      way: a.cassation.open ? t('court.wayCassation') : t('court.wayNone') },
  ];
  const paths = [...new Set([a.path, a.recourse.path, a.cassation.path, ...(a.free === 'proximity' ? ['/ma/loi/58-25/art_329'] : []),
    ...(a.free === 'admin-appeal' ? ['/ma/loi/58-25/art_215'] : []), a.oral ? '/ma/loi/58-25/art_96' : '/ma/loi/58-25/art_95',
    a.lawyer === 'aid' ? '/ma/loi/58-25/art_311' : '/ma/loi/58-25/art_79', '/ma/loi/58-25/art_376'])];
  return (
    <KitPage slug={slug} title={t('court.title')} lead={t('court.lead')}>
      <AnswerCard share over={t(crime ? 'court.overCrime' : 'court.over')} value={t(`court.courts.${a.court}`)}
                  under={<p className="m-0">{t(`court.lines.${a.court}`)}</p>} />
      <Sheet>
        <Chips label={t('court.subject')} value={subject} onChange={(v) => set({ s: v })}
               options={SUBJECTS.map((k) => ({ key: k, label: t(`court.subjects.${k}`) }))} />
        {counted ? (
          <MoneyField label={t('court.amount')} value={s.m} onChange={(m) => set({ m })}
                      note={t('court.amountNote', { proximity: money(PROXIMITY), final: money(FINAL), cassation: money(CASSATION) })} />
        ) : null}
      </Sheet>
      {crime ? (
        <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
          <p className="m-0 text-body">{t('court.crimeLine')}</p>
          <SourceFold paths={['/ma/loi/22-01/art_40', '/ma/loi/22-01/art_21', '/ma/loi/22-01/art_384']} label={articleLabel} />
          <div className="flex flex-wrap gap-2">
            <Button to={refPath(slug, 'journeys/complaint')}>{t('court.toComplaint')}</Button>
          </div>
        </section>
      ) : (
        <>
          <section className="rounded-card bg-sheet px-5 py-5 sm:px-7">
            <h2 className="m-0 mb-3 text-h3 font-bold">{t('court.ladderTitle')}</h2>
            <Ladder tiers={tiers} />
          </section>
          <section className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
            <h2 className="m-0 text-h3 font-bold">{t('court.howTitle')}</h2>
            <ul className="m-0 flex list-none flex-col gap-1.5 p-0">
              <li className="text-body">• {t(a.oral ? 'court.oral' : subject === 'family' ? 'court.familyOral' : 'court.written')}</li>
              <li className="text-body">• {t(a.free === 'proximity' ? 'court.free' : a.free === 'admin-appeal' ? 'court.adminFree' : 'court.fees')}</li>
              <li className="text-body">• {t(a.lawyer === 'aid' ? 'court.workerAid' : 'court.ownLawyer')}</li>
              {a.cassation.open ? <li className="text-body">• {t('court.cassationLawyer')}</li> : null}
            </ul>
            <SourceFold paths={paths} label={articleLabel} />
            <div className="flex flex-wrap gap-2">
              <Button to={refPath(slug, a.court === 'proximity' ? 'journeys/small-claim' : 'journeys/lawsuit')}>{t(a.court === 'proximity' ? 'court.toSmall' : 'court.toLawsuit')}</Button>
              <Button variant="quiet" to={refPath(slug, 'pages/courts')}>{t('court.toPage')}</Button>
              <Button variant="quiet" to={refPath(slug, 'tools/deadline')}>{t('court.toDeadline')}</Button>
            </div>
          </section>
        </>
      )}
    </KitPage>
  );
}
