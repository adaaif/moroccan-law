import { Button } from '@/shared/components/ui';
import { Chips } from '../../../kit/tool/parts';
import Stepper from '../../../kit/tool/Stepper';
import type { Area } from '../area';
import type { Tanzil as TanzilCase } from '../engine';
import Cites from '../parts/Cites';
import { useT } from '../strings';

/** A «تنزيل» (IR26 of the inheritance review; arts 315–320): people who are not heirs set in the place of a son or a
 *  daughter. How many; whether the words made them that child's equal (counted by rise, art. 317 §1) or not (counted
 *  among the heirs, art. 317 §2); and, only when it changes something, whether the heirs agree to more than the third
 *  it shares with the will and the compulsory bequest. */
export default function Tanzil({ c, set, answer, setOpen }: Area) {
  const { t } = useT();
  const z = c.tanzil;
  const put = (patch: Partial<TanzilCase>) => set({ tanzil: { as: 'son', count: 1, equal: false, agreed: false, ...z, ...patch } });
  const cut = answer.state === 'ok' && Boolean(answer.result.tanzil?.cut);
  const yesNo = [{ key: 'n', label: t('office.tanzil.no') }, { key: 'y', label: t('office.tanzil.yes') }];
  return (
    <section aria-labelledby="tanzil-title" className="flex flex-col gap-3 rounded-card bg-sheet px-5 py-5 sm:px-7">
      <div className="flex flex-col gap-1">
        <h2 id="tanzil-title" className="m-0 text-lead font-semibold">{t('office.tanzil.title')}</h2>
        <p className="m-0 text-meta text-ink-soft">{t('office.tanzil.lead')}</p>
      </div>
      <Chips<string> label={t('office.tanzil.as')} value={z?.as ?? ''} onChange={(as) => put({ as: as as TanzilCase['as'] })}
                     options={[{ key: 'son', label: t('office.tanzil.son') }, { key: 'daughter', label: t('office.tanzil.daughter') }]} />
      {z ? (
        <>
          <div className="flex flex-col">
            <Stepper label={t('office.tanzil.count')} value={z.count} min={1} max={20} onChange={(count) => put({ count })} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Chips<string> label={t(`office.tanzil.equal_${c.deceased}`)} value={z.equal ? 'y' : 'n'} onChange={(k) => put({ equal: k === 'y' })}
                           options={[{ key: 'y', label: t('office.tanzil.equalYes') }, { key: 'n', label: t('office.tanzil.equalNo') }]} />
            <p className="m-0 text-meta text-ink-soft">{t(z.equal ? 'office.tanzil.byRise' : 'office.tanzil.byAmong')}</p>
          </div>
          {cut || z.agreed ? (
            <Chips<string> label={t('office.tanzil.agreed')} value={z.agreed ? 'y' : 'n'} onChange={(k) => put({ agreed: k === 'y' })} options={yesNo} />
          ) : null}
        </>
      ) : null}
      <Cites today={[315, 316, 317, 318, 319, 320]} />
      <Button variant="quiet" className="self-start" onClick={() => { set({ tanzil: null }); setOpen({ tanzil: false }); }}>{t('office.close')}</Button>
    </section>
  );
}
