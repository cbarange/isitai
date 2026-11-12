//! Exit codes and argument handling of the `isitai` binary.

use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Output, Stdio};

const AI_TEXT: &str = "Paris :contentReference[oaicite:0]{index=0}.";

fn isitai(args: &[&str]) -> Output {
    Command::new(env!("CARGO_BIN_EXE_isitai"))
        .args(args)
        .output()
        .expect("the binary runs")
}

/// Runs the binary with `input` on its standard input.
fn isitai_stdin(args: &[&str], input: &[u8]) -> Output {
    let mut child = Command::new(env!("CARGO_BIN_EXE_isitai"))
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .expect("the binary runs");
    // Dropping the handle closes the pipe. The binary may stop reading at its limit.
    let _ = child.stdin.take().unwrap().write_all(input);
    child.wait_with_output().expect("the binary ends")
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
fn dash_reads_standard_input() {
    let out = isitai_stdin(&["-"], format!("<p>{AI_TEXT}</p>").as_bytes());
    assert_eq!(code(&out), 1);
    let reports: serde_json::Value = serde_json::from_slice(&out.stdout).unwrap();
    assert_eq!(reports[0]["path"], "-");
    assert_eq!(reports[0]["media"], "text/html");
    assert_eq!(reports[0]["evidence"][0]["id"], "text.oaicite");

    // Same report as the same bytes in a file, apart from `path`.
    let (_, path) = file("stdin", "page", &format!("<p>{AI_TEXT}</p>"));
    let mut from_file: serde_json::Value =
        serde_json::from_slice(&isitai(&[&path]).stdout).unwrap();
    from_file[0]["path"] = "-".into();
    assert_eq!(reports, from_file);

    assert_eq!(code(&isitai_stdin(&["-"], b"Bonjour.")), 0);
    assert_eq!(code(&isitai_stdin(&["-"], b"")), 0);
}

#[test]
fn standard_input_over_the_limit_is_an_error() {
    let size = AI_TEXT.len().to_string();
    assert_eq!(
        code(&isitai_stdin(
            &["--max-bytes", &size, "-"],
            AI_TEXT.as_bytes()
        )),
        1
    );
    // One byte over: an error, and no report from a cut input.
    let out = isitai_stdin(&["--max-bytes", "43", "-"], AI_TEXT.as_bytes());
    assert_eq!(code(&out), 2);
    assert!(stderr(&out).contains("-: stream is larger than the limit of 43 bytes"));
    assert!(!String::from_utf8_lossy(&out.stdout).contains("verdict"));

    for args in [&["--max-bytes"][..], &["--max-bytes", "1k", "-"]] {
        let out = isitai_stdin(args, b"x");
        assert_eq!(code(&out), 2);
        assert!(stderr(&out).contains("--max-bytes needs a number of bytes"));
    }
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
        assert!(usage.contains("- reads standard input"));
        assert!(usage.contains("Options apply to the files that follow them."));
        assert!(usage.contains("Exit code 0 does not mean human-made"));
    }
}
