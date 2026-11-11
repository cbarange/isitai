//! Usage: isitai [--anchors roots.pem] [--text "string"] [FILE...]
//! Prints one JSON report per input. Exit: 0 no-signal, 1 AI signal or proof, 2 error.

use isitai::{check_reader, check_text, Options, Rules, Verdict};
use std::process::ExitCode;

fn main() -> ExitCode {
    let mut args = std::env::args().skip(1);
    let mut opts = Options::default();
    let mut reports = Vec::new();
    let rules = Rules::embedded();
    let mut error = false;

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--anchors" => match args.next().map(std::fs::read_to_string) {
                Some(Ok(pem)) => opts.trust_anchors_pem = Some(pem),
                _ => return usage("--anchors needs a readable PEM file"),
            },
            "--text" => match args.next() {
                Some(t) => reports.push(serde_json::to_value(check_text(&t, &rules)).unwrap()),
                None => return usage("--text needs a value"),
            },
            "-h" | "--help" => return usage(""),
            path => match std::fs::File::open(path) {
                Ok(file) => {
                    let file_opts = Options {
                        declared_mime: mime_from_ext(path),
                        ..opts.clone()
                    };
                    let report = check_reader(std::io::BufReader::new(file), &file_opts, &rules);
                    let mut v = serde_json::to_value(report).unwrap();
                    v["path"] = path.into();
                    reports.push(v);
                }
                Err(e) => {
                    eprintln!("{path}: {e}");
                    error = true;
                }
            },
        }
    }
    if reports.is_empty() && !error {
        return usage("");
    }
    println!("{}", serde_json::to_string_pretty(&reports).unwrap());

    let no_signal = serde_json::to_value(Verdict::NoSignal).unwrap();
    let capture = serde_json::to_value(Verdict::CaptureProven).unwrap();
    if error {
        ExitCode::from(2)
    } else if reports
        .iter()
        .all(|r| r["verdict"] == no_signal || r["verdict"] == capture)
    {
        ExitCode::SUCCESS
    } else {
        ExitCode::from(1)
    }
}

/// MIME implied by the file extension, compared with the sniffed type to flag polyglots.
/// Only formats whose sniffed MIME (crate `infer`) matches exactly are listed.
fn mime_from_ext(path: &str) -> Option<String> {
    let ext = std::path::Path::new(path)
        .extension()?
        .to_str()?
        .to_ascii_lowercase();
    let mime = match ext.as_str() {
        "jpg" | "jpeg" => "image/jpeg",
        "png" => "image/png",
        "webp" => "image/webp",
        "gif" => "image/gif",
        "avif" => "image/avif",
        "pdf" => "application/pdf",
        "mp4" => "video/mp4",
        "mov" => "video/quicktime",
        "mp3" => "audio/mpeg",
        _ => return None,
    };
    Some(mime.into())
}

fn usage(msg: &str) -> ExitCode {
    if !msg.is_empty() {
        eprintln!("error: {msg}");
    }
    eprintln!("usage: isitai [--anchors roots.pem] [--text \"string\"] [FILE...]");
    ExitCode::from(2)
}
