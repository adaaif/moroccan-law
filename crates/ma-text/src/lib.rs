//! Arabic and French legal text, folded the same way when an article is indexed and when someone searches.
//!
//! - `fold`: one spelling for the letters people write several ways (أ إ آ ٱ → ا, ة → ه, ى → ي), no vowel
//!   marks or tatweel, Western digits, lower-case Latin without accents, a number's dots and slashes as
//!   dashes (65.99 → 65-99), everything else a single space.
//! - `stem`: a light stem (the article and the common prefixes and suffixes off), so «العقود» meets «عقود».
//! - `search_terms`: a query's words, folded, without the small words, stemmed.
//! - `layout_candidates`: Arabic typed while the keyboard was still in French (AZERTY) or English (QWERTY).

use unicode_normalization::char::decompose_compatible;

/// What one character of the input becomes.
#[derive(Clone, Copy, PartialEq)]
enum Class {
    Keep(char),
    Digit(char),
    /// A dot, dash or slash: kept (as a dash) only between two digits.
    NumberMark,
    Space,
    Drop,
}

fn classify(c: char) -> Class {
    match c {
        // Vowel marks, shadda, sukun, superscript alef, Quranic marks, tatweel, Latin accents.
        '\u{064B}'..='\u{065F}' | '\u{0670}' | '\u{06D6}'..='\u{06ED}' | '\u{0640}' | '\u{0300}'..='\u{036F}' => {
            Class::Drop
        }
        '\u{200B}'..='\u{200F}' | '\u{202A}'..='\u{202E}' | '\u{2066}'..='\u{2069}' | '\u{FEFF}' => Class::Drop,
        'ة' | 'ہ' | 'ۃ' => Class::Keep('ه'),
        'ى' | 'ی' | 'ې' | 'ۍ' => Class::Keep('ي'),
        'ٱ' | 'ٲ' | 'ٳ' => Class::Keep('ا'),
        'ک' | 'ڪ' | 'ڭ' | 'گ' => Class::Keep('ك'),
        'ڤ' | 'ڢ' => Class::Keep('ف'),
        'پ' => Class::Keep('ب'),
        '\u{0660}'..='\u{0669}' => Class::Digit(char::from(b'0' + (c as u32 - 0x0660) as u8)),
        '\u{06F0}'..='\u{06F9}' => Class::Digit(char::from(b'0' + (c as u32 - 0x06F0) as u8)),
        '0'..='9' => Class::Digit(c),
        '.' | '-' | '/' | '\u{2010}' | '\u{2011}' | '\u{2012}' | '\u{2013}' => Class::NumberMark,
        'ß' => Class::Keep('s'),
        _ if c.is_alphabetic() => match c.to_lowercase().next() {
            Some(lower) => Class::Keep(lower),
            None => Class::Keep(c),
        },
        _ => Class::Space,
    }
}

/// `s` folded, and for each char of the result the index (in chars) of the char of `s` it came from.
/// A run of spaces folds to one space, mapped to the first char of the run; no space leads or trails.
pub fn fold_map(s: &str) -> (String, Vec<usize>) {
    let mut classes: Vec<(Class, usize)> = Vec::with_capacity(s.len());
    for (i, c) in s.chars().enumerate() {
        decompose_compatible(c, |d| classes.push((classify(d), i)));
    }
    let mut out = String::with_capacity(s.len());
    let mut map = Vec::with_capacity(s.len());
    let mut space_at: Option<usize> = None;
    let mut last: Option<char> = None;
    let push = |out: &mut String, map: &mut Vec<usize>, space_at: &mut Option<usize>, c: char, at: usize| {
        if let Some(sp) = space_at.take() {
            if !out.is_empty() {
                out.push(' ');
                map.push(sp);
            }
        }
        out.push(c);
        map.push(at);
    };
    for (n, &(class, at)) in classes.iter().enumerate() {
        match class {
            Class::Drop => {}
            Class::Keep(c) | Class::Digit(c) => {
                push(&mut out, &mut map, &mut space_at, c, at);
                last = Some(c);
            }
            Class::NumberMark => {
                let after_digit = space_at.is_none() && last.is_some_and(|c| c.is_ascii_digit());
                let before_digit = classes[n + 1..]
                    .iter()
                    .find(|(k, _)| *k != Class::Drop)
                    .is_some_and(|(k, _)| matches!(k, Class::Digit(_)));
                if after_digit && before_digit {
                    push(&mut out, &mut map, &mut space_at, '-', at);
                    last = Some('-');
                } else if space_at.is_none() {
                    space_at = Some(at);
                }
            }
            Class::Space => {
                if space_at.is_none() {
                    space_at = Some(at);
                }
            }
        }
    }
    (out, map)
}

pub fn fold(s: &str) -> String {
    fold_map(s).0
}

pub fn tokens(s: &str) -> Vec<String> {
    fold(s).split(' ').filter(|w| !w.is_empty()).map(str::to_owned).collect()
}

fn is_arabic(w: &str) -> bool {
    w.chars().any(|c| ('\u{0621}'..='\u{064A}').contains(&c))
}

const PREFIXES: [&str; 6] = ["وال", "بال", "كال", "فال", "لل", "ال"];
const SUFFIXES: [&str; 8] = ["ها", "ان", "ات", "ون", "ين", "يه", "ه", "ي"];

/// A light stem of one folded word (the Light10 rules): «و» off a word of four letters or more, then one
/// definite-article prefix, then each common suffix once in turn, never leaving fewer than two letters.
/// Latin words and numbers come back as they are.
pub fn stem(word: &str) -> String {
    if !is_arabic(word) {
        return word.to_owned();
    }
    let mut w: Vec<char> = word.chars().collect();
    if w.len() >= 4 && w[0] == 'و' {
        w.remove(0);
    }
    for p in PREFIXES {
        let p: Vec<char> = p.chars().collect();
        if w.len() >= p.len() + 2 && w.starts_with(&p) {
            w.drain(..p.len());
            break;
        }
    }
    for s in SUFFIXES {
        let s: Vec<char> = s.chars().collect();
        if w.len() >= s.len() + 2 && w.ends_with(&s) {
            w.truncate(w.len() - s.len());
        }
    }
    w.into_iter().collect()
}

/// Folded small words a query can leave out: they match almost every article.
const STOPWORDS: &[&str] = &[
    "في", "من", "علي", "الي", "عن", "ان", "او", "ما", "لا", "هذا", "هذه", "ذلك", "تلك", "التي", "الذي", "الذين",
    "كل", "بعض", "غير", "ثم", "قد", "بين", "عند", "لدي", "مع", "كما", "اذا", "هو", "هي", "به", "بها", "له", "لها",
    "le", "la", "les", "de", "des", "du", "un", "une", "et", "en", "au", "aux", "pour", "par", "sur", "dans", "a", "l", "d",
];

pub fn is_stopword(folded: &str) -> bool {
    STOPWORDS.contains(&folded)
}

/// A query's words as the index holds them: folded, small words left out (unless nothing else is left),
/// stemmed, each once, in the order typed.
pub fn search_terms(query: &str) -> Vec<String> {
    let words = tokens(query);
    let kept: Vec<&String> = words.iter().filter(|w| !is_stopword(w)).collect();
    let words: Vec<&String> = if kept.is_empty() { words.iter().collect() } else { kept };
    let mut out: Vec<String> = Vec::new();
    for w in words {
        let s = stem(w);
        if !out.contains(&s) {
            out.push(s);
        }
    }
    out
}

/// The Arabic letter on each key, by the Latin character the same key types in French (AZERTY) and in
/// English (QWERTY). The Arabic layouts keep their letters on the same physical keys.
const AZERTY: &[(char, &str)] = &[
    ('a', "ض"), ('z', "ص"), ('e', "ث"), ('r', "ق"), ('t', "ف"), ('y', "غ"), ('u', "ع"), ('i', "ه"), ('o', "خ"),
    ('p', "ح"), ('^', "ج"), ('$', "د"), ('q', "ش"), ('s', "س"), ('d', "ي"), ('f', "ب"), ('g', "ل"), ('h', "ا"),
    ('j', "ت"), ('k', "ن"), ('l', "م"), ('m', "ك"), ('ù', "ط"), ('w', "ئ"), ('x', "ء"), ('c', "ؤ"), ('v', "ر"),
    ('b', "لا"), ('n', "ى"), (',', "ة"), (';', "و"), (':', "ز"), ('!', "ظ"),
];
const QWERTY: &[(char, &str)] = &[
    ('q', "ض"), ('w', "ص"), ('e', "ث"), ('r', "ق"), ('t', "ف"), ('y', "غ"), ('u', "ع"), ('i', "ه"), ('o', "خ"),
    ('p', "ح"), ('[', "ج"), (']', "د"), ('a', "ش"), ('s', "س"), ('d', "ي"), ('f', "ب"), ('g', "ل"), ('h', "ا"),
    ('j', "ت"), ('k', "ن"), ('l', "م"), (';', "ك"), ('\'', "ط"), ('z', "ئ"), ('x', "ء"), ('c', "ؤ"), ('v', "ر"),
    ('b', "لا"), ('n', "ى"), ('m', "ة"), (',', "و"), ('.', "ز"), ('/', "ظ"), ('`', "ذ"),
];

fn retype(s: &str, layout: &[(char, &str)]) -> String {
    let mut out = String::new();
    for c in s.chars() {
        let lower = c.to_lowercase().next().unwrap_or(c);
        match layout.iter().find(|(k, _)| *k == lower) {
            Some((_, arabic)) => out.push_str(arabic),
            None => out.push(c),
        }
    }
    out
}

/// What a query in Latin letters would have been had the keyboard been in Arabic: («azerty», …) then
/// («qwerty», …), each once, only when it gives at least two Arabic letters. «hgtzg 53» → «الفصل 53».
/// Whether to use one is the search's call (it tries them when the query as typed finds little).
pub fn layout_candidates(query: &str) -> Vec<(&'static str, String)> {
    let latin = query.chars().filter(|c| c.is_ascii_alphabetic()).count();
    if latin < 2 || is_arabic(query) {
        return Vec::new();
    }
    let mut out: Vec<(&'static str, String)> = Vec::new();
    for (name, layout) in [("azerty", AZERTY), ("qwerty", QWERTY)] {
        let typed = retype(query, layout);
        let letters = typed.chars().filter(|c| ('\u{0621}'..='\u{064A}').contains(c)).count();
        if letters >= 2 && !out.iter().any(|(_, t)| *t == typed) {
            out.push((name, typed));
        }
    }
    out
}

/// Moroccan Darija typed in Latin letters (B6 of the search plan): a digit for an Arabic letter inside a word
/// («9anoun», «ch7al», «3la»), or its common words. A French or English query is not this.
pub fn is_arabizi(query: &str) -> bool {
    if is_arabic(query) {
        return false;
    }
    const WORDS: [&str; 24] = ["wach", "wash", "chno", "chnou", "chnu", "kifach", "kifash", "bghit", "dyal", "dial",
        "khas", "khassni", "machi", "bzaf", "daba", "kayn", "kayna", "mol", "lmol", "ila", "3la", "f", "fl", "dak"];
    let words: Vec<String> = query.split_whitespace().map(|w| w.trim_matches(|c: char| !c.is_alphanumeric()).to_lowercase()).collect();
    let digit_inside = words.iter().any(|w| {
        let cs: Vec<char> = w.chars().collect();
        // Read once a word, not once a digit: a word of digits alone was read again at each of them.
        let letters = cs.iter().any(|x| x.is_ascii_alphabetic());
        cs.iter().enumerate().any(|(i, c)| matches!(c, '2' | '3' | '5' | '7' | '8' | '9')
            && letters && (i > 0 || cs.len() > 1))
    });
    let darija_words = words.iter().filter(|w| WORDS.contains(&w.as_str())).count();
    digit_inside || darija_words >= 2
}

/// The ways a word of Arabizi may be written in Arabic letters, likeliest first, at most `limit`: digits for their
/// letters (3 ع, 7 ح, 9 ق, 2 ء, 5 خ, 8 غ), «ch» ش, «kh» خ, «gh» غ, «ou» و; a vowel kept long or left out; t, s, d,
/// h, k each as their two Arabic letters. Which one is right is the corpus's call (the server keeps the spelling the
/// law uses most).
pub fn arabizi_spellings(word: &str, limit: usize) -> Vec<String> {
    let slots = arabizi_slots(word);
    // The likeliest first: fewer second choices, earlier ones changed last. A pick waits in line, and each pick taken
    // from the front puts behind it the picks one more second choice away, in slot order: the line stays in order of
    // second choices without sorting. At most 4 × limit picks wait; a pick is made only when it will wait, so a long
    // word costs its length at each step, not its length once for each of its letters.
    let wait = 4 * limit;
    let mut out: Vec<String> = Vec::new();
    let mut line: std::collections::VecDeque<Vec<usize>> = std::collections::VecDeque::from([vec![0; slots.len()]]);
    let mut seen = std::collections::HashSet::new();
    while let Some(pick) = line.pop_front() {
        let spelled: String = pick.iter().zip(&slots).map(|(p, s)| s[*p]).collect();
        if !spelled.is_empty() && seen.insert(spelled.clone()) {
            out.push(spelled);
            if out.len() >= limit {
                break;
            }
        }
        for (k, s) in slots.iter().enumerate() {
            if line.len() >= wait {
                break;
            }
            if pick[k] + 1 < s.len() {
                let mut next = pick.clone();
                next[k] += 1;
                line.push_back(next);
            }
        }
    }
    out
}

/// Each position of a word of Arabizi: its Arabic choices, the first the likeliest.
fn arabizi_slots(word: &str) -> Vec<Vec<&'static str>> {
    let w: Vec<char> = word.to_lowercase().chars().collect();
    let mut slots: Vec<Vec<&'static str>> = Vec::new();
    let mut i = 0;
    while i < w.len() {
        let two: String = w[i..(i + 2).min(w.len())].iter().collect();
        let (choices, step): (Vec<&'static str>, usize) = match two.as_str() {
            "ch" | "sh" => (vec!["ش"], 2),
            "kh" => (vec!["خ"], 2),
            "gh" => (vec!["غ"], 2),
            "ou" | "oo" => (vec!["و"], 2),
            "th" => (vec!["ث", "ت"], 2),
            "dh" => (vec!["ذ", "ض"], 2),
            _ => match w[i] {
                '2' => (vec!["ء", "ا"], 1),
                '3' => (vec!["ع"], 1),
                '5' => (vec!["خ"], 1),
                '6' => (vec!["ط"], 1),
                '7' => (vec!["ح"], 1),
                '8' => (vec!["غ"], 1),
                '9' => (vec!["ق"], 1),
                'a' => (if i == 0 { vec!["ا"] } else { vec!["ا", ""] }, 1),
                'e' => (if i == 0 { vec!["ا"] } else { vec!["", "ي"] }, 1),
                'i' => (if i == 0 { vec!["ا", "ي"] } else { vec!["ي", ""] }, 1),
                'o' | 'u' => (if i == 0 { vec!["ا", "و"] } else { vec!["و", ""] }, 1),
                'y' => (vec!["ي"], 1),
                'w' => (vec!["و"], 1),
                'b' | 'p' => (vec!["ب"], 1),
                't' => (vec!["ت", "ط"], 1),
                'd' => (vec!["د", "ض"], 1),
                's' => (vec!["س", "ص"], 1),
                'z' => (vec!["ز"], 1),
                'r' => (vec!["ر"], 1),
                'l' => (vec!["ل"], 1),
                'm' => (vec!["م"], 1),
                'n' => (vec!["ن"], 1),
                'f' | 'v' => (vec!["ف"], 1),
                'k' => (vec!["ك", "ق"], 1),
                'q' => (vec!["ق"], 1),
                'g' => (vec!["ك", "ج"], 1),
                'j' => (vec!["ج"], 1),
                'h' => (vec!["ه", "ح"], 1),
                'x' => (vec!["كس"], 1),
                'c' => (vec!["س", "ك"], 1),
                c if c.is_ascii_digit() => (vec![""], 1),
                _ => (vec![""], 1),
            },
        };
        // A letter written twice is one (a doubled consonant has no letter of its own in Arabic script).
        let same = slots.last().is_some_and(|last| last.len() == 1 && choices.len() == 1 && last[0] == choices[0]
            && !matches!(choices[0], "ا" | "و" | "ي"));
        if !same {
            slots.push(choices);
        }
        i += step;
    }
    slots
}

/// Where `needle` occurs in `haystack`, both folded, as whole words: char spans (start, end exclusive) in
/// `haystack` as given. Whole words only: «الإدارة» matches «الادارة» but not «للإدارة», where a preposition
/// is attached.
pub fn find_folded(haystack: &str, needle: &str) -> Vec<(usize, usize)> {
    let needle = fold(needle);
    if needle.is_empty() {
        return Vec::new();
    }
    let (folded, map) = fold_map(haystack);
    let width = needle.chars().count();
    let mut out = Vec::new();
    // `from` in bytes and `chars`, the chars before it: counted as the search goes, each char once, so a text with many
    // matches costs its length, not its length again at every match.
    let (mut from, mut chars) = (0, 0);
    while let Some(i) = folded[from..].find(&needle) {
        let start = from + i;
        let a = chars + folded[from..start].chars().count();
        let end = start + needle.len();
        let before_ok = folded[..start].chars().next_back().is_none_or(|c| c == ' ');
        let after_ok = folded[end..].chars().next().is_none_or(|c| c == ' ');
        if before_ok && after_ok {
            out.push((map[a], map[a + width - 1] + 1));
        }
        from = start + folded[start..].chars().next().map_or(1, char::len_utf8);
        chars = a + 1;
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    fn vectors(name: &str) -> Vec<serde_json::Value> {
        let path = format!("{}/../vectors/{name}.json", env!("CARGO_MANIFEST_DIR"));
        serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap()
    }

    #[test]
    fn fold_vectors() {
        for v in vectors("fold") {
            assert_eq!(fold(v["in"].as_str().unwrap()), v["out"].as_str().unwrap(), "{v}");
        }
    }

    #[test]
    fn stem_vectors() {
        for v in vectors("stem") {
            assert_eq!(stem(&fold(v["in"].as_str().unwrap())), v["out"].as_str().unwrap(), "{v}");
        }
    }

    #[test]
    fn search_terms_vectors() {
        for v in vectors("terms") {
            let want: Vec<String> = v["out"].as_array().unwrap().iter().map(|x| x.as_str().unwrap().to_owned()).collect();
            assert_eq!(search_terms(v["in"].as_str().unwrap()), want, "{v}");
        }
    }

    #[test]
    fn arabizi_vectors() {
        for v in vectors("arabizi") {
            if let Some(word) = v["word"].as_str() {
                let got = arabizi_spellings(word, 48);
                assert!(got.iter().any(|s| s == v["has"].as_str().unwrap()), "{word}: {got:?}");
            } else {
                assert_eq!(is_arabizi(v["query"].as_str().unwrap()), v["arabizi"].as_bool().unwrap(), "{}", v["query"]);
            }
        }
    }

    /// The spellings as the first version of `arabizi_spellings` made them (every pick made, then sorted and cut):
    /// the line must answer the same for every word and every limit.
    fn spellings_as_first_made(word: &str, limit: usize) -> Vec<String> {
        let slots = arabizi_slots(word);
        let mut out: Vec<String> = Vec::new();
        let mut frontier: Vec<(usize, Vec<usize>)> = vec![(0, vec![0; slots.len()])];
        let mut seen = std::collections::HashSet::new();
        while let Some((cost, pick)) = frontier.first().cloned() {
            frontier.remove(0);
            let spelled: String = pick.iter().zip(&slots).map(|(p, s)| s[*p]).collect();
            if !spelled.is_empty() && seen.insert(spelled.clone()) {
                out.push(spelled);
                if out.len() >= limit {
                    break;
                }
            }
            for (k, s) in slots.iter().enumerate() {
                if pick[k] + 1 < s.len() {
                    let mut next = pick.clone();
                    next[k] += 1;
                    frontier.push((cost + 1, next));
                }
            }
            frontier.sort_by_key(|(c, _)| *c);
            if frontier.len() > 4 * limit {
                frontier.truncate(4 * limit);
            }
        }
        out
    }

    /// A fixed sequence of numbers (xorshift): the same words at every run, no crate needed.
    fn numbers(mut x: u64) -> impl Iterator<Item = usize> {
        std::iter::repeat_with(move || {
            x ^= x << 13;
            x ^= x >> 7;
            x ^= x << 17;
            x as usize
        })
    }

    #[test]
    fn spellings_answer_as_first_made() {
        // Random words; every short word of a few letters; and a letter many times then another, where the line's
        // length decides which picks are read (13 «a» then «t»: the «ط» pick is read only if it waits).
        let letters: Vec<char> = "abcdefghijklmnopqrstuvwxyz0123456789ABCHKT-'é ".chars().collect();
        let mut n = numbers(0x9e3779b97f4a7c15);
        let mut words: Vec<String> = (0..300)
            .map(|_| {
                let len = n.next().unwrap() % 33;
                (0..len).map(|_| letters[n.next().unwrap() % letters.len()]).collect()
            })
            .collect();
        let few: Vec<char> = "aeitkh-2".chars().collect();
        let mut short = vec![String::new()];
        for _ in 0..4 {
            short = short.iter().flat_map(|w| few.iter().map(move |c| format!("{w}{c}"))).collect();
            words.extend(short.iter().cloned());
        }
        for unit in ["a", "e", "i", "o", "t", "ou", "ae", "th", "3a", "?"] {
            for times in 0..=13 / unit.len() {
                for tail in ["", "t", "e", "?"] {
                    words.push(format!("{}{tail}", unit.repeat(times)));
                    words.push(format!("{tail}{}", unit.repeat(times)));
                }
            }
        }
        for word in &words {
            for limit in [0, 1, 2, 3, 4, 5, 7, 12, 48] {
                assert_eq!(arabizi_spellings(word, limit), spellings_as_first_made(word, limit), "{word:?} {limit}");
            }
        }
        for unit in ["a", "3a", "chi", "2e", "kh"] {
            let word = unit.repeat(50 / unit.len());
            assert_eq!(arabizi_spellings(&word, 48), spellings_as_first_made(&word, 48), "{word:?}");
        }
    }

    #[test]
    fn a_long_word_is_spelled_at_once() {
        // 2,000 letters took minutes (a copy of every pick for every letter at every step).
        let word = format!("3{}", "a".repeat(1999));
        let started = std::time::Instant::now();
        let got = arabizi_spellings(&word, 48);
        assert!(started.elapsed().as_secs() < 20, "{:?}", started.elapsed());
        assert_eq!(got.len(), 48);
        assert_eq!(got[0], format!("ع{}", "ا".repeat(1999)));
        assert_eq!(got[47], format!("ع{}", "ا".repeat(1952)));
    }

    /// Where the first version of `find_folded` found a needle (each match's place counted from the start of the text).
    fn found_as_first_made(haystack: &str, needle: &str) -> Vec<(usize, usize)> {
        let needle = fold(needle);
        if needle.is_empty() {
            return Vec::new();
        }
        let (folded, map) = fold_map(haystack);
        let mut out = Vec::new();
        let mut from = 0;
        while let Some(i) = folded[from..].find(&needle) {
            let start = from + i;
            let end = start + needle.len();
            let before_ok = folded[..start].chars().next_back().is_none_or(|c| c == ' ');
            let after_ok = folded[end..].chars().next().is_none_or(|c| c == ' ');
            if before_ok && after_ok {
                let a = folded[..start].chars().count();
                let b = folded[..end].chars().count();
                out.push((map[a], map[b - 1] + 1));
            }
            from = start + folded[start..].chars().next().map_or(1, char::len_utf8);
        }
        out
    }

    #[test]
    fn finds_as_first_made() {
        let pieces = ["الإدارة", "الادارة", "للإدارة", "ة", "ه", "0", "٠", "5.2", "a", "é", "E", " ", "  ", "،", "ـ", "َ", "ﷲ",
                      "-", "/", "aa", "اا"];
        let needles = ["الإدارة", "ه", "0", "a", "aa", "اا", "5.2", "5", "é", "ﷲ", "الله", "", " "];
        let mut n = numbers(0x2545f4914f6cdd1d);
        for _ in 0..400 {
            let len = n.next().unwrap() % 30;
            let text: String = (0..len).map(|_| pieces[n.next().unwrap() % pieces.len()]).collect();
            for needle in needles {
                assert_eq!(find_folded(&text, needle), found_as_first_made(&text, needle), "{text:?} {needle:?}");
            }
        }
    }

    #[test]
    fn a_long_text_with_many_matches_is_read_once() {
        // A megabyte with a match every few letters took seconds (each match counted from the start of the text).
        let text = "المادة 0 من الفصل ".repeat(30_000);
        let started = std::time::Instant::now();
        let spans = find_folded(&text, "0");
        assert!(started.elapsed().as_secs() < 20, "{:?}", started.elapsed());
        assert_eq!(spans.len(), 30_000);
        let chars: Vec<char> = text.chars().collect();
        assert!(spans.iter().all(|&(a, b)| chars[a..b] == ['0']));
    }

    #[test]
    fn layout_vectors() {
        for v in vectors("layout") {
            let got: Vec<String> = layout_candidates(v["in"].as_str().unwrap()).into_iter().map(|(_, t)| t).collect();
            let want: Vec<String> = v["out"].as_array().unwrap().iter().map(|x| x.as_str().unwrap().to_owned()).collect();
            assert_eq!(got, want, "{v}");
        }
    }

    #[test]
    fn finds_whole_folded_words() {
        let s = "تعتبر الإدارة مسؤولة، وللإدارة أن تطلب من الادارة";
        let chars: Vec<char> = s.chars().collect();
        let spans = find_folded(s, "الإدارة");
        let words: Vec<String> = spans.iter().map(|&(a, b)| chars[a..b].iter().collect()).collect();
        assert_eq!(words, vec!["الإدارة", "الادارة"]);
    }

    #[test]
    fn map_points_back_to_the_source() {
        let s = "الْمَادَّة  5.2";
        let (folded, map) = fold_map(s);
        assert_eq!(folded, "الماده 5-2");
        let chars: Vec<char> = s.chars().collect();
        assert_eq!(chars[map[0]], 'ا');
        assert_eq!(chars[*map.last().unwrap()], '2');
        assert_eq!(folded.chars().count(), map.len());
    }
}
