# COMMANDS.md — Spec Kit run order (reference)

> Note: depending on the Spec Kit version, commands appear as `/speckit.specify`
> or `/specify`. The ORDER below is what's stable — check the prefix after init.

## One-time setup (before Phase 0)
```
1. uv tool install specify-cli          # or: uvx --from git+https://github.com/github/spec-kit specify
2. specify init . --integration claude --force
3. pip install graphifyy && graphify install --project
4. /speckit.constitution                # paste briefs/constitution.md
```

## Per phase — repeat for Phase 0 through Phase 7
```
5.  /speckit.specify                    # paste briefs/phase-N-*.md
6.  /speckit.clarify                    # answer from docs/PLAN.md, never improvise
7.  /speckit.plan                       # paste the "Notes for /plan" block of the brief
8.  /speckit.tasks
9.  /speckit.analyze                    # fix findings; rerun until clean
10. MANUAL REVIEW of tasks.md           # the human gate — non-negotiable
11. /speckit.implement
12. run tests + CI locally; fix until green
13. /graphify .                         # refresh the code graph
14. git add -A && git commit -m "phase N: <name>" && git tag phase-N
```

## After Phase 7
```
15. final /graphify . refresh -> git tag v0.1.0
```

Usage notes:
- /clarify runs AFTER specify, BEFORE plan — kill ambiguity before the plan
  crystallizes around a wrong guess.
- /analyze runs AFTER tasks, BEFORE implement — it is a consistency linter
  across spec/plan/tasks/constitution, not a correctness check of intent.
  Your step-10 review is where intent gets verified.
