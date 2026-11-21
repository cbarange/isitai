"""isitai: find proof or signals that a text or file was made by AI.

Every function returns a dict with the same keys as the Node.js package and the CLI:
``verdict`` ("ai-proven", "capture-proven", "ai-signal", "inconsistent", "ai-likely",
"no-signal"), ``media``, ``generator``, ``evidence``, ``warnings``, ``history``,
``history_summary``, ``coefficient``, ``notes``, ``version``.

``coefficient`` is the statistical score of a plain text (detector ``text-light-v1``):
``{"lr", "lr_interval", "coverage", "calibration_id", "prevalence_used", "posterior"}``.
``lr`` is a likelihood ratio (how much more often this score is seen on AI text than on
human text in the calibration data), **not** the probability that the text is AI-made.
``posterior`` is that probability and stays ``None`` unless you pass ``prevalence``, the
share of AI text you expect. Every field is ``None`` when the detector abstains: text
under 150 words, or no calibration table for its language (today: English only); a
warning says which. The key is absent when ``score=False`` or the input is not plain
text. ``ai-likely`` means no proof, no signal, and a score above the 1 % false-positive
threshold of the table: an estimate with a measured error rate, never a proof. Do not
use it to grade or accuse a person: writers who are not native speakers are known to be
flagged more often by this kind of detector.

``history`` (absent when empty) lists the actions of the active C2PA manifest in order,
at most 64: ``{"action", "digital_source_type"?, "software"?}``. ``digital_source_type``
is the one the action declares or, failing that, the type of the first action of the
ingredient it refers to. ``history_summary`` (absent when the history establishes nothing)
is ``"ai-then-edited"`` or ``"capture-then-ai-edited"``.
The history is what the manifest declares; it is not evidence and the verdict ignores it.

``no-signal`` never means "human": it means nothing was found.
Text spans in ``evidence[].location`` are UTF-8 byte offsets; use ``location["text"]``.
For a file in another encoding (UTF-16 with a byte order mark, Windows-1252) they are
offsets in the decoded text, and a warning names the encoding.

isitai makes no network request. For a remote file, open it with your own client and
give the response to ``check_stream``.
"""
from __future__ import annotations

import json
import os
from typing import Any, BinaryIO, Dict, Optional, Union

from . import _isitai

__all__ = ["check", "check_text", "check_file", "check_stream", "DEFAULT_MAX_STREAM_BYTES"]

Report = Dict[str, Any]

#: Default ``max_bytes`` of ``check_stream``: 256 MiB.
DEFAULT_MAX_STREAM_BYTES: int = _isitai.DEFAULT_MAX_STREAM_BYTES

_READ_SIZE = 1024 * 1024


def check_text(
    text: str, *, score: bool = True, prevalence: Optional[float] = None
) -> Report:
    """Checks a text string: AI copy-paste artifacts, and the statistical score.

    ``score``: ``False`` turns the statistical score off (no ``coefficient`` key).
    ``prevalence``: share of AI text you expect among the texts you check, strictly
    between 0 and 1; anything else raises ``ValueError``. With it the report gives
    ``coefficient["posterior"]``; without it a likelihood ratio only.
    """
    return json.loads(_isitai.check_text_json(text, score, prevalence))


def check_file(
    path: Union[str, "os.PathLike[str]"],
    *,
    trust_anchors_pem: Optional[str] = None,
    declared_mime: Optional[str] = None,
    effort: Optional[str] = None,
    score: bool = True,
    prevalence: Optional[float] = None,
) -> Report:
    """Checks a file by path. The file is streamed, never loaded whole.

    ``trust_anchors_pem``: PEM bundle of trusted C2PA roots. It replaces the default,
    which is the trust lists embedded in the library: the two official C2PA lists
    (manifest signers, time-stamp authorities) and the older interim list. The bundle
    is used for signers and for time-stamps, so it must also hold the roots of the
    time-stamps to trust. A valid C2PA manifest whose signer
    does not chain to the roots in use gives at most ``ai-signal``. A bundle without
    a usable certificate raises ``ValueError``.

    ``effort``: ``"standard"`` (default; every layer) or ``"fast"``. ``"fast"`` skips
    the XMP scan of the whole file; C2PA validation may still read a signed file whole;
    ``"fast"`` can miss unsigned metadata, including a contradiction that ``"standard"``
    would report. An unknown value raises ``ValueError``.

    Text rules also run on the content of text-like files (HTML, XML, SVG, shell script).

    ``score`` and ``prevalence``: as in ``check_text``; they apply to plain text files
    only (markup is not scored).
    """
    return json.loads(
        _isitai.check_file_json(
            os.fspath(path), trust_anchors_pem, declared_mime, effort, score, prevalence
        )
    )


def check(
    data: Union[bytes, bytearray, memoryview],
    *,
    trust_anchors_pem: Optional[str] = None,
    declared_mime: Optional[str] = None,
    effort: Optional[str] = None,
    score: bool = True,
    prevalence: Optional[float] = None,
) -> Report:
    """Checks in-memory bytes (an upload). Prefer ``check_file`` for files on disk.

    Same keyword arguments as ``check_file``.
    """
    return json.loads(
        _isitai.check_bytes_json(
            bytes(data), trust_anchors_pem, declared_mime, effort, score, prevalence
        )
    )


def check_stream(
    fileobj: BinaryIO,
    *,
    max_bytes: int = DEFAULT_MAX_STREAM_BYTES,
    trust_anchors_pem: Optional[str] = None,
    declared_mime: Optional[str] = None,
    effort: Optional[str] = None,
    score: bool = True,
    prevalence: Optional[float] = None,
) -> Report:
    """Checks a stream that cannot seek: any binary object with ``read(size)``.

    Examples: ``urllib.request.urlopen(url)``, a boto3 ``StreamingBody``,
    ``sys.stdin.buffer``, the ``raw`` of a ``requests`` response (set
    ``raw.decode_content = True`` first, or a compressed body arrives compressed).
    The caller opens the source: isitai makes no network request.

    The stream is read into memory in chunks, up to ``max_bytes``, then checked like
    ``check``. A stream that holds more than ``max_bytes`` raises ``ValueError``: a cut
    file is never analysed, because its C2PA result would be wrong. A ``read`` that
    returns ``str`` (a file opened in text mode) raises ``TypeError``.

    Same other keyword arguments as ``check_file``.
    """
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int):
        raise TypeError(f"max_bytes must be an int, got {type(max_bytes).__name__}")
    if max_bytes < 0:
        raise ValueError(f"max_bytes must not be negative, got {max_bytes}")
    # One growing buffer: memory follows the bytes received, not the number of reads.
    data = bytearray()
    while True:
        # One byte more than the limit is enough to know that the stream is too large.
        chunk = fileobj.read(min(_READ_SIZE, max_bytes + 1 - len(data)))
        if chunk is None:
            # A non-blocking stream with no data ready: not the end of the stream.
            raise TypeError("check_stream needs a blocking stream, read() returned None")
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise TypeError(f"check_stream needs a binary stream, read() returned {type(chunk).__name__}")
        if len(chunk) == 0:
            break
        data += chunk  # extends by the chunk's bytes, whatever the memoryview item size
        if len(data) > max_bytes:
            raise ValueError(f"stream is larger than the limit of {max_bytes} bytes")
    return check(
        bytes(data),
        trust_anchors_pem=trust_anchors_pem,
        declared_mime=declared_mime,
        effort=effort,
        score=score,
        prevalence=prevalence,
    )
