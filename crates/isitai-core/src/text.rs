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
