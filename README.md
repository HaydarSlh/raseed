# Raseed — رصيد — Planning Root

This folder is the project root **before Phase 0**. It contains the planning
artifacts that drive the spec-driven build. The actual repository skeleton
(backend/, frontend/, docker-compose.yml, ...) is created BY Phase 0 via Spec Kit.

Contents:
- `CLAUDE.md` — master context for the implementation agent (Claude Code).
- `COMMANDS.md` — the exact Spec Kit command order to run, kept as a reference.
- `briefs/constitution.md` — paste into `/speckit.constitution` (once, first).
- `briefs/phase-0..7-*.md` — paste each into `/speckit.specify` for that phase.
- `docs/PLAN.md` — the authoritative implementation plan v1.1 (all decisions).

How to use: follow COMMANDS.md top to bottom. One phase = one spec-kit feature.
Never improvise answers to `/speckit.clarify` — resolve them from docs/PLAN.md.
