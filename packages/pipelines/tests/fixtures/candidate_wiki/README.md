# Captured inputs for Candidate Wiki command tests

`closed_ingestions.json` supplies one valid captured Document and two closed ingestions of it.
The ingestions share the exact filename and Source; their identities and dates differ.
The proposal sets are empty because selection and publication do not depend on Actors, Organizations, Events, Assertions, or their evidence.
The fixture does not claim to prove ingestion or extraction quality.

The fixture loader parses Domain Core records and persists them through the real storage APIs.
The public-command tests exercise real selection, view construction, rendering, and publication with no substituted build function.
Expected selected identities and exit behavior are stated in the tests, independently of generated Wiki output.
Build IDs are derived outputs, not frozen expectations.

Keep this input at this integration boundary.
Pure selection tests construct only ingestion records and never load this file.
Changes to the required captured-input or storage contracts can require updating this fixture; unrelated private helper refactors must not change the behavioral assertions.
Do not regenerate fixture expectations from the implementation under test or add ingestion execution solely to prepare Wiki tests.

For manual UAT from the repository root:

```sh
wiki_example=$(mktemp -d)
uv run python -m packages.pipelines.tests.support.candidate_wiki_fixture "$wiki_example"
uv run kotekomi --config "$wiki_example/kotekomi.toml" wiki build report.pdf --candidate --ingestion-run igr_older
```

Inspect `archive/review/wiki/manifest.json` beneath that directory: `ingestion_run_id` must be `igr_older`.
Repeat the command; it must retain the same build.
Select `igr_newer`; it must activate another build and retain the older one.
Selecting `igr_missing`, `igr_unclosed`, or `other.pdf` with `igr_older` must fail and preserve the active build.
Without `--ingestion-run`, choose entry 2 to select the older ingestion interactively.
The loader refuses to overwrite an existing Ledger.
