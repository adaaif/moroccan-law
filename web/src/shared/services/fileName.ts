/** The site's Latin name, the one readers see beside the Arabic «قانون» (15 Nov 2026: the address is 3adala.com). */
export const SITE_NAME = '3adala';

/** The name of a file a reader saves (a picture, a calendar, an export): the site's name first, «3adala-clock.png». */
export const fileName = (what: string) => `${SITE_NAME}-${what}`;
