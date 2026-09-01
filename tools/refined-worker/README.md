# ReFinED ORG-R2 worker

This isolated Python environment exists only for the ORG-R2 derived evaluation.

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

Normal evaluation starts `scripts/refined_organization_type_worker.py` with the
same Python executable and uses `download_files=false`.

The Adapter rejects any resource tree whose digest differs from `resource-lock.json`.
