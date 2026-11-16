/** The search page's code as the router loads it, fetched too when the box gets the finger (HM7 of
 *  the hard-moment review). The app sets it: an `import()` in the box would carry its own list of the page's 38 files, 0.6 KB at first
 *  load. */
export const loaders: { searchPage?: () => Promise<unknown> } = {};
