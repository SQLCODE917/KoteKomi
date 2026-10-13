"""Local clipboard delivery; no knowledge of extraction semantics."""

import os
import subprocess
from collections.abc import Callable
from sys import platform

from kotekomi_application.ingestion_inspection import InspectionClipboardPort


class ClipboardAdapter(InspectionClipboardPort):
    def __init__(self, terminal_copy: Callable[[str], None]) -> None:
        self.terminal_copy = terminal_copy

    def copy(self, text: str) -> str:
        if platform == "darwin" and not (
            os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_TTY")
        ):
            subprocess.run(["pbcopy"], input=text, encoding="utf-8", check=True, timeout=2)
            return "Copied"
        self.terminal_copy(text)
        return "Sent to terminal clipboard"
