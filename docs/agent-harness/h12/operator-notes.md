# H12 Operator Notes

## Current weakness

Generated local scripts have been carrying too much bespoke state logic. H12 moves that logic into deterministic harness commands.

## Intended script pattern after H12

A generated local step should:

1. call deterministic preflight
2. apply the smallest patch it needs
3. run fast syntax/static checks on touched files
4. record failure through a deterministic command if it stops
5. use deterministic recovery only for known failed local candidate branches
6. avoid hand-coded branch-reset policies

## Safety boundary

Dirty `main` is protected. Recovery from dirty state is only for an expected local candidate branch at an expected base.
