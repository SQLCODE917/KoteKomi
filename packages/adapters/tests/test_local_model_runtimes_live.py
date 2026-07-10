"""Opt-in live checks for operator-owned local model servers."""

import os
from pathlib import Path

import pytest
from kotekomi_adapters import LlamaServerModelRuntime, OllamaModelRuntime

PROMPT_PATH = Path(__file__).resolve().parents[3] / "prompts/propose_assertions.md"


@pytest.mark.skipif(
    "KOTEKOMI_LIVE_LLAMA_SERVER_MODEL" not in os.environ,
    reason="Set KOTEKOMI_LIVE_LLAMA_SERVER_MODEL to run the llama-server live check.",
)
def test_live_llama_server_passive_readiness() -> None:
    runtime = LlamaServerModelRuntime(
        endpoint=os.environ.get("KOTEKOMI_LIVE_LLAMA_SERVER_ENDPOINT", "http://127.0.0.1:8080/v1"),
        model=os.environ["KOTEKOMI_LIVE_LLAMA_SERVER_MODEL"],
        prompt_text=PROMPT_PATH.read_text(encoding="utf-8"),
        timeout_seconds=300,
        context_tokens=32768,
        max_output_tokens=8192,
    )

    assert runtime.check_readiness().ready is True


@pytest.mark.skipif(
    "KOTEKOMI_LIVE_OLLAMA_MODEL" not in os.environ,
    reason="Set KOTEKOMI_LIVE_OLLAMA_MODEL to run the Ollama live check.",
)
def test_live_ollama_structured_output_readiness() -> None:
    runtime = OllamaModelRuntime(
        endpoint=os.environ.get("KOTEKOMI_LIVE_OLLAMA_ENDPOINT", "http://127.0.0.1:11434"),
        model=os.environ["KOTEKOMI_LIVE_OLLAMA_MODEL"],
        prompt_text=PROMPT_PATH.read_text(encoding="utf-8"),
        timeout_seconds=300,
        context_tokens=16384,
        max_output_tokens=8192,
    )

    assert runtime.check_readiness().ready is True
