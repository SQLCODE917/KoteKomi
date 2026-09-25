"""Replay reader: sacrificial, read-only demo over persisted HP-8 state.

Removal contract: delete this package, the ``kotekomi-replay`` entry under
``[project.scripts]`` in ``packages/pipelines/pyproject.toml``, and the
``scripts/replay_canonical.sh`` wrapper that runs a canonical ingest then the
replay.
"""

from kotekomi_pipelines.replay_reader.model import (
    ParagraphAnnotationProfile,
    build_profile,
)
from kotekomi_pipelines.replay_reader.render import (
    render_annotated_paragraph,
    render_live_block,
    run_replay,
)
from kotekomi_pipelines.replay_reader.transport import main

__all__ = [
    "ParagraphAnnotationProfile",
    "build_profile",
    "render_annotated_paragraph",
    "render_live_block",
    "run_replay",
    "main",
]
