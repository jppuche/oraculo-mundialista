---
doc_type: guide
purpose: Captured office-prode scoring rules + formalized point function + decision-optimizer design (Phase 5). Source of truth for the objective the optimizer maximizes.
audience: [agents, humans]
when_to_use:
  - Designing or coding the Phase 5 decision optimizer
  - Deciding what the probability engine must output (scoreline grid, not just 1X2)
  - Any time per-match expected-points are computed or a prediction is chosen
last_verified: 2026-06-04
maintenance: living
related_docs:
  - tooling_and_methods.md
assumptions:
  - Rules captured from the office platform's full Terms & Conditions on 2026-06-04 (authoritative; an earlier "Cómo jugar" page agreed). No phase multipliers stated; uniform scoring confirmed across group stage and knockouts (the penalty bonus is the only knockout-specific item).
  - Tournament-level section "Final Soñada": pick Campeón + Subcampeón, 10 pts each, locks at start of Fecha 3 (captured 2026-06-04 from platform UI). Pending: confirm no further-round predictions unlock later.
freshness_check: Re-confirm if the platform publishes amendments before kickoff (2026-06-11). Final Soñada config captured 2026-06-04; verify no later-phase predictions unlock during the tournament.
---

# Prode Rules — Captured Spec + Optimizer Objective

**Captured 2026-06-04 from the office prode platform. This doc defines the function the Phase 5 decision optimizer maximizes. The probability engine (layer 1) is scoring-agnostic and does not depend on this; the optimizer (layer 2) depends entirely on it.**

## TL;DR
- **Per-match scoreline prediction with partial credit**, NOT a 1X2 pool. Exact scoreline = 12, correct outcome (non-exact) = 5, correct goal count of one team = 2. B+C stack (max 7 below exact).
- **Optimal play = argmax of expected points over the scoreline grid**, not "predict the most likely 1X2". Pure Python, ~36-64 candidate scorelines, 0 tokens.
- **Penalty bonus (+5) is only reachable by predicting a draw** in knockouts. It gives draw predictions option value the optimizer must include, or it undervalues draws in elimination matches.
- **Submission is match-by-match, editable until each kickoff.** No locked bracket. Qualitative overlay (Phase 6) has maximum value right before each match. No bracket optimizer needed.
- No phase multipliers (confirmed in ToS). Tiebreakers reward exact scorelines (soft secondary incentive).
- **Second optimizer: "Final Soñada"** — pick Campeón + Subcampeón (distinct teams), **10 pts each, locks at start of Fecha 3** (so conditioned on 2 group matchdays). Futures/assignment: tournament Monte Carlo → marginals → best A≠B pair. Separate from the per-match optimizer.

## 1. Captured rules

### 1.1 Submission mode + deadlines
- Predict matches of the **enabled rounds**; load or modify until each match's **kickoff**.
- Only matches that have **started** get locked. Everything else stays editable.
- Implication: per-match prediction, no upfront bracket, full freedom to update with last-minute info (lineups, injuries) before each kickoff.

### 1.2 Scoring (`Método de calificación`) — same structure as the official page
- **A** — Acierto de resultado y marcador exacto (cantidad de goles de cada equipo) → **12 puntos**
- **B** — Acertar resultado (ganador o empate, no exacto) → **5 puntos**
- **C** — Acertar marcador (cantidad de goles) de **uno** de los equipos → **2 puntos**
- **D** — Acertar al ganador de los penales → **5 puntos** (knockouts only; only offered when you predicted a draw — see §1.4)

B and C stack. A is a flat 12 (it does NOT decompose into 5+2+extra). The "+2" of C is awarded **once** (one team), never per-team — getting both teams' counts right is by definition the exact scoreline (A=12).

### 1.3 Worked example (real result: Argentina 3 - 1 France) — all verified
| Prediction | Points | Reason |
|------------|--------|--------|
| 3 - 1 | 12 | Exact scoreline (A) |
| 3 - 0 | 7 | Correct winner (5) + Argentina's 3 goals (2) |
| 2 - 1 | 7 | Correct winner (5) + France's 1 goal (2) |
| 2 - 0 | 5 | Correct winner only (5) |
| 0 - 1 | 2 | Wrong winner; France's 1 goal matches (2) |
| 3 - 3 | 2 | Wrong outcome (draw); Argentina's 3 goals match (2) |
| 0 - 2 | 0 | No match |
| 0 - 0 | 0 | No match |

### 1.4 Penalties (knockouts only)
- A knockout match decided on penalties: the **result is taken over 90/120 min only**, penalties excluded. So the predicted scoreline is scored against the regulation/extra-time score (a draw).
- The platform offers an **extra prediction** for who advances on penalties — **only visible if you predicted a draw** in the main result.
- Penalty prediction adds **+5** only if you pick the correct shootout winner.

Verified example (real: Argentina 1 - 1 France, 120'; Argentina win on penalties):
| Prediction | Points | Reason |
|------------|--------|--------|
| 1-1, pen: Argentina | 17 | Exact (12) + correct pen winner (5) |
| 1-1, pen: France | 12 | Exact (12); pen winner wrong (0) |
| 0-0, pen: Argentina | 10 | Correct draw (5) + correct pen winner (5) |
| 0-0, pen: France | 5 | Correct draw (5); pen winner wrong (0) |

If you predict a draw but miss the pen winner, you keep only the match-result points.

### 1.5 Tiebreakers (ranking position on equal points)
1. Most **exact scorelines in the round** (`fecha`).
2. Most **exact scorelines in the tournament**.
3. Earlier account activation.

Soft secondary incentive: exact scorelines break ties, so among equal-EV predictions, slightly favor the one with higher exact-hit probability. Low weight; do not distort EV for it.

### 1.6 Suspended / rescheduled
- Suspended then resumed: points computed normally once finished.
- Rescheduled to a later date: points count only toward the **General ranking**, not the original round's ranking/prizes.
- Organization reserves interpretation rights for exceptional cases. (No optimizer impact; tracking-side note for Phase 7.)

### 1.7 Final Soñada (tournament-level prediction — a SECOND optimizer) — CONFIG CAPTURED 2026-06-04
- Predict the **2 podium teams: Campeón + Subcampeón**. **10 extra points for each correct** (max 20), per the official rules page.
- **Deadline: start of Fecha 3** (third group-stage matchday; **2026-06-24, opens with Switzerland–Canada; group stage ends 06-27**), per the rules page. So the bet is conditioned on Fechas 1-2 results, committed long before knockouts. **Runway is comfortable (~13 days from the Jun 11 kickoff); it does NOT compete with the per-match optimizer's first hard deadline.**
- Constraint (ToS): **no team repeats** → Campeón ≠ Subcampeón.
- Structurally a **futures / assignment problem**, different from the per-match optimizer. See §3.2.
- *(No further predictions in the portal as of 2026-06-04. Second-round predictions are expected to unlock when the group stage ends — re-check the platform then.)*

## 2. Formalized point function (Python-ready, Phase 5 implements verbatim)

```python
def outcome(h: int, a: int) -> str:
    return "H" if h > a else ("A" if a > h else "D")

def match_points(pred, actual, pen_pred=None, pen_actual=None) -> int:
    """
    pred, actual: (home_goals, away_goals) over 90/120 min (penalties excluded).
    pen_pred:   team you predicted to win the shootout ("H"/"A"), or None. Only
                meaningful (and only offered by the platform) when pred is a draw.
    pen_actual: team that actually won the shootout ("H"/"A"), or None if the match
                did not go to penalties.
    """
    ph, pa = pred
    ah, aa = actual

    if ph == ah and pa == aa:
        pts = 12                                   # A: exact scoreline
    else:
        pts = 0
        if outcome(ph, pa) == outcome(ah, aa):
            pts += 5                               # B: correct outcome (non-exact)
        if ph == ah or pa == aa:                   # C: one team's goal count
            pts += 2                               # (in non-exact branch, at most one can match)

    # Penalty bonus: knockouts only, requires a DRAW prediction AND the match
    # actually went to penalties (i.e., real result was a draw).
    if ph == pa and pen_pred is not None:
        if ah == aa and pen_actual is not None and pen_pred == pen_actual:
            pts += 5

    return pts
```

**Falsified by:** any cell in the §1.3 or §1.4 tables not reproduced by `match_points`. (All 12 cells reproduce — checked 2026-06-04.)

## 3. Optimizer design (Phase 5)

The probability engine outputs a distribution over scorelines `P(h, a)` per match (this is why the engine must produce the **full scoreline grid**, e.g. a bivariate-Poisson / Dixon-Coles matrix, not just `P(H), P(D), P(A)`). The optimizer then:

```
best = argmax over candidate (ph, pa) of  E[ match_points((ph,pa), (H,A)) ]
     = argmax  sum_{(H,A)} P(H,A) * match_points((ph,pa),(H,A))
```

- **Candidate grid:** scorelines 0-6 per side is more than enough (realistically 0-4). ~36-64 candidates. Trivial compute, **0 Claude tokens** — fits the budget philosophy.
- **Expected value decomposes cleanly:**
  - `12 * P(ph, pa)` (exact)
  - `+ 5 * P(outcome(ph,pa) and (H,A) != (ph,pa))` (outcome, non-exact)
  - `+ 2 * P(exactly one of {H==ph, A==pa} and (H,A) != (ph,pa))` (one-team goals)
- **Knockout draw option value:** when evaluating a draw candidate `(d, d)`, add
  `5 * P(match ends in a draw) * P(pen pick wins | draw)`, with the pen pick = the team with higher shootout-win probability (≈ pre-match favorite; shootouts are close to 50/50, so this term ≈ `5 * P(draw) * ~0.5-0.55`). **Do not omit this** — it is the only access to +5 and systematically tilts knockout optima toward draws when the draw mass is competitive.

### Why this is NOT a 1X2 problem
Backing the most likely **outcome** (e.g. "favorite wins") maximizes the 5-point term but throws away the 12-point exact mass and the +2 one-team mass. The modal **scoreline** (often 1-0 / 2-1 / 1-1) usually also carries a strong outcome, so it tends to win the argmax — but the optimizer must be run on the grid, because the partial-credit structure and the penalty edge create cases where the EV-max scoreline is not the naive "favorite by 1 goal." Let the numbers decide per match.

### What the engine must therefore deliver
- Full `P(h, a)` matrix per match (not just 1X2). Confirms the layer-1 design: a goal model (Dixon-Coles / bivariate Poisson) that yields scoreline probabilities.
- For knockouts: a `P(draw over 90/120)` and a shootout-winner probability (can start at ~0.5 with a small favorite tilt; refine later).

### 3.2 Final Soñada optimizer (futures / assignment) — objective now defined
- Objective: `max  10 * P(A = champion) + 10 * P(B = runner-up)` over team pairs with **A ≠ B**.
- Needs marginals `P(team = champion)` and `P(team = runner-up)` from a **tournament Monte Carlo**: simulate the full 104-match bracket many times (10k+) from the scoreline engine's per-match probabilities; tally how often each team is champion / loses the final.
- Solve by brute force over all ~48×47 ordered pairs (trivial) or Hungarian. Still 0 Claude tokens.
- **Non-obvious:** runner-up = *reaches the final and loses it*, so `P(runner-up)` peaks for strong-but-not-dominant teams, not the favorite. The optimal slate is NOT mechanically "top-2 favorites" — the two marginals decide. The favorite usually goes to Campeón (higher marginal); Subcampeón = the team most likely to reach and lose the final.
- **Deadline = start of Fecha 3 (2026-06-24, opens Switzerland–Canada):** condition the simulation on Fechas 1-2 results (group standings, observed form, confirmed injuries). Build the simulator to accept partial group results, not only pre-tournament priors. Comfortable runway — build this *after* the Jun 11 per-match optimizer ships.

### 3.3 Objective = expected points (EV), NOT rank-dependent — a deliberate scope choice
- **Prizes are by ranking, not absolute score:** the rules define a per-matchday winner (top score each matchday) and an overall tournament winner (top cumulative). Winning the prode is therefore a competitive, rank-dependent objective.
- **The optimizer still maximizes plain expected points (risk-neutral EV) per match.** Two reasons: (1) the project's objective is **measuring calibration** (objective 1), not winning the office pool (explicitly anecdotal) — EV-max is the right target for calibration; (2) it is also globally optimal here because the scoring is **separable per match** (no coupling across matches → each match is an independent argmax; no sequential-planning problem).
- **When the lens WOULD flip:** only if the goal were to *win*. Near a matchday/tournament close, a player who is behind should **increase variance** (chase improbable exact scorelines for their high ceiling) while a leader should **reduce** it — a rank-dependent objective that depends on the field and on the shrinking pool of remaining matches. This is **documented, not implemented**: it would contaminate the calibration metric and requires modeling the N opponents. Revisit only if JP decides to play to win.
- The exact-scoreline tiebreaker (§1.5) is a mild nudge in that same rank-dependent direction; §1.5 already says: don't distort EV for it.

## 4. Assumptions + open questions

| # | Item | Status | Why it matters |
|---|------|--------|----------------|
| 1 | No phase multipliers (groups = knockouts in points) | **Confirmed** — the ToS Método de calificación is flat; only the penalty bonus is knockout-specific | Closed. The optimizer weights all rounds equally on the precision metric. |
| 2 | Final Soñada config | **CAPTURED 2026-06-04** — 2 positions (Campeón + Subcampeón), 10 pts each, locks at start of Fecha 3, no repeat | Objective defined (§3.2). |
| 3 | Penalty pick is a binary team choice (not a pen scoreline) | **Confirmed** from examples | "Ganador por penales: Argentina/Brasil" — binary. Confirms the +5 model. |
| 4 | C ("+2 one team") is flat 2, awarded once | **Confirmed** from §1.3 | Prevents double-counting. |
| 5 | Further-round / later predictions beyond Final Soñada | **None in portal as of 2026-06-04**; expected to unlock after group stage | Only Campeón + Subcampeón available now. Re-check the platform when groups end. |
| 6 | Prizes are by **ranking** (Ganador de Fecha + Ganador General), not absolute score | **Confirmed** — rules, game-objective section | Optimizer stays **EV-pure** (project objective = calibration); rank-dependent play documented in §3.3, not implemented |

**Status 2026-06-04:** #1 closed (ToS, no multipliers). #2 captured (Final Soñada: Campeón + Subcampeón × 10 pts, locks start of Fecha 3 = 2026-06-24). #6 confirmed (prizes by ranking → EV-pure chosen, §3.3). #5: nothing further in the portal now — expected to unlock after group stage; re-check then.

## 5. Rules notes (non-optimizer)
- **Using a model is allowed by the pool's rules**: what they prohibit is fraud and platform manipulation (fake identities, multi-accounts), not analytical aids. Forecasting well is the game's whole point.
- **Organizer discretion:** scoring and interpretation decisions are final and the rules can change via the platform; re-check before each phase.

## Source
Captured from the office pool platform on 2026-06-04 (provided by JP). **The verbatim terms and rules pages are kept out of the public repo (organizer's text, employer-specific).** Per-match scoring + worked examples reproduce 1:1 against the official rules page — the 12 cells of §1.3/§1.4 ARE the official examples, so `match_points` is validated against source, not only against this derived doc. No public URL (gated office platform). Provenance: `DIRECT_FETCH`. Confidence: `HIGH` for per-match scoring + Final Soñada (ToS + self-verifying examples). **Final Soñada config** (Campeón + Subcampeón, 10 pts each, deadline start of Fecha 3): the terms leave it generic, but the concrete config is `CONFIRMED` via the platform UI (JP visual 2026-06-04). **Fecha 3 dated 2026-06-24/27** (opens Switzerland–Canada), confirmed by JP against the platform fixture.
