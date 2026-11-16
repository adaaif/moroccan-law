//! `ma_law` for Python: the same folding and citation reading the browser runs (see ma-wasm).

use pyo3::prelude::*;
use pyo3::types::PyDict;

/// The text folded for search: one spelling per letter, no vowel marks, Western digits, 65.99 → 65-99.
#[pyfunction]
fn fold(s: &str) -> String {
    ma_text::fold(s)
}

/// The folded words of a text.
#[pyfunction]
fn tokens(s: &str) -> Vec<String> {
    ma_text::tokens(s)
}

/// A light stem of one folded word.
#[pyfunction]
fn stem(word: &str) -> String {
    ma_text::stem(word)
}

/// A query's words as the index holds them: folded, small words out, stemmed, each once.
#[pyfunction]
fn search_terms(query: &str) -> Vec<String> {
    ma_text::search_terms(query)
}

/// A folded text's words, each stemmed: what the index stores for an article.
#[pyfunction]
fn index_terms(s: &str) -> Vec<String> {
    ma_text::tokens(s).iter().map(|w| ma_text::stem(w)).collect()
}

/// Whether a query is Darija typed in Latin letters (B6 of the search plan).
#[pyfunction]
fn is_arabizi(query: &str) -> bool {
    ma_text::is_arabizi(query)
}

/// A word of Arabizi in Arabic letters, likeliest first, at most `limit` ways.
#[pyfunction]
fn arabizi_spellings(word: &str, limit: usize) -> Vec<String> {
    ma_text::arabizi_spellings(word, limit)
}

/// [(start, end)]: where `needle` stands in `haystack` as whole words, both folded (char offsets).
#[pyfunction]
fn find_folded(haystack: &str, needle: &str) -> Vec<(usize, usize)> {
    ma_text::find_folded(haystack, needle)
}

/// [(layout, text)]: the query had the keyboard been in Arabic (AZERTY, then QWERTY).
#[pyfunction]
fn layout_candidates(query: &str) -> Vec<(String, String)> {
    ma_text::layout_candidates(query).into_iter().map(|(l, t)| (l.to_owned(), t)).collect()
}

fn as_dicts<'py>(py: Python<'py>, cites: Vec<ma_cite::Citation>) -> PyResult<Vec<Bound<'py, PyDict>>> {
    cites
        .into_iter()
        .map(|c| {
            let d = PyDict::new(py);
            d.set_item("kind", c.kind.as_str())?;
            d.set_item("start", c.start)?;
            d.set_item("end", c.end)?;
            d.set_item("raw", c.raw)?;
            d.set_item("article", c.article)?;
            d.set_item("text_kind", c.text_kind)?;
            d.set_item("text_number", c.text_number)?;
            d.set_item("code", c.code)?;
            d.set_item("issue", c.issue)?;
            d.set_item("issue_suffix", c.issue_suffix)?;
            d.set_item("date", c.date)?;
            Ok(d)
        })
        .collect()
}

/// The citations in running text: [{kind, start, end, raw, article, text_kind, text_number, code, issue, date}].
#[pyfunction]
fn parse_citations<'py>(py: Python<'py>, text: &str) -> PyResult<Vec<Bound<'py, PyDict>>> {
    as_dicts(py, ma_cite::parse(text))
}

/// A search query read as a citation (looser forms than running text).
#[pyfunction]
fn parse_query<'py>(py: Python<'py>, query: &str) -> PyResult<Vec<Bound<'py, PyDict>>> {
    as_dicts(py, ma_cite::parse_query(query))
}

#[pymodule]
fn ma_law(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(fold, m)?)?;
    m.add_function(wrap_pyfunction!(tokens, m)?)?;
    m.add_function(wrap_pyfunction!(stem, m)?)?;
    m.add_function(wrap_pyfunction!(search_terms, m)?)?;
    m.add_function(wrap_pyfunction!(index_terms, m)?)?;
    m.add_function(wrap_pyfunction!(layout_candidates, m)?)?;
    m.add_function(wrap_pyfunction!(find_folded, m)?)?;
    m.add_function(wrap_pyfunction!(is_arabizi, m)?)?;
    m.add_function(wrap_pyfunction!(arabizi_spellings, m)?)?;
    m.add_function(wrap_pyfunction!(parse_citations, m)?)?;
    m.add_function(wrap_pyfunction!(parse_query, m)?)?;
    Ok(())
}
