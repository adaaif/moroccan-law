# Fonts

`public/fonts/` holds Markazi Text and Readex Pro (SIL Open Font License 1.1, the licence files beside them),
variable in weight, each cut in two: the Arabic letters with the digits and punctuation, and the Latin letters
(a page fetches the Latin file only when it has Latin letters). Made from the google/fonts repository's
`ofl/markazitext/MarkaziText[wght].ttf` and `ofl/readexpro/ReadexPro[HEXP,wght].ttf` (HEXP pinned to 0,
weight kept 300–700) with fontTools:

```bash
AR="U+0020-0040,U+005B-0060,U+007B-007E,U+00A0,U+00AB,U+00B0,U+00BB,U+00D7,U+0600-0605,U+060C-061F,U+0621-065F,U+0660-0671,U+067E,U+0686,U+06A4,U+06A9,U+06AF,U+06CC,U+06D4,U+200C-200F,U+2010-2014,U+2018-201E,U+2022,U+2026,U+2039-203A,U+2212,U+25CC"
LA="U+0020-007E,U+00A0-00FF,U+0152-0153,U+2010-2014,U+2018-201E,U+2022,U+2026,U+2039-203A,U+20AC,U+2212"
pyftsubset MarkaziText[wght].ttf --unicodes="$AR" --layout-features='*' --flavor=woff2 --output-file=markazi-text-arabic.woff2
pyftsubset MarkaziText[wght].ttf --unicodes="$LA" --layout-features='*' --flavor=woff2 --output-file=markazi-text-latin.woff2
# Readex Pro the same, after fontTools.varLib.instancer pins HEXP=0 and wght=(300, 700).
```

An Arabic page fetches about 97 KB of fonts (Google Fonts sent 121 KB from two other origins, its stylesheet
holding the page's first paint).

**Source Serif 4** (SIL OFL 1.1, `OFL-SourceSerif4.txt`) sets French law (N15 of the read-and-trusted review, 27 Oct 2026:
Markazi's Latin read small and heavy at the law's size). From google/fonts `ofl/sourceserif4/SourceSerif4[opsz,wght].ttf`
(sha256 97b2d4da…ca0b), weight 400–600 at optical size 20, the Latin letters and the layout features French uses
(29 KB; with every feature 52 KB). Only a page that shows French law fetches it:

```bash
python -m fontTools.varLib.instancer 'SourceSerif4[opsz,wght].ttf' wght=400:600 opsz=20 -o ss4.ttf
pyftsubset ss4.ttf --unicodes="$LA" --layout-features='kern,liga,ccmp,locl,mark,mkmk' --flavor=woff2 \
  --output-file=source-serif-4-latin.woff2
```
