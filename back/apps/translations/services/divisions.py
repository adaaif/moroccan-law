"""A French article's tail that is the next part's heading («Section VI : Du licenciement pour motifs technologiques…»,
N15 of the read-and-trusted review): Adala's and the BO's French run a division's heading into the article before it,
where the Arabic reader puts it apart. Taken out where an article's French is served, and by `trim_french_divisions`."""
import re

HEAD = re.compile(r'^\s*(?:livre|titre|chapitre|section|sous-section|partie|paragraphe)\s+'
                  r'(?:[ivxlc]+|\d+|premier|première|unique|préliminaire)\b\s*(?:[:.\-–—].*)?$', re.I)
TITLE_MAX = 160


def trim(body: str) -> str:
    """The body without the division headings at its end (a heading's title on its own line goes with it)."""
    lines = body.rstrip().split('\n')
    while len(lines) > 1:
        last = lines[-1].strip()
        if HEAD.match(last):
            lines.pop()
        elif len(lines) > 2 and HEAD.match(lines[-2].strip()) and len(last) <= TITLE_MAX and not last.endswith(('.', ';', ',')):
            del lines[-2:]
        else:
            break
    return '\n'.join(lines).rstrip()
