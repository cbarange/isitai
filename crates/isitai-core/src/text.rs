use crate::{Evidence, Layer, Location, Origin, Rules};

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

    #[test]
    fn utm_chatgpt_is_strong() {
        assert_eq!(
            v("see https://example.com/?utm_source=chatgpt.com"),
            Verdict::AiSignal
        );
    }

    #[test]
    fn french_self_disclosure() {
        assert_eq!(
            v("En tant que modèle de langage, je ne peux pas."),
            Verdict::AiSignal
        );
    }

    #[test]
    fn one_weak_is_not_enough_two_are() {
        assert_eq!(v("## Titre\nTexte"), Verdict::NoSignal);
        assert_eq!(v("## Titre\nTexte\u{200B} ici"), Verdict::AiSignal);
    }
}
