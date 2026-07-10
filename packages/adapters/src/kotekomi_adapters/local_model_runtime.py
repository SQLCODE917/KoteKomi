"""Local model runtime Adapters for Ollama and llama.cpp."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from kotekomi_application import ModelProposal
from kotekomi_application.model_proposal_validation import validate_model_proposal
from kotekomi_domain.models import JsonValue

PROPOSE_ASSERTIONS_PROMPT_ID = "propose_assertions"
DEFAULT_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class LocalModelRuntimeConfig:
    base_url: str
    model_name: str
    context_window: int
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS
    prompt_id: str = PROPOSE_ASSERTIONS_PROMPT_ID


class LocalModelRuntimeError(RuntimeError):
    """A local runtime could not return a valid model proposal response."""


class OllamaModelRuntime:
    def __init__(self, config: LocalModelRuntimeConfig, prompt_text: str) -> None:
        self._config = config
        self._prompt_text = prompt_text

    @property
    def model_name(self) -> str:
        return self._config.model_name

    @property
    def prompt_id(self) -> str:
        return self._config.prompt_id

    def propose_assertions(
        self, *, document_id: str, source_id: str, document_text: str
    ) -> tuple[ModelProposal, ...]:
        payload = {
            "model": self.model_name,
            "messages": _messages(
                self._prompt_text,
                document_id=document_id,
                source_id=source_id,
                document_text=document_text,
            ),
            "format": _proposal_json_schema(),
            "stream": False,
            "think": False,
            "options": {"num_ctx": self._config.context_window},
        }
        response = _post_json(
            _join_url(self._config.base_url, "/api/chat"),
            payload,
            self._config.timeout_seconds,
        )
        message = _object(response, "Ollama response").get("message")
        content = _required_string(
            _object(message, "Ollama response.message"),
            "content",
            "Ollama response.message",
        )
        return _parse_proposals(content, "Ollama response")


class LlamaCppModelRuntime:
    def __init__(self, config: LocalModelRuntimeConfig, prompt_text: str) -> None:
        self._config = config
        self._prompt_text = prompt_text

    @property
    def model_name(self) -> str:
        return self._config.model_name

    @property
    def prompt_id(self) -> str:
        return self._config.prompt_id

    def propose_assertions(
        self, *, document_id: str, source_id: str, document_text: str
    ) -> tuple[ModelProposal, ...]:
        payload = {
            "model": self.model_name,
            "messages": _messages(
                self._prompt_text,
                document_id=document_id,
                source_id=source_id,
                document_text=document_text,
            ),
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": self._config.context_window,
        }
        response = _post_json(
            _join_url(self._config.base_url, "/chat/completions"),
            payload,
            self._config.timeout_seconds,
        )
        choices = _array(
            _object(response, "llama-server response").get("choices"),
            "llama-server response.choices",
        )
        if not choices:
            raise LocalModelRuntimeError("llama-server response.choices must not be empty.")
        choice = _object(choices[0], "llama-server response.choices[0]")
        message = _object(choice.get("message"), "llama-server response.choices[0].message")
        content = _required_string(message, "content", "llama-server response.choices[0].message")
        return _parse_proposals(content, "llama-server response")


def _messages(
    prompt_text: str, *, document_id: str, source_id: str, document_text: str
) -> list[dict[str, str]]:
    return [
        {"role": "system", "content": prompt_text},
        {
            "role": "user",
            "content": (
                "Propose records for this Document only.\n"
                f"source_id: {source_id}\n"
                f"document_id: {document_id}\n\n"
                "Document text follows:\n"
                f"{document_text}"
            ),
        },
    ]


def _proposal_json_schema() -> dict[str, object]:
    return {
        "type": "object",
        "required": ["proposals"],
        "properties": {
            "proposals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["record_type", "stable_label", "record", "evidence"],
                    "properties": {
                        "record_type": {"type": "string"},
                        "stable_label": {"type": "string"},
                        "record": {"type": "object"},
                        "evidence": {"type": "object"},
                    },
                },
            }
        },
    }


def _post_json(url: str, payload: Mapping[str, object], timeout_seconds: float) -> object:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310
            response_text = response.read().decode("utf-8")
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise LocalModelRuntimeError(
            f"Local model runtime returned HTTP {exc.code}: {body}"
        ) from exc
    except URLError as exc:
        raise LocalModelRuntimeError(f"Local model runtime is unavailable: {exc.reason}") from exc
    except TimeoutError as exc:
        raise LocalModelRuntimeError("Local model runtime request timed out.") from exc
    try:
        return json.loads(response_text)
    except json.JSONDecodeError as exc:
        raise LocalModelRuntimeError("Local model runtime returned malformed JSON.") from exc


def _parse_proposals(content: str, context: str) -> tuple[ModelProposal, ...]:
    try:
        payload: object = json.loads(content)
    except json.JSONDecodeError as exc:
        raise LocalModelRuntimeError(f"{context} content is not valid JSON.") from exc
    root = _object(payload, f"{context} content")
    proposal_values = _array(root.get("proposals"), f"{context} content.proposals")
    proposals: list[ModelProposal] = []
    for index, proposal_value in enumerate(proposal_values):
        proposal_context = f"{context} content.proposals[{index}]"
        proposal = _object(proposal_value, proposal_context)
        proposals.append(
            validate_model_proposal(
                ModelProposal(
                    record_type=_required_string(proposal, "record_type", proposal_context),
                    stable_label=_required_string(proposal, "stable_label", proposal_context),
                    record=_json_object(proposal.get("record"), f"{proposal_context}.record"),
                    evidence=_json_object(proposal.get("evidence"), f"{proposal_context}.evidence"),
                )
            )
        )
    return tuple(proposals)


def _join_url(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}{path}"


def _object(value: object, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise LocalModelRuntimeError(f"{context} must be an object.")
    return cast(dict[str, object], value)


def _array(value: object, context: str) -> list[object]:
    if not isinstance(value, list):
        raise LocalModelRuntimeError(f"{context} must be an array.")
    return cast(list[object], value)


def _required_string(payload: dict[str, object], key: str, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise LocalModelRuntimeError(f"{context}.{key} must be a non-empty string.")
    return value


def _json_object(value: object, context: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise LocalModelRuntimeError(f"{context} must be an object.")
    try:
        converted = json.loads(json.dumps(value))
    except TypeError as exc:
        raise LocalModelRuntimeError(f"{context} must contain JSON values.") from exc
    return cast(dict[str, JsonValue], converted)
