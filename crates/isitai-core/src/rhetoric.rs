//! Rhetorical patterns: a structural reading of the prose.
//!
//! Two shapes, both from the same observation about generated text: a sentence that
//! reverses the one before it ("Ce n'est pas simple. C'est complexe."), and a closing
//! three-part cadence ("Il analyse, traite et livre.").
//!
//! Both are **frequent in formal human writing**: legal notices, administrative letters,
//! academic prose. A layer that turned them into `ai-signal` would flag every security
//! notice and every contract. So this module produces evidence with a span, and
//! [`crate::verdict`] ignores [`Layer::Rhetoric`] by construction.
//!
//! What it is for: showing *where* a text builds its cadence, in a form a human can
//! check. Never a score, never a rate — the pattern counts are a description, not a
//! probability.

use crate::{Evidence, Layer, Location, Origin, Strength};

/// Kept short: a span is a pointer for a human to look at, not a copy of the text.
const MAX_SPAN_CHARS: usize = 200;

/// Contrastive connectors that open a sentence. French and English, because the
/// pattern is syntactic rather than lexical and both languages carry it.
const CONTRAST: [&str; 14] = [
    "mais",
    "or",
    "toutefois",
    "cependant",
    "néanmoins",
    "pourtant",
    "en réalité",
    "en fait",
    "au contraire",
    "but",
    "yet",
    "however",
    "in reality",
    "in fact",
];

/// Scans `input` for the two patterns, returning one evidence per occurrence.
pub fn scan(input: &str) -> Vec<Evidence> {
    let spans = sentences(input);
    let mut out = Vec::new();

    for &(start, end) in &spans {
        let sentence = &input[start..end];
        if let Some(span) = not_x_but_y(sentence) {
            out.push(evidence(
                "rhetoric.not-x-but-y",
                "reversal inside one sentence (not X, but Y)",
                start + span.0,
                start + span.1,
                input,
            ));
        }
        if let Some(span) = triptych(sentence) {
            out.push(evidence(
                "rhetoric.triptych",
                "three-part cadence with three short coordinated items",
                start + span.0,
                start + span.1,
                input,
            ));
        }
    }

    for window in spans.windows(2) {
        let (a_start, a_end) = window[0];
        let (b_start, b_end) = window[1];
        let a = &input[a_start..a_end];
        let b = &input[b_start..b_end];
        if negates(a) && opens_with_contrast(b) {
            out.push(evidence(
                "rhetoric.pivot-pair",
                "the sentence after a negation opens on a contrast connector",
                a_start,
                b_end,
                input,
            ));
        }
    }

    out.sort_by_key(|e| match &e.location {
        Some(Location::Span { start, .. }) => *start,
        _ => 0,
    });
    out
}

fn evidence(id: &str, detail: &str, start: usize, end: usize, input: &str) -> Evidence {
    Evidence {
        id: id.to_string(),
        layer: Layer::Rhetoric,
        // Weak on purpose, twice over: a pattern is not a proof, and this layer cannot
        // reach the verdict anyway. The strength only orders the report.
        strength: Strength::Weak,
        origin: Origin::Ai,
        detail: detail.to_string(),
        location: Some(Location::Span {
            start,
            end,
            text: input[start..end].chars().take(MAX_SPAN_CHARS).collect(),
        }),
    }
}

/// Byte spans of the sentences of `input`, trimmed. Splitting on `.`, `!` and `?`
/// followed by whitespace: a decimal point or an abbreviation will cut a sentence in
/// two, which costs a missed or spurious pair, never a wrong span.
fn sentences(input: &str) -> Vec<(usize, usize)> {
    let bytes = input.as_bytes();
    let mut out = Vec::new();
    let mut start = 0usize;
    let mut i = 0usize;
    while i < bytes.len() {
        if matches!(bytes[i], b'.' | b'!' | b'?') {
            let mut j = i + 1;
            while j < bytes.len() && bytes[j].is_ascii_whitespace() {
                j += 1;
            }
            push_span(input, start, i + 1, &mut out);
            if j >= bytes.len() {
                return out;
            }
            start = j;
            i = j;
            continue;
        }
        i += 1;
    }
    if start < bytes.len() {
        push_span(input, start, bytes.len(), &mut out);
    }
    out
}

fn push_span(input: &str, start: usize, end: usize, out: &mut Vec<(usize, usize)>) {
    let bytes = input.as_bytes();
    let mut s = start;
    let mut e = end.min(bytes.len());
    while s < e && bytes[s].is_ascii_whitespace() {
        s += 1;
    }
    while e > s && bytes[e - 1].is_ascii_whitespace() {
        e -= 1;
    }
    if e > s && input[s..e].chars().count() >= 2 {
        out.push((s, e));
    }
}

fn opens_with_contrast(sentence: &str) -> bool {
    let low = sentence.to_lowercase();
    CONTRAST.iter().any(|c| {
        low.strip_prefix(c)
            .map(|rest| rest.is_empty() || !rest.starts_with(|ch: char| ch.is_alphanumeric()))
            .unwrap_or(false)
    })
}

fn negates(sentence: &str) -> bool {
    let low = sentence.to_lowercase();
    (low.contains("ne ") || low.contains("n'")) && low.contains("pas") || low.contains(" no ")
}

/// `Ce n'est pas simple, c'est complexe.` inside a single sentence.
fn not_x_but_y(sentence: &str) -> Option<(usize, usize)> {
    let low = sentence.to_lowercase();
    let neg = [
        "ce n'est pas",
        "ce n’est pas",
        "il ne s'agit pas",
        "it is not",
    ]
    .iter()
    .find_map(|p| low.find(p))?;
    let contrast = ["c'est", "il s'agit de", "it is", "but it is"]
        .iter()
        .find_map(|p| low[neg..].find(p).map(|i| i + neg))?;
    if contrast <= neg || !low[neg..contrast].contains(',') {
        return None;
    }
    Some((0, sentence.len()))
}

/// `Il analyse, traite et livre.` — exactly three short coordinated items.
fn triptych(sentence: &str) -> Option<(usize, usize)> {
    let body = sentence.trim_end_matches(['.', '!', '?', ' ']);
    let parts: Vec<&str> = body.split(", ").collect();
    if parts.len() != 2 {
        return None;
    }
    let tail: Vec<&str> = parts[1].split(" et ").collect();
    if tail.len() != 2 {
        return None;
    }
    let items = [parts[0], tail[0], tail[1]];
    if items.iter().any(|item| {
        let words = item.split_whitespace().count();
        words == 0 || words > 4
    }) {
        return None;
    }
    Some((0, sentence.len()))
}

#[cfg(test)]
mod tests {
    use crate::{check_text, Layer, Rules, Verdict};

    fn rhetoric(input: &str) -> Vec<String> {
        super::scan(input).into_iter().map(|e| e.id).collect()
    }

    #[test]
    fn pivot_pair_is_found_after_a_negation() {
        let ids = rhetoric("Cette approche n'est pas suffisante. Mais elle reste utile.");
        assert_eq!(ids, vec!["rhetoric.pivot-pair"]);
    }

    #[test]
    fn pivot_pair_needs_the_connector() {
        let ids = rhetoric("Cette approche n'est pas suffisante. Elle reste utile.");
        assert!(
            ids.is_empty(),
            "un motif sans connecteur ne doit rien produire"
        );
    }

    #[test]
    fn reversal_inside_one_sentence_is_found() {
        let ids = rhetoric("Ce n'est pas un problème de vitesse, c'est un problème de forme.");
        assert_eq!(ids, vec!["rhetoric.not-x-but-y"]);
    }

    #[test]
    fn three_part_cadence_is_found() {
        assert_eq!(
            rhetoric("Il analyse, traite et livre."),
            vec!["rhetoric.triptych"]
        );
    }

    #[test]
    fn a_four_item_list_is_not_a_triptych() {
        assert!(rhetoric("Il analyse, trie, traite et livre.").is_empty());
    }

    #[test]
    fn plain_human_text_produces_nothing() {
        assert!(rhetoric("Bonjour, je rentre demain soir. On se voit samedi ?").is_empty());
    }

    /// The invariant this layer exists to keep: whatever it finds, the verdict is the
    /// same as without it. A formal notice full of these patterns is not `ai-signal`.
    #[test]
    fn rhetoric_never_changes_the_verdict() {
        let text = "Ce n'est pas une question de moyens, c'est une question de choix. \
                    La mesure n'est pas suffisante. Mais elle éclaire. \
                    Il observe, compare et conclut. \
                    Le rapport n'est pas public. Cependant il circule.";
        let report = check_text(text, &Rules::embedded());
        assert_eq!(report.verdict, Verdict::NoSignal);
        assert!(
            report.evidence.iter().all(|e| e.layer == Layer::Rhetoric),
            "seule la couche rhétorique doit parler ici"
        );
        assert!(
            report.evidence.len() >= 3,
            "les motifs doivent tout de même être rapportés : {} trouvé(s)",
            report.evidence.len()
        );
    }
}
