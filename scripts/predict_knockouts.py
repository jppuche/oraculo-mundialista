"""predict_knockouts.py - predicciones EV-optimas para las eliminatorias del WC2026 (R32+).

Mismo engine + optimizer que predict_matchday, pero para KO:
  optimize_match(knockout=True) puntua el grid a 120' (penalty.overtime_grid): el alargue
  redistribuye la masa de empate (sigue empate -> penales, o se resuelve -> favorito), y el
  +5 de penales usa P(empate 120') = P(va a penales), no P(empate 90'). Corrige el sobre-tilt
  a empates del draw-option-value (D14). prode_rules 1.4 + docs/penalty_model_design.md.

Reglas de KO que cablea (prode_rules 1.4):
  - El marcador se puntua sobre 90/120 min (penales EXCLUIDOS del score base).
  - El +5 de penales se cobra solo si tu pick es un empate.
  - pen_win_prob=0.55 constante = "acerto el ganador de la tanda eligiendo al favorito"
    (~moneda al aire con leve sesgo). Calibrar por matchup desde shootouts.csv es un
    refinamiento de 2o orden con su propio oraculo (D2), NO bloqueante.

Sedes: neutrales salvo anfitriones (Mexico/USA/Canada), segun la columna `neutral` de
martj42. NO es oraculo: editable hasta cada kickoff.

Uso:
  .venv/Scripts/python.exe scripts/predict_knockouts.py --from 2026-06-29 --to 2026-07-03 --mode full
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from wcprode import ingest
from wcprode.engine import DixonColesEngine
from wcprode.optimizer import DEFAULT_PEN_WIN_PROB, optimize_match
from wcprode.penalty import ET_TIME_SCALE

DEFAULT_XI = 0.0018


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--from", dest="dfrom", default="2026-06-28")
    ap.add_argument("--to", dest="dto", default="2026-07-19")
    ap.add_argument("--mode", dest="mode", choices=["full", "rho0"], default="full",
                    help="full = DC completo (rho fitted); rho0 = Poisson indep. ponderado")
    ap.add_argument("--xi", dest="xi", type=float, default=DEFAULT_XI,
                    help="time-decay rate (default 0.0018, D7: no recalibrar)")
    ap.add_argument("--pen-win-prob", dest="pen_win_prob", type=float, default=DEFAULT_PEN_WIN_PROB,
                    help="P(ganar la tanda) si predigo empate; 0.55 = favorito pre-partido (D2)")
    args = ap.parse_args()

    fit_rho = (args.mode == "full")

    # ingest + fit sobre partidos jugados (mismo fit que grupos; max decay = mas reciente)
    df, _ = ingest.load_results()
    played = ingest.played_results(df)
    eng = DixonColesEngine(xi=args.xi, fit_rho=fit_rho).fit(played)

    fixtures = ingest.wc2026_knockout_fixtures(df, dfrom=args.dfrom, dto=args.dto)
    sel = fixtures.sort_values(["date", "home_team"]).reset_index(drop=True)

    print(
        f"# WC2026 KNOCKOUTS - prediccion EV-optima | modo={args.mode} "
        f"(fit_rho={fit_rho}, rho={eng.rho_:.4f}, gamma={eng.home_adv_:.4f}, xi={eng.xi}) "
        f"| fit={len(played)} partidos | pen_win_prob={args.pen_win_prob} | grid@120'(c={ET_TIME_SCALE:.3f}) | {len(sel)} cruces"
    )
    print(
        "# grid puntuado a 120' (penalty.overtime_grid, alargue): el +5 de penales usa "
        "P(empate 120'); P(H/D/A) y modal son a 120'. prode_rules 1.4 + penalty_model_design.md (D14)\n"
    )
    if len(sel) == 0:
        print("(sin cruces en la ventana)")
        return

    for _, row in sel.iterrows():
        grid = eng.predict(row["home_team"], row["away_team"], neutral=bool(row["neutral"])).grid
        r = optimize_match(grid, knockout=True, pen_win_prob=args.pen_win_prob)
        ph, pa = r["best"]
        mh, ma = r["modal_scoreline"]
        alts = ", ".join(f"{a}-{b}" for (a, b), _ in r["ranking"][1:4])
        venue = "neutral" if row["neutral"] else "LOCAL"
        # draw-option-value: si el pick es empate, el +5 de penales esta en juego.
        if ph == pa:
            fav = row["home_team"] if r["p_home"] >= r["p_away"] else row["away_team"]
            pen_note = f"  <- EMPATE (+pen, P(emp)={r['p_draw']:.2f}, favorito {fav})"
        else:
            pen_note = ""
        print(
            f"{row['date']}  {row['home_team']:>24} {ph}-{pa} {row['away_team']:<24}"
            f"  EV={r['best_ev']:.2f}  [H {r['p_home']:.2f} D {r['p_draw']:.2f} A {r['p_away']:.2f}]"
            f"  modal {mh}-{ma} (P={r['p_best_exact']:.2f})  alt: {alts}  ({venue}){pen_note}"
        )


if __name__ == "__main__":
    main()
