"""Headless interaction, worker lifecycle, and terminal geometry regressions."""

from __future__ import annotations

import asyncio
import json
import subprocess
from collections.abc import Callable
from dataclasses import replace
from threading import Event

import pytest
from kotekomi_adapters.extraction_view.render import annotated_rows, profile_annotations
from kotekomi_adapters.extraction_view.tui import (
    MessageStream,
    ReplayApp,
    SourcePane,
)
from kotekomi_application.ingestion_debug_summary import DebugSummary
from kotekomi_application.ingestion_inspection import ParagraphSnapshot
from rich.text import Text
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.widgets import Static

from packages.pipelines.tests.test_replay_reader import example_profile


def content(app: ReplayApp, selector: str) -> str:
    visual = app.query_one(selector, Static).content
    assert isinstance(visual, Text)
    return visual.plain


def test_layers_selection_resize_and_completion_stay_inspectable() -> None:
    profile = example_profile()

    def operation(
        publish: Callable[[ParagraphSnapshot], None], out: MessageStream, err: MessageStream
    ) -> int:
        publish(ParagraphSnapshot(0, 1, profile, "complete"))
        out.write("Ingestion run: igr_example\n")
        return 0

    async def scenario() -> None:
        app = ReplayApp(operation, mode="replay", cancel=lambda: None)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause()
            assert app.finished
            assert "Browse intelligence" in content(app, "#status")
            source = content(app, "#source")
            assert "Mention · organization" in source
            assert "Grounding · Acme Corporation" in source
            assert "Proposal · Organization, Event" in source
            await pilot.press("n")
            assert app.selected_keys[0] == "hp1_mentions:0"
            assert 'Source: "Acme Corp"' in content(app, "#inspector")
            await pilot.press("3")
            assert "Grounding ·" not in content(app, "#source")
            assert app.selected_keys[0] == "hp1_mentions:0"
            await pilot.press("3")
            assert "Grounding ·" in content(app, "#source")
            await pilot.resize_terminal(50, 20)
            await pilot.pause()
            assert app.screen.has_class("narrow")
            assert app.selected_keys[0] == "hp1_mentions:0"
            await pilot.press("q")
            assert app.return_value == 0

    asyncio.run(scenario())


def test_long_frames_scroll_and_selection_survives_new_phase() -> None:
    profile = example_profile()
    profile = replace(profile, text=profile.text + "\n" + ("source line\n" * 80))
    first = replace(profile, present_stages=frozenset({"hp1_mentions"}))
    advance = Event()
    posted = Event()
    completed = Event()

    def operation(
        publish: Callable[[ParagraphSnapshot], None], out: MessageStream, err: MessageStream
    ) -> int:
        publish(ParagraphSnapshot(0, 1, first))
        posted.set()
        assert advance.wait(5)
        publish(ParagraphSnapshot(0, 1, profile, "complete"))
        completed.set()
        return 0

    async def scenario() -> None:
        app = ReplayApp(operation, mode="replay", cancel=lambda: None)
        async with app.run_test(size=(80, 24)) as pilot:
            try:
                assert await asyncio.to_thread(posted.wait, 2)
                await pilot.pause()
                await pilot.press("n")
                pane = app.query_one("#source-scroll", VerticalScroll)
                pane.scroll_to(y=25, animate=False)
                await pilot.pause()
                before = pane.scroll_y
                assert before > 0
                width = app.query_one(SourcePane).content_size.width
                before_offset = annotated_rows(first, app.visible_stages, width)[
                    int(before)
                ].source_start
                advance.set()
                assert await asyncio.to_thread(completed.wait, 2)
                await pilot.pause()
                assert app.selected_keys[0] == "hp1_mentions:0"
                after_rows = annotated_rows(profile, app.visible_stages, width)
                assert after_rows[int(pane.scroll_y)].source_start == before_offset
                assert "Grounding ·" in content(app, "#source")
                assert "\033" not in content(app, "#source")
                await pilot.resize_terminal(45, 18)
                await pilot.pause()
                assert pane.max_scroll_y > 0
            finally:
                advance.set()

    asyncio.run(scenario())


def test_browsing_pauses_follow_and_can_resume_latest_paragraph() -> None:
    profile = example_profile()

    def operation(
        publish: Callable[[ParagraphSnapshot], None], out: MessageStream, err: MessageStream
    ) -> int:
        publish(ParagraphSnapshot(0, 2, profile, "complete"))
        publish(ParagraphSnapshot(1, 2, profile, "complete"))
        return 0

    async def scenario() -> None:
        app = ReplayApp(operation, mode="replay", cancel=lambda: None)
        async with app.run_test(size=(110, 30)) as pilot:
            await pilot.pause()
            assert app.current == 1
            await pilot.press("left_square_bracket")
            assert app.current == 0
            assert not app.following
            await pilot.press("f")
            assert app.following
            assert app.current == 1

    asyncio.run(scenario())


@pytest.mark.parametrize("key", ["q", "ctrl+c"])
def test_quit_during_worker_execution_cancels_and_returns_promptly(key: str) -> None:
    advance = Event()
    posted = Event()

    def operation(
        publish: Callable[[ParagraphSnapshot], None], out: MessageStream, err: MessageStream
    ) -> int:
        publish(ParagraphSnapshot(0, 1, example_profile()))
        posted.set()
        assert advance.wait(5)
        err.write("A typed ingestion failure\n")
        return 7

    async def scenario() -> None:
        app = ReplayApp(operation, mode="replay", cancel=advance.set)
        async with app.run_test() as pilot:
            try:
                assert await asyncio.to_thread(posted.wait, 2)
                await pilot.pause()
                await pilot.press(key)
                assert app.exit_requested
                assert not app.finished
                assert advance.is_set()
                assert app.operation_code == app.return_value == 130
            finally:
                advance.set()

    asyncio.run(scenario())


def test_worker_failure_remains_visible_and_final_view_is_retained() -> None:
    def operation(
        publish: Callable[[ParagraphSnapshot], None], out: MessageStream, err: MessageStream
    ) -> int:
        publish(ParagraphSnapshot(0, 1, example_profile()))
        raise ValueError("fixture failure")

    async def scenario() -> None:
        app = ReplayApp(operation, mode="replay", cancel=lambda: None)
        async with app.run_test() as pilot:
            await pilot.pause()
            assert app.finished and app.operation_code == 1
            assert "fixture failure" in content(app, "#error")
            assert "Mention ·" in content(app, "#source")
            await pilot.press("q")
            assert app.return_value == 1

    asyncio.run(scenario())


def test_mouse_selects_annotation_and_monochrome_keeps_labels(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("NO_COLOR", "1")
    profile = example_profile()

    def operation(
        publish: Callable[[ParagraphSnapshot], None], out: MessageStream, err: MessageStream
    ) -> int:
        publish(ParagraphSnapshot(0, 1, profile, "complete"))
        return 0

    async def scenario() -> None:
        app = ReplayApp(operation, mode="replay", cancel=lambda: None)
        async with app.run_test(size=(120, 32)) as pilot:
            await pilot.pause()
            assert await pilot.click(SourcePane, offset=(3, 1))
            await pilot.pause()
            assert app.selected_keys[0] == "hp1_mentions:0"
            rows = annotated_rows(profile, profile.present_stages, 100, color=False)
            labels = [row for row in rows if row.annotation_key]
            assert len(labels) == len(profile_annotations(profile))
            assert all(
                span.style.color is None
                for row in labels
                for span in row.text.spans
                if not isinstance(span.style, str)
            )

    asyncio.run(scenario())


@pytest.mark.parametrize("remote_mac", [False, True])
def test_copy_exports_browsed_paragraph_layers_selection_and_viewport(
    monkeypatch: pytest.MonkeyPatch,
    remote_mac: bool,
) -> None:
    from kotekomi_adapters.extraction_view import clipboard

    monkeypatch.setattr(clipboard, "platform", "darwin" if remote_mac else "linux")
    if remote_mac:
        monkeypatch.setenv("SSH_CONNECTION", "fixture remote session")
    profile = example_profile()
    profile = replace(profile, text=profile.text + "\n" + ("Unicode café 🐈\tline\n" * 80))

    def operation(
        publish: Callable[[ParagraphSnapshot], None], out: MessageStream, err: MessageStream
    ) -> int:
        publish(ParagraphSnapshot(0, 2, profile, "complete"))
        publish(ParagraphSnapshot(1, 2, example_profile(), "complete"))
        return 0

    async def scenario() -> None:
        app = ReplayApp(operation, mode="replay", cancel=lambda: None)
        async with app.run_test(size=(100, 24)) as pilot:
            await pilot.pause()
            assert "Replay of saved results complete" in content(app, "#status")
            await pilot.press("left_square_bracket", "3", "n", "n")
            pane = app.query_one("#source-scroll", VerticalScroll)
            pane.scroll_to(y=25, animate=False)
            await pilot.pause()
            await pilot.press("c")
            captured = DebugSummary.model_validate_json(app.clipboard)
            assert captured.paragraph_ordinal == app.current == 0
            assert app.latest == 1
            assert captured.source.text == profile.text
            assert captured.operation.mode == "replay"
            assert captured.operation.status == "complete"
            assert captured.operation.exit_code == 0
            assert captured.selected_record_id == "ref_fixture"
            assert "hp3_grounding" not in captured.records
            assert "hp2_references" in captured.records
            assert not next(p for p in captured.phases if p.stage == "hp3_grounding").enabled
            assert "view" not in json.loads(app.clipboard)
            assert "\033" not in app.clipboard
            for binding in app.BINDINGS:
                assert isinstance(binding, Binding)
                assert binding.key != "s"

    asyncio.run(scenario())


def test_native_mac_copy_freezes_running_state_and_keeps_ingestion_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from kotekomi_adapters.extraction_view import clipboard

    monkeypatch.setattr(clipboard, "platform", "darwin")
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    monkeypatch.delenv("SSH_TTY", raising=False)
    payloads: list[str] = []

    def pbcopy(
        command: list[str], *, input: str, encoding: str, check: bool, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        assert command == ["pbcopy"]
        assert encoding == "utf-8" and check and timeout == 2
        payloads.append(input)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", pbcopy)
    advance, posted = Event(), Event()
    profile = example_profile()

    def operation(
        publish: Callable[[ParagraphSnapshot], None], out: MessageStream, err: MessageStream
    ) -> int:
        publish(ParagraphSnapshot(0, 1, profile))
        posted.set()
        assert advance.wait(5)
        publish(
            ParagraphSnapshot(0, 1, replace(profile, text=profile.text + " Updated."), "complete")
        )
        return 0

    async def scenario() -> None:
        app = ReplayApp(operation, mode="ingestion", cancel=lambda: None)
        async with app.run_test() as pilot:
            try:
                assert await asyncio.to_thread(posted.wait, 2)
                await pilot.pause()
                assert "Ingestion running" in content(app, "#status")
                await pilot.press("c")
                assert len(payloads) == 1
                captured = DebugSummary.model_validate_json(payloads[0])
                assert captured.operation.mode == "ingestion"
                assert captured.operation.status == "running"
                assert captured.operation.exit_code is None
                assert not app.finished and not app.exit_requested
                advance.set()
                await pilot.pause()
                assert app.finished
                assert "Ingestion complete" in content(app, "#status")
                assert app.snapshots[0].profile.text.endswith(" Updated.")
                assert captured.source.text == profile.text
                assert json.loads(payloads[0])["operation"]["status"] == "running"
            finally:
                advance.set()

    asyncio.run(scenario())


@pytest.mark.parametrize("failure", ["unavailable", "timeout"])
def test_clipboard_failure_is_visible_and_does_not_change_operation(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    from kotekomi_adapters.extraction_view import clipboard

    monkeypatch.setattr(clipboard, "platform", "darwin")
    monkeypatch.delenv("SSH_CONNECTION", raising=False)
    monkeypatch.delenv("SSH_TTY", raising=False)
    notices: list[tuple[str, str]] = []

    def pbcopy(
        command: list[str], *, input: str, encoding: str, check: bool, timeout: int
    ) -> subprocess.CompletedProcess[str]:
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, timeout)
        raise FileNotFoundError("pbcopy unavailable")

    def notify(message: str, *, severity: str = "information") -> None:
        notices.append((message, severity))

    monkeypatch.setattr(subprocess, "run", pbcopy)

    def operation(
        publish: Callable[[ParagraphSnapshot], None], out: MessageStream, err: MessageStream
    ) -> int:
        publish(ParagraphSnapshot(0, 1, example_profile(), "complete", "A presentation failure"))
        return 7

    async def scenario() -> None:
        app = ReplayApp(operation, mode="replay", cancel=lambda: None)
        monkeypatch.setattr(app, "notify", notify)
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("c")
            assert notices[-1][0].startswith("Snapshot copy failed:")
            assert notices[-1][1] == "error"
            assert app.finished and app.operation_code == 7
            assert "Mention ·" in content(app, "#source")
            assert "A presentation failure" in content(app, "#error")
            await pilot.press("q")
            assert app.return_value == 7

    asyncio.run(scenario())


def test_copy_before_source_arrives_reports_no_paragraph(monkeypatch: pytest.MonkeyPatch) -> None:
    advance = Event()
    notices: list[str] = []

    def notify(message: str, *, severity: str = "information") -> None:
        notices.append(message)

    def operation(
        publish: Callable[[ParagraphSnapshot], None], out: MessageStream, err: MessageStream
    ) -> int:
        assert advance.wait(5)
        return 0

    async def scenario() -> None:
        app = ReplayApp(operation, mode="replay", cancel=lambda: None)
        monkeypatch.setattr(app, "notify", notify)
        async with app.run_test() as pilot:
            try:
                await pilot.press("c")
                assert notices == ["No paragraph is available to copy yet."]
                assert app.clipboard == ""
                assert not app.exit_requested
            finally:
                advance.set()

    asyncio.run(scenario())
