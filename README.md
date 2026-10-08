# Oráculo Mundialista

> Predicting the 2026 World Cup for an office pool that pays for **exact scorelines** — and using it as a small, honest case study in how to build a statistical model *with* guardrails instead of vibes.

![status](https://img.shields.io/badge/status-concluded_(WC2026)-555)
![tests](https://img.shields.io/badge/tests-130%2F130_green-2ea44f)
![engine](https://img.shields.io/badge/engine-Dixon--Coles_%2B_time--decay-1f6feb)
![runtime](https://img.shields.io/badge/runtime_deps-3-555)
![python](https://img.shields.io/badge/python-3.11%2B-1f6feb)
![method](https://img.shields.io/badge/approach-MLE_%E2%86%92_expected--value_optimization-8957e5)

---

## TL;DR

An office World Cup pool ("prode") doesn't pay for guessing the winner — it pays for the **exact final score**, with partial credit. That changes the whole problem: you can't just predict "Brazil wins," you need the probability of *every possible scoreline* and then pick the one that scores the most points on average.

This repo is the engine that does it. It was also built backwards on purpose: **the exam that grades the model was written, adversarially reviewed, and locked before a single line of the model existed.** That discipline — and what it caught — is the interesting part.

**Want the 5-minute version with sliders?** → [`docs/teaching/modelo_interactivo.html`](docs/teaching/modelo_interactivo.html) — a self-contained interactive explainer (just open it in a browser). The math you move around on screen is the *actual* algorithm, ported to run live.

---

## The problem in one minute

In most prediction pools you tick a winner. This one is different — for each match you submit a **scoreline** (e.g. `2-1`), and that single guess earns points through three channels at once:

| You get… | When |
|---:|---|
| **12** | the exact scoreline (both numbers right) |
| **5** | the correct outcome — win/draw — even if the score is wrong |
| **+2** | the right goal count for *one* of the teams (stacks with the 5) |
| **+5** | (knockouts only) the penalty-shootout winner — *only if you predicted a draw* |

Here's the twist that makes it a real problem. Take the real result **Argentina 3 – 1 France**. Four different predictions that all "got the winner right" score **7, 7, 5, and 2** points. In a who-wins pool they'd be identical. Here they're not — so a model that only says "Argentina wins" is leaving points on the table. You need an opinion about *every* plausible score.

---

## How it works — four layers, plain language

The system is deliberately split so each piece does one job. (Each has a live slider in the [interactive explainer](docs/teaching/modelo_interactivo.html).)

**1 · Turn teams into goal rates.** Goals are rare events that happen at some average rate over 90 minutes — the natural fit is a **Poisson** distribution. Every national team gets an *attack* and a *defence* number; combine the two teams' numbers and you get how many goals each side is expected to score.

**2 · Fix what plain Poisson gets wrong (Dixon-Coles).** A famous 1997 result: the simple model *under-counts low scores* — exactly the `0-0`, `1-0`, `0-1`, `1-1` results that are most common in football. Dixon & Coles add a small correction that nudges precisely those four cells. And here's why that matters for *us*: those are the same cells where our pool pays the big `12`s and the `+2`s. We didn't pick this model because a blog liked it — we picked it because its whole reason to exist is to sharpen the exact corner of the grid our scoring rewards.

**3 · Weight recent matches more (time-decay).** We have ~49,000 international matches back to 1872 — but Brazil in 1970 tells you nothing about Brazil in 2026. Every match enters the fit with a weight that fades exponentially with age. This single knob turns out to move the predictions *~10× more than the choice of model itself* — recency is the heavyweight, not the fancy math.

**4 · From probabilities to a decision (the optimizer).** Now the payoff. The engine produces a full grid of scoreline probabilities for a match; the optimizer runs every candidate scoreline through the scoring rules and computes its **expected points** — the average payout across all the ways the match could end — and picks the best one. This is why it sometimes chooses a score that *isn't* the single most likely: in Korea–Czechia the most probable single score was `1-1`, but `1-0` wins because "a home win" covers more probability than "a draw." Same arithmetic, on the other hand, is exactly why it predicted `0-0` for Brazil–Morocco, where the draw mass led.

> The guiding question is never *"what's the most likely result?"* but *"which prediction collects the most points, averaged over every future?"*

---

## How it was built (the part worth reading)

The model itself is a weekend of math. The *process* is the case study — every step below is a deliberate inversion of how side projects usually get built:

- **The exam was written before the code.** A test oracle that grades the engine — acceptance cells from the pool's official rules, parameter recovery on synthetic data, a cross-fit against an independent implementation (`statsmodels`), reproduction of a published external reference, structural invariants — was designed and committed **before** the engine existed. The agents building the model were not allowed to touch those tests: a builder who "needs" to change a test stops and escalates.
- **An adversarial review attacked the design first.** Before any code, an independent review pass tried to break the plan — and flagged that the two highest-leverage components (the low-score correction and the recency weighting) had **no binding test**. Both gaps were closed with new oracle tests before building started.
- **Dependencies pass a gate, not a vibe check.** An executable `dependency-gate` blocks any package install that doesn't have a written audit (maintainer, real adoption, transitive surface, license). The engine runs on three audited foundational libraries — surface you don't import is surface you don't have to trust.
- **And the punchline that justifies all of it:** the build still produced a real bug — a subtle gradient inconsistency that **passed all five blocking test families**, because their tidy data never triggered it. It was caught by the one diagnostic marked *report-only*, running on messy real-world data. Lesson logged: don't dismiss the test that doesn't gate.

This is the actual portfolio point. Not "I can fit a Poisson model" — it's: *here's what it looks like to verify before trusting, encode the safety net as a mechanism instead of a paragraph, and run a process that catches its own mistakes.*

📄 The oracle itself: [`tests/test_engine_oracle.py`](tests/test_engine_oracle.py) · the decision log: [`docs/DECISIONS.md`](docs/DECISIONS.md).

---

## What we're honest about (not yet validated)

Intellectual honesty is a feature here, not an afterthought:

- **The magnitudes that matter to *this* pool were never measured by anyone.** All the published research scores a different metric (who-wins accuracy), in a different sport (club football). Whether Dixon-Coles actually beats plain Poisson *in expected pool points* — now measured, and **it doesn't, detectably.** On WC2018/14/10 (rolling-origin, held-out, N=192, paired bootstrap SE) the ρ-correction adds +0.04 pool points/match (z=+0.57) — indistinguishable from zero with the most powerful test available, even though the paired SE is ~2.5× finer than the marginal one. We keep it (it's the theoretical base and does no harm at our ξ), but it isn't a source of points (D8). EP is blind to grid calibration, so we also ran the log-loss leg (#10) — on a metric ~25× more sensitive, ρ doesn't help there either and even trends *worse* (z=+1.47, not significant). Across both metrics ρ earns no place; we keep it on theory, but ρ0 now has empirical backing if we ever simplify. The bivariate variant is a separate leg.
- **The recency knob — measured, and the worry didn't hold.** It's borrowed from club football, and the fear was that it forgets too fast for national teams (~10–15 matches a year) — the suspected reason Brazil–Morocco comes out near-even and the USA looked like a home underdog. Backtested on WC2018/14/10 (rolling-origin, held-out expected pool points), ξ=0.0018 sits inside a *flat* optimum: decaying *faster* is what hurts, not slower, and the USA/Morocco surprises were small-sample noise, not a systematic bias. A plausible hunch, falsified by its own test — the "measure, don't assume" payoff in miniature. **2022 stays deliberately untouched** — reserved as the virgin hold-out for a future final verdict (the exploratory legs, bivariate and penalties, are now closed: D10/D14).
- Predictions stay **editable until each kickoff**, so the system ships on declared assumptions and refines as the tournament gives it real data.

> Success here is defined as *calibration measured out-of-sample* — not "how many results I got right," and explicitly **not** beating coworkers (that's just the office joke that funded the excuse to build this).

---

## Repository structure

```
wcprode/          the engine
  engine.py         Dixon-Coles + time-decay fit (numpy/scipy, analytic gradient)
  scoring.py        the pool's point function — verbatim from the official rules
  optimizer.py      expected-value maximization over the scoreline grid
  tournament.py     Final Soñada: tournament Monte-Carlo → champion/runner-up marginals
  ingest.py         data loading from the pinned source
  data_validation.py  the ingestion gate (schema, range, integrity checks)
  backtest.py         rolling-origin held-out backtest harness (multi-cup)
  bivariate.py        bivariate-Poisson (Karlis-Ntzoufras), analytic-gradient MLE (D10)
  penalty.py          extra-time + shootout model: scores the knockout grid at 120' (D14)
tests/
  test_engine_oracle.py   the pre-approved exam — builders never edit this
  test_tournament_oracle.py  the Final Soñada exam — also never edited
  test_backtest_oracle.py the backtest exam — also never edited
  test_bivariate_oracle.py the bivariate-Poisson exam — also never edited
  test_penalty_oracle.py  the extra-time/shootout exam (D14) — the fifth, also never edited
  test_*.py               scoring, optimizer & scorer-wiring checks vs the official examples
scripts/
  predict_matchday.py     generate EV-optimal picks for a date range (group stage)
  predict_knockouts.py    EV-optimal knockout picks, scoring the grid at 120' (D14)
  score_matchday.py       grade predictions vs real results (match_points, incl. KO +5)
  actuals_from_csv.py     derive the actuals .md from the pinned CSV (no hand transcription)
  diff_repin.py           classify a re-pin diff (NA→score/reschedule/add vs altered score)
  predict_final_sonada.py the Final Soñada pick (tournament Monte-Carlo)
  sanity_backtest_wc2018.py   the report-only diagnostic that caught the bug
  backtest_multicup.py    multi-cup rolling-origin ξ calibration (Phase 3)
  backtest_models.py      DC-full vs ρ0 in held-out pool points, paired SE (D8)
  backtest_logloss.py     DC-full vs ρ0 in held-out log-loss (grid calibration, #10)
  backtest_bivariado.py   bivariate vs DC-full vs ρ0, paired EP + log-loss (D10)
predictions/        versioned prediction snapshots (tracking + evidence)
docs/
  teaching/         ← the interactive explainer + learning checklist
  prode_rules.md    scoring spec + optimizer design
  final_sonada_design.md  Final Soñada design + oracle (D5)
  backtest_design.md      backtest harness design + oracle + API contract (D6)
  bivariate_design.md     bivariate-Poisson (KN) design + oracle (D10)
  data_security.md  ingestion threat model + validation gate design
  DECISIONS.md      decision log (why in-house, why the gate, etc.)
```

Generate predictions yourself:
```bash
.venv/Scripts/python.exe scripts/predict_matchday.py --from 2026-06-15 --to 2026-06-17 --mode full
```

---

## Status & roadmap

**Concluded (the tournament is over; this repo is a finished case study).** The pipeline ran live through the whole tournament with all tests green (130/130, all **five** oracles passing): every round from the group stage to the semifinals was predicted and then scored against real results (see `predictions/scored_*.md`), and the final was predicted on 2026-07-18 (`predictions/final_full_2026-07-18.txt`; it is not scored in this repo). The Final Soñada (Argentina + Spain) was locked on Jun 24. Knockouts are scored at 120' by an extra-time/shootout model (D14). Phase-3 validation is closed: the recency knob (ξ) calibrated out-of-sample (D7); DC-vs-ρ0 measured across EP and log-loss (D8: the ρ-correction earns no place in either; ρ0 is empirically viable); and a Karlis-Ntzoufras bivariate-Poisson earns no significant place either (D10: EP z=1.73, n.s.) — so **no form of goal-dependence (ρ nor KN) pays its way against national teams.** A dependency gate screened installs (audits in `docs/dep_audits/`).

| Milestone | When | Notes |
|------|------|---------------|
| Refresh picks per matchday — done ✅ | rolling, until each kickoff | re-fetch recent results → re-fit → update only the picks that moved |
| **Final Soñada** — locked ✅ (Argentina + Spain) | done **Jun 24** | re-pinned + re-fit, tournament Monte-Carlo re-run |
| Recency knob (ξ) — calibrated ✅ | done 2026-06-15 | rolling-origin backtest on WC2018/14/10 → ξ=0.0018 confirmed (flat optimum) |
| Model comparison (DC vs ρ0) — measured ✅ | done 2026-06-15 | paired backtest WC2018/14/10 on EP (#8, z=+0.57) and log-loss (#10, z=+1.47 *worse*, n.s.): ρ earns no place; keep `fit_rho` (ρ0 viable) |
| Bivariate-Poisson (explicit dependence) — measured ✅ | done 2026-06-16 | paired backtest, EP bivariate vs ρ0 z=1.73 (n.s.), log-loss tie; λ3≈0.05. Closes Phase 3: no dependence form pays its way. Needed an analytic gradient — the numerical one didn't converge at 300-team scale and flipped the sign (D10) |
| Knockouts (R32 → final) — done ✅ | Jun 28 – Jul 18 | scored at 120' via the extra-time/shootout model (D14); R32, R16, quarterfinals and semifinals predicted and scored; final predicted |


---

## Tech & methodology

- **Engine:** Dixon-Coles bivariate-Poisson with exponential time-decay, fit by maximum likelihood (`scipy.optimize`, analytic gradient). Pure `numpy`/`scipy`/`pandas` — **three runtime dependencies**, a deliberately minimal tree (the rejected alternative stack pulled in ~75 transitive packages).
- **Decision layer:** expected-value maximization over the full scoreline grid under the pool's real scoring — separable per match, so each pick is an independent `argmax`.
- **Verification:** a pre-committed test oracle (acceptance vs official examples · synthetic parameter-recovery · cross-fit against `statsmodels` · external-reference reproduction · invariants · a real-data diagnostic), plus an executable dependency-gate and an adversarial design review. Methodology inherited from a parent research system: verify-before-trust, source-first, declared assumptions.
- **Data:** one pinned, hash-verified public source (international results back to 1872, CC0). No scraping, no pickles, no surprises.

---

## Notes

- **Built with** [Claude Code](https://claude.com/claude-code) as an orchestration exercise — part of the point was to practice multi-agent build pipelines (design → adversarial review → parallel builders → verification), not just to ship a model.
- **What is not here:** the office pool's verbatim terms and rules pages are the organizer's text and carry employer-specific details, so they stay out of the public tree; the scoring spec they define is captured in `docs/prode_rules.md`, and its 12 worked examples are the oracle for `tests/test_match_points.py`. Session handoffs and the private notes repo they point to are omitted too.
- **Data provenance:** fixtures and results are pinned by hash in `data/raw/sources.lock.json` and re-fetched by the ingest scripts (raw CSVs are not committed). The third-place combinations table (`data/raw/wc2026_thirds_combinations.json`) is derived from the Wikipedia third-place table pinned by `oldid` (CC BY-SA 4.0) and is committed because the engine needs it at import time.
- **Reproduce the green suite** (130 tests; the oracle tests fail loudly, by design, when the pinned data is absent):

  ```bash
  pip install -e ".[dev]"
  python -c "from wcprode.ingest import download_pinned as d; d('results.csv'); d('shootouts.csv')"
  # O5 reference fixture: download https://www.football-data.co.uk/mmz4281/1718/E0.csv to data/raw/E0_1718.csv
  pytest -q
  ```
- **Language:** docs and code in English; the interactive explainer is in Spanish (built for its first reader). Internal history before this repo lives in its parent up to commit `84bda57`.

## License

MIT — see [`LICENSE`](LICENSE).

---

*Measure, don't assume.*
