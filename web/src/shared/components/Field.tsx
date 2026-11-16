import { useId, useState, type InputHTMLAttributes, type ReactNode } from 'react';
import { useTranslation } from 'react-i18next';
import '@/shared/locales/pages';

type FieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'id'> & {
  label: string;
  hint?: string;
  error?: string;
  /** Shown under the error or the hint, e.g. a way out of the error. */
  after?: ReactNode;
};

const inputClass =
  'h-12 w-full rounded-control border bg-sheet px-4 text-body text-ink outline-none ' +
  'focus-visible:border-stamp focus-visible:ring-4 focus-visible:ring-wash';

function useDescription(hint?: string, error?: string) {
  const id = useId();
  return {
    id,
    describedBy: error ? `${id}-error` : hint ? `${id}-hint` : undefined,
    note: error ? (
      <p id={`${id}-error`} className="text-meta text-repealed">
        {error}
      </p>
    ) : hint ? (
      <p id={`${id}-hint`} className="text-meta text-ink-soft">
        {hint}
      </p>
    ) : null,
  };
}

export function TextField({ label, hint, error, after, className, ...input }: FieldProps) {
  const { id, describedBy, note } = useDescription(hint, error);
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-meta font-medium">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={`${inputClass} ${error ? 'border-repealed' : 'border-field'} ${className ?? ''}`}
        {...input}
      />
      {note}
      {after}
    </div>
  );
}

/** A password field always has its eye: people type it on phones. The password reads left to
 *  right in both languages, so the eye sits on the physical right, past the end of the text. */
export function PasswordField({ label, hint, error, after, ...input }: Omit<FieldProps, 'type'>) {
  const { t } = useTranslation();
  const [shown, setShown] = useState(false);
  const { id, describedBy, note } = useDescription(hint, error);
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-meta font-medium">
        {label}
      </label>
      <div className="relative">
        <input
          id={id}
          type={shown ? 'text' : 'password'}
          dir="ltr"
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={`${inputClass} pr-12 ${error ? 'border-repealed' : 'border-field'}`}
          {...input}
        />
        <button
          type="button"
          onClick={() => setShown((s) => !s)}
          aria-label={shown ? t('pages:auth.hidePassword') : t('pages:auth.showPassword')}
          aria-pressed={shown}
          className="absolute inset-y-0 right-1 my-auto flex h-10 w-10 items-center justify-center rounded-control text-ink-soft hover:bg-paper"
        >
          <svg aria-hidden="true" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12z" />
            <circle cx="12" cy="12" r="3" />
            {shown ? null : <path d="M4 4l16 16" />}
          </svg>
        </button>
      </div>
      {note}
      {after}
    </div>
  );
}
