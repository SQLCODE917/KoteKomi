# H14 verification-plan coverage expansion

H14 expands the deterministic `verification-plan` coverage map for
harness-owned code paths. H13 added a targeted CLI delimiter regression rule.
H14 generalizes that approach so known harness areas produce deterministic
required checks instead of relying on ad hoc operator choice or broad local
full-suite pytest.

The implementation should remain small: update `verification_plan.py`, add
focused unit coverage, add acceptance tests that exercise fixture repositories,
and preserve H13 delimiter behavior. Unknown changed paths must still fail
closed.
