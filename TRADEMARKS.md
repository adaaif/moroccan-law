# Trademarks

The licences of this repository (see `REUSE.toml` and `LICENSES/`) cover its code, its data and its editorial text.
They do not cover the service's name and marks.

## What is not licensed

- The names «قانون» and 3adala, as used for this service.
- The wordmark «قانون المغرب» and every drawing of it (`web/public/brand/`, `back/apps/corpus/data/wordmark.svg`).
- The icons made from them (`web/public/icons/`, `web/public/favicon.ico`, `web/public/apple-touch-icon.png`).

These belong to 3adala.com. No licence in this repository, whatever the licence of the file that holds
them, grants a right to use them. The files are marked `LicenseRef-Trademarks` in `REUSE.toml`.

## What you may do

- Run, study, change and share the code under its licence.
- Say truthfully that your work is based on this repository, or links to the service, using the name in plain text.

## What you may not do

- Publish a site, an app or a service under the name or the marks, or under a name or a mark close enough to be
  confused with them.
- Use the marks in a way that suggests the service endorses, runs or checks your work.

A fork that runs as a public site must take a name and marks of its own: replace the files listed above; set
`SITE_NAME`, `SITE_URL`, `FETCH_USER_AGENT` and `DEFAULT_FROM_EMAIL`; and replace the name where the code writes it
(`grep -rn '3adala\|قانون المغرب' back web/src web/index.html web/public`: the letters, the gate page, the assistants'
names, robots.txt, the share pictures, `app.name` in the locales).

## Asking

To use the name or the marks beyond what is allowed here, write to contact@3adala.com.

## Other marks

The sign-in button shows Google's «G» (`web/src/features/accounts/GoogleButton.tsx`), as Google's sign-in rules ask.
It is Google's trademark and is used only for that button.
