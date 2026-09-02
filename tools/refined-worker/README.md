# ReFinED isolated workers

This pinned Python 3.10 environment supports derived ReFinED evidence without adding
ReFinED to KoteKomi's Python 3.12 dependency graph.

ReFinED V1 officially uses caller-supplied `Span` records through
`Refined.process_text(text, spans=...)`.

It is intentionally excluded from KoteKomi's Python 3.12 dependency graph.

Create a Python 3.10 environment, install `requirements.txt`, then run:

```bash
<worker-python> scripts/setup_refined_organization_type_worker.py \
  --data-dir <resource-directory> \
  --manifest <temporary-setup-manifest>
```

The setup command is the only network-enabled step.

The sealed ORG-R2 evaluation starts `scripts/refined_organization_type_worker.py`.

HP-3 entity identity grounding starts `scripts/refined_entity_linking_worker.py`.

Both workers use the same pinned resources and `download_files=false` during normal
operation. HP-3 uses caller-supplied spans with `apply_class_check=false` because it
requests identity candidates rather than Organization classification.

Configure HP-3 with:

```toml
[entity_linking]
adapter = "refined"
python_executable = "/absolute/or/config-relative/worker/python"
data_dir = "/absolute/or/config-relative/resource-directory"
timeout_seconds = 300
```

KoteKomi selects the repository-owned worker script. Configuration cannot substitute
an untrusted script.

The Adapter rejects any resource tree whose digest differs from `resource-lock.json`.
