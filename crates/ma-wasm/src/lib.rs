//! `ma_law` for the browser: the same folding and citation reading the server runs (see ma-py).
//! Results cross as JSON strings; offsets are given in chars and in UTF-16 units (what JavaScript slices).

use serde_json::json;
use wasm_bindgen::prelude::*;

#[wasm_bindgen]
pub fn fold(s: &str) -> String {
    ma_text::fold(s)
}

/// JSON [[layout, text], …]: the query had the keyboard been in Arabic.
#[wasm_bindgen(js_name = layoutCandidates)]
pub fn layout_candidates(query: &str) -> String {
    json!(ma_text::layout_candidates(query)).to_string()
}

fn utf16_offsets(text: &str) -> Vec<usize> {
    let mut out = Vec::with_capacity(text.len() + 1);
    let mut at = 0;
    for c in text.chars() {
        out.push(at);
        at += c.len_utf16();
    }
    out.push(at);
    out
}

fn as_json(text: &str, cites: Vec<ma_cite::Citation>) -> String {
    let u16 = utf16_offsets(text);
    let rows: Vec<serde_json::Value> = cites
        .into_iter()
        .map(|c| {
            json!({
                "kind": c.kind.as_str(), "start": c.start, "end": c.end,
                "start16": u16[c.start], "end16": u16[c.end], "raw": c.raw, "article": c.article,
                "text_kind": c.text_kind, "text_number": c.text_number, "code": c.code, "issue": c.issue,
                "issue_suffix": c.issue_suffix, "date": c.date,
            })
        })
        .collect();
    serde_json::Value::Array(rows).to_string()
}

/// JSON: the citations in running text.
#[wasm_bindgen(js_name = parseCitations)]
pub fn parse_citations(text: &str) -> String {
    as_json(text, ma_cite::parse(text))
}

/// JSON: a search query read as a citation.
#[wasm_bindgen(js_name = parseQuery)]
pub fn parse_query(query: &str) -> String {
    as_json(query, ma_cite::parse_query(query))
}
