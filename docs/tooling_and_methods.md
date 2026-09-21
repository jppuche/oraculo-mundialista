---
doc_type: guide
purpose: How Claude Code orchestration features + the Karpathy autoresearch pattern apply to THIS project's phases. Decision-oriented, project-scoped.
audience: [agents, humans]
when_to_use:
  - Choosing which tool to use for a given phase (build, backtest, track, research)
  - Before running an automated model/feature search (Phase 3) — read the anti-overfit guard first
  - Calibrating the single planned /deep-research run
last_verified: 2026-06-04
maintenance: living
related_docs:
  - data_sources.md
---

# Tooling & Methods — capabilities mapped to our phases

**General feature descriptions live in the parent repo's `docs/reference/claude_code_novelties_2026-06.md` (DIRECT_FETCH-verified). This doc holds only how we APPLY them here, to avoid duplication.**

## TL;DR
- Code phases (engine, backtest harness, optimizer) -> **`/goal`** build-until-green loops + auto mode.
- Phase 3 model/feature search -> **autoresearch pattern** (via `/goal` or a Workflow) optimizing **held-out expected points** (the prode's real metric — NOT RPS), never the dev split. Overfit guard is mandatory, not optional.
- Phase 7 tracking -> **local** Desktop scheduled task or `/loop`, NOT a cloud routine (would need to clone the parent repo, which is not public).
- Any unattended loop -> **inside the sandbox** (WSL2 + `sandbox-runtime`).
- One planned **`/deep-research`** for Q1 (historical odds), but recon barata first — may not need to spend it.

## Capability -> phase map
| Phase | Tool | Note |
|---|---|---|
| 1 Collect data (48 teams) | Subagents / background sessions | Independent fetch+normalize, low token cost; can run `--bg` |
| 1.5 Methodology research | `/deep-research` (1x) | Broad/ambiguous search; results in a report, not context |
| 2 Build engine v0 | `/goal` + auto mode | Build-until-green (pytest + reference RPS) |
| 3 Backtest + model/feature search | **autoresearch pattern** via `/goal` or Workflow | Optimize held-out **expected points** (not RPS); deterministic backtest = 0 tokens to run |
| 4 Interpret results | Agent Teams (1x) | Judgment/adversarial; autoresearch's experiment log is good input |
| 5 Decision optimizer | `/goal` (build) | When unblocked by prode rules |
| 7 Submit + track | Desktop scheduled task / `/loop` | Local, daily during the tournament; not cloud routine |

## `/goal` for the code phases (2, 3-build, 5)
The evaluator only reads the transcript, so the condition must be demonstrable by Claude's own output. Example for Phase 2:
```
/goal pytest tests/ exits 0, the Dixon-Coles fit reproduces a published reference RPS within +/-0.002 AND its scoreline grid matches a known DC reference matrix (low-score cells, not just the 1X2 marginal) on the sample dataset, and no TODO remains in engine/ — or stop after 25 turns
```
The scoreline-grid assert matters: an engine can hit the 1X2 RPS target while producing a poorly-calibrated `P(h,a)`, and the prode pays on the grid. Always bound it (turns/time). Evaluator tokens (Haiku) are negligible; the main turns are the real spend.

## Phase 3: autoresearch pattern — the methodological decision
Structurally a near-perfect fit: single objective metric (RPS), a file the agent edits (features/model), a time-boxed experiment (the CPU backtest). **But the central risk of this project IS overfitting**, and autoresearch as published has only one validation split and no metric-hacking guard.

Non-negotiable guard before any automated search:
1. The loop optimizes **held-out expected points** (the prode's real metric, not RPS) on a development set of cups it CAN see.
2. The **final** chosen config is validated **once** on a test cup the loop **never** saw.
3. Use **rolling-origin / nested CV**, not a single split (sparse data: ~10-15 matches/team).
4. **Skeptically re-validate** any improvement ("convergence != evidence"). Round 1 expected model tweaks to barely move RPS — but that was a 1X2 result; on **expected points** the model family may matter more (low-score grid mass where 12s and 2s live). Test it; whichever way it lands (model matters / doesn't) is a valuable, portfolio-worthy result.

No GPU needed: we use the *pattern*, not Karpathy's nanochat repo. The pattern ≈ `/goal` (sequential) or a Dynamic Workflow (parallel experiment branches, keep-best, then validate the winner once).

## Unattended runs -> sandbox
`/goal` loops and autoresearch run with reduced/disabled prompts. On Windows that means **WSL2 + `npx @anthropic-ai/sandbox-runtime claude`** (wraps Bash + MCP + hooks), per the parent reference doc. The autoresearch use case is exactly why the pending sandbox install matters.

## Round 2 `/deep-research` (Q1 historical odds) — calibrated
- **Recon barata first:** 2-3 WebFetches to known candidates (football-data.co.uk, OddsPortal). If that resolves availability, we may not spend the single planned run.
- **If we run it — pre-flight:** WebSearch enabled; allowlist fetch domains (avoid mid-run prompts); route the fan-out to a smaller model, synthesis to the strong one; run a narrow slice (one cup) first to gauge token spend in `/workflows`.
- **Expectation:** deep-research returns the *map of sources* (coverage/format/license), not the validated dataset. Downloading + checking columns stays manual.

## Sources
See the verification log + links in `../../docs/reference/claude_code_novelties_2026-06.md`. Project round-1 sources are archived locally.
