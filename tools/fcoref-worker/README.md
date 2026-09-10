# F-Coref isolated worker

This pinned Python 3.12 environment supports derived coreference observations without
forcing F-Coref's Transformers and Torch requirements into KoteKomi's application
environment.

Install the managed runtime and exact model resources with:

```bash
uv run kotekomi model resources install --resource fcoref
```

Installation is the only network-enabled step. Normal evaluation and ingestion use
the repository-owned `scripts/fcoref_worker.py` with offline mode enabled.

F-Coref observations remain fallible derived evidence. They become production-eligible
only after the frozen held-out bake-off records zero wrong antecedent resolutions.
