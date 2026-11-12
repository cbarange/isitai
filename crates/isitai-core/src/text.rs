use crate::{Evidence, Layer, Location, Origin, Rules, SNIFF_LEN};

/// Windows-1252 for the bytes 0x80 to 0x9F; every other byte is the code point of
/// the same value, as in Latin-1. The five bytes the code page leaves undefined
/// (0x81, 0x8D, 0x8F, 0x90, 0x9D) map to the control of the same value, as browsers do.
#[rustfmt::skip]
const WINDOWS_1252_80_9F: [char; 32] = [
    '\u{20AC}', '\u{81}',   '\u{201A}', '\u{192}',  '\u{201E}', '\u{2026}', '\u{2020}', '\u{2021}',
    '\u{2C6}',  '\u{2030}', '\u{160}',  '\u{2039}', '\u{152}',  '\u{8D}',   '\u{17D}',  '\u{8F}',
    '\u{90}',   '\u{2018}', '\u{2019}', '\u{201C}', '\u{201D}', '\u{2022}', '\u{2013}', '\u{2014}',
    '\u{2DC}',  '\u{2122}', '\u{161}',  '\u{203A}', '\u{153}',  '\u{9D}',   '\u{17E}',  '\u{178}',
];

/// Decodes the content of a file as text. Returns the text and, when the content
/// is not UTF-8, the name of its encoding; `None` when the content is not text.
/// `truncated`: the bytes are the start of a longer content, so the cut may fall
/// inside a character.
///
/// - UTF-16 LE or BE needs a byte order mark, which is left out of the text.
/// - UTF-8 is returned as it is: a leading byte order mark stays in the text.
/// - Anything else is read as Windows-1252, but only when it is clearly text.
///
/// Clearly text: the first `SNIFF_LEN` bytes (or UTF-16 characters) hold no NUL
/// and no other control below U+0020, apart from tab, LF, CR and FF.
pub fn decode(bytes: Vec<u8>, truncated: bool) -> Option<(String, Option<&'static str>)> {
    type Unit = fn([u8; 2]) -> u16;
    let utf16: [(&[u8], &str, Unit); 2] = [
        (b"\xFF\xFE", "UTF-16LE", u16::from_le_bytes),
        (b"\xFE\xFF", "UTF-16BE", u16::from_be_bytes),
    ];
    for (bom, name, unit) in utf16 {
        if let Some(body) = bytes.strip_prefix(bom) {
            let text = decode_utf16(body, unit, truncated)?;
            let clear = !text.chars().take(SNIFF_LEN).any(is_binary_control);
            return clear.then_some((text, Some(name)));
        }
    }
    let error = match String::from_utf8(bytes) {
        Ok(text) => return Some((text, None)),
        Err(error) => error,
    };
    // The size limit can cut the last character in two: keep what precedes it.
    if truncated && error.utf8_error().error_len().is_none() {
        let valid = error.utf8_error().valid_up_to();
        let mut bytes = error.into_bytes();
        bytes.truncate(valid);
        let text = String::from_utf8(bytes).expect("valid up to this length");
        return Some((text, None));
    }
    let bytes = error.into_bytes();
    let head = &bytes[..bytes.len().min(SNIFF_LEN)];
    if head.iter().any(|&b| is_binary_control(char::from(b))) {
        return None;
    }
    let text = bytes
        .iter()
        .map(|&b| match b {
            0x80..=0x9F => WINDOWS_1252_80_9F[usize::from(b - 0x80)],
            _ => char::from(b),
        })
        .collect();
    Some((text, Some("Windows-1252")))
}

/// A control character that text files do not hold.
fn is_binary_control(c: char) -> bool {
    c < ' ' && !matches!(c, '\t' | '\n' | '\r' | '\x0C')
}

/// Strict UTF-16: a lone surrogate or half a code unit means the content is not text.
fn decode_utf16(body: &[u8], unit: fn([u8; 2]) -> u16, truncated: bool) -> Option<String> {
    let (pairs, rest) = body.as_chunks::<2>();
    if !rest.is_empty() && !truncated {
        return None;
    }
    let mut units: Vec<u16> = pairs.iter().map(|&pair| unit(pair)).collect();
    // The size limit can cut a surrogate pair in two: drop its first half.
    if truncated && matches!(units.last(), Some(0xD800..=0xDBFF)) {
        units.pop();
    }
    String::from_utf16(&units).ok()
}

pub fn scan(input: &str, rules: &Rules) -> Vec<Evidence> {
    let mut out = Vec::new();
    for rule in &rules.text {
        let mut it = rule.regex.find_iter(input);
        let Some(first) = it.next() else { continue };
        let count = 1 + it.count();
        out.push(Evidence {
            id: rule.id.clone(),
            layer: Layer::Artifact,
            strength: rule.strength,
            origin: Origin::Ai,
            detail: format!(
                "{} ({count} occurrence{})",
                rule.detail,
                if count > 1 { "s" } else { "" }
            ),
            location: Some(Location::Span {
                start: first.start(),
                end: first.end(),
                text: first.as_str().chars().take(200).collect(),
            }),
        });
    }
    // Rhetorical shape comes last: it describes the prose, and never decides the verdict.
    out.extend(crate::rhetoric::scan(input));
    out
}

#[cfg(test)]
mod tests {
    use crate::{check_text, Rules, Verdict};

    fn v(s: &str) -> Verdict {
        check_text(s, &Rules::embedded()).verdict
    }

    #[test]
    fn plain_human_text_has_no_signal() {
        assert_eq!(
            v("Bonjour, je rentre demain soir. On se voit samedi ?"),
            Verdict::NoSignal
        );
    }

    #[test]
    fn french_typography_is_not_a_signal() {
        // U+202F narrow no-break space and U+00A0 before French punctuation.
        assert_eq!(
            v("Il a dit\u{202F}: «\u{00A0}oui\u{00A0}»\u{202F}!"),
            Verdict::NoSignal
        );
    }

    #[test]
    fn emoji_zwj_is_not_a_signal() {
        assert_eq!(
            v("Famille \u{1F468}\u{200D}\u{1F469}\u{200D}\u{1F467} au parc"),
            Verdict::NoSignal
        );
    }

    #[test]
    fn leading_bom_is_not_a_signal() {
        assert_eq!(v("\u{FEFF}Hello"), Verdict::NoSignal);
    }

    #[test]
    fn oaicite_is_strong() {
        assert_eq!(
            v("Paris is big :contentReference[oaicite:0]{index=0}."),
            Verdict::AiSignal
        );
    }

    /// Ids of the rules that match.
    fn ids(s: &str) -> Vec<String> {
        let report = check_text(s, &Rules::embedded());
        report.evidence.into_iter().map(|e| e.id).collect()
    }

    #[test]
    fn citeturn_spaced_and_glued() {
        for s in [
            "Paris cite turn0search1 turn0news2.",
            "Paris citeturn0search3.",
            "Paris citeturn0image12",
            "Paris \u{E200}cite\u{E202}turn0search0\u{E202}turn1view0\u{E201}.",
        ] {
            assert_eq!(ids(s), ["text.citeturn"], "{s}");
            assert_eq!(v(s), Verdict::AiSignal);
        }
        // Not tokens: code, ordinary words.
        for s in [
            "export const turn = (n) => `turn${n}`;",
            "return1search2",
            "the turn0 of the screw",
        ] {
            assert_eq!(v(s), Verdict::NoSignal, "{s}");
        }
    }

    #[test]
    fn utm_alone_is_weak() {
        let link = "see https://example.com/?utm_source=chatgpt.com";
        assert_eq!(ids(link), ["text.utm-ai"]);
        assert_eq!(v(link), Verdict::NoSignal);
        assert_eq!(
            v("https://example.com/?id=3&utm_source=openai"),
            Verdict::NoSignal
        );
    }

    #[test]
    fn self_disclosure_in_the_assistant_voice() {
        for s in [
            "As an AI language model, I cannot browse the internet.",
            "as an ai language model I can't do that",
            "I'm sorry, but as an AI model I do not have opinions.",
            "As an AI, I don't have feelings.",
            "As an AI assistant, I cannot.",
            "As of my last knowledge update, the record stood at 9.58 s.",
            "As of my knowledge cutoff, no such law existed.",
            "En tant que modèle de langage, je ne peux pas.",
            "EN TANT QUE MODÈLE DE LANGAGE, JE NE PEUX PAS.",
            "En tant qu'IA, je n'ai pas d'opinion personnelle.",
            "En tant qu’IA, je n'ai pas d'opinion personnelle.",
            "En tant qu'intelligence artificielle, je ne ressens rien.",
        ] {
            assert_eq!(ids(s), ["text.self-disclosure"], "{s}");
            assert_eq!(v(s), Verdict::AiSignal);
        }
    }

    #[test]
    fn self_disclosure_words_in_a_human_sentence() {
        for s in [
            "As an AI model grows, its training bill grows faster.",
            "En tant qu'intelligence artificielle générative, ChatGPT ne « comprend » pas ce qu'il écrit.",
            "En tant qu'IA dite « de confiance », le système doit pourtant être audité.",
            // The pronoun must be the word "I", uppercase, in the same clause.
            "As an AI company, it grew fast. I was there.",
            "As an AI lab scales, AI costs rise.",
            "as an ai startup i guess they did fine",
            "Sold as an AI\nI disagree.",
        ] {
            assert_eq!(v(s), Verdict::NoSignal, "{s}");
        }
    }

    #[test]
    fn markdown_is_not_a_signal() {
        assert_eq!(v("## Titre\nTexte **gras**"), Verdict::NoSignal);
        // With one zero-width character: still one weak rule only.
        assert_eq!(ids("## Titre\nTexte\u{200B} ici"), ["text.zero-width"]);
        assert_eq!(v("## Titre\nTexte\u{200B} ici"), Verdict::NoSignal);
    }

    #[test]
    fn one_weak_is_not_enough_two_are() {
        let link = "https://example.com/?utm_source=chatgpt.com";
        assert_eq!(v("Voici le plan\u{200B} ici"), Verdict::NoSignal);
        assert_eq!(v(link), Verdict::NoSignal);
        assert_eq!(
            v(&format!("Voici le plan\u{200B} : {link}")),
            Verdict::AiSignal
        );
    }

    #[test]
    fn self_disclosure_needs_the_assistant_voice() {
        assert_eq!(
            v("As an AI language model, I cannot browse the web."),
            Verdict::AiSignal
        );
        assert_eq!(v("As an AI, I don't have opinions."), Verdict::AiSignal);
        assert_eq!(v("En tant qu'IA, je ne peux pas."), Verdict::AiSignal);
        for human in [
            "As an AI model grows, its training bill grows faster.",
            "Costs rise as an AI language model gets deployed to millions of users.",
            "As an AI researcher, I think this is overhyped.",
            "En tant qu'intelligence artificielle générative, ChatGPT pose des questions.",
        ] {
            assert_eq!(v(human), Verdict::NoSignal, "{human}");
        }
    }
}
