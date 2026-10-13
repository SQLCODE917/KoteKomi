# Architecture Vocabulary

Use these terms for architectural roles in code, documentation, tests, and reviews.

Use the project [Domain Vocabulary](./domain.md) for business concepts and for the canonical layer names.

Do not replace a precise product term with an architectural term.

Do not replace an architectural term with a product term.

Do not redefine a Domain Vocabulary term here; `domain.md` owns those definitions.

## System model

KoteKomi composes these layers in inward dependency order:

```text
Presentation -> Pipeline -> Application Layer use case -> Port <- Adapter -> external system

Domain Core (below the Application Layer; imports no external package)
```

The Domain Vocabulary defines the layer names: Domain Core, Application Layer, Adapter, Port, Pipeline, Ledger, and Archive.

## Equivalences from generic hexagonal language

Map generic hexagonal names to KoteKomi terms.

Do not use the generic names as KoteKomi terms.

| Generic name | KoteKomi term |
| --- | --- |
| domain model | Domain Core |
| application core | Domain Core plus Application Layer (two layers, never one) |
| outbound port | Port |
| driven adapter | Adapter |
| driving adapter | Pipeline |
| composition root | Pipeline (the command-line layer that composes use cases and selects and wires the concrete Adapters) |

## Architecture boundary terms

These terms describe shapes and roles at a Port, Adapter, or Pipeline boundary.

| Term | Meaning |
| --- | --- |
| use case | One Application Layer operation that coordinates domain rules through Ports to produce an observable outcome. |
| boundary contract | The explicit input and output contract at a Port, Adapter, or Pipeline boundary. |
| DTO | A shape owned by an Application Layer use case input or result, or by an Adapter boundary. |
| mapper | A pure function that translates between a DTO and a Domain Core record at a boundary. |
| external system | Anything outside the Application Layer and the Domain Core: databases, model runtimes, vector indexes, graph libraries, filesystems, browsers, clocks, or remote services. |

## Required usage

- Use Domain Core, Application Layer, Adapter, Port, and Pipeline as the canonical terms.
- Do not alternate between primary/secondary, left/right, input/output, and driving/driven adapter terminology.
- Say whether an interface is a Port when introducing it.
- Name Ports after capabilities, not technologies.
- Name Adapters after their technology and the Port they implement.
- Name use cases with a domain action.
- Keep DTOs and Domain Core records distinct.
- Use `mapper` for a pure boundary-translation function.

## Dependency direction

- A Pipeline composes Application Layer use cases.
- A use case depends on Ports; it does not depend on Adapters.
- An Adapter implements a Port.
- The Application Layer depends on the Domain Core; it does not depend on tools.
- The Domain Core imports no external package.
- Only the Pipeline composition layer may import every layer.
- Adapters may depend on frameworks and vendor SDKs.
- Domain Core records and pure domain rules do not depend on frameworks, vendor SDKs, environment variables, or process-global state.
