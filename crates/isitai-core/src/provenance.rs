use crate::rules::Dst;
use crate::{Evidence, HistoryEntry, HistorySummary, Layer, Location, Origin, Strength};
use c2pa::{Context, Reader, ValidationState};
use serde_json::{json, Value};
use std::io::{Read, Seek};

pub struct Provenance {
    pub evidence: Vec<Evidence>,
    pub generator: Option<String>,
    pub warnings: Vec<String>,
    pub history: Vec<HistoryEntry>,
    pub history_summary: Option<HistorySummary>,
}

/// C2PA settings shared by [`read`] and [`validate_trust_anchors`]: no network,
/// trust checked against `anchors_pem` when given.
fn context(anchors_pem: Option<&str>) -> Result<Context, String> {
    let mut settings = json!({
        "verify": { "remote_manifest_fetch": false, "ocsp_fetch": false, "verify_trust": true }
    });
    if let Some(pem) = anchors_pem {
        settings["trust"] = json!({ "trust_anchors": pem });
    }
    Context::new()
        .with_settings(settings.to_string().as_str())
        .map_err(|e| e.to_string())
}

/// Checks that a PEM bundle can be used as `Options::trust_anchors_pem`: it holds at
/// least one certificate block and c2pa accepts it. Call it once before checking
/// files: with an unusable bundle, no C2PA manifest can be read at all.
pub fn validate_trust_anchors(pem: &str) -> Result<(), String> {
    const BEGIN: &str = "-----BEGIN CERTIFICATE-----";
    const END: &str = "-----END CERTIFICATE-----";
    let has_block = pem
        .split_once(BEGIN)
        .is_some_and(|(_, rest)| rest.contains(END));
    if !has_block {
        return Err(format!(
            "trust anchors: no PEM certificate block ({BEGIN} ... {END}) found"
        ));
    }
    context(Some(pem))
        .map(drop)
        .map_err(|_| "trust anchors: the PEM bundle holds no certificate that can be loaded".into())
}

/// Reads the C2PA manifest store. Never touches the network.
/// Returns Ok(None) when the file carries no manifest.
pub fn read<R: Read + Seek + Send>(
    input: &mut R,
    mime: &str,
    anchors_pem: Option<&str>,
    dst_rules: &Dst,
) -> Result<Option<Provenance>, String> {
    let ctx = context(anchors_pem)?;
    let reader = match Reader::from_context(ctx).with_stream(mime, &mut *input) {
        Ok(r) => r,
        Err(c2pa::Error::JumbfNotFound | c2pa::Error::ProvenanceMissing) => return Ok(None),
        // Must stay visible: a MIME name c2pa does not know looks exactly like "no manifest".
        Err(c2pa::Error::UnsupportedType) => {
            return Err(format!("unsupported type for C2PA: {mime}"))
        }
        Err(e) => return Err(e.to_string()),
    };
    let store: Value = serde_json::from_str(&reader.json()).map_err(|e| e.to_string())?;
    Ok(interpret(&store, reader.validation_state(), dst_rules))
}

/// What a manifest store (the JSON of `c2pa::Reader`) establishes, given its
/// validation state. `None` when the store has no active manifest.
fn interpret(store: &Value, state: ValidationState, dst_rules: &Dst) -> Option<Provenance> {
    let label = store.get("active_manifest").and_then(Value::as_str)?;
    let (history, truncated) = history(store);
    let mut warnings = Vec::new();
    match state {
        ValidationState::Trusted => {}
        ValidationState::Valid => {
            warnings.push("C2PA manifest is valid but its signer is not in the trust list".into())
        }
        ValidationState::Invalid => warnings.push(
            "C2PA manifest is invalid: the file changed after signing, or the manifest is broken"
                .into(),
        ),
    }
    if truncated {
        warnings.push(format!(
            "C2PA history truncated to the first {MAX_HISTORY} actions"
        ));
    }
    // A manifest that fails validation establishes nothing: neither who made the
    // file, nor anything about the chain.
    let valid = state != ValidationState::Invalid;
    Some(Provenance {
        evidence: evidence(store, label, state, dst_rules),
        generator: valid
            .then(|| generator(&store["manifests"][label]))
            .flatten(),
        warnings,
        history_summary: valid.then(|| summarize(&history, dst_rules)).flatten(),
        history,
    })
}

/// Name of the tool that wrote the manifest.
fn generator(manifest: &Value) -> Option<String> {
    manifest["claim_generator_info"]
        .as_array()
        .and_then(|a| a.first())
        .and_then(|g| g["name"].as_str())
        .or_else(|| manifest["claim_generator"].as_str())
        .map(str::to_string)
}

/// Longest action name, source type or software name kept from a manifest, in characters.
const MAX_FIELD_CHARS: usize = 128;

/// Bounds a string that comes from a manifest, which may be hostile.
fn truncate(s: &str) -> String {
    s.chars().take(MAX_FIELD_CHARS).collect()
}

/// Actions of a manifest in declared order, each with the label of its assertion.
fn actions(manifest: &Value) -> impl Iterator<Item = (&str, &Value)> {
    manifest["assertions"]
        .as_array()
        .into_iter()
        .flatten()
        .filter_map(|a| Some((a["label"].as_str()?, a)))
        .filter(|(label, _)| label.starts_with("c2pa.actions"))
        .flat_map(|(label, a)| {
            let list = a["data"]["actions"].as_array().into_iter().flatten();
            list.map(move |action| (label, action))
        })
}

/// Last path segment of the `digitalSourceType` an action declares.
fn source_type(action: &Value) -> Option<String> {
    let dst = action["digitalSourceType"].as_str()?;
    Some(dst.rsplit('/').next().unwrap_or(dst).to_string())
}

/// One piece of evidence per distinct AI or capture `digitalSourceType` in the chain
/// of the active manifest: declared by its own actions or, capped at `Strong`,
/// inherited from the manifest of an ingredient. Ingredient manifest trust is not
/// verified, so an inherited type is never a proof.
fn evidence(store: &Value, label: &str, state: ValidationState, dst_rules: &Dst) -> Vec<Evidence> {
    let manifest = &store["manifests"][label];
    let strength = match state {
        ValidationState::Trusted => Strength::Proof,
        ValidationState::Valid => Strength::Strong,
        ValidationState::Invalid => Strength::Weak,
    };
    let state_name = format!("{state:?}").to_lowercase();
    // Own types first: for the same value, the declared one wins over the inherited one.
    let own = actions(manifest)
        .filter_map(|(assertion, action)| Some((assertion, action, source_type(action)?, false)));
    let inherited = actions(manifest)
        .take(MAX_HISTORY)
        .filter(|(_, action)| source_type(action).is_none())
        .filter_map(|(assertion, action)| {
            let value = inherited_type(store, manifest, action, MAX_INGREDIENT_DEPTH)?;
            Some((assertion, action, value, true))
        });

    let mut out: Vec<Evidence> = Vec::new();
    for (assertion, action, value, inherited) in own.chain(inherited) {
        // Neutral values (e.g. `digitalArt`) are not evidence either way.
        let Some(origin) = dst_rules.origin(&value) else {
            continue;
        };
        let id = format!("c2pa.dst.{value}");
        if out.iter().any(|e| e.id == id) {
            continue;
        }
        let name = truncate(action["action"].as_str().unwrap_or("?"));
        let (strength, detail) = if inherited {
            (
                strength.min(Strength::Strong),
                format!(
                    "C2PA {name} action uses an ingredient whose manifest declares digitalSourceType {value} (manifest {state_name}; the ingredient manifest is not verified)"
                ),
            )
        } else {
            (
                strength,
                format!(
                    "C2PA {name} action declares digitalSourceType {value} (manifest {state_name})"
                ),
            )
        };
        out.push(Evidence {
            id,
            layer: Layer::Provenance,
            strength,
            origin,
            detail,
            location: Some(Location::Field {
                field: format!("{label}/{assertion}"),
            }),
        });
    }
    // Safety net against a false capture proof: an AI type declared by any other
    // manifest of the store (an ingredient no action links to, one behind an action
    // with its own type, or one past the lookup bound) still counts as an AI hint.
    if !out.iter().any(|e| e.origin == Origin::Ai) {
        if let Some((other, value)) = ai_type_elsewhere(store, label, dst_rules) {
            out.push(Evidence {
                id: format!("c2pa.dst.{value}"),
                layer: Layer::Provenance,
                strength: strength.min(Strength::Strong),
                origin: Origin::Ai,
                detail: format!(
                    "a manifest in the C2PA provenance chain declares digitalSourceType {value} (manifest {state_name}; that manifest is not verified)"
                ),
                location: Some(Location::Field {
                    field: truncate(other),
                }),
            });
        }
    }
    // "Capture, then AI edit" is AI-edited content, not a contradiction.
    if out.iter().any(|e| e.origin == Origin::Ai) {
        out.retain(|e| e.origin == Origin::Ai);
    }
    out
}

/// First AI `digitalSourceType` declared by an action of any manifest of the store
/// other than `active`, with the label of that manifest.
fn ai_type_elsewhere<'a>(
    store: &'a Value,
    active: &str,
    dst_rules: &Dst,
) -> Option<(&'a str, String)> {
    store["manifests"]
        .as_object()?
        .iter()
        .filter(|(label, _)| label.as_str() != active)
        .find_map(|(label, manifest)| {
            actions(manifest)
                .filter_map(|(_, action)| source_type(action))
                .find(|value| dst_rules.origin(value) == Some(Origin::Ai))
                .map(|value| (label.as_str(), truncate(&value)))
        })
}

/// Ingredient manifests followed from one action; also stops a cyclic store.
const MAX_INGREDIENT_DEPTH: usize = 16;

/// Actions kept in the history, and actions whose ingredient is looked up.
const MAX_HISTORY: usize = 64;

/// The first [`MAX_HISTORY`] actions of the active manifest, in declared order, and
/// whether the manifest lists more.
fn history(store: &Value) -> (Vec<HistoryEntry>, bool) {
    let manifest = &store["manifests"][store["active_manifest"].as_str().unwrap_or_default()];
    let mut entries = actions(manifest).filter_map(|(_, action)| {
        let agent = &action["softwareAgent"];
        Some(HistoryEntry {
            action: truncate(action["action"].as_str()?),
            digital_source_type: declared_type(store, manifest, action, MAX_INGREDIENT_DEPTH)
                .as_deref()
                .map(truncate),
            // A string in actions v1, an object with a `name` in v2.
            software: agent
                .as_str()
                .or_else(|| agent["name"].as_str())
                .map(truncate),
        })
    });
    let history: Vec<_> = entries.by_ref().take(MAX_HISTORY).collect();
    (history, entries.next().is_some())
}

/// `digitalSourceType` of an action: its own or, failing that, the inherited one.
fn declared_type(store: &Value, manifest: &Value, action: &Value, depth: usize) -> Option<String> {
    source_type(action).or_else(|| inherited_type(store, manifest, action, depth))
}

/// `digitalSourceType` the manifest of an action's ingredient declares, when the
/// store contains that manifest.
fn inherited_type(store: &Value, manifest: &Value, action: &Value, depth: usize) -> Option<String> {
    let label = ingredient(manifest, action)?["active_manifest"].as_str()?;
    origin_type(store, label, depth.checked_sub(1)?)
}

/// `digitalSourceType` a manifest declares for where its asset comes from: the one
/// of its first action, when that action is `c2pa.created` or `c2pa.opened`.
fn origin_type(store: &Value, label: &str, depth: usize) -> Option<String> {
    let manifest = store["manifests"].get(label)?;
    let (_, first) = actions(manifest).next()?;
    if !ORIGIN_ACTIONS.contains(&first["action"].as_str()?) {
        return None;
    }
    declared_type(store, manifest, first, depth)
}

/// First ingredient of `manifest` an action refers to. Three link forms exist in real
/// files: `parameters.ingredient.url`, `parameters.ingredients[].url` (the URL ends with
/// the ingredient label) and the older `parameters.instanceId`.
fn ingredient<'a>(manifest: &'a Value, action: &Value) -> Option<&'a Value> {
    let params = &action["parameters"];
    let labels: Vec<&str> = params["ingredients"]
        .as_array()
        .into_iter()
        .flatten()
        .chain([&params["ingredient"]])
        .filter_map(|link| link["url"].as_str()?.rsplit('/').next())
        .collect();
    let instance_id = params["instanceId"].as_str();
    manifest["ingredients"].as_array()?.iter().find(|i| {
        i["label"].as_str().is_some_and(|l| labels.contains(&l))
            || (instance_id.is_some() && i["instance_id"].as_str() == instance_id)
    })
}

/// Actions that say where the asset comes from. C2PA requires them to come first.
const ORIGIN_ACTIONS: [&str; 2] = ["c2pa.created", "c2pa.opened"];

/// Actions that modify the content: the editing actions among the `c2pa_action`
/// constants of c2pa-rs 0.92.0, plus `c2pa.color_adjustments` from C2PA 1.x.
/// Not listed, so they establish nothing: format changes (`c2pa.converted`,
/// `c2pa.transcoded`, `c2pa.repackaged`), `c2pa.published`, `c2pa.redacted`,
/// watermarking, `c2pa.unknown` and vendor actions.
const EDIT_ACTIONS: [&str; 10] = [
    "c2pa.color_adjustments",
    "c2pa.cropped",
    "c2pa.drawing",
    "c2pa.edited",
    "c2pa.filtered",
    "c2pa.orientation",
    "c2pa.placed",
    "c2pa.removed",
    "c2pa.resized",
    "c2pa.translated",
];

/// What a history establishes, without guessing: the first action must declare an AI
/// or capture origin, and a later action must be a known edit.
fn summarize(history: &[HistoryEntry], dst_rules: &Dst) -> Option<HistorySummary> {
    let (first, later) = history.split_first()?;
    if !ORIGIN_ACTIONS.contains(&first.action.as_str()) {
        return None;
    }
    let origin = |e: &HistoryEntry| dst_rules.origin(e.digital_source_type.as_deref()?);
    let mut edits = later
        .iter()
        .filter(|e| EDIT_ACTIONS.contains(&e.action.as_str()));
    match origin(first)? {
        Origin::Ai => edits.next().map(|_| HistorySummary::AiThenEdited),
        Origin::Capture => edits
            .find(|e| origin(e) == Some(Origin::Ai))
            .map(|_| HistorySummary::CaptureThenAiEdited),
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::Rules;

    const DST: &str = "http://cv.iptc.org/newscodes/digitalsourcetype/";

    fn entry(action: &str, dst: Option<&str>) -> HistoryEntry {
        HistoryEntry {
            action: action.into(),
            digital_source_type: dst.map(str::to_string),
            software: None,
        }
    }

    /// The history without the truncation flag.
    fn history(store: &Value) -> Vec<HistoryEntry> {
        super::history(store).0
    }

    fn summary(entries: &[HistoryEntry]) -> Option<HistorySummary> {
        summarize(entries, &Rules::embedded().dst)
    }

    #[test]
    fn ai_then_a_known_edit() {
        let ai = entry("c2pa.created", Some("trainedAlgorithmicMedia"));
        let then = |action| summary(&[ai.clone(), entry(action, None)]);
        assert_eq!(then("c2pa.cropped"), Some(HistorySummary::AiThenEdited));
        // Not edits: a format change, a vendor action.
        assert_eq!(then("c2pa.transcoded"), None);
        assert_eq!(then("com.vendor.magic"), None);
        assert_eq!(summary(&[ai]), None);
    }

    #[test]
    fn capture_then_an_ai_edit() {
        let capture = entry("c2pa.opened", Some("digitalCapture"));
        let ai_edit = entry("c2pa.edited", Some("compositeWithTrainedAlgorithmicMedia"));
        assert_eq!(
            summary(&[capture.clone(), ai_edit]),
            Some(HistorySummary::CaptureThenAiEdited)
        );
        // An edit that declares no AI source says nothing about AI.
        assert_eq!(summary(&[capture, entry("c2pa.edited", None)]), None);
    }

    #[test]
    fn unknown_origin_establishes_nothing() {
        let ai_edit = entry("c2pa.edited", Some("trainedAlgorithmicMedia"));
        assert_eq!(summary(&[]), None);
        assert_eq!(
            summary(&[entry("c2pa.opened", None), ai_edit.clone()]),
            None
        );
        // Neutral source type.
        assert_eq!(
            summary(&[entry("c2pa.created", Some("digitalArt")), ai_edit.clone()]),
            None
        );
        // The origin must be the first action.
        assert_eq!(
            summary(&[
                ai_edit,
                entry("c2pa.created", Some("digitalCapture")),
                entry("c2pa.edited", Some("trainedAlgorithmicMedia")),
            ]),
            None
        );
    }

    /// Shapes copied from `c2pa::Reader::json()` on the c2pa-rs fixtures.
    fn store(active_actions: Value, ingredients: Value) -> Value {
        json!({
            "active_manifest": "active",
            "manifests": {
                "active": {
                    "assertions": [
                        { "label": "c2pa.hash.data", "data": {} },
                        { "label": "c2pa.actions.v2", "data": { "actions": active_actions } }
                    ],
                    "ingredients": ingredients
                },
                "generator": {
                    "assertions": [{ "label": "c2pa.actions.v2", "data": { "actions": [
                        { "action": "c2pa.created", "digitalSourceType": format!("{DST}trainedAlgorithmicMedia") }
                    ]}}]
                },
                "camera": {
                    "assertions": [{ "label": "c2pa.actions.v2", "data": { "actions": [
                        { "action": "c2pa.created", "digitalSourceType": format!("{DST}digitalCapture") }
                    ]}}]
                },
                // Opened from "camera": its origin is found one manifest further.
                "resaved": {
                    "assertions": [{ "label": "c2pa.actions.v2", "data": { "actions": [
                        { "action": "c2pa.opened", "parameters": { "ingredient": { "url": "self#jumbf=c2pa.assertions/c2pa.ingredient" } } }
                    ]}}],
                    "ingredients": [{ "label": "c2pa.ingredient", "active_manifest": "camera" }]
                },
                // Opens itself.
                "loop": {
                    "assertions": [{ "label": "c2pa.actions.v2", "data": { "actions": [
                        { "action": "c2pa.opened", "parameters": { "instanceId": "xmp:iid:loop" } }
                    ]}}],
                    "ingredients": [{ "label": "c2pa.ingredient", "instance_id": "xmp:iid:loop", "active_manifest": "loop" }]
                }
            }
        })
    }

    #[test]
    fn history_keeps_order_source_type_and_software() {
        // ocsp.jpg (Photoshop): own source types, software as a string.
        let h = history(&store(
            json!([
                { "action": "c2pa.opened", "digitalSourceType": format!("{DST}compositeWithTrainedAlgorithmicMedia") },
                { "action": "c2pa.cropped" },
                { "action": "c2pa.edited", "softwareAgent": "Adobe Firefly" },
                { "action": "c2pa.resized", "softwareAgent": { "name": "Tool", "version": "2" } }
            ]),
            json!([]),
        ));
        assert_eq!(
            h[0],
            entry("c2pa.opened", Some("compositeWithTrainedAlgorithmicMedia"))
        );
        assert_eq!(h[1], entry("c2pa.cropped", None));
        assert_eq!(h[2].software.as_deref(), Some("Adobe Firefly"));
        assert_eq!(h[3].software.as_deref(), Some("Tool"));
        assert_eq!(h.len(), 4);
    }

    #[test]
    fn history_takes_source_type_from_the_ingredient_manifest() {
        let ingredients = json!([
            { "label": "c2pa.ingredient.v3", "active_manifest": "resaved" },
            { "label": "c2pa.ingredient__1", "instance_id": "xmp:iid:1", "active_manifest": "camera" },
            { "label": "c2pa.ingredient__2", "active_manifest": "not-in-store" },
            { "label": "c2pa.ingredient__3", "active_manifest": "loop" }
        ]);
        let link = |label: &str| json!({ "ingredient": { "url": format!("self#jumbf=c2pa.assertions/{label}") } });
        let h = history(&store(
            json!([
                { "action": "c2pa.opened", "parameters": { "ingredients": [
                    { "url": "self#jumbf=/c2pa/active/c2pa.assertions/c2pa.ingredient.v3" }
                ]}},
                { "action": "c2pa.placed", "parameters": { "instanceId": "xmp:iid:1" } },
                { "action": "c2pa.placed", "parameters": link("c2pa.ingredient__2") },
                { "action": "c2pa.placed", "parameters": link("c2pa.ingredient__3") },
                { "action": "c2pa.edited", "digitalSourceType": format!("{DST}trainedAlgorithmicMedia") }
            ]),
            ingredients,
        ));
        let types: Vec<_> = h.iter().map(|e| e.digital_source_type.as_deref()).collect();
        assert_eq!(
            types,
            [
                Some("digitalCapture"), // through "resaved" to "camera"
                Some("digitalCapture"), // by instanceId
                None,                   // manifest not in the store
                None,                   // cyclic store
                Some("trainedAlgorithmicMedia"),
            ]
        );
        assert_eq!(
            summarize(&h, &Rules::embedded().dst),
            Some(HistorySummary::CaptureThenAiEdited)
        );
    }

    #[test]
    fn history_of_a_store_without_actions_is_empty() {
        assert!(history(&json!({})).is_empty());
        assert!(history(&json!({ "active_manifest": "x", "manifests": {} })).is_empty());
    }

    use ValidationState::{Invalid, Trusted, Valid};

    fn link(label: &str) -> Value {
        json!({ "ingredient": { "url": format!("self#jumbf=c2pa.assertions/{label}") } })
    }

    /// Active manifest that opens the ingredient signed by `manifest`, then runs `later`.
    fn opened_from(manifest: &str, later: Value) -> Value {
        let mut actions =
            vec![json!({ "action": "c2pa.opened", "parameters": link("c2pa.ingredient") })];
        actions.extend(later.as_array().unwrap().iter().cloned());
        let mut s = store(
            json!(actions),
            json!([{ "label": "c2pa.ingredient", "active_manifest": manifest }]),
        );
        s["manifests"]["active"]["claim_generator_info"] = json!([{ "name": "Photo Editor" }]);
        s
    }

    /// A store whose chain holds no AI manifest at all.
    fn without_generator(mut store: Value) -> Value {
        store["manifests"]
            .as_object_mut()
            .unwrap()
            .remove("generator");
        store
    }

    fn read_store(store: &Value, state: ValidationState) -> Provenance {
        interpret(store, state, &Rules::embedded().dst).unwrap()
    }

    /// (id, origin, strength) of each piece of evidence.
    fn found(p: &Provenance) -> Vec<(&str, Origin, Strength)> {
        p.evidence
            .iter()
            .map(|e| (e.id.as_str(), e.origin, e.strength))
            .collect()
    }

    const AI: &str = "c2pa.dst.trainedAlgorithmicMedia";
    const COMPOSITE: &str = "c2pa.dst.compositeWithTrainedAlgorithmicMedia";
    const CAPTURE: &str = "c2pa.dst.digitalCapture";

    #[test]
    fn own_source_type_follows_the_validation_state() {
        let s = store(
            json!([{ "action": "c2pa.created", "digitalSourceType": format!("{DST}trainedAlgorithmicMedia") }]),
            json!([]),
        );
        for (state, strength) in [
            (Trusted, Strength::Proof),
            (Valid, Strength::Strong),
            (Invalid, Strength::Weak),
        ] {
            let p = read_store(&s, state);
            assert_eq!(found(&p), [(AI, Origin::Ai, strength)]);
            assert!(!p.evidence[0].detail.contains("ingredient"));
        }
    }

    #[test]
    fn trusted_ai_image_cropped_in_another_tool_is_an_ai_signal() {
        let p = read_store(
            &opened_from("generator", json!([{ "action": "c2pa.cropped" }])),
            Trusted,
        );
        // Inherited from the ingredient: capped at strong, never a proof.
        assert_eq!(found(&p), [(AI, Origin::Ai, Strength::Strong)]);
        assert!(p.evidence[0].detail.contains("ingredient"));
        assert_eq!(crate::verdict(&p.evidence), crate::Verdict::AiSignal);
        assert_eq!(p.history_summary, Some(HistorySummary::AiThenEdited));
    }

    #[test]
    fn inherited_source_type_is_never_above_the_manifest_state() {
        let s = opened_from("generator", json!([]));
        assert_eq!(
            found(&read_store(&s, Valid)),
            [(AI, Origin::Ai, Strength::Strong)]
        );
        assert_eq!(
            found(&read_store(&s, Invalid)),
            [(AI, Origin::Ai, Strength::Weak)]
        );
        // An inherited capture is no proof of capture either.
        let camera = read_store(
            &without_generator(opened_from("camera", json!([]))),
            Trusted,
        );
        assert_eq!(
            found(&camera),
            [(CAPTURE, Origin::Capture, Strength::Strong)]
        );
        assert_eq!(crate::verdict(&camera.evidence), crate::Verdict::NoSignal);
    }

    #[test]
    fn own_source_type_wins_over_the_same_inherited_one() {
        let own = json!([{ "action": "c2pa.edited", "digitalSourceType": format!("{DST}trainedAlgorithmicMedia") }]);
        let p = read_store(&opened_from("generator", own), Trusted);
        assert_eq!(found(&p), [(AI, Origin::Ai, Strength::Proof)]);
        assert!(!p.evidence[0].detail.contains("ingredient"));
    }

    #[test]
    fn capture_then_ai_edit_is_ai_not_a_contradiction() {
        let ai_edit = json!({ "action": "c2pa.edited", "digitalSourceType": format!("{DST}compositeWithTrainedAlgorithmicMedia") });
        // Capture declared by the active manifest itself.
        let own = store(
            json!([
                { "action": "c2pa.created", "digitalSourceType": format!("{DST}digitalCapture") },
                ai_edit.clone()
            ]),
            json!([]),
        );
        // Capture inherited from the opened ingredient.
        let inherited = opened_from("camera", json!([ai_edit]));
        for s in [own, inherited] {
            let p = read_store(&s, Trusted);
            assert_eq!(found(&p), [(COMPOSITE, Origin::Ai, Strength::Proof)]);
            assert_eq!(crate::verdict(&p.evidence), crate::Verdict::AiProven);
            assert_eq!(p.history_summary, Some(HistorySummary::CaptureThenAiEdited));
        }
        // An AI ingredient placed in a capture: no capture evidence either.
        let mut placed = store(
            json!([
                { "action": "c2pa.created", "digitalSourceType": format!("{DST}digitalCapture") },
                { "action": "c2pa.placed", "parameters": link("c2pa.ingredient") }
            ]),
            json!([{ "label": "c2pa.ingredient", "active_manifest": "generator" }]),
        );
        assert_eq!(
            found(&read_store(&placed, Trusted)),
            [(AI, Origin::Ai, Strength::Strong)]
        );
        // The AI manifest is in the store but no action links to it (or the link sits
        // behind an action with its own type): still no capture proof.
        placed["manifests"]["active"]["ingredients"] = json!([]);
        let unlinked = read_store(&placed, Trusted);
        assert_eq!(found(&unlinked), [(AI, Origin::Ai, Strength::Strong)]);
        assert_eq!(
            match &unlinked.evidence[0].location {
                Some(Location::Field { field }) => Some(field.as_str()),
                _ => None,
            },
            Some("generator")
        );
        assert_eq!(crate::verdict(&unlinked.evidence), crate::Verdict::AiSignal);
        // Without any AI manifest in the store, the capture is a proof.
        assert_eq!(
            found(&read_store(&without_generator(placed), Trusted)),
            [(CAPTURE, Origin::Capture, Strength::Proof)]
        );
    }

    #[test]
    fn ai_ingredient_past_the_lookup_bound_is_still_found() {
        let mut actions = vec![
            json!({ "action": "c2pa.created", "digitalSourceType": format!("{DST}digitalCapture") }),
        ];
        actions.extend(vec![json!({ "action": "c2pa.cropped" }); MAX_HISTORY + 5]);
        actions.push(json!({ "action": "c2pa.placed", "parameters": link("c2pa.ingredient") }));
        let s = store(
            json!(actions),
            json!([{ "label": "c2pa.ingredient", "active_manifest": "generator" }]),
        );
        assert_eq!(
            found(&read_store(&s, Trusted)),
            [(AI, Origin::Ai, Strength::Strong)]
        );
    }

    #[test]
    fn warnings_and_generator_follow_the_validation_state() {
        let s = opened_from("generator", json!([{ "action": "c2pa.cropped" }]));
        let trusted = read_store(&s, Trusted);
        assert!(trusted.warnings.is_empty());
        assert_eq!(trusted.generator.as_deref(), Some("Photo Editor"));

        let valid = read_store(&s, Valid);
        assert_eq!(
            valid.warnings,
            ["C2PA manifest is valid but its signer is not in the trust list"]
        );
        assert_eq!(valid.generator.as_deref(), Some("Photo Editor"));
        assert_eq!(valid.history_summary, Some(HistorySummary::AiThenEdited));

        let invalid = read_store(&s, Invalid);
        assert_eq!(
            invalid.warnings,
            ["C2PA manifest is invalid: the file changed after signing, or the manifest is broken"]
        );
        assert_eq!(invalid.generator, None);
        assert_eq!(invalid.history_summary, None);
        assert_eq!(invalid.history, trusted.history);
        assert_eq!(invalid.history.len(), 2);
    }

    #[test]
    fn store_without_active_manifest_is_no_provenance() {
        assert!(interpret(&json!({ "manifests": {} }), Trusted, &Rules::embedded().dst).is_none());
    }

    #[test]
    fn history_is_bounded() {
        let long = "é".repeat(300);
        let action = json!({
            "action": format!("vendor.{long}"),
            "digitalSourceType": format!("{DST}{long}"),
            "softwareAgent": long
        });
        let kept = "é".repeat(MAX_FIELD_CHARS);

        let exact = read_store(
            &store(json!(vec![action.clone(); MAX_HISTORY]), json!([])),
            Trusted,
        );
        assert_eq!(exact.history.len(), MAX_HISTORY);
        assert!(exact.warnings.is_empty());
        let first = &exact.history[0];
        assert_eq!(first.action.chars().count(), MAX_FIELD_CHARS);
        assert_eq!(first.digital_source_type.as_deref(), Some(kept.as_str()));
        assert_eq!(first.software.as_deref(), Some(kept.as_str()));

        let over = read_store(
            &store(json!(vec![action; MAX_HISTORY + 1]), json!([])),
            Trusted,
        );
        assert_eq!(over.history.len(), MAX_HISTORY);
        assert_eq!(
            over.warnings,
            ["C2PA history truncated to the first 64 actions"]
        );
    }

    #[test]
    fn evidence_detail_bounds_the_action_name() {
        let s = store(
            json!([{ "action": "x".repeat(5000), "digitalSourceType": format!("{DST}trainedAlgorithmicMedia") }]),
            json!([]),
        );
        assert!(read_store(&s, Trusted).evidence[0].detail.len() < 300);
    }

    /// Self-signed C2PA test root ("FOR TESTING_ONLY"), from the c2pa-rs settings tests.
    const TEST_ROOT: &str = "-----BEGIN CERTIFICATE-----
MIICEzCCAcWgAwIBAgIUW4fUnS38162x10PCnB8qFsrQuZgwBQYDK2VwMHcxCzAJ
BgNVBAYTAlVTMQswCQYDVQQIDAJDQTESMBAGA1UEBwwJU29tZXdoZXJlMRowGAYD
VQQKDBFDMlBBIFRlc3QgUm9vdCBDQTEZMBcGA1UECwwQRk9SIFRFU1RJTkdfT05M
WTEQMA4GA1UEAwwHUm9vdCBDQTAeFw0yMjA2MTAxODQ2NDFaFw0zMjA2MDcxODQ2
NDFaMHcxCzAJBgNVBAYTAlVTMQswCQYDVQQIDAJDQTESMBAGA1UEBwwJU29tZXdo
ZXJlMRowGAYDVQQKDBFDMlBBIFRlc3QgUm9vdCBDQTEZMBcGA1UECwwQRk9SIFRF
U1RJTkdfT05MWTEQMA4GA1UEAwwHUm9vdCBDQTAqMAUGAytlcAMhAGPUgK9q1H3D
eKMGqLGjTXJSpsrLpe0kpxkaFMe7KUAuo2MwYTAdBgNVHQ4EFgQUXuZWArP1jiRM
fgye6ZqRyGupTowwHwYDVR0jBBgwFoAUXuZWArP1jiRMfgye6ZqRyGupTowwDwYD
VR0TAQH/BAUwAwEB/zAOBgNVHQ8BAf8EBAMCAYYwBQYDK2VwA0EA8E79g54u2fUy
dfVLPyqKmtjenOUMvVQD7waNbetLY7kvUJZCd5eaDghk30/Q1RaNjiP/2RfA/it8
zGxQnM2hCA==
-----END CERTIFICATE-----
";

    #[test]
    fn trust_anchors_must_hold_a_usable_certificate() {
        assert_eq!(validate_trust_anchors(TEST_ROOT), Ok(()));
        assert_eq!(
            validate_trust_anchors(&format!("# roots\n{TEST_ROOT}{TEST_ROOT}")),
            Ok(())
        );
        let no_block = [
            "",
            "not a pem file",
            "-----BEGIN CERTIFICATE-----\nMIIC",
            "-----BEGIN PRIVATE KEY-----\nMIIC\n-----END PRIVATE KEY-----\n",
            // A base64 line alone: c2pa would take it for a certificate hash list.
            "aGVsbG8gd29ybGQ=\n",
        ];
        for pem in no_block {
            let err = validate_trust_anchors(pem).unwrap_err();
            assert!(err.contains("no PEM certificate block"), "{pem:?}: {err}");
        }
        let junk = "-----BEGIN CERTIFICATE-----\nnot base64 at all\n-----END CERTIFICATE-----\n";
        let err = validate_trust_anchors(junk).unwrap_err();
        assert!(err.contains("no certificate that can be loaded"), "{err}");
    }
}
