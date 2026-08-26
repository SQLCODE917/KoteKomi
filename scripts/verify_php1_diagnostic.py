"""Run the six PHP-1 paragraph-hypothesis diagnostic cases."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from php1_diagnostic_support import Php1DiagnosticCase, run_cases

CASES = (
    Php1DiagnosticCase(
        "AD-06",
        "raw/Anthropic–United_States_Department_of_Defense_dispute.pdf",
        "https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute",
        "partnered with Palantir and Amazon Web Services",
    ),
    Php1DiagnosticCase(
        "AD-13",
        "raw/Anthropic–United_States_Department_of_Defense_dispute.pdf",
        "https://en.wikipedia.org/wiki/Anthropic%E2%80%93United_States_Department_of_Defense_dispute",
        "all lawful purposes",
    ),
    Php1DiagnosticCase(
        "AI-06",
        "raw/Artificial_intelligence_safety_institute.pdf",
        "https://en.wikipedia.org/wiki/AI_Safety_Institute",
        "joint safety test",
    ),
    Php1DiagnosticCase(
        "AI-14",
        "raw/Artificial_intelligence_safety_institute.pdf",
        "https://en.wikipedia.org/wiki/AI_Safety_Institute",
        "renamed to the Singapore AISI",
    ),
    Php1DiagnosticCase(
        "CS-05",
        "raw/241030_Allen_Safety_Network.pdf",
        "https://csis.org/allen-safety-network",
        "joined the U.S. AISI Consortium",
    ),
    Php1DiagnosticCase(
        "CS-10",
        "raw/241030_Allen_Safety_Network.pdf",
        "https://csis.org/allen-safety-network",
        "Recommendation",
    ),
)


def run(config_path: Path | None) -> dict[str, object]:
    return run_cases(
        config_path,
        CASES,
        representation_policy_version="php1-diagnostic-v2",
        include_raw_output=False,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=None)
    print(json.dumps(run(parser.parse_args().config), sort_keys=True))
