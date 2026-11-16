# Design

The tokens and the rules of the interface. The values below come from `web/src/shared/design/app.css`.

## Where the tokens live

- `web/src/shared/design/app.css` imports Tailwind 4 and defines the tokens in its `@theme` block: colours, the two
  faces, the type sizes and the corners. Tailwind turns each into utilities (`bg-paper`, `text-stamp`, `text-meta`,
  `rounded-card`).
- Components use tokens by name, never a raw hex.
- The twelve topic colours are plain custom properties on `:root`, read through `--t` by the topic pages.
- Night redefines every colour token twice: under `@media (prefers-color-scheme: dark)` unless the reader chose
  light, and under `:root[data-theme='dark']` when they chose dark.

## Colours

| Token | Light | Dark | Use |
|---|---|---|---|
| `ink` | `#1e1b2c` | `#ece9f4` | text |
| `ink-soft` | `#5d586e` | `#b2adc3` | secondary text |
| `muted` | `#8a8598` | `#7f7992` | the quietest text |
| `paper` | `#f4f2ee` | `#13111a` | the page's warm ground |
| `sheet` | `#ffffff` | `#1c1925` | sheets and cards |
| `rule` / `rule-soft` | `#e4e0da` / `#efece6` | `#2f2b3c` / `#262333` | lines |
| `field` | `#8a8478` | `#6e6888` | an input's edge, 3:1 on sheet and paper |
| `chip` / `tick` | `#ebe8e2` / `#ddd9d2` | `#2b2839` / `#44405a` | chips, ticks |
| `stamp` | `#5b3a9e` | `#b9a5f3` | the violet: links, the current place, the primary action, the law's source |
| `stamp-deep` | `#3f2876` | `#d6cbf8` | a link under the pointer |
| `wash` | `#efe9f8` | `#2a2446` | the source chip's ground |
| `stamp-line` | `#c9b9ee` | `#5a4a94` | violet rules |
| `target-wash` | `#f4effa` | `#242040` | the article an address names |
| `on-stamp` | `#ffffff` | `#10131a` | text on violet |
| `in-force` | `#0e7157` | `#4fc39a` | status |
| `amended` / `amended-wash` | `#93540a` / `#fdf3e6` | `#e3a651` / `#3a2c17` | status; a version assembled from amendments |
| `repealed` | `#b42318` | `#f0796d` | status |
| `people` / `people-fill` / `people-wash` | `#a35a00` / `#f0a21b` / `#fff1d9` | `#f2b44a` / `#f0a21b` / `#33270f` | people's words (explanations, guides) |
| `on-people` | `#241400` | `#241400` | text on saffron |
| `talk` / `talk-wash` | `#126b60` / `#e1f2ee` | `#5cc8b6` / `#143029` | the conversation |
| `chart-1` / `chart-2` | `#5b3a9e` / `#d97706` | `#9479dc` / `#cf7d14` | the two series of a chart |
| `sign-red` / `sign-blue` | `#c1272d` / `#1d5ba8` | `#c8333a` / `#2b67b8` | road signs and the urgent band only |
| `band-ink` | `#1f3a72` | `#26467f` | a navy urgent band |
| `scrim` | `#080710` | `#080710` | under a sheet or a drawer |

- `share-1` to `share-6` colour budget shares, in chart order: `#5b3a9e`, `#8a6fc9`, `#c4b4ea`, `#0f7b5f`,
  `#a15c07`, `#a3a1b6`.
- The topic colours, `--color-t-<slug>` (light, dark): family `#c2417a`, `#ef7aa8`; work `#2b66c9`, `#7fa8ff`;
  housing `#11806a`, `#4fc3a6`; road `#b86e00`, `#f0b34a`; consumer `#a6338f`, `#e07cc9`; land `#5e7f1f`, `#a8c45a`;
  tax `#8d6e00`, `#e0c24a`; health `#c8463d`, `#f08a80`; papers `#0e7490`, `#4cc3dc`; business `#a0522d`, `#e09a6e`;
  justice `#3f51b5`, `#9aa8f0`; digital `#455a64`, `#a7b9c2`.
- Status colours differ in lightness as well as hue. A status colour never draws a sign.
- Warnings appear only when something is wrong for the reader: repealed, not yet in force, changing on a date, a
  passage that could not be read.

## Type

- `font-law` is Markazi Text. It sets the law's own words and nothing else.
- `font-ui` is Readex Pro. It sets the interface and everything people write.
- French law is set in Source Serif 4 (`font-law-fr`, in `french.css`, loaded only with French law).
- The fonts are self-hosted in `web/public/fonts/` (SIL OFL 1.1), variable in weight, with `font-display: swap`.
  Each face is cut in two by `unicode-range`, Arabic and Latin, so an Arabic page fetches no Latin cut.

Seven sizes for the interface and one for the law, used by name, never as an arbitrary value. Titles grow with the
screen between a phone and a desk.

| Token | Size | Line height |
|---|---|---|
| `text-meta` | 0.875rem (14 px) | 1.5 |
| `text-body` | 1rem (16 px) | 1.65 |
| `text-lead` | 1.125rem (18 px) | 1.6 |
| `text-h3` | 1.375rem (22 px) | 1.35 |
| `text-h2` | 1.75rem (28 px) | 1.25 |
| `text-h1` | clamp(2rem, 1.7rem + 1.2vw, 2.75rem), 32 to 44 px | 1.15 |
| `text-display` | clamp(3rem, 2.5rem + 1.6vw, 3.75rem), 48 to 60 px | 1.1 |
| `text-law` | clamp(1.3125rem, 1.25rem + 0.25vw, 1.375rem), 21 to 22 px | 1.85 |

Markazi has a small x-height, so the law's size reads a step smaller than Readex at the same pixels.

## Corners, spacing and targets

- Three corners: `rounded-control` (10 px) for controls, `rounded-card` (18 px) for cards and sheets, `rounded-full`
  for chips and pills. No rings around cards; shadows only on what floats.
- **Nothing under 14 px.** `text-meta` is the floor, and `npm run check:budget` fails on any smaller size in `src/`.
- **Every target is 44 px at least.** Buttons are `h-11` (the primary `h-12`). A small mark a finger must hit, such
  as the source chip, carries `data-hit`, which extends its touch area to 44 px without changing what the eye sees.
- Focus is a 2 px outline in `stamp`, 2 px away.
- One grid: `Page` holds every page inside 1104 px of content, with a 16 px gutter on a phone. A reading page keeps a
  720 px column and, on a desk, a 300 px side column.

## The kit

Pages are built from `web/src/shared/components/`:

- `ui.tsx`: `Page`, `Card`, `Note` (tones `people`, `talk`, `warn`, `law`; `quiet` draws a rule on its start side),
  `Button` (`primary`, `secondary`, `quiet`, `icon`), `ListRow`, `SectionHeader`, `EmptyState`, and skeletons in the
  page's shape (`Skeleton`, `PageSkeleton`, `LinesSkeleton`).
- `Sheet.tsx`: the one sheet. It rises from the bottom on a phone and follows the finger down; `centered` makes it a
  card on a desk. `dismiss.ts` (`useDismiss`) closes it with Escape or the phone's back and gives focus back.
- `Field.tsx` (`TextField`, `PasswordField`) and `buttons.ts` (class strings for the rare control that cannot be a
  component).
- Every route sets its title with `usePageTitle` (`shared/services/title.ts`).

## The law on the page

- **The source stamp.** Wherever a source is named, a chip names the Bulletin's issue and page in violet ink
  (`text-stamp` on `bg-wash`), for example «الجريدة الرسمية 7533 · الصفحة 2168». A tap opens the printed page
  (`features/corpus/article/Stamp.tsx`). A version assembled from amendments is unofficial: its chip is amber and
  says so, since the Bulletin prevails. An article reached by its link presses its stamp once.
- **The law in Markazi.** The law's words are `font-law text-law`, and they stay Arabic and right to left in both
  interface languages (`AR` in `features/corpus/format.ts`).
- **Articles numbered in the margin.** Each article's label stands in the margin, the word small over the number
  large, on the text page and in search results (`Margin` in `features/search/SearchParts.tsx`).
- The tools come on request: a row on a desk, a sheet on a phone. Printing prints the law, never the tools.
- The horseshoe arch (`features/topics/Arch.tsx`) marks the ways in only: the topics' doors and windows, the icon.
  Never a card, a button or an article.

## Languages and direction

- **Arabic first.** Pages are right to left in Arabic. French is a full second language, addressed as `vous`, and its
  pages are left to right. Every string is in `ar.json` and `fr.json` with the same keys; `applyLanguage` sets `lang`
  and `dir` on `<html>`.
- Layout uses logical classes (`ms-*`, `pe-*`, `end-*`). «‹» and «›» mirror by themselves; only an SVG arrow is
  turned (`rtl:rotate-180`).
- **Western digits**, as the BO prints them. Dates use `Intl.DateTimeFormat` with `ar-MA` and `fr-MA`. Today is
  Morocco's day (`shared/services/today.ts`).
- **Typed text gets `dir="auto"`.** An empty field keeps the page's direction, and each typed line takes its own.
  Emails and passwords are `dir="ltr"`.
- **The voice recorder and player stay left to right** on every page: `dir="ltr"` on the control, play on the left,
  the waveform filling from the left (`features/discussion/audio/`).
- **Charts run left to right** on every page, time and amounts growing to the right, the words in their own
  direction, with a legend for coloured kinds. **The percent sign stays to the right of its number**: `pct()` in
  `shared/locales/i18n.ts` wraps the number and its sign in a left-to-right isolate, so it reads «39٪».
- Server errors arrive as codes and are translated as `errors.<field>.<code>` in both locales.

## Motion

- A sheet rises, a panel slides in from its side, content fades in. All of it is off under reduced motion.
- Three view transitions say where you went: a door into its topic's window (`topic-arch`), an article's number into
  its discussion (`article-talk`), a result's label into the article's number (`article-label`). Nothing else moves
  between pages.

## The first-load budget

`npm run build`, then `npm run check:budget` (`web/scripts/check-budget.mjs`), reads the gzip sizes in `dist/`:

- the JavaScript at first load, the stylesheet, and the fonts an Arabic page needs;
- the prerendered home and the largest landing page, when a prerender has written them;
- that the French words load apart, and that no text is under 14 px.

Over a limit, it fails. The limits are in the script, and a change that needs more says why in its commit. What a
reader asks for comes when asked: lazy pages, their words in `pages.*.json`, a feature's CSS with its pages.
