"""predict_matchday.py — predicciones optimas (expected points) para los partidos
del WC2026 en una ventana de fechas. Deliverable usable: una linea por partido,
lista para cargar en el prode.

Usa el engine in-house (DixonColesEngine, Dixon & Coles 1997) + optimizer (argmax EV
sobre la grilla de marcadores). NO es oraculo: editable.

Modos (--mode):
  full  : DC completo (rho fitted + decay)            -> fit_rho=True
  rho0  : Poisson independiente ponderado (rho=0)     -> fit_rho=False (modo escalera dia-1)

Uso:
  .venv/Scripts/python.exe scripts/predict_matchday.py                                  # 11-13 jun, full
  .venv/Scripts/python.exe scripts/predict_matchday.py --from 2026-06-11 --to 2026-06-27
  .venv/Scripts/python.exe scripts/predict_matchday.py --mode rho0
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from wcprode import ingest
from wcprode.engine import DixonColesEngine
from wcprode.optimizer import optimize_match

DEFAULT_XI = 0.0018


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="dfrom", default="2026-06-11")
    ap.add_argument("--to", dest="dto", default="2026-06-13")
    ap.add_argument("--mode", dest="mode", choices=["full", "rho0"], default="full",
                    help="full = DC completo (rho fitted); rho0 = Poisson indep. ponderado")
    ap.add_argument("--xi", dest="xi", type=float, default=DEFAULT_XI,
                    help="time-decay rate (default 0.0018, half-life ~385 dias)")
    args = ap.parse_args()

    fit_rho = (args.mode == "full")

    # ingest + fit sobre partidos jugados
    df, _ = ingest.load_results()
    played = ingest.played_results(df)
    eng = DixonColesEngine(xi=args.xi, fit_rho=fit_rho).fit(played)

    fixtures = ingest.wc2026_group_fixtures(df)
    sel = fixtures[(fixtures["date"] >= args.dfrom) & (fixtures["date"] <= args.dto)].reset_index(drop=True)

    print(
        f"# WC2026 — prediccion EV-optima | modo={args.mode} "
        f"(fit_rho={fit_rho}, rho={eng.rho_:.4f}, gamma={eng.home_adv_:.4f}, xi={eng.xi}) "
        f"| fit={len(played)} partidos | {len(sel)} fixtures\n"
    )
    if len(sel) == 0:
        print("(sin fixtures en la ventana)")
        return

    for _, row in sel.iterrows():
        # grupos: sin penales (knockout=False). neutral segun la columna martj42.
        grid = eng.predict(row["home_team"], row["away_team"], neutral=bool(row["neutral"])).grid
        r = optimize_match(grid)
        ph, pa = r["best"]
        mh, ma = r["modal_scoreline"]
        alts = ", ".join(f"{a}-{b}" for (a, b), _ in r["ranking"][1:4])
        venue = "neutral" if row["neutral"] else "LOCAL"
        print(
            f"{row['date']}  {row['home_team']:>22} {ph}-{pa} {row['away_team']:<22}"
            f"  EV={r['best_ev']:.2f}  [H {r['p_home']:.2f} D {r['p_draw']:.2f} A {r['p_away']:.2f}]"
            f"  modal {mh}-{ma} (P={r['p_best_exact']:.2f})  alt: {alts}  ({venue})"
        )


if __name__ == "__main__":
    main()
