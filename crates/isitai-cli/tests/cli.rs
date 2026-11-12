//! Exit codes and argument handling of the `isitai` binary.

use std::path::PathBuf;
use std::process::{Command, Output};

const AI_TEXT: &str = "Paris :contentReference[oaicite:0]{index=0}.";

fn isitai(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_isitai"))
        .args(args)
        .output()
        .expect("the binary runs")
}

fn code(out: &Output) -> i32 {
    out.status.code().expect("exit code")
}

fn stderr(out: &Output) -> String {
    String::from_utf8_lossy(&out.stderr).into_owned()
}

/// A fresh directory for one test, with one file in it.
fn file(test: &str, name: &str, content: &str) -> (PathBuf, String) {
    let dir = std::env::temp_dir().join(format!("isitai-cli-{}-{test}", std::process::id()));
    std::fs::create_dir_all(&dir).unwrap();
    let path = dir.join(name);
    std::fs::write(&path, content).unwrap();
    (dir, path.to_str().unwrap().to_string())
}

#[test]
fn exit_0_when_nothing_is_found() {
    let (_, path) = file("nothing", "note.txt", "Bonjour, je rentre demain soir.");
    let out = isitai(&[&path]);
    assert_eq!(code(&out), 0);
    assert!(String::from_utf8_lossy(&out.stdout).contains("\"no-signal\""));
}

#[test]
fn exit_1_on_an_ai_signal() {
    assert_eq!(code(&isitai(&["--text", AI_TEXT])), 1);
    let (_, path) = file("signal", "page.html", &format!("<p>{AI_TEXT}</p>"));
    let out = isitai(&[&path]);
    assert_eq!(code(&out), 1);
    assert!(String::from_utf8_lossy(&out.stdout).contains("\"text.oaicite\""));
}

#[test]
fn unknown_option_is_a_usage_error() {
    let (_, path) = file("unknown", "note.txt", "Bonjour.");
    for option in ["--json", "--effrot", "--"] {
        let out = isitai(&[&path, option]);
        assert_eq!(code(&out), 2, "{option}");
        assert!(stderr(&out).contains(&format!("unknown option `{option}`")));
        assert!(out.stdout.is_empty());
    }
}

#[test]
fn unknown_effort_is_a_usage_error() {
    let out = isitai(&["--effort", "thorough", "--text", "x"]);
    assert_eq!(code(&out), 2);
    assert!(stderr(&out).contains("unknown effort `thorough` (expected fast or standard)"));
    assert_eq!(code(&isitai(&["--effort", "fast", "--text", "x"])), 0);
    assert_eq!(code(&isitai(&["--effort", "standard", "--text", "x"])), 0);
    assert_eq!(code(&isitai(&["--effort"])), 2);
}

#[test]
fn directory_is_an_error() {
    let (dir, path) = file("directory", "ai.txt", AI_TEXT);
    let out = isitai(&[dir.to_str().unwrap()]);
    assert_eq!(code(&out), 2);
    assert!(stderr(&out).contains("is a directory"));
    // The error wins over a signal found in another file.
    assert_eq!(code(&isitai(&[&path, dir.to_str().unwrap()])), 2);
}

#[test]
fn missing_file_is_an_error() {
    assert_eq!(code(&isitai(&["/definitely/missing.jpg"])), 2);
}

#[test]
fn unusable_anchors_are_a_usage_error() {
    let (_, note) = file("anchors", "note.txt", "Bonjour.");
    let (_, empty) = file("anchors", "empty.pem", "");
    let (_, junk) = file(
        "anchors",
        "junk.pem",
        "-----BEGIN CERTIFICATE-----\nnot base64\n-----END CERTIFICATE-----\n",
    );
    for (pem, message) in [
        (&empty, "no PEM certificate block"),
        (&junk, "no certificate that can be loaded"),
    ] {
        let out = isitai(&["--anchors", pem, &note]);
        assert_eq!(code(&out), 2);
        assert!(stderr(&out).contains(message), "{}", stderr(&out));
        assert!(stderr(&out).contains(pem.as_str()));
        assert!(out.stdout.is_empty());
    }
    assert_eq!(
        code(&isitai(&["--anchors", "/definitely/missing.pem", &note])),
        2
    );
    assert_eq!(code(&isitai(&["--anchors"])), 2);
}

#[test]
fn usage_says_what_options_and_exit_code_0_mean() {
    for args in [&["--help"][..], &[]] {
        let out = isitai(args);
        assert_eq!(code(&out), 2);
        let usage = stderr(&out);
        assert!(usage.contains("[--effort fast|standard]"));
        assert!(usage.contains("Options apply to the files that follow them."));
        assert!(usage.contains("Exit code 0 does not mean human-made"));
    }
}
