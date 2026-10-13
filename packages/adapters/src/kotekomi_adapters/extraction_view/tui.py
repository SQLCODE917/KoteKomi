"""Textual application for live and stored source-attached extraction intelligence."""

from __future__ import annotations

import asyncio
import os
import subprocess
from collections.abc import Callable
from io import StringIO

from kotekomi_application.ingestion_debug_summary import (
    OperationMode,
    SnapshotOperation,
    build_debug_summary,
    phase_statuses,
)
from kotekomi_application.ingestion_inspection import (
    STAGE_ORDER,
    InspectionClipboardPort,
    InspectionControlPort,
    ParagraphSnapshot,
)
from rich.style import Style
from rich.text import Text
from textual import events, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.message import Message
from textual.widgets import Footer, Static

from kotekomi_adapters.extraction_view.clipboard import ClipboardAdapter
from kotekomi_adapters.extraction_view.render import (
    STAGE_COLORS,
    STAGE_LABELS,
    AnnotatedRow,
    annotated_rows,
    profile_annotations,
)


class ParagraphChanged(Message):
    def __init__(self, snapshot: ParagraphSnapshot) -> None:
        super().__init__()
        self.snapshot = snapshot


class StatusChanged(Message):
    def __init__(self, text: str, is_error: bool = False) -> None:
        super().__init__()
        self.text = text
        self.is_error = is_error


class OperationFinished(Message):
    def __init__(self, code: int) -> None:
        super().__init__()
        self.code = code


class MessageStream(StringIO):
    """A worker-owned output stream; posts lines without replacing global stdout."""

    def __init__(self, post: Callable[[Message], bool], *, is_error: bool = False) -> None:
        super().__init__()
        self._post = post
        self._is_error = is_error
        self._pending = ""

    def write(self, text: str) -> int:
        self._pending += text
        while "\n" in self._pending:
            line, self._pending = self._pending.split("\n", 1)
            if line:
                self._post(StatusChanged(line, self._is_error))
        return len(text)

    def flush(self) -> None:
        if self._pending:
            self._post(StatusChanged(self._pending, self._is_error))
            self._pending = ""


class SourcePane(Static):
    can_focus = True

    class AnnotationSelected(Message):
        def __init__(self, key: str) -> None:
            super().__init__()
            self.key = key

    def on_click(self, event: events.Click) -> None:
        key = event.style.meta.get("annotation")
        if isinstance(key, str):
            self.post_message(self.AnnotationSelected(key))


class PhasePane(Static):
    class LayerToggled(Message):
        def __init__(self, index: int) -> None:
            super().__init__()
            self.index = index

    def on_click(self, event: events.Click) -> None:
        index = event.style.meta.get("layer")
        if isinstance(index, int):
            self.post_message(self.LayerToggled(index))


Operation = Callable[[Callable[[ParagraphSnapshot], None], MessageStream, MessageStream], int]


class ReplayApp(App[int]):
    TITLE = "KoteKomi · Extraction intelligence"
    CSS = """
    Screen { background: #080e18; color: #dae8f5; }
    #title { height: 2; color: #63e6ee; text-style: bold; padding: 0 1; }
    #progress { height: auto; max-height: 5; padding: 0 1; }
    #body { height: 1fr; }
    #source-scroll { width: 2fr; border: round #1b6772; }
    #source { height: auto; padding: 0 1; }
    #inspector-scroll { width: 1fr; border: round #414477; }
    #inspector { height: auto; padding: 0 1; }
    #status { height: auto; max-height: 4; padding: 0 1; color: #80cbc4; }
    #error { height: auto; max-height: 4; padding: 0 1; color: #ff8a80; }
    .narrow #body { layout: vertical; }
    .narrow #source-scroll { width: 1fr; height: 2fr; }
    .narrow #inspector-scroll { width: 1fr; height: 1fr; }
    """
    BINDINGS = [
        Binding("q,ctrl+c", "quit", "Quit", priority=True),
        Binding("c", "copy_snapshot", "Copy summary"),
        Binding("left_square_bracket", "paragraph(-1)", "Previous paragraph"),
        Binding("right_square_bracket", "paragraph(1)", "Next paragraph"),
        Binding("f", "follow", "Follow"),
        Binding("n,down", "annotation(1)", "Next annotation"),
        Binding("p,up", "annotation(-1)", "Previous annotation"),
        *[
            Binding(
                str(index + 1), f"layer({index})", f"{index + 1} {STAGE_LABELS[stage]}", show=False
            )
            for index, stage in enumerate(STAGE_ORDER)
        ],
    ]

    def __init__(
        self,
        operation: Operation,
        *,
        mode: OperationMode,
        cancel: InspectionControlPort,
        clipboard: InspectionClipboardPort | None = None,
    ) -> None:
        super().__init__()
        self.operation = operation
        self.cancel_operation = cancel
        self.clipboard_port: InspectionClipboardPort = clipboard or ClipboardAdapter(
            lambda text: self.call_from_thread(self.copy_to_clipboard, text)
        )
        self.mode: OperationMode = mode
        self.snapshots: dict[int, ParagraphSnapshot] = {}
        self.visible_stages = set(STAGE_ORDER)
        self.selected_keys: dict[int, str | None] = {}
        self.current: int | None = None
        self.latest: int | None = None
        self.following = True
        self.finished = False
        self.exit_requested = False
        self.operation_code = 0
        self._scroll_positions: dict[int, AnnotatedRow] = {}
        self._pending_scroll_anchor: AnnotatedRow | None = None
        self._scroll_restore_scheduled = False
        self._rendered_rows: tuple[AnnotatedRow, ...] = ()
        self._rendered_ordinal: int | None = None
        self._status_lines: list[str] = []
        self._operation_error = ""
        self._view_mounted = False
        self._color = os.environ.get("NO_COLOR") is None

    def compose(self) -> ComposeResult:
        yield Static("KOTEKOMI · EXTRACTION INTELLIGENCE", id="title")
        yield PhasePane("Preparing Source…", id="progress")
        with Horizontal(id="body"):
            with VerticalScroll(id="source-scroll"):
                yield SourcePane("Waiting for authoritative text…", id="source", markup=False)
            with VerticalScroll(id="inspector-scroll"):
                yield Static(
                    "Select an annotation to inspect its intelligence.",
                    id="inspector",
                    markup=False,
                )
        yield Static("", id="error", markup=False)
        yield Static("Starting…", id="status", markup=False)
        yield Footer()

    def on_mount(self) -> None:
        self._view_mounted = True
        self._set_layout()
        self.query_one(SourcePane).focus()
        self._refresh_status()
        self._run_operation()

    @work(thread=True, exclusive=True)
    def _run_operation(self) -> None:
        out = MessageStream(self.post_message)
        err = MessageStream(self.post_message, is_error=True)

        def publish(snapshot: ParagraphSnapshot) -> None:
            self.post_message(ParagraphChanged(snapshot))

        try:
            code = self.operation(publish, out, err)
        except Exception as error:
            # Presentation/operation errors are visible; this worker must not kill the screen.
            err.write(f"Operation failed: {error}\n")
            code = 1
        finally:
            out.flush()
            err.flush()
        if not self.exit_requested:
            self.post_message(OperationFinished(code))

    def _set_layout(self, width: int | None = None) -> None:
        self.screen.set_class((self.size.width if width is None else width) < 100, "narrow")

    def on_resize(self, event: events.Resize) -> None:
        self._set_layout(event.size.width)
        if self._view_mounted:
            self.call_after_refresh(self._refresh_view)

    def on_paragraph_changed(self, event: ParagraphChanged) -> None:
        snapshot = event.snapshot
        self.snapshots[snapshot.ordinal] = snapshot
        self.latest = snapshot.ordinal
        if self.current is None or self.following:
            self._switch_paragraph(snapshot.ordinal)
        elif self.current == snapshot.ordinal:
            self._refresh_view()

    def on_status_changed(self, event: StatusChanged) -> None:
        self._status_lines.append(event.text)
        self._status_lines = self._status_lines[-3:]
        if event.is_error:
            self._operation_error = event.text
        self._refresh_status()

    def on_operation_finished(self, event: OperationFinished) -> None:
        if self.exit_requested:
            return
        self.finished = True
        self.operation_code = event.code
        self._refresh_view()
        self._refresh_status()

    def _refresh_status(self) -> None:
        operation_label = "Ingestion" if self.mode == "ingestion" else "Replay of saved results"
        terminal = (
            operation_label + (" complete" if self.operation_code == 0 else " failed")
            if self.finished
            else operation_label + " running"
        )
        if self.finished:
            terminal += " · Browse intelligence or press q to exit"
        self.query_one("#status", Static).update(Text("\n".join([terminal, *self._status_lines])))
        self.query_one("#error", Static).update(Text("\n".join(self._visible_errors())))

    def _visible_errors(self) -> tuple[str, ...]:
        presentation_error = next(
            (
                f"Paragraph {item.ordinal + 1}: {item.error}"
                for item in reversed(tuple(self.snapshots.values()))
                if item.error
            ),
            "",
        )
        return tuple(text for text in (self._operation_error, presentation_error) if text)

    def _switch_paragraph(self, ordinal: int) -> None:
        pane = self.query_one("#source-scroll", VerticalScroll)
        changed = self.current != ordinal
        if changed and self.current is not None and self._rendered_rows:
            self._scroll_positions[self.current] = (
                self._pending_scroll_anchor
                or self._rendered_rows[min(int(pane.scroll_y), len(self._rendered_rows) - 1)]
            )
        self.current = ordinal
        if changed:
            self._pending_scroll_anchor = self._scroll_positions.get(
                ordinal, AnnotatedRow(Text(), 0, 0)
            )
        self._refresh_view()

    def _restore_scroll(self) -> None:
        self._scroll_restore_scheduled = False
        anchor = self._pending_scroll_anchor
        self._pending_scroll_anchor = None
        if anchor is None:
            return
        target = next(
            (
                index
                for index, row in enumerate(self._rendered_rows)
                if anchor.annotation_key is not None and row.annotation_key == anchor.annotation_key
            ),
            None,
        )
        if target is None:
            target = next(
                (
                    index
                    for index, row in enumerate(self._rendered_rows)
                    if row.annotation_key is None
                    and (
                        row.source_start <= anchor.source_start < row.source_end
                        or row.source_start == row.source_end == anchor.source_start
                    )
                ),
                0,
            )
        self.query_one("#source-scroll", VerticalScroll).scroll_to(
            y=target, animate=False, immediate=True
        )

    def _refresh_view(self, preserve_scroll: bool = True) -> None:
        if self.current is None or not self._view_mounted:
            return
        snapshot = self.snapshots[self.current]
        visible = [
            item
            for item in profile_annotations(snapshot.profile)
            if item.stage in self.visible_stages
        ]
        key = self.selected_keys.get(self.current)
        if key is not None and not any(item.key == key for item in visible):
            key = None
            self.selected_keys[self.current] = None
        selected = next((item for item in visible if item.key == key), None)
        source = self.query_one(SourcePane)
        pane = self.query_one("#source-scroll", VerticalScroll)
        anchor = self._pending_scroll_anchor
        if not preserve_scroll:
            anchor = self._pending_scroll_anchor = None
        elif anchor is None and self._rendered_ordinal == self.current and self._rendered_rows:
            anchor = self._rendered_rows[min(int(pane.scroll_y), len(self._rendered_rows) - 1)]
        width = max(2, source.content_size.width)
        rows = annotated_rows(snapshot.profile, self.visible_stages, width, key, color=self._color)
        self._rendered_rows, self._rendered_ordinal = rows, self.current
        content = Text(no_wrap=True)
        for index, row in enumerate(rows):
            if index:
                content.append("\n")
            content.append_text(row.text)
        source.update(content)
        if anchor is not None:
            self._pending_scroll_anchor = anchor
            if not self._scroll_restore_scheduled:
                self._scroll_restore_scheduled = True
                self.call_after_refresh(self._restore_scroll)
        statuses = phase_statuses(snapshot.profile, snapshot.status, self.finished)
        inspector = (
            "Select a source-attached label; n / p cycles annotations.\n\nPhase results:\n"
            + "\n".join(f"{STAGE_LABELS[stage]}: {statuses[stage]}" for stage in STAGE_ORDER)
        )
        if selected is not None:
            inspector = (
                f'{selected.label}\n\nSource: "{selected.span.text}"\n'
                f"Range: {selected.span.start}:{selected.span.end}\n"
                f"Phase result: {statuses[selected.stage]}\n\n{selected.details}"
            )
        self.query_one("#inspector", Static).update(Text(inspector))
        progress = Text(
            f"Paragraph {snapshot.ordinal + 1}/{snapshot.total} · {snapshot.status}"
            + (" · reused" if snapshot.receipt_reused else "")
            + (" · " + ", ".join(snapshot.gap_reasons) if snapshot.gap_reasons else "")
            + " · "
            f"{'following' if self.following else 'browsing'}\n"
        )
        for index, stage in enumerate(STAGE_ORDER):
            state = statuses[stage]
            mark = {"complete": "✓", "received": "✓", "pending": "·", "not run": "—"}.get(
                state, "!"
            )
            token = Text(
                f"{index + 1} {STAGE_LABELS[stage]}{mark}"
                + (" [off]" if stage not in self.visible_stages else "")
            )
            token.stylize(
                Style(
                    color=STAGE_COLORS[stage] if self._color else None,
                    dim=stage not in self.visible_stages,
                    meta={"layer": index},
                )
            )
            if index:
                progress.append("  ")
            progress.append_text(token)
        self.query_one("#progress", Static).update(progress)
        self._refresh_status()

    def on_phase_pane_layer_toggled(self, event: PhasePane.LayerToggled) -> None:
        self.action_layer(event.index)

    def on_source_pane_annotation_selected(self, event: SourcePane.AnnotationSelected) -> None:
        self._select_annotation(event.key)

    def _select_annotation(self, key: str) -> None:
        if self.current is None:
            return
        self.selected_keys[self.current] = key
        self._refresh_view(preserve_scroll=False)
        source = self.query_one(SourcePane)
        snapshot = self.snapshots[self.current]
        rows = annotated_rows(
            snapshot.profile,
            self.visible_stages,
            max(2, source.content_size.width),
            key,
            color=self._color,
        )
        row = next((index for index, item in enumerate(rows) if item.annotation_key == key), None)
        if row is not None:
            pane = self.query_one("#source-scroll", VerticalScroll)
            if row < pane.scroll_y or row >= pane.scroll_y + pane.content_size.height:
                pane.scroll_to(y=max(0, row - 1), animate=False)

    def action_annotation(self, direction: int) -> None:
        if self.current is None:
            return
        keys = [
            item.key
            for item in profile_annotations(self.snapshots[self.current].profile)
            if item.stage in self.visible_stages
        ]
        if not keys:
            return
        key = self.selected_keys.get(self.current)
        index = keys.index(key) if key in keys else (-1 if direction > 0 else 0)
        self._select_annotation(keys[(index + direction) % len(keys)])

    def action_layer(self, index: int) -> None:
        stage = STAGE_ORDER[index]
        if stage in self.visible_stages:
            self.visible_stages.remove(stage)
        else:
            self.visible_stages.add(stage)
        self._refresh_view()

    def action_paragraph(self, direction: int) -> None:
        if self.current is None:
            return
        ordinals = sorted(self.snapshots)
        index = ordinals.index(self.current)
        target = max(0, min(len(ordinals) - 1, index + direction))
        self.following = False
        self._switch_paragraph(ordinals[target])

    def action_follow(self) -> None:
        self.following = not self.following
        if self.following and self.latest is not None:
            self._switch_paragraph(self.latest)
        else:
            self._refresh_view()

    async def action_copy_snapshot(self) -> None:
        if self.current is None:
            self.notify("No paragraph is available to copy yet.", severity="warning")
            return
        snapshot = self.snapshots[self.current]
        try:
            captured = build_debug_summary(
                snapshot.profile,
                ordinal=snapshot.ordinal,
                paragraph_status=snapshot.status,
                operation=SnapshotOperation(
                    mode=self.mode,
                    status=("complete" if self.operation_code == 0 else "failed")
                    if self.finished
                    else "running",
                    exit_code=self.operation_code if self.finished else None,
                ),
                visible_stages=self.visible_stages,
                selected_key=self.selected_keys.get(self.current),
                context=snapshot.context,
                errors=self._visible_errors(),
            )
            payload = captured.clipboard_json()
            message = await asyncio.to_thread(self.clipboard_port.copy, payload)
            self.notify(
                f"{message}: paragraph {captured.paragraph_ordinal + 1} · "
                f"{sum(len(rows) for rows in captured.records.values())} records"
            )
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            self.notify(f"Snapshot copy failed: {error}", severity="error")

    async def action_quit(self) -> None:
        if self.finished:
            self.exit(self.operation_code)
        else:
            self.exit_requested = True
            self.operation_code = 130
            try:
                self.cancel_operation()
            finally:
                self.exit(130)
