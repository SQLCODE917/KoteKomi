# TDD: ReFinED Worker Channel Recovery

- **Status:** Accepted
- **Parent:** [Ingestion Architecture Review](2026-09-04-Ingestion-Architecture-Review.md)
- **Depends on:** [Hybrid Entity Identity Grounding](2026-09-01-hybrid-entity-identity-grounding.md)

## 1. Context & Problem

KoteKomi uses persistent ReFinED workers to avoid repeated model initialization.
The entity-linking Adapter sends one JSON line and expects one JSON line in return.
The contextual-type Adapter uses a duplicate transport with the same behavior.

Each current transport waits for stdout to become readable under a timeout.
Each transport then calls a blocking line read outside that timeout.
A worker can write one byte and delay the rest beyond the configured timeout.

A transport also keeps its worker after a timeout.
The worker can complete the timed-out response after the caller starts another request.
The next request can receive the late response because the protocol has no correlation value.

The architecture review reproduced both failures with local worker probes.
Source alignment rejects many contaminated responses.
Source alignment cannot prove that a response belongs to one transport exchange.

A **WorkerExchange** is one correlated request line and response line.
A **WorkerRequestId** identifies one WorkerExchange.
A **WholeExchangeDeadline** bounds request writing and complete response reading.
A **PoisonedWorker** is a worker whose response stream cannot serve another request safely.

Primary flow:

1. The Adapter sends one task payload to the shared ReFinED transport.
2. The transport adds a unique WorkerRequestId and writes one bounded request line.
3. The worker echoes the WorkerRequestId with one bounded response line.
4. The transport validates the complete frame and returns the task payload to the Adapter.
5. The Adapter maps valid ReFinED evidence into existing Application DTOs.

When a WorkerExchange fails, the transport terminates the PoisonedWorker.
The next WorkerExchange starts a new worker with empty pipes.

## 2. Goals

- A ReFinED call returns or fails within its configured deadline and cleanup allowance.
- A ReFinED call never receives another call's response.
- A healthy worker remains reusable across sequential calls.
- A failed worker cannot contribute evidence to a later call.
- Operators can distinguish timeout, framing, correlation, size, and worker-exit failures.

## 3. Requirements

### Shared ReFinED transport

- RWC-TRN-01: The shared transport creates one unique WorkerRequestId per WorkerExchange.
- RWC-TRN-02: The shared transport permits one active WorkerExchange per worker.
- RWC-TRN-03: The WholeExchangeDeadline starts before the transport writes request bytes.
- RWC-TRN-04: The WholeExchangeDeadline ends after the transport reads one complete response line.
- RWC-TRN-05: Partial response bytes do not extend the WholeExchangeDeadline.
- RWC-TRN-06: The transport limits each request frame and response frame to 16 MiB.
- RWC-TRN-07: The transport accepts a response only when its WorkerRequestId matches the request.
- RWC-TRN-08: The transport validates canonical JSON and the exact exchange-envelope fields.
- RWC-TRN-09: The transport marks a worker as poisoned after any channel failure.
- RWC-TRN-10: The transport terminates a PoisonedWorker before it returns the channel failure.
- RWC-TRN-11: The transport kills a worker that does not terminate within one second.
- RWC-TRN-12: The next request starts a fresh worker after a channel failure.
- RWC-TRN-13: A valid task-level blocked response keeps the healthy worker reusable.
- RWC-TRN-14: The transport closes every stdin and stdout pipe when it discards a worker.

### Worker protocol

- RWC-WRK-01: Each worker accepts one canonical WorkerExchange request per input line.
- RWC-WRK-02: Each WorkerExchange request contains a schema version, WorkerRequestId, and payload.
- RWC-WRK-03: Each worker echoes the exact WorkerRequestId in its WorkerExchange response.
- RWC-WRK-04: Each WorkerExchange response contains a schema version, WorkerRequestId, and payload.
- RWC-WRK-05: The payload retains the existing worker-specific request and response contract.
- RWC-WRK-06: A worker-level failure response echoes the request WorkerRequestId.
- RWC-WRK-07: The entity-linker runtime identity changes when the worker exchange protocol changes.

### ReFinED Adapters

- RWC-ADP-01: The entity-linking Adapter uses the shared ReFinED transport.
- RWC-ADP-02: The contextual-type Adapter uses the shared ReFinED transport.
- RWC-ADP-03: Each Adapter validates its worker-specific response after channel validation.
- RWC-ADP-04: Each Adapter discards its worker after an invalid worker-specific response.
- RWC-ADP-05: The entity-linking Adapter retains the exact WorkerExchange response as raw output.
- RWC-ADP-06: Neither Adapter maps WorkerRequestId into semantic evidence.

### Application behavior

- RWC-APP-01: A channel failure produces the existing runtime-failed task outcome.
- RWC-APP-02: A channel failure produces no ReFinED candidate evidence.
- RWC-APP-03: Existing Source alignment remains required after channel validation.
- RWC-APP-04: The Application Layer retains existing retry and partial-result decisions.

## 4. Proposed Architecture

```text
Hybrid Pipeline
    |
    v
Application ReFinED Port
    |
    v
ReFinED Adapter
    |
    v
Shared framed transport ----> persistent isolated worker
    |                              |
    +---- timeout/reset ----------+
```

The shared transport owns subprocess lifecycle, framing, deadlines, and correlation.
Each ReFinED Adapter owns its worker-specific mapping and validation.
Each worker owns ReFinED invocation and worker-specific response construction.
The Application Layer owns the terminal task outcome.

## 5. Key Interactions

### Healthy WorkerExchange

```text
Adapter          Transport          Worker
  | payload          |                 |
  |----------------->|                 |
  |                   | id + payload    |
  |                   |---------------->|
  |                   | id + result     |
  |                   |<----------------|
  | validated result  |                 |
  |<------------------|                 |
```

### Failed WorkerExchange

```text
Adapter          Transport          Worker A          Worker B
  | payload          |                 |                 |
  |----------------->|                 |                 |
  |                   | id A            |                 |
  |                   |---------------->|                 |
  |                   | partial output  |                 |
  |                   |<----------------|                 |
  |                   | deadline        |                 |
  |                   | terminate/kill  |                 |
  | timeout           |---------------->|                 |
  |<------------------|                 |                 |
  | retry payload     |                 |                 |
  |------------------>| start fresh worker               |
  |                   |---------------------------------->|
```

## 6. Data Model

This TDD adds no Ledger record.
WorkerRequestId remains transport evidence.
The entity-linking raw output retains the complete WorkerExchange response.
Existing ModelRun records retain the runtime failure and task lineage.
The entity-linker runtime identity is `isolated:refined-worker-exchange-v1`.
Historical evaluation artifacts retain the worker identity and script digest observed by their runs.

## 7. APIs / Interfaces

The WorkerExchange request and response use these required fields:

```text
schema_version = refined_worker_exchange_v1
request_id     = rwr_<32 lowercase hexadecimal characters>
payload        = worker-specific JSON object
```

The shared transport exposes request, discard, and close operations to ReFinED Adapters.
The request operation returns the WorkerRequestId, payload, and exact response bytes.

Channel failures use these stable codes:

```text
worker_timeout
worker_exited
worker_start_failed
worker_write_failed
worker_request_too_large
worker_response_too_large
worker_malformed_frame
worker_correlation_mismatch
worker_cleanup_failed
```

## 8. Behavior & Domain Rules

The transport uses one monotonic WholeExchangeDeadline for each request.
The transport reads response bytes in bounded non-blocking chunks.
The first readable byte does not complete a WorkerExchange.

The transport treats every channel failure as evidence that the worker is poisoned.
The transport discards all buffered bytes with the PoisonedWorker.
The transport does not retry a semantic task automatically.

The next explicit request can start one fresh worker.
The fresh worker reloads the pinned ReFinED resources through the existing worker behavior.

A worker-specific blocked payload is a complete correlated response.
The Adapter maps that payload through its existing typed failure path.

## 9. Acceptance Criteria

- AC-RWC-01: Tests prove a silent worker fails within the deadline plus cleanup allowance.
- AC-RWC-02: Tests prove one byte followed by a delayed newline cannot extend the deadline.
- AC-RWC-03: Tests prove request B cannot receive request A's late response.
- AC-RWC-04: Tests prove a wrong WorkerRequestId poisons and resets the worker.
- AC-RWC-05: Tests prove malformed, oversized, and EOF responses poison and reset the worker.
- AC-RWC-06: Tests prove the next request succeeds through a fresh worker after each failure.
- AC-RWC-07: Tests prove sequential valid requests reuse one worker.
- AC-RWC-08: Tests prove a valid blocked payload does not reset the worker.
- AC-RWC-09: Worker tests prove success and failure responses echo WorkerRequestId.
- AC-RWC-10: Adapter tests prove both ReFinED Adapters use correlated responses.
- AC-RWC-11: Application tests prove channel failure creates no candidate evidence.
- AC-RWC-12: Formatting, lint, type checking, and focused tests pass.

## 10. Reference Implementations

- Total deadline: follow `packages/adapters/src/kotekomi_adapters/model_http.py`.
- Worker reset: follow `packages/adapters/src/kotekomi_adapters/docling_pdf_parser.py`.
- Entity-link mapping: preserve `packages/adapters/src/kotekomi_adapters/refined_entity_linking.py`.
- Type mapping: preserve `packages/adapters/src/kotekomi_adapters/refined_organization_type.py`.

## 11. Constraints and Halt Conditions

The transport must not start one ReFinED process per healthy request.
The transport must not use a fixed delay to drain a timed-out response.
The transport must not accept Source alignment as request correlation.
The transport must not add an automatic semantic retry.
The transport must not expose subprocess objects across the Adapter boundary.

Halt if worker reset cannot complete within the declared cleanup allowance.
Halt if correlation requires WorkerRequestId to become accepted Ledger state.
