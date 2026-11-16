import { useId, useState, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { useMe } from '@/features/accounts/accounts.service';
import { TextField } from '@/shared/components/Field';
import { Button, Page, PageSkeleton } from '@/shared/components/ui';
import { ApiError } from '@/shared/services/api';
import { usePageTitle } from '@/shared/services/title';
import '@/shared/locales/pages';
import { body, check, KINDS, mayAsk, MOST, standing, VOLUMES, type Form } from './access';
import { accessApi, useAccess, useKeepAccess } from './access.api';
import { Alerts, StandingLine } from './parts';
import { Sent } from './Sent';
import { useRefusals } from './said';
import '@/features/corpus/library.css';
import './access.css';

/** Every field the form sends, so a refusal of one is said beside it and the rest above the button. */
const FIELDS = ['name', 'kind', 'purpose', 'wants', 'wants_api', 'wants_data', 'runs_at', 'volume', 'commercial', 'terms', 'consent'];

const EMPTY: Form = { name: '', kind: '', purpose: '', wants_api: false, wants_data: false, runs_at: '', volume: '',
  commercial: null, terms: false, consent: false };

/**
 * /data/request, behind sign-in: the six answers (who, what for, what, where, how much, whether it earns money), the
 * terms accepted and the consent, never ticked for the person (law 09-08). Every refusal of the server is said in words,
 * beside its field where it has one. An account whose address is not proven is told so, with the way to prove it; one
 * that already asked sees where its request stands instead of the form, and so does one that just sent it.
 */
export default function RequestPage() {
  const { t } = useTranslation();
  usePageTitle([t('pages:access.form.title')]);
  const me = useMe();
  const access = useAccess();
  const b = access.data;
  if (!b || !me.data) return <Page width="reading"><PageSkeleton /></Page>;
  const s = standing(b);
  const head = (
    <header className="lb-head">
      <div>
        <h1>{t('pages:access.form.title')}</h1>
        <p className="lead">{t('pages:access.form.lead', { days: b.answer_days })}</p>
      </div>
    </header>
  );
  if (b.position === 'closed' || !mayAsk(s)) {
    return (
      <Page width="reading" className="lb ax">
        {head}
        {b.position === 'closed' ? <p className="ax-standing">{t('pages:errors.access.closed')}</p> : <StandingLine body={b} />}
        {b.position !== 'closed' && b.request && (s === 'waiting' || s === 'more') ? <Sent request={b.request} open /> : null}
        <p className="m-0"><Link to="/data">{t('pages:access.form.back')}</Link></p>
      </Page>
    );
  }
  return (
    <Page width="reading" className="lb ax">
      {head}
      {s === 'none' ? null : <StandingLine body={b} />}
      {me.data.email_proven ? null : (
        <p role="note" className="ax-unproven">
          {t('pages:access.form.unproven')} <Link to="/account#prove">{t('pages:access.form.prove')}</Link>
        </p>
      )}
      <RequestForm terms={b.terms} />
    </Page>
  );
}

function RequestForm({ terms }: { terms: string }) {
  const { t } = useTranslation();
  const keep = useKeepAccess();
  const said = useRefusals();
  const [f, setF] = useState<Form>(EMPTY);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const set = <K extends keyof Form>(k: K, v: Form[K]) => { setF((x) => ({ ...x, [k]: v })); setError(null); };
  const send = async () => {
    // The fields the server would refuse are said before asking it; it checks again and has the last word.
    const local = check(f);
    if (local.length) { setError(new ApiError(400, local.map(([field, code]) => ({ field, code })))); return; }
    setBusy(true); setError(null);
    try {
      keep(await accessApi.send(body(f, terms)));
      window.scrollTo(0, 0);
    } catch (e) { setError(e); } finally { setBusy(false); }
  };
  const err = (name: string) => said.field(error, name);
  return (
    <form noValidate className="ax-form" onSubmit={(e) => { e.preventDefault(); void send(); }}>
      <Group title={t('pages:access.form.who')}>
        <TextField label={t('pages:access.form.name')} hint={t('pages:access.form.nameHint')} error={err('name')} dir="auto"
                   value={f.name} maxLength={MOST.name} autoComplete="name" onChange={(e) => set('name', e.target.value)} />
        <Choice legend={t('pages:access.form.kind')} name="kind" error={err('kind')} value={f.kind} onChange={(v) => set('kind', v)}
                options={KINDS.map((k) => [k, t(`pages:access.form.kinds.${k}`)])} />
      </Group>

      <Group title={t('pages:access.form.purpose')}>
        <Purpose value={f.purpose} error={err('purpose')} onChange={(v) => set('purpose', v)} />
      </Group>

      <Group title={t('pages:access.form.wants')}>
        <fieldset className="ax-fieldset" aria-describedby={err('wants') ? 'wants-error' : undefined}>
          <legend className="ax-legend">{t('pages:access.form.wantsHint')}</legend>
          <label className="ax-tick">
            <input type="checkbox" checked={f.wants_api} onChange={(e) => set('wants_api', e.target.checked)} />
            <span><b>{t('pages:access.form.wantsApi')}</b><small>{t('pages:access.ask.api.d')}</small></span>
          </label>
          <label className="ax-tick">
            <input type="checkbox" checked={f.wants_data} onChange={(e) => set('wants_data', e.target.checked)} />
            <span><b>{t('pages:access.form.wantsData')}</b><small>{t('pages:access.ask.data.d')}</small></span>
          </label>
          {err('wants') ? <p id="wants-error" className="ax-error">{err('wants')}</p> : null}
        </fieldset>
      </Group>

      <Group title={t('pages:access.form.runsAt')} aside={t('pages:access.form.optional')}>
        <TextField label={t('pages:access.form.runsAtLabel')} hint={t('pages:access.form.runsAtHint')} error={err('runs_at')} dir="auto"
                   value={f.runs_at} maxLength={MOST.runs_at} inputMode="url" onChange={(e) => set('runs_at', e.target.value)} />
      </Group>

      <Group title={t('pages:access.form.volume')}>
        <Choice legend={t('pages:access.form.volumeHint')} name="volume" error={err('volume')} value={f.volume} onChange={(v) => set('volume', v)}
                options={VOLUMES.map((k) => [k, t(`pages:access.form.volumes.${k}`)])} stacked />
      </Group>

      <Group title={t('pages:access.form.commercial')}>
        <Choice legend={t('pages:access.form.commercialHint')} name="commercial" error={err('commercial')}
                value={f.commercial === null ? '' : f.commercial ? 'yes' : 'no'} onChange={(v) => set('commercial', v === 'yes')}
                options={[['yes', t('pages:access.form.yes')], ['no', t('pages:access.form.no')]]} />
      </Group>

      <Group title={t('pages:access.form.agree')}>
        <label className="ax-tick">
          <input type="checkbox" checked={f.terms} onChange={(e) => set('terms', e.target.checked)}
                 aria-describedby={err('terms') ? 'terms-error' : undefined} />
          <span>
            <b>{t('pages:access.form.terms')}</b>
            <small><Link to="/data/terms" target="_blank" rel="noopener">{t('pages:access.terms.title')}</Link></small>
          </span>
        </label>
        {err('terms') ? <p id="terms-error" className="ax-error">{err('terms')}</p> : null}
        <div className="ax-consent">
          <h3>{t('pages:access.form.keep')}</h3>
          {(t('pages:access.form.keepText', { returnObjects: true }) as string[]).map((p) => <p key={p}>{p}</p>)}
          <label className="ax-tick">
            {/* Law 09-08: never ticked for the person. */}
            <input type="checkbox" checked={f.consent} onChange={(e) => set('consent', e.target.checked)}
                   aria-describedby={err('consent') ? 'consent-error' : undefined} />
            <span><b>{t('pages:access.form.consent')}</b><small><Link to="/privacy#write">{t('pages:access.form.privacy')}</Link></small></span>
          </label>
          {err('consent') ? <p id="consent-error" className="ax-error">{err('consent')}</p> : null}
        </div>
      </Group>

      <div className="ax-send">
        <Button variant="primary" type="submit" disabled={busy}>{busy ? t('pages:access.form.sending') : t('pages:access.form.send')}</Button>
        <Alerts lines={said.form(error, FIELDS)} />
        <FormLinks error={error} />
      </div>
    </form>
  );
}

/** A refusal that has a way out: an address to prove, a request already waiting on «وصولي». */
function FormLinks({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!(error instanceof ApiError)) return null;
  if (error.codeFor('email') === 'unproven') return <Link to="/account#prove">{t('pages:access.form.prove')}</Link>;
  if (error.codeFor('request') || error.codeFor('access') === 'live') return <Link to="/data/access">{t('pages:access.states.toAccount')}</Link>;
  if (error.codeFor('terms') === 'stale') return <Link to="/data/terms" target="_blank" rel="noopener">{t('pages:access.terms.title')}</Link>;
  return null;
}

/** One question of the form: its title on a rule, what it asks under it. */
function Group({ title, aside, children }: { title: string; aside?: string; children: ReactNode }) {
  return (
    <section className="ax-group">
      <h2>{title}{aside ? <small>{aside}</small> : null}</h2>
      {children}
    </section>
  );
}

/** One answer of a few, as buttons a finger can hit; its refusal under it. */
function Choice({ legend, name, value, options, onChange, error, stacked = false }: {
  legend: string; name: string; value: string; options: [string, string][]; onChange: (v: string) => void; error?: string; stacked?: boolean;
}) {
  const id = useId();
  return (
    <fieldset className="ax-fieldset" aria-describedby={error ? `${id}-error` : undefined}>
      <legend className="ax-legend">{legend}</legend>
      <div className={`ax-choices ${stacked ? 'stacked' : ''}`}>
        {options.map(([v, label]) => (
          <label key={v}>
            <input type="radio" name={name} value={v} checked={value === v} onChange={() => onChange(v)} />
            <span>{label}</span>
          </label>
        ))}
      </div>
      {error ? <p id={`${id}-error`} className="ax-error">{error}</p> : null}
    </fieldset>
  );
}

/** What will be built or studied: a text box of 600 characters, with what is left of them. */
function Purpose({ value, error, onChange }: { value: string; error?: string; onChange: (v: string) => void }) {
  const { t } = useTranslation();
  const id = useId();
  const left = MOST.purpose - value.length;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-meta font-medium">{t('pages:access.form.purposeLabel')}</label>
      <textarea id={id} dir="auto" rows={6} maxLength={MOST.purpose} value={value} onChange={(e) => onChange(e.target.value)}
                aria-invalid={error ? true : undefined} aria-describedby={`${id}-hint ${id}-count${error ? ` ${id}-error` : ''}`}
                className={`ax-textarea ${error ? 'bad' : ''}`} />
      <div className="ax-under">
        <p id={`${id}-hint`} className="m-0 text-meta text-ink-soft">{t('pages:access.form.purposeHint')}</p>
        <p id={`${id}-count`} className={`ax-count ${left < 60 ? 'low' : ''}`} aria-live="polite">
          {t('pages:access.form.left', { n: left })}
        </p>
      </div>
      {error ? <p id={`${id}-error`} className="ax-error">{error}</p> : null}
    </div>
  );
}
