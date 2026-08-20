# PDF Authoritative Text Fidelity

## Decision

The Docling representation path is the sole producer of authoritative PDF text.

KoteKomi stores that text unchanged in the accepted `DocumentRepresentationBundle`.

Poppler and qpdf inspect deposited PDF bytes before extraction.

Their output must not rewrite, supplement, or validate individual characters in authoritative text.

KoteKomi must reject a representation that loses a required source-text anchor.

KoteKomi must not add source-specific text fixers or a Docling-to-Poppler compatibility layer.

## Problem

The canonical `anthropic-dod-dispute-v1` PDF contains this title text:

```text
Anthropic–United States Department of Defense dispute
```

The observed Docling representation stored an ASCII hyphen in place of the en dash.

The stored title therefore failed the locked exact-text anchor.

The PDF bytes were unchanged.

Poppler exposed the en dash during preflight inspection.

## Root Cause

KoteKomi passes `item.text` from the Docling extraction result into the authoritative representation.

The character substitution occurred before KoteKomi created the `DocumentRepresentationBundle`.

The observed versions were Docling 2.111.0 and docling-parse 7.8.0.

KoteKomi has no supported Docling configuration for Unicode dash preservation.

The tested `force_backend_text` and `enforce_same_font` options preserved the same ASCII hyphen output.

This identifies the current primary extraction stack as the source of the mismatch.

It does not establish which lower-level parser implementation made the substitution.

## Current Control

The canonical scenario locks the deposited PDF digest and source-text anchors.

`kotekomi-agent test-ingest` reports `primary_text_fidelity_failed` when the primary representation omits a required anchor.

The command blocks canonical acceptance in that condition.

The command does not normalize source expectations or rewrite representation text.

Poppler remains an independent source-byte inspector.

Docling remains the only authoritative text producer.

## Why KoteKomi Does Not Patch Text

A cross-tool patch would create a second text authority.

It would hide parser defects behind an expanding set of character rules.

It would make the accepted representation depend on unrecorded agreement between independent tools.

It would also make retrieval and `ContextManifest` output differ from the primary representation.

The rejection gate keeps the defect visible and keeps one producer responsible for authoritative text.

## Revisit Conditions

Revisit this decision only after an upstream Docling or docling-parse change offers a documented Unicode-preservation control or fixes the observed output.

First rerun the locked canonical PDF through the public deposited-source Pipeline.

Then verify the exact title anchor, persisted `DocumentRepresentationBundle`, restart reload, and deterministic re-ingest.

If the primary text passes unchanged, update the pinned extraction dependency and its regression tests through an accepted TDD.

If KoteKomi replaces Docling, replace the single authoritative producer through an accepted TDD.

Do not combine strings from the old and new producers.
