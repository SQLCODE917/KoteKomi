# H14 operator notes

H14 should not use broad local full-suite pytest as a substitute for the
deterministic planner. The local step should execute the focused checks emitted
by the H14 manifest and the dogfooded verification plan. CI remains the
authoritative full-suite gate.

If a candidate fails before push, reset the local candidate branch to the H14
spec commit and rerun the candidate step. If candidate CI fails after push, keep
the pushed candidate as evidence, record a CI failure receipt, diagnose logs,
and repair with a follow-up candidate commit.
