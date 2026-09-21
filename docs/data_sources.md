# Data Sources — World Cup 2026 Prode

Manifest of candidate data sources. **Phase 1 verification done 2026-06-04** (orchestrator DIRECT_FETCH — see Verification Log below). The 3 critical sources for Jun 11 are resolved: martj42 (CONFIRMED, live), Elo (derive from martj42), fixtures (CONFIRMED). Backtest-only sources (historical odds) stay deferred. **Security: threat model + ingestion gate (`data_validation.py` sketch) in [data_security.md](data_security.md) — pin martj42 to a commit SHA before fetching.**

| Source | Provides | URL (verify) | Status | Notes |
|--------|----------|--------------|--------|-------|
| martj42 international results | Results + **shootouts.csv** (penalties) + goalscorers | [github.com/martj42/international_results](https://github.com/martj42/international_results) | **CONFIRMED** | Commits **daily** (latest 2026-06-04), CC0 license, ~49k matches 1872→2026. **Kaggle credential (verified): 2539 votes, Usability 10.00, 382 notebooks — adoption lives on Kaggle, not GitHub's 176★.** `results.csv`: date, home/away_team, home/away_score, tournament, city, country, neutral. README says "up to 2024" but that is stale text — commit history proves fresh. **Base of the fit + penalty data.** |
| World Football Elo | Elo ratings per national team | [eloratings.net](https://www.eloratings.net/) | **PARTIAL → DERIVE** | Site is a SPA, no official export (headless scrape, or [Kaggle mirror](https://www.kaggle.com/datasets/saifalnimri/international-football-elo-ratings) only to 2025, 3rd-party). **Decision: compute our own Elo from martj42 results** (public formula, fresh to 2026, full control + consistent with time-decay). eloratings = optional validation reference, NOT a hard dependency |
| FIFA / Coca-Cola ranking | Official ranking | fifa.com/.../ranking | TO-VERIFY | Weaker than Elo, but a feature |
| WC2026 fixtures | 104-match schedule, 12 groups | [fixturedownload.com](https://fixturedownload.com/results/fifa-world-cup-2026) (CSV/JSON/ICS) + Kaggle | **CONFIRMED** | Draw done 2025-12-05; 72 group + 32 knockout. Group stage Jun 11-27; **Fecha 3 = Jun 24-27 (opens Switzerland–Canada), R32 from Jun 28**. Aggregator → cross-validate group assignments + kickoff times vs FIFA official before use |
| Historical penalty shootouts | Past shootout outcomes (winner) | **martj42 `shootouts.csv`** | **CONFIRMED** | Same repo (CC0): date, home/away_team, winner, first_shooter. Calibrate the +5 draw-option-value term (knockouts, Jun 28+). Already covered — no separate source needed |
| Scoreline validation set | Held-out matches with actual scorelines | derive from martj42 | DERIVED | Score the optimizer on real `match_points` / expected points, not just RPS. Built from the results dataset, not a new source |
| Historical closing odds | Bookmaker closing odds, past WCs | TBD | RISK | **Best backtest benchmark.** Availability uncertain → candidate for the `/deep-research` run |
| Opta supercomputer 2026 | Published title/advance probabilities | (Opta / TheAnalyst) | REFERENCE | 2026 sanity-check only; historicals not easily available |
| WC2026 bracket + Annex C (495 combos) | tercero→slot R32 + reglas de desempate | [WP knockout](https://en.wikipedia.org/wiki/2026_FIFA_World_Cup_knockout_stage) + [third-place template](https://en.wikipedia.org/wiki/Template:2026_FIFA_World_Cup_third-place_table) | **CONFIRMED (2026-06-15)** | Pineado por oldid (1359418806 / 1357614390). 495 combos validados estructuralmente; desempate 2026 = head-to-head PRIMERO. Ingesta: `scripts/ingest_thirds_table.py`. Residual: PDF FIFA primario inalcanzable (render JS). Para la Final Soñada (D5) |
| WC2026 group composition (A-L) | qué 4 equipos por grupo | martj42 fixtures (membresía) + [Wikipedia](https://en.wikipedia.org/wiki/2026_FIFA_World_Cup) (etiquetas) | **CONFIRMED (2026-06-15)** | Membresía autoritativa de martj42; etiquetas A-L ancladas por Pot 1; A-F cruzados vs `actuals_2026-06-15.md`. Ingesta: `scripts/ingest_groups.py` |

## Open data questions (for /deep-research)

> **Priority note (2026-06-04 audit):** these are **backtest** questions, NOT on the Jun 11 critical path. Phase 1 = the 3 critical sources above (martj42 results, Elo, fixtures) is the real blocker. Defer the odds deep-research post-kickoff.

1. Is clean historical **closing odds** data for past World Cups publicly available, and in what format? Soundest out-of-sample backtest benchmark (a 1X2/market signal — feeds the outcome term + Final Soñada futures more than the exact-scoreline term).
2. Best-practice **calibration** approach for sparse international football (few matches per team per cycle)?

## Verification Log (Phase 1 — 2026-06-04, orchestrator DIRECT_FETCH)

| # | Claim | Provenance | Confidence | Source | Falsified by |
|---|-------|------------|------------|--------|--------------|
| 1 | martj42 dataset is fresh to 2026, not "up to 2024" | DIRECT_FETCH | HIGH | [commits/master](https://github.com/martj42/international_results/commits/master) — latest 2026-06-04, "May results" 2026-06-01 | A `results.csv` whose max(date) < 2026 despite the recent commits |
| 2 | martj42 license = CC0-1.0 (unrestricted use) | DIRECT_FETCH | HIGH | [repo](https://github.com/martj42/international_results) | LICENSE file showing other than CC0-1.0 |
| 3 | eloratings.net has no official export (SPA scrape or 3rd-party mirror only) | DIRECT_FETCH + SEARCH_INDEX | MEDIUM | [eloratings.net](https://www.eloratings.net/) (SPA, empty fetch) + [Kaggle mirror](https://www.kaggle.com/datasets/saifalnimri/international-football-elo-ratings) | A documented official `.tsv`/CSV/API endpoint on the site |
| 4 | WC2026 fixtures available as structured CSV/JSON; draw done 2025-12-05 | DIRECT_FETCH + SEARCH_INDEX | HIGH | [fixturedownload](https://fixturedownload.com/results/fifa-world-cup-2026) + [Wikipedia](https://en.wikipedia.org/wiki/2026_FIFA_World_Cup) | FIFA official fixture contradicting the aggregator's group/date data |
| 5 | WC2026 bracket (R32 pairings, 495-combo thirds table, head-to-head-first tiebreak) verified for the Final Soñada (D5) | DIRECT_FETCH (2026-06-15) | HIGH (structural) | WP knockout oldid=1359418806 + third-place template oldid=1357614390; ESPN+Yahoo (tiebreak, "new for 2026") | A FIFA-primary Annex C contradicting the pinned Wikipedia table; struct. validation (495 C(12,8), perfect matching, slot eligibility) failing |

**Net:** the only hard dependency for Jun 11 (martj42) is CONFIRMED and live; Elo is derived, not fetched; fixtures are abundant. **Phase 1 effectively unblocked** — next is env + engine build.

## Known constraints

- xG (expected goals) for national teams is **thin** vs club football — TO-VERIFY, likely limits feature richness. Not a blocker: Dixon-Coles fits on goals, not xG.
