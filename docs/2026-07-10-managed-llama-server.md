# Managed llama-server

## 1. Context

The Mac runs local applications that use the same Apple Silicon memory and inference capacity.

Starting a separate llama-server per application creates port conflicts and concurrent model loading.

KoteKomi must use one user-scoped managed llama-server instance.

## 2. Decision

macOS launchd owns the shared llama-server process.

The LaunchAgent runs only in the logged-in user domain.

The LaunchAgent does not require root access.

The managed server binds only `127.0.0.1:8080`.

The managed server runs in router mode.

The LaunchAgent passes `-c 16384`, `-np 1`, `--models-max 1`, `--slots`, and `--jinja`.

The one slot permits one active inference request.

The one loaded-model limit prevents competing models from occupying unified memory.

The slots endpoint exposes passive occupancy state.

## 3. Ownership

launchd starts, restarts, and stops the managed server.

The installer replaces the current user's PATH launcher with a reversible guard.

The guard rejects direct `llama-server` starts.

The LaunchAgent invokes the configured binary by absolute path.

KoteKomi remains an HTTP client of the managed server.

KoteKomi never starts, stops, or reloads llama-server.

Other controlled local applications must become HTTP clients of the managed server.

Those applications must not spawn or stop llama-server.

The managed service utility installs and removes only the current user's LaunchAgent.

The utility never invokes `sudo`.

## 4. Readiness

`kotekomi model status` performs passive checks only.

The command reads the router model inventory and slot state.

The command does not send a completion or load a model.

The command reports the configured model state and the number of idle slots.

KoteKomi submits extraction when the configured model is unloaded or loaded with one idle slot.

The router autoloads the configured model for the first submitted request.

KoteKomi fails fast when the model is loading, sleeping, or the slot is busy.

The router remains the final concurrency authority because another client can occupy the slot after a preflight check.

## 5. Scope

This design can enforce exclusive ownership for controlled applications.

User-space software cannot prevent an arbitrary process from executing the llama-server binary by absolute path.

The project enforces the architecture by migrating each controlled application to the managed endpoint.

## 6. Acceptance Criteria

- A repository-managed utility renders the current user's LaunchAgent plist.
- The plist starts router mode with one slot, one model, and slots enabled.
- The utility uses `launchctl bootstrap gui/<uid>` and `launchctl bootout gui/<uid>`.
- The utility guards the current user's PATH launcher and restores its original target on uninstall.
- KoteKomi's default model identifier matches the configured router preset.
- KoteKomi readiness sends no completion request.
- KoteKomi reports model and slot state through structured JSON.
- KoteKomi rejects extraction when the shared server is not idle.
- Unit tests cover plist rendering, service commands, model inventory parsing, and busy-slot rejection.
