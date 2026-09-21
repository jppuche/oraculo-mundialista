"""predict_final_sonada.py — Final Soñada (segundo optimizador): Monte Carlo de
torneo -> marginales P(campeón)/P(subcampeón) -> par óptimo A≠B (10 pts c/u).

docs/final_sonada_design.md. Motor in-house (DixonColesEngine) provee P(h,a) por
matchup; wcprode.tournament simula el bracket WC2026 verificado (DIRECT_FETCH).

Condicionamiento: fija los partidos de grupo YA jugados (del pin de martj42) y simula
el resto. Con el pin pre-torneo => corrida PROVISIONAL (priors pre-torneo). Para la
corrida real cerca del deadline (2026-06-24): re-pin martj42 (Fechas 1-2) -> re-fit
-> re-correr; el condicionamiento entra solo.

Uso:
  .venv/Scripts/python.exe scripts/predict_final_sonada.py --n 50000 --seed 20260624
"""
import argparse
import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from wcprode import ingest
from wcprode.engine import DixonColesEngine
from wcprode.tournament import TournamentSimulator, final_sonada_pick, load_thirds_table

REPO = Path(__file__).resolve().parent.parent
DEFAULT_XI = 0.0018
WC_START, WC_END = "2026-06-11", "2026-06-27"


def load_groups() -> dict:
    data = json.loads((REPO / "data" / "raw" / "wc2026_groups.json").read_text(encoding="utf-8"))
    return data["groups"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50_000, help="número de simulaciones")
    ap.add_argument("--seed", type=int, default=20260624)
    ap.add_argument("--xi", type=float, default=DEFAULT_XI)
    ap.add_argument("--top", type=int, default=12, help="cuántos equipos listar")
    ap.add_argument("--results", default=None,
                    help="CSV de results alternativo (overlay de resultados confirmados "
                         "pendientes de upstream); si se pasa NO verifica hash. "
                         "Default: el pin verificado de sources.lock.json")
    ap.add_argument("--out", default=None,
                    help="Ruta del reporte .md (default: predictions/final_sonada_<pinned_at>.md)")
    args = ap.parse_args()

    if args.results:
        df, _ = ingest.load_results(path=args.results, verify=False)
    else:
        df, _ = ingest.load_results()
    played = ingest.played_results(df)
    eng = DixonColesEngine(xi=args.xi, fit_rho=True).fit(played)

    groups = load_groups()
    team_group = {t: L for L, ts in groups.items() for t in ts}

    # fixtures de grupo NO jugados -> remaining (con label de grupo + neutral)
    fixtures = ingest.wc2026_group_fixtures(df)
    remaining = [
        (team_group[r["home_team"]], r["home_team"], r["away_team"], bool(r["neutral"]))
        for _, r in fixtures.iterrows()
    ]
    # partidos de grupo WC2026 YA jugados -> condicionamiento (fijos)
    wc_played = played[(played["tournament"] == "FIFA World Cup")
                       & (played["date"] >= WC_START) & (played["date"] <= WC_END)]
    played_results = [
        (r["home_team"], r["away_team"], int(round(float(r["home_score"]))),
         int(round(float(r["away_score"]))))
        for _, r in wc_played.iterrows()
    ]

    def provider(home, away, neutral=True):
        return eng.predict(home, away, neutral=neutral).grid

    sim = TournamentSimulator(
        groups=groups, played_results=played_results, remaining_fixtures=remaining,
        thirds_table=load_thirds_table(), prob_provider=provider,
    )
    res = sim.run(n_sims=args.n, seed=args.seed)
    pick = final_sonada_pick(res["champion"], res["runnerup"])

    champ = res["champion"]
    runr = res["runnerup"]
    se = res["se"]
    n_played = len(played_results)
    provisional = n_played < 72

    def top(d, k):
        return sorted(d.items(), key=lambda kv: kv[1], reverse=True)[:k]

    # ---- stdout ----
    tag = "PROVISIONAL (pin pre-torneo)" if n_played == 0 else \
          (f"condicionado en {n_played} partidos jugados"
           + (" (PROVISIONAL, grupos incompletos)" if provisional else ""))
    print(f"# Final Soñada — Monte Carlo de torneo | N={args.n} seed={args.seed} | {tag}")
    print(f"# fit={len(played)} partidos | xi={args.xi} rho={eng.rho_:.4f} gamma={eng.home_adv_:.4f}\n")
    print(f"{'CAMPEÓN':<22}{'P':>7}{'±SE':>7}     {'SUBCAMPEÓN':<22}{'P':>7}")
    tc, tr = top(champ, args.top), top(runr, args.top)
    for (ct, cp), (rt, rp) in zip(tc, tr):
        print(f"{ct:<22}{cp:>7.3f}{se[ct]:>7.3f}     {rt:<22}{rp:>7.3f}")
    print(f"\nPAR ÓPTIMO (max 10·P(camp)+10·P(subcamp), A≠B):")
    print(f"  Campeón    -> {pick['champion']}  (P={champ[pick['champion']]:.3f})")
    print(f"  Subcampeón -> {pick['runnerup']}  (P={runr[pick['runnerup']]:.3f})")
    print(f"  EV = {pick['expected_points']:.3f} pts")

    # ---- reporte markdown ----
    lines = [
        "# Oráculo Mundialista — Final Soñada (Monte Carlo de torneo)",
        "",
        "## Provenance / config",
        f"- **Método:** {args.n} simulaciones del bracket WC2026 verificado "
        "(docs/final_sonada_design.md §3.1), probs por matchup del DixonColesEngine.",
        f"- **Fit:** {len(played)} partidos, xi={args.xi}, rho={eng.rho_:.4f}, gamma={eng.home_adv_:.4f}.",
        f"- **Condicionamiento:** {tag}. seed={args.seed}.",
        "- **Knobs (JP 2026-06-15):** tilt anfitrión por sede (knockouts), penales 0.55 al favorito.",
        "- **Objetivo:** 10·P(campeón) + 10·P(subcampeón), A≠B (prode_rules §3.2).",
        "",
        "## Par óptimo",
        "",
        f"- **Campeón:** {pick['champion']}  (P={champ[pick['champion']]:.3f} ± {se[pick['champion']]:.3f})",
        f"- **Subcampeón:** {pick['runnerup']}  (P={runr[pick['runnerup']]:.3f})",
        f"- **EV esperado:** {pick['expected_points']:.2f} pts (de 20 posibles)",
        "",
        f"## Marginales (top {args.top})",
        "",
        "| # | Campeón | P | ±SE | Subcampeón | P |",
        "|---|---------|---|-----|------------|---|",
    ]
    for i, ((ct, cp), (rt, rp)) in enumerate(zip(tc, tr), 1):
        lines.append(f"| {i} | {ct} | {cp:.3f} | {se[ct]:.3f} | {rt} | {rp:.3f} |")
    lines += [
        "",
        "## Lectura honesta",
        "",
        "- **Subcampeón ≠ 2° favorito:** subcampeón = llega a la final y la pierde; su "
        "marginal la maximiza el fuerte-pero-no-dominante, no el favorito (prode_rules §3.2).",
        "- **xi=0.0018 CALIBRADO (D7):** en plateau plano de EP held-out [0.0005-0.003]; no recalibrar.",
        f"- **N={args.n}:** el SE de las marginales del top está reportado; la cola es ruidosa.",
    ]
    if provisional:
        lines.append(f"- **PROVISIONAL (grupos incompletos):** {n_played} partidos de grupo "
                     "condicionados; el resto (Fecha 3 + knockouts) simulado. La cola es ruidosa.")
    if args.out:
        out = Path(args.out)
    else:
        lock = json.loads((REPO / "data" / "raw" / "sources.lock.json").read_text(encoding="utf-8"))
        pinned = lock["martj42_international_results"]["pinned_at"]
        out = REPO / "predictions" / f"final_sonada_{pinned}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nReporte escrito en: {out}")


if __name__ == "__main__":
    main()
