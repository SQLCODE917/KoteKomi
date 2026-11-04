"""Preserve warning blocks across process transport and the Textual stream."""

from __future__ import annotations

import multiprocessing
import warnings

from kotekomi_adapters.extraction_view.execution import ProcessOutput
from kotekomi_adapters.extraction_view.tui import MessageStream, StatusChanged
from kotekomi_application.ingestion_execution import TextEvent
from textual.message import Message


def test_python_warning_survives_both_output_boundaries() -> None:
    warning = warnings.formatwarning(
        "Checkpoint has unused pooler weights.",
        UserWarning,
        "/models/classifier.py",
        123,
        line="    warnings.warn(\n",
    )
    receive, send = multiprocessing.get_context("spawn").Pipe(duplex=False)
    try:
        output = ProcessOutput(send, is_error=True)
        output.write(warning)
        event = TextEvent.model_validate_json(receive.recv_bytes())
        assert event.text == warning.rstrip("\n")
        assert event.is_error
        assert not receive.poll()

        messages: list[StatusChanged] = []

        def post(message: Message) -> bool:
            assert isinstance(message, StatusChanged)
            messages.append(message)
            return True

        stream = MessageStream(post, is_error=True)
        # A warning can arrive in partial writes; preserve its complete block.
        stream.write(event.text[:12])
        assert messages == []
        stream.write(event.text[12:] + "\n")
        assert len(messages) == 1
        assert messages[0].text == warning.rstrip("\n")
        assert messages[0].is_error
        stream.write("Unterminated diagnostic")
        stream.flush()
        assert messages[-1].text == "Unterminated diagnostic"

        output.write("Unterminated diagnostic")
        output.flush()
        tail = TextEvent.model_validate_json(receive.recv_bytes())
        assert tail.text == "Unterminated diagnostic"
    finally:
        send.close()
        receive.close()
