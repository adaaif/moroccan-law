import { useState } from 'react';
import type { Picture } from './discussion.api';
import { Sheet } from '@/shared/components/Sheet';
import { useT } from './strings';

/** A contribution's pictures, one at a time and whole. */
export function Lightbox({ pictures, start, onClose }: { pictures: Picture[]; start: number; onClose: () => void }) {
  const { t } = useT();
  const [i, setI] = useState(start);
  const p = pictures[i];
  return (
    <Sheet centered label={t('pictures.open')} onClose={onClose} wide>
      <div className="flex flex-col gap-3">
        <img src={p.full} alt="" width={p.width} height={p.height} className="max-h-[70vh] w-full rounded-control bg-paper object-contain" />
        <div className="flex items-center gap-2">
          {pictures.length > 1 ? (
            <span dir="ltr" className="flex gap-2">
              {pictures.map((x, k) => (
                <button key={x.id} type="button" onClick={() => setI(k)} aria-current={k === i}
                        className={`size-11 overflow-hidden rounded-control border-2 ${k === i ? 'border-stamp' : 'border-transparent'}`}>
                  <img src={x.thumb} alt="" className="size-full object-cover" />
                </button>
              ))}
            </span>
          ) : null}
          <button type="button" onClick={onClose} className="ms-auto h-11 rounded-control border border-rule px-5 text-body hover:bg-paper">{t('pictures.close')}</button>
        </div>
      </div>
    </Sheet>
  );
}
