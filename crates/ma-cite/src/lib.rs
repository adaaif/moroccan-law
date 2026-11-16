//! Moroccan legal citations, read from running text (a contract, a judgment) or from a search query.
//!
//! The text is folded first (`ma_text::fold_map`), so «الفصل ٤١٨ من ق.ل.ع» and «الفصل 418 من ق ل ع» read
//! alike; every citation then points back to the exact words it was read from (`start`, `end`, `raw`).
//!
//! Forms read:
//! - an article: «الفصل 418 من ق.ل.ع», «م 53 م.أ», «المادة الأولى من القانون رقم 31.13», «المواد 5 و6 و7»,
//!   the dual «المادتين 41 و 51», «الفصلين 230 و231», «article 6 de la loi n° 31-13», «art. 1er du DOC»;
//! - a text: «ظهير شريف رقم 1.58.250», «المرسوم رقم 2.22.729», «loi n° 70-03», a code by its name;
//! - a BO issue: «الجريدة الرسمية عدد 7533», «ج.ر 7533», «BO n° 7533»;
//! - (B5 of the search plan) a range of articles: «المواد من 5 إلى 9», «articles 5 à 9»; an article by its ordinal
//!   word past ten: «الفصل الحادي عشر», «المادة الحادية والعشرون»; a text by its date: «ظهير 12 غشت 1913»,
//!   «dahir du 12 août 1913».
//!
//! In a query (`parse_query`) a few looser forms count too: a code and a number («مدونة الأسرة 53»,
//! «ق.ل.ع 230») and a text number alone («1.58.250», «31.13»).

use regex::Regex;
use std::sync::OnceLock;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Kind {
    Article,
    Text,
    Issue,
}

impl Kind {
    pub fn as_str(self) -> &'static str {
        match self {
            Kind::Article => "article",
            Kind::Text => "text",
            Kind::Issue => "issue",
        }
    }
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Citation {
    pub kind: Kind,
    /// Char offsets in the text given, `end` exclusive.
    pub start: usize,
    pub end: usize,
    /// The words as written.
    pub raw: String,
    /// «418», «5-bis», «1»: the article, when one is named.
    pub article: Option<String>,
    /// law, organic_law, dahir, decree_law, decree, order, decision.
    pub text_kind: Option<&'static str>,
    /// «31-13», «1-58-250»: the text's number, dashed.
    pub text_number: Option<String>,
    /// doc, family, penal, civil_procedure, criminal_procedure, labour, tax, commerce, road, constitution.
    pub code: Option<&'static str>,
    pub issue: Option<u32>,
    /// «bis» for an issue printed «7465 مكرر» / «7465 bis».
    pub issue_suffix: Option<&'static str>,
    /// «1913-08-12»: a text named by the day it was signed («ظهير 12 غشت 1913»), when it has no number.
    pub date: Option<String>,
}

// ── vocabulary (folded spellings) ────────────────────────────────────────────

const NUM: &str = r"[0-9]+(?:-[0-9]+)*";
const ORD_AR: &str = "الاولي|الاول|الثانيه|الثاني|الثالثه|الثالث|الرابعه|الرابع|الخامسه|الخامس|السادسه|السادس|السابعه|السابع|الثامنه|الثامن|التاسعه|التاسع|العاشره|العاشر";
const ORDINALS: [(&str, u32); 20] = [
    ("الاولي", 1), ("الاول", 1), ("الثانيه", 2), ("الثاني", 2), ("الثالثه", 3), ("الثالث", 3), ("الرابعه", 4),
    ("الرابع", 4), ("الخامسه", 5), ("الخامس", 5), ("السادسه", 6), ("السادس", 6), ("السابعه", 7), ("السابع", 7),
    ("الثامنه", 8), ("الثامن", 8), ("التاسعه", 9), ("التاسع", 9), ("العاشره", 10), ("العاشر", 10),
];

/// The units of an ordinal past ten («الحادي عشر», «الثانية والعشرون»), folded.
const UNITS: [(&str, u32); 18] = [
    ("الحاديه", 1), ("الحادي", 1), ("الثانيه", 2), ("الثاني", 2), ("الثالثه", 3), ("الثالث", 3), ("الرابعه", 4),
    ("الرابع", 4), ("الخامسه", 5), ("الخامس", 5), ("السادسه", 6), ("السادس", 6), ("السابعه", 7), ("السابع", 7),
    ("الثامنه", 8), ("الثامن", 8), ("التاسعه", 9), ("التاسع", 9),
];
/// The tens, as written and as often typed.
const TENS: [(&str, u32); 16] = [
    ("العشرون", 20), ("العشرين", 20), ("الثلاثون", 30), ("الثلاثين", 30), ("الاربعون", 40), ("الاربعين", 40),
    ("الخمسون", 50), ("الخمسين", 50), ("الستون", 60), ("الستين", 60), ("السبعون", 70), ("السبعين", 70),
    ("الثمانون", 80), ("الثمانين", 80), ("التسعون", 90), ("التسعين", 90),
];
/// Months by their Moroccan, Middle-Eastern and French names, folded.
const MONTHS: [(&str, u32); 36] = [
    ("يناير", 1), ("ينير", 1), ("فبراير", 2), ("يبراير", 2), ("مارس", 3), ("ابريل", 4), ("ماي", 5), ("مايو", 5),
    ("مايه", 5), ("يونيو", 6), ("يونيه", 6), ("يوليوز", 7), ("يوليه", 7),
    ("يوليو", 7), ("غشت", 8), ("اغسطس", 8), ("شتنبر", 9), ("سبتمبر", 9), ("اكتوبر", 10), ("نونبر", 11),
    ("نوفمبر", 11), ("دجنبر", 12), ("ديسمبر", 12), ("janvier", 1), ("fevrier", 2), ("mars", 3), ("avril", 4),
    ("mai", 5), ("juin", 6), ("juillet", 7), ("aout", 8), ("septembre", 9), ("octobre", 10), ("novembre", 11),
    ("decembre", 12), ("decmbre", 12),
];

/// An ordinal word of any rank up to 99, longest forms first so «الحادي عشر» is not read as «الحادي».
fn ordinals_group() -> String {
    let units = UNITS.iter().map(|(w, _)| *w).collect::<Vec<_>>().join("|");
    let tens = TENS.iter().map(|(w, _)| *w).collect::<Vec<_>>().join("|");
    format!("(?:(?:{units}) (?:عشره|عشر)|(?:{units}|الاول|الاولي) و(?:{tens})|{tens}|{ORD_AR})")
}

/// «الحادي عشر» → 11, «الثانية والعشرون» → 22, «الخمسون» → 50, «الاولي» → 1; a «مكرر» after it is left out.
fn ordinal(token: &str) -> Option<u32> {
    let words: Vec<&str> = token.split(' ').filter(|w| !matches!(*w, "مكرر" | "مكرره" | "مرتين")).collect();
    let unit = |w: &str| UNITS.iter().chain(ORDINALS.iter()).find(|(u, _)| *u == w).map(|(_, n)| *n);
    let ten = |w: &str| TENS.iter().find(|(t, _)| *t == w).map(|(_, n)| *n);
    match words.as_slice() {
        [u, teen] if *teen == "عشر" || *teen == "عشره" => unit(u).filter(|n| *n < 10).map(|n| n + 10),
        [u, tens] => Some(unit(u)? + ten(tens.strip_prefix('و')?)?),
        [one] => ten(one).or_else(|| ORDINALS.iter().find(|(w, _)| w == one).map(|(_, n)| *n)),
        _ => None,
    }
}

/// Text kinds; a kind that contains another («القانون التنظيمي» / «القانون») comes first.
const TEXT_KINDS: [(&str, &[&str]); 7] = [
    ("organic_law", &["القانون التنظيمي", "قانون تنظيمي", "loi organique"]),
    ("decree_law", &["المرسوم بقانون", "مرسوم بقانون", "decret loi"]),
    ("law", &["القانون", "قانون", "loi"]),
    ("dahir", &["الظهير الشريف", "ظهير شريف", "الظهير", "ظهير", "dahir"]),
    ("decree", &["المرسوم", "مرسوم", "decret"]),
    ("order", &["القرار المشترك", "قرار مشترك", "القرار", "قرار", "arrete conjoint", "arrete"]),
    ("decision", &["المقرر", "مقرر", "decision"]),
];

/// Codes by name, then their short forms (letters with dots), which count only next to an article or in a
/// query: alone, «م ت» or «ق ج» are too likely to be something else.
const CODES: [(&str, &[&str], &[&str]); 10] = [
    ("doc", &["قانون الالتزامات والعقود", "ظهير الالتزامات والعقود", "الالتزامات والعقود",
              "dahir des obligations et des contrats", "dahir des obligations et contrats"], &["ق ل ع", "doc"]),
    ("family", &["مدونه الاسره", "code de la famille", "moudawana", "mudawana"], &["م ا ش", "م ا"]),
    // «جنائي» alone, «C.P.» and «CP» name the penal code next to an article only («الفصل 490 جنائي», «art. 490 C.P.»:
    // the famous-articles review, 9 Nov 2026).
    ("penal", &["مجموعه القانون الجنائي", "القانون الجنائي", "code penal"], &["ق ج", "c pen", "c p", "cp", "جنائي", "الجنائي"]),
    ("civil_procedure", &["قانون المسطره المدنيه", "المسطره المدنيه", "code de procedure civile"], &["ق م م", "cpc"]),
    ("criminal_procedure", &["قانون المسطره الجنائيه", "المسطره الجنائيه", "code de procedure penale"],
     &["ق م ج", "cpp"]),
    ("labour", &["مدونه الشغل", "code du travail"], &["م ش"]),
    ("tax", &["المدونه العامه للضرايب", "code general des impots"], &["م ع ض", "cgi"]),
    ("commerce", &["مدونه التجاره", "code de commerce"], &["م ت"]),
    ("road", &["مدونه السير علي الطرق", "مدونه السير", "code de la route"], &[]),
    ("constitution", &["الدستور", "constitution"], &[]),
];

/// An Arabic name as it may be written with a preposition or «و» stuck to its first word: «بالجريدة»,
/// «للفصل», «لمدونة», «وبالقانون». Latin names come back as they are.
fn clitic(name: &str) -> String {
    if !name.chars().next().is_some_and(|c| ('\u{0621}'..='\u{064A}').contains(&c)) {
        return name.to_owned();
    }
    match name.strip_prefix("ال") {
        Some(rest) => format!("(?:و?(?:[بفك]?ال|لل)){rest}"),
        None => format!("(?:و?[بفكل]?){name}"),
    }
}

/// A name as the text it is matched against is written: folded (`ma_text::fold`). The table above is written by
/// hand, and «القانون الجنائي» folds to «القانون الجنايي» (a hamza on its seat becomes its seat): written unfolded, the
/// penal code and the criminal procedure were never read by their names, only by «ق ج» (9 Nov 2026).
fn folded(name: &str) -> String {
    ma_text::fold(name)
}

/// One named group per kind (`k_law`…), so a match says which kind it read.
fn kinds_group() -> String {
    let groups: Vec<String> = TEXT_KINDS
        .iter()
        .map(|(key, names)| format!("(?P<k_{key}>{})", names.iter().map(|n| clitic(&folded(n))).collect::<Vec<_>>().join("|")))
        .collect();
    format!("(?:{})", groups.join("|"))
}

/// One named group per code (`c_doc`…).
fn codes_group(short: bool) -> String {
    let groups: Vec<String> = CODES
        .iter()
        .map(|(key, long, abbr)| {
            let mut names: Vec<String> = long.iter().map(|n| clitic(&folded(n))).collect();
            if short {
                names.extend(abbr.iter().map(|a| folded(a)));
            }
            format!("(?P<c_{key}>{})", names.join("|"))
        })
        .collect();
    format!("(?:{})", groups.join("|"))
}

/// A text's date after its kind, the groups named `{p}day`, `{p}month`, `{p}year`. Before 1956 (H9 of
/// the Bulletin-from-No.-1 review) the Hijri day comes first and the Gregorian after «الموافق», the year after «سنة»: «الظهير الشريف
/// الصادر في 9 رمضان 1331 (12 غشت 1913)», «القرار الوزيري المؤرخ في 3 ذي القعدة عام 1344 الموافق 15 مايو سنة
/// 1926», «ظهيرنا الشريف الصادر يوم فاتح ربيع الاول …».
fn dated_tail(p: &str) -> String {
    let months = MONTHS.iter().map(|(m, _)| *m).collect::<Vec<_>>().join("|");
    format!(
        r"(?:نا)?(?: (?:الشريف|الوزيري|المقيمي))?(?: (?:الصادر|الصادره|المؤرخ|المؤرخه|المورخ|المورخه))?(?: (?:في|بتاريخ|يوم|du|en date du))?(?: (?:فاتح|[0-9]{{1,2}})(?: من)? [^ 0-9]{{2,8}}(?: [^ 0-9]{{2,8}})?(?: عام)? 1[34][0-9]{{2}}(?: (?:الموافق|موافق)(?: ل)?)?)? (?P<{p}day>فاتح|[0-9]{{1,2}}) (?P<{p}month>{months}) (?:(?:سنه|عام) )?(?P<{p}year>[0-9]{{4}})"
    )
}

/// The day a text was signed, from `dated_tail`'s groups, when it is a day.
fn date_from(c: &regex::Captures, p: &str) -> Option<String> {
    let day_text = c.name(&format!("{p}day"))?.as_str();
    let month_name = c.name(&format!("{p}month"))?.as_str();
    let month = MONTHS.iter().find(|(name, _)| *name == month_name).map(|(_, n)| *n).unwrap_or(0);
    let day: u32 = if day_text == "فاتح" { 1 } else { day_text.parse().unwrap_or(0) };
    let year: u32 = c.name(&format!("{p}year"))?.as_str().parse().unwrap_or(0);
    if !(1..=31).contains(&day) || !(1900..=2100).contains(&year) || month == 0 {
        return None;
    }
    Some(format!("{year:04}-{month:02}-{day:02}"))
}

fn kind_from(c: &regex::Captures) -> Option<&'static str> {
    TEXT_KINDS.iter().find(|(key, _)| c.name(&format!("k_{key}")).is_some()).map(|(key, _)| *key)
}

fn code_from(c: &regex::Captures) -> Option<&'static str> {
    CODES.iter().find(|(key, _, _)| c.name(&format!("c_{key}")).is_some()).map(|(key, _, _)| *key)
}

struct Patterns {
    article: Regex,
    range: Regex,
    dated: Regex,
    text: Regex,
    code: Regex,
    issue: Regex,
    query_code_number: Regex,
    query_number_code: Regex,
    query_number: Regex,
    one_number: Regex,
}

const NO: &str = "(?: (?:رقم|عدد|n|no|numero))?";

fn patterns() -> &'static Patterns {
    static P: OnceLock<Patterns> = OnceLock::new();
    P.get_or_init(|| {
        let art_num = format!(
            r"(?:{NUM}(?:er|e)?(?: (?:مكرره|مكرر)(?: مرتين)?| bis| ter| quater)?|{}(?: (?:مكرره|مكرر))?|premiere|premier)",
            ordinals_group()
        );
        // A list is joined by «و» / «et»; a comma folds to a space, so «5، 6 و7» is numbers by spaces closed by
        // «و». Numbers by spaces alone are not a list («الفصل 13.- 1» is article 13 and its paragraph I).
        let art_list = format!(r"{art_num}(?:(?: {art_num})*(?: و ?| et ){art_num})*");
        // The dual names two articles, as a list does: «المادتين 41 و 51 أعلاه», «بالفصلين 230 و231 من ق.ل.ع»
        // (nominative «المادتان», «الفصلان»); its two numbers are read by `art_list` like a plural's.
        let words = ["الفصول", "الفصلين", "الفصلان", "الفصل", "المواد", "المادتين", "المادتان", "الماده"]
            .iter()
            .map(|w| clitic(w))
            .collect::<Vec<_>>()
            .join("|");
        let target = format!(r"(?:{}|{}(?:{}|{NO} (?P<tnum>{NUM})))", codes_group(true), kinds_group(), dated_tail("t"));
        // «من», «في», the Darija «ديال» / «د», the French «du» and its kin.
        let link = r"(?: (?:من|في|ديال|د|de la|de l|du|des|de))?";
        Patterns {
            article: Regex::new(&format!(
                r"(?P<word>{words}|فصل|ماده|articles|article|art|ف|م) (?P<nums>{art_list})(?:{link} (?P<target>{target}))?"
            ))
            .unwrap(),
            range: Regex::new(&format!(
                r"(?P<word>{words}|articles|art) (?:من )?(?P<a>[0-9]{{1,4}}) (?:الي|حتي|a|au) (?P<b>[0-9]{{1,4}})(?:{link} (?P<target>{target}))?"
            ))
            .unwrap(),
            dated: Regex::new(&format!(r"{}{}", kinds_group(), dated_tail(""))).unwrap(),
            text: Regex::new(&format!(r"{}{NO} (?P<num>{NUM})", kinds_group())).unwrap(),
            code: Regex::new(&codes_group(false)).unwrap(),
            issue: Regex::new(&format!(
                r"(?:{} الرسميه|ج ر|bulletin officiel|b o|bo){NO} (?P<issue>[0-9]{{3,5}})(?P<bis> مكرر| bis)?",
                clitic("الجريده")
            ))
            .unwrap(),
            query_code_number: Regex::new(&format!(r"^{} (?P<num>{NUM})$", codes_group(true))).unwrap(),
            // A number then its code, no article word: «490 من القانون الجنائي», «490 جنائي», «490 code pénal».
            query_number_code: Regex::new(&format!(r"^(?P<num>{art_num}){link} {}$", codes_group(true))).unwrap(),
            query_number: Regex::new(&format!(r"^(?P<num>{NUM})$")).unwrap(),
            one_number: Regex::new(&art_num).unwrap(),
        }
    })
}

// ── reading ──────────────────────────────────────────────────────────────────

/// «418» → 418, «5 مكرر» → 5-bis, «5 مكرر مرتين» → 5-ter, «الاولي» → 1, «1er» → 1.
fn article_number(token: &str) -> String {
    let t = token.trim();
    let suffix = if t.contains("مرتين") || t.ends_with(" ter") {
        "-ter"
    } else if t.contains("مكرر") || t.ends_with(" bis") {
        "-bis"
    } else if t.ends_with(" quater") {
        "-quater"
    } else {
        ""
    };
    let head = t.split(' ').next().unwrap_or("");
    let digits: String = head.trim_end_matches("er").trim_end_matches('e').to_owned();
    if digits.chars().next().is_some_and(|c| c.is_ascii_digit()) {
        return format!("{digits}{suffix}");
    }
    if head == "premier" || head == "premiere" {
        return "1".into();
    }
    match ordinal(t) {
        Some(n) => format!("{n}{suffix}"),
        None => String::new(),
    }
}

/// The numbers of «5 و6 و7» / «5, 6 et 7», each with its own bis/ter.
fn split_numbers(list: &str) -> Vec<String> {
    patterns().one_number.find_iter(list).map(|m| article_number(m.as_str())).filter(|n| !n.is_empty()).collect()
}

struct Folded {
    text: String,
    map: Vec<usize>,
    chars: Vec<char>,
}

impl Folded {
    fn new(s: &str) -> Self {
        let (text, map) = ma_text::fold_map(s);
        Folded { text, map, chars: s.chars().collect() }
    }

    /// Whether a match sits on word edges of the folded text.
    fn on_edges(&self, start: usize, end: usize) -> bool {
        let before = self.text[..start].chars().next_back();
        let after = self.text[end..].chars().next();
        before.is_none_or(|c| c == ' ') && after.is_none_or(|c| c == ' ')
    }

    /// Byte span in the folded text → char span in the source, and the source's words.
    fn source(&self, start: usize, end: usize) -> (usize, usize, String) {
        let a = self.text[..start].chars().count();
        let b = self.text[..end].chars().count();
        let s = self.map[a];
        let e = self.map[b - 1] + 1;
        (s, e, self.chars[s..e].iter().collect())
    }
}

/// Every match of `re` that sits on word edges, left to right, never overlapping.
fn matches<'a>(f: &'a Folded, re: &'a Regex) -> Vec<regex::Captures<'a>> {
    let mut out = Vec::new();
    let mut at = 0;
    while at <= f.text.len() {
        let Some(c) = re.captures_at(&f.text, at) else { break };
        let m = c.get(0).unwrap();
        if f.on_edges(m.start(), m.end()) {
            at = m.end();
            out.push(c);
        } else {
            at = m.start() + f.text[m.start()..].chars().next().map_or(1, char::len_utf8);
        }
    }
    out
}

fn overlaps(taken: &[(usize, usize)], s: usize, e: usize) -> bool {
    taken.iter().any(|&(a, b)| s < b && a < e)
}

/// The citations in running text, in reading order. A one-letter article word («ف», «م») counts only with
/// the text it belongs to, and the short code letters («ق.ل.ع») only after an article.
pub fn parse(text: &str) -> Vec<Citation> {
    let f = Folded::new(text);
    parse_folded(&f, false)
}

fn parse_folded(f: &Folded, query: bool) -> Vec<Citation> {
    let p = patterns();
    let mut out: Vec<Citation> = Vec::new();
    let mut taken: Vec<(usize, usize)> = Vec::new();

    // A range, every article of it (at most a hundred): «المواد من 5 إلى 9» is 5, 6, 7, 8 and 9.
    for c in matches(f, &p.range) {
        let m = c.get(0).unwrap();
        let (a, b): (u32, u32) = (c["a"].parse().unwrap_or(0), c["b"].parse().unwrap_or(0));
        if a == 0 || b <= a || b - a > 100 {
            continue;
        }
        let (code, text_kind) = (code_from(&c), kind_from(&c));
        let text_number = c.name("tnum").map(|n| n.as_str().to_owned());
        let (start, end, raw) = f.source(m.start(), m.end());
        for n in a..=b {
            out.push(Citation {
                kind: Kind::Article, start, end, raw: raw.clone(), article: Some(n.to_string()), text_kind,
                text_number: text_number.clone(), code, issue: None, issue_suffix: None, date: date_from(&c, "t"),
            });
        }
        taken.push((m.start(), m.end()));
    }
    for c in matches(f, &p.article) {
        let m = c.get(0).unwrap();
        if overlaps(&taken, m.start(), m.end()) {
            continue;
        }
        let word = &c["word"];
        if !query && (word == "ف" || word == "م") && c.name("target").is_none() {
            continue;
        }
        let (code, text_kind) = (code_from(&c), kind_from(&c));
        let text_number = c.name("tnum").map(|n| n.as_str().to_owned());
        let (start, end, raw) = f.source(m.start(), m.end());
        for number in split_numbers(&c["nums"]) {
            out.push(Citation {
                kind: Kind::Article, start, end, raw: raw.clone(), article: Some(number), text_kind,
                text_number: text_number.clone(), code, issue: None, issue_suffix: None, date: date_from(&c, "t"),
            });
        }
        taken.push((m.start(), m.end()));
    }
    for c in matches(f, &p.issue) {
        let m = c.get(0).unwrap();
        if overlaps(&taken, m.start(), m.end()) {
            continue;
        }
        let (start, end, raw) = f.source(m.start(), m.end());
        out.push(Citation {
            kind: Kind::Issue, start, end, raw, article: None, text_kind: None, text_number: None, code: None,
            issue: c["issue"].parse().ok(), issue_suffix: c.name("bis").map(|_| "bis"), date: None,
        });
        taken.push((m.start(), m.end()));
    }
    // A text by the day it was signed, when no number names it.
    for c in matches(f, &p.dated) {
        let m = c.get(0).unwrap();
        if overlaps(&taken, m.start(), m.end()) {
            continue;
        }
        let Some(date) = date_from(&c, "") else {
            continue;
        };
        let (start, end, raw) = f.source(m.start(), m.end());
        out.push(Citation {
            kind: Kind::Text, start, end, raw, article: None, text_kind: kind_from(&c), text_number: None, code: None,
            issue: None, issue_suffix: None, date: Some(date),
        });
        taken.push((m.start(), m.end()));
    }
    for c in matches(f, &p.text) {
        let m = c.get(0).unwrap();
        if overlaps(&taken, m.start(), m.end()) {
            continue;
        }
        let (start, end, raw) = f.source(m.start(), m.end());
        out.push(Citation {
            kind: Kind::Text, start, end, raw, article: None, text_kind: kind_from(&c),
            text_number: Some(c["num"].to_owned()), code: None, issue: None, issue_suffix: None, date: None,
        });
        taken.push((m.start(), m.end()));
    }
    for c in matches(f, &p.code) {
        let m = c.get(0).unwrap();
        if overlaps(&taken, m.start(), m.end()) {
            continue;
        }
        let (start, end, raw) = f.source(m.start(), m.end());
        out.push(Citation {
            kind: Kind::Text, start, end, raw, article: None, text_kind: None, text_number: None,
            code: code_from(&c), issue: None, issue_suffix: None, date: None,
        });
        taken.push((m.start(), m.end()));
    }
    out.sort_by_key(|c| (c.start, c.article.clone()));
    out
}

/// A search query read as a citation: the forms of `parse`, plus «مدونة الأسرة 53» / «ق.ل.ع 230» (an
/// article of a code) and a text number typed alone («1.58.250» a dahir, «2.22.729» a decree, «31.13» a law).
pub fn parse_query(query: &str) -> Vec<Citation> {
    let f = Folded::new(query);
    let p = patterns();
    if let Some(c) = p.query_code_number.captures(&f.text).or_else(|| p.query_number_code.captures(&f.text)) {
        let (start, end, raw) = f.source(0, f.text.len());
        return vec![Citation {
            kind: Kind::Article, start, end, raw, article: Some(article_number(&c["num"])), text_kind: None,
            text_number: None, code: code_from(&c), issue: None, issue_suffix: None, date: None,
        }];
    }
    if let Some(c) = p.query_number.captures(&f.text) {
        let num = &c["num"];
        let groups: Vec<&str> = num.split('-').collect();
        let text_kind = match groups.as_slice() {
            [first, _, _] if *first == "1" => Some("dahir"),
            [first, _, _] if *first == "2" => Some("decree"),
            [_, year] if year.len() == 2 => Some("law"),
            _ => None,
        };
        if let Some(kind) = text_kind {
            let (start, end, raw) = f.source(0, f.text.len());
            return vec![Citation {
                kind: Kind::Text, start, end, raw, article: None, text_kind: Some(kind),
                text_number: Some(num.to_owned()), code: None, issue: None, issue_suffix: None, date: None,
            }];
        }
    }
    parse_folded(&f, true)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn as_json(c: &Citation) -> serde_json::Value {
        let mut v = serde_json::json!({
            "kind": c.kind.as_str(), "raw": c.raw, "article": c.article, "text_kind": c.text_kind,
            "text_number": c.text_number, "code": c.code, "issue": c.issue,
        });
        if let Some(s) = c.issue_suffix {
            v["issue_suffix"] = s.into();
        }
        if let Some(d) = &c.date {
            v["date"] = d.clone().into();
        }
        v
    }

    #[test]
    fn citation_vectors() {
        let path = format!("{}/../vectors/cite.json", env!("CARGO_MANIFEST_DIR"));
        let vectors: Vec<serde_json::Value> = serde_json::from_str(&std::fs::read_to_string(path).unwrap()).unwrap();
        for v in vectors {
            let input = v["in"].as_str().unwrap();
            let got: Vec<serde_json::Value> = if v["query"].as_bool().unwrap_or(false) {
                parse_query(input).iter().map(as_json).collect()
            } else {
                parse(input).iter().map(as_json).collect()
            };
            assert_eq!(serde_json::Value::Array(got), v["want"], "{input}");
        }
    }

    #[test]
    fn spans_point_at_the_words() {
        let s = "طبقا لمقتضيات الفصل ٤١٨ من ق.ل.ع، فإن";
        let c = &parse(s)[0];
        let chars: Vec<char> = s.chars().collect();
        assert_eq!(chars[c.start..c.end].iter().collect::<String>(), "الفصل ٤١٨ من ق.ل.ع");
    }
}
