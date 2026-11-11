"""isitai: find proof or signals that a text or file was made by AI.

Every function returns a dict with the same keys as the Node.js package and the CLI:
``verdict`` ("ai-proven", "capture-proven", "ai-signal", "inconsistent", "no-signal"),
``media``, ``generator``, ``evidence``, ``warnings``, ``version``.

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
) -> Report:
    """Checks a file by path. The file is streamed, never loaded whole.

    ``trust_anchors_pem``: PEM bundle of trusted C2PA roots. Without it, a valid
    C2PA manifest gives at most ``ai-signal``.
    """
    return json.loads(_isitai.check_file_json(os.fspath(path), trust_anchors_pem, declared_mime))


def check(
    data: Union[bytes, bytearray, memoryview],
    *,
    trust_anchors_pem: Optional[str] = None,
    declared_mime: Optional[str] = None,
) -> Report:
    """Checks in-memory bytes (an upload). Prefer ``check_file`` for files on disk."""
    return json.loads(_isitai.check_bytes_json(bytes(data), trust_anchors_pem, declared_mime))
