import type { AccessAct } from './AccessSheet';

/** What is open beside the list: a request's sheet or an access's, perhaps on one of its acts. */
export type Open = { kind: 'request' | 'access'; id: number; act?: AccessAct };
