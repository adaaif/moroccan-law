import { note } from '@/shared/analytics/note';
import { useSession } from '@/shared/stores/session';

/** The server's one error shape: {"errors": [{"field", "code"}]}. Codes are translated here, never sentences; an error
 *  may carry data for its sentence (a suggested address, the minutes to wait, where a link went), or for the page (the
 *  Turnstile key a sign-in past the brake asks the check with). */
export type FieldError = { field: string; code: string; suggestion?: string; minutes?: number; to?: string; sitekey?: string };

export class ApiError extends Error {
  readonly status: number;
  readonly errors: FieldError[];

  constructor(status: number, errors: FieldError[] = []) {
    super(`API ${status}`);
    this.status = status;
    this.errors = errors;
  }

  codeFor(field: string): string | undefined {
    return this.errors.find((e) => e.field === field)?.code;
  }
}

/** The fetch never reached the server (offline, DNS, server down). */
export class NetworkError extends Error {}

/** A call to the API that the server failed (5xx) or that got no answer at all (0), for the measures: the path as asked,
 *  which the measures' engine cuts to its endpoint before it leaves (shared/analytics). A call the page itself
 *  stopped is not a failure. */
const failed = (path: string, status: number, error?: unknown) => {
  if ((error as Error | undefined)?.name !== 'AbortError') note('api.failed', { endpoint: path, status });
};

let refreshing: Promise<boolean> | null = null;

/** One refresh at a time. Only the server refusing the token itself (401) ends the session, and says so: a busy server
 *  (429, perhaps someone else behind the same carrier address), a deploy's restart (502) or no network keeps it, and
 *  this one call fails. */
function refreshTokens(): Promise<boolean> {
  const tokens = useSession.getState().tokens;
  if (!tokens) return Promise.resolve(false);
  refreshing ??= (async () => {
    try {
      const response = await fetch('/api/auth/token/refresh/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh: tokens.refresh }),
      });
      if (response.status === 401) {
        useSession.getState().clear({ ended: true });
        return false;
      }
      if (response.status >= 500) failed('/auth/token/refresh/', response.status);
      if (!response.ok) return false;
      const body = (await response.json()) as { access: string; refresh?: string };
      useSession.getState().setTokens({ access: body.access, refresh: body.refresh ?? tokens.refresh });
      return true;
    } catch (e) {
      // Offline: keep the session, this call fails.
      failed('/auth/token/refresh/', 0, e);
      return false;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

type ApiInit = Omit<RequestInit, 'body'> & { json?: unknown };

/** Reads (no method given) that never look at an account go without the token: the server's answer is the same, and it is compressed
 *  (S16 of the performance audit: a signed-in reader's law page was sent uncompressed, 320 KB instead of 59). */
const OPEN = /^\/(corpus|search|sources|budget|open|follows\/news|explain\/(text|new|week|words)|discussion\/(counts|questions|answered))\/|^\/topics\/(?![\w-]+\/review\/)/;

export async function api<T>(path: string, init: ApiInit = {}): Promise<T> {
  const { json, headers: extraHeaders, ...rest } = init;
  const send = () => {
    const headers = new Headers(extraHeaders);
    if (json !== undefined) headers.set('Content-Type', 'application/json');
    const access = useSession.getState().tokens?.access;
    if (access && (rest.method || !OPEN.test(path))) headers.set('Authorization', `Bearer ${access}`);
    return fetch(`/api${path}`, {
      ...rest,
      headers,
      body: json !== undefined ? JSON.stringify(json) : undefined,
    });
  };

  let response: Response;
  try {
    response = await send();
    if (response.status === 401 && useSession.getState().tokens && (await refreshTokens())) {
      response = await send();
    }
  } catch (e) {
    failed(path, 0, e);
    throw new NetworkError();
  }

  if (!response.ok) {
    if (response.status >= 500) failed(path, response.status);
    let errors: FieldError[] = [];
    try {
      const body = (await response.json()) as { errors?: FieldError[] };
      if (Array.isArray(body.errors)) errors = body.errors;
    } catch {
      // No JSON body.
    }
    throw new ApiError(response.status, errors);
  }
  return response.status === 204 ? (undefined as T) : ((await response.json()) as T);
}
