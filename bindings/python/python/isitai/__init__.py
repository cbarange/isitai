"""isitai: find proof or signals that a text or file was made by AI.

Every function returns a dict with the same keys as the Node.js package and the CLI:
``verdict`` ("ai-proven", "capture-proven", "ai-signal", "inconsistent", "no-signal"),
``media``, ``generator``, ``evidence``, ``warnings``, ``history``, ``history_summary``,
``version``.

``history`` (absent when empty) lists the actions of the active C2PA manifest in order,
at most 64: ``{"action", "digital_source_type"?, "software"?}``. ``digital_source_type``
is the one the action declares or, failing that, the type of the first action of the
ingredient it refers to. ``history_summary`` (absent when the history establishes nothing)
is ``"ai-then-edited"`` or ``"capture-then-ai-edited"``.
The history is what the manifest declares; it is not evidence and the verdict ignores it.

``no-signal`` never means "human": it means nothing was found.
Text spans in ``evidence[].location`` are UTF-8 byte offsets; use ``location["text"]``.
"""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional, Union

from . import _isitai

__all__ = ["check", "check_text", "check_file"]

Report = Dict[str, Any]


def check_text(text: str) -> Report:
    """Checks a text string for AI copy-paste artifacts."""
    return json.loads(_isitai.check_text_json(text))


def check_file(
    path: Union[str, "os.PathLike[str]"],
    *,
    trust_anchors_pem: Optional[str] = None,
    declared_mime: Optional[str] = None,
    effort: Optional[str] = None,
) -> Report:
    """Checks a file by path. The file is streamed, never loaded whole.

    ``trust_anchors_pem``: PEM bundle of trusted C2PA roots. It replaces the default,
    which is the two official C2PA trust lists embedded in the library (manifest
    signers, time-stamp authorities). The bundle is used for both, so it must also
    hold the roots of the time-stamps to trust. A valid C2PA manifest whose signer
    does not chain to the roots in use gives at most ``ai-signal``. A bundle without
    a usable certificate raises ``ValueError``.

    ``effort``: ``"standard"`` (default; every layer) or ``"fast"``. ``"fast"`` skips
    the XMP scan of the whole file; C2PA validation may still read a signed file whole;
    ``"fast"`` can miss unsigned metadata, including a contradiction that ``"standard"``
    would report. An unknown value raises ``ValueError``.

    Text rules also run on the content of text-like files (HTML, XML, SVG, shell script).
    """
    return json.loads(
        _isitai.check_file_json(os.fspath(path), trust_anchors_pem, declared_mime, effort)
    )


def check(
    data: Union[bytes, bytearray, memoryview],
    *,
    trust_anchors_pem: Optional[str] = None,
    declared_mime: Optional[str] = None,
    effort: Optional[str] = None,
) -> Report:
    """Checks in-memory bytes (an upload). Prefer ``check_file`` for files on disk.

    Same keyword arguments as ``check_file``.
    """
    return json.loads(
        _isitai.check_bytes_json(bytes(data), trust_anchors_pem, declared_mime, effort)
    )
