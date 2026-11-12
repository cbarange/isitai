//! Usage: isitai [--anchors roots.pem] [--effort fast|standard] [--max-bytes N] [--text "string"] [FILE|-...]
//! Options apply to the files that follow them. `--anchors` replaces the embedded
//! C2PA trust lists, for signers and for time-stamps.
//! `-` reads standard input, whole and into memory, up to `--max-bytes` (default 256 MiB).
//! Prints one JSON report per input. Exit: 0 nothing found (which does not mean
//! human-made), 1 AI signal or proof, 2 error.

use isitai::{
    check_reader, check_stream, check_text, validate_trust_anchors, Options, Report, Rules,
    Verdict, DEFAULT_MAX_STREAM_BYTES,
};
use std::process::ExitCode;

fn main() -> ExitCode {
    let mut args = std::env::args().skip(1);
    let mut opts = Options::default();
    let mut max_bytes = DEFAULT_MAX_STREAM_BYTES;
    let mut reports = Vec::new();
    let rules = Rules::embedded();
    let mut error = false;

    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--anchors" => match read_anchors(args.next()) {
                Ok(pem) => opts.trust_anchors_pem = Some(pem),
                Err(e) => return usage(&e),
            },
            "--effort" => match args.next().as_deref().map(str::parse) {
                Some(Ok(effort)) => opts.effort = effort,
                Some(Err(e)) => return usage(&e),
                None => return usage("--effort needs a value"),
            },
            "--max-bytes" => match args.next().map(|n| n.parse()) {
                Some(Ok(n)) => max_bytes = n,
                _ => return usage("--max-bytes needs a number of bytes"),
            },
            "--text" => match args.next() {
                Some(t) => reports.push(serde_json::to_value(check_text(&t, &rules)).unwrap()),
                None => return usage("--text needs a value"),
            },
            "-h" | "--help" => return usage(""),
            unknown if unknown.starts_with("--") => {
                return usage(&format!("unknown option `{unknown}`"))
            }
            "-" => match check_stream(std::io::stdin().lock(), max_bytes, &opts, &rules) {
                Ok(report) => reports.push(with_path(report, "-")),
                Err(e) => {
                    eprintln!("-: {e}");
                    error = true;
                }
            },
            path => match open_file(path) {
                Ok(file) => {
                    let file_opts = Options {
                        declared_mime: mime_from_ext(path),
                        ..opts.clone()
                    };
                    let report = check_reader(std::io::BufReader::new(file), &file_opts, &rules);
                    reports.push(with_path(report, path));
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

/// The report as printed for a file argument: with the argument as `path`.
fn with_path(report: Report, path: &str) -> serde_json::Value {
    let mut v = serde_json::to_value(report).unwrap();
    v["path"] = path.into();
    v
}

/// Reads the PEM bundle given to `--anchors` and checks that it is usable.
fn read_anchors(path: Option<String>) -> Result<String, String> {
    let path = path.ok_or("--anchors needs a PEM file")?;
    let pem = std::fs::read_to_string(&path).map_err(|e| format!("--anchors {path}: {e}"))?;
    validate_trust_anchors(&pem).map_err(|e| format!("--anchors {path}: {e}"))?;
    Ok(pem)
}

/// Opens a regular file. A directory opens without error on Unix and fails with
/// "Access is denied" on Windows, so it is refused first, with one message everywhere.
fn open_file(path: &str) -> std::io::Result<std::fs::File> {
    if std::fs::metadata(path)?.is_dir() {
        return Err(std::io::Error::other("is a directory"));
    }
    std::fs::File::open(path)
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
    eprintln!(
        "usage: isitai [--anchors roots.pem] [--effort fast|standard] [--max-bytes N] [--text \"string\"] [FILE|-...]"
    );
    eprintln!("Options apply to the files that follow them.");
    eprintln!("- reads standard input, whole and into memory, up to --max-bytes (default {DEFAULT_MAX_STREAM_BYTES}).");
    eprintln!("--anchors replaces the embedded C2PA trust lists (signers and time-stamps).");
    eprintln!("Exit code: 0 nothing found, 1 AI signal or proof, 2 error.");
    eprintln!("Exit code 0 does not mean human-made: it means no proof and no signal was found.");
    ExitCode::from(2)
}
