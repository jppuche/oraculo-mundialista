"""backtest_multicup.py — calibración de xi sobre WC2018 + WC2014 + WC2010 (Fase 3).

Experimento rolling-origin held-out por copa:
  - held_out = 64 partidos de cada copa (FIFA World Cup en el rango de fechas).
  - played (universo de fit) = TODOS los jugados (incluyendo las copas held-out,
    para rolling REAL: el pasado de cada copa alimenta el fit de fechas posteriores).
  - Modo: full (fit_rho=True), ventana 8 años.
  - Grid de xi: configurable por --xi-grid (default: rango para calibración de Fase 3).
  - SE bootstrap: 2000 iter, seed=20260615 (contrato).

GUARDRAIL DURO: ningún partido de held_out puede caer en 2022-11-20..2022-12-18.
WC2022 es RESERVADA VIRGEN para la validación final de Fase 3.

Reporte: una línea por xi con EP, SE bootstrap, n_predicted, n_skipped.
La interpretación (si xi está bien calibrado, decisión de Fase 3) la hace el orquestador.

Uso:
  # Smoke-run (WC2018, grid chico):
  .venv/Scripts/python.exe scripts/backtest_multicup.py --cups 2018 --xi-grid 0.0005 0.0018 0.005

  # Experimento completo (3 copas, grid Fase 3):
  .venv/Scripts/python.exe scripts/backtest_multicup.py

Rangos de fechas verificados (64 partidos c/u):
  WC2018: 2018-06-14..2018-07-15
  WC2014: 2014-06-12..2014-07-13
  WC2010: 2010-06-11..2010-07-11
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np

from wcprode import ingest
from wcprode.backtest import xi_grid_search, CUP_RANGES, cup_held_out, assert_no_wc2022

# ---- grid de xi por defecto para el experimento completo de Fase 3 ----------
DEFAULT_XI_GRID = [0.0001, 0.0005, 0.001, 0.0018, 0.003, 0.005, 0.010]


def _print_table(cup_label: str, table: list, n_matches_held: int):
    print(f"\n--- {cup_label} (held_out={n_matches_held} partidos) ---")
    print(f"{'xi':>10}  {'EP':>8}  {'SE':>8}  {'n_pred':>8}  {'n_skip':>8}")
    print("-" * 54)
    for xi, ep, se, n_pred in table:
        n_skip = n_matches_held - n_pred
        ep_str = f"{ep:.4f}" if not (isinstance(ep, float) and ep != ep) else "  nan"
        se_str = f"{se:.4f}" if not (isinstance(se, float) and se != se) else "  nan"
        print(f"{xi:>10.4f}  {ep_str:>8}  {se_str:>8}  {n_pred:>8}  {n_skip:>8}")


def main():
    ap = argparse.ArgumentParser(
        description="Calibración de xi (backtest multi-copa rolling-origin, Fase 3)"
    )
    ap.add_argument(
        "--cups", dest="cups", nargs="+", type=int,
        choices=[2018, 2014, 2010], default=[2018, 2014, 2010],
        metavar="YEAR",
        help="Copas a procesar (default: 2018 2014 2010). Solo esos años son válidos."
    )
    ap.add_argument(
        "--xi-grid", dest="xi_grid", nargs="+", type=float,
        default=DEFAULT_XI_GRID,
        metavar="XI",
        help=f"Grid de xi (default: {DEFAULT_XI_GRID})"
    )
    ap.add_argument(
        "--window-years", dest="window_years", type=float, default=8.0,
        help="Ventana de fit en años (default 8). 0 = todo el historial."
    )
    ap.add_argument(
        "--n-boot", dest="n_boot", type=int, default=2000,
        help="Iteraciones bootstrap SE (default 2000)"
    )
    args = ap.parse_args()

    window_years = args.window_years if args.window_years > 0 else None
    xi_grid = sorted(args.xi_grid)

    # ---- ingest
    df, _ = ingest.load_results()
    played = ingest.played_results(df)
    played = played.copy()
    import pandas as pd
    played["date"] = pd.to_datetime(played["date"])

    cups = sorted(args.cups, reverse=True)  # más reciente primero para presentación

    print(
        f"# backtest_multicup.py — calibración de xi (Fase 3)\n"
        f"# universo fit: {len(played)} partidos jugados\n"
        f"# copas held-out: {[str(c) for c in cups]}\n"
        f"# grid xi: {xi_grid}\n"
        f"# modo: full (fit_rho=True) | ventana: {window_years}a | bootstrap: {args.n_boot} iter"
    )

    aggregated: dict[float, list[float]] = {xi: [] for xi in xi_grid}

    for year in cups:
        cup_label = f"WC{year}"
        held_out = cup_held_out(played, year)

        # GUARDRAIL DURO — WC2022 VIRGEN
        assert_no_wc2022(held_out, cup_label)

        n_held = len(held_out)
        if n_held == 0:
            print(f"\n[WARN] {cup_label}: 0 partidos en held_out — verificar ingest.")
            continue

        print(f"\n# corriendo {cup_label} ({n_held} partidos held-out, {len(xi_grid)} valores de xi)...")

        res = xi_grid_search(
            played, held_out, xi_grid,
            fit_rho=True,
            window_years=window_years,
            n_boot=args.n_boot,
            seed=20260615,
        )

        _print_table(cup_label, res["table"], n_held)
        print(f"  argmax_xi({cup_label}) = {res['argmax_xi']:.4f}")

        for xi, ep, se, n_pred in res["table"]:
            if not (isinstance(ep, float) and ep != ep):  # excluir nan
                aggregated[xi].append(ep)

    # ---- resumen agregado (media no ponderada de EP por copa)
    if len(cups) > 1:
        print(f"\n--- AGREGADO ({len(cups)} copas, media no ponderada de EP) ---")
        print(f"{'xi':>10}  {'EP_medio':>10}  {'copas':>6}")
        print("-" * 34)
        agg_table = []
        for xi in xi_grid:
            eps = aggregated[xi]
            if eps:
                ep_mean = np.mean(eps)
                agg_table.append((xi, ep_mean, len(eps)))
                print(f"{xi:>10.4f}  {ep_mean:>10.4f}  {len(eps):>6}")
        if agg_table:
            best = max(agg_table, key=lambda r: r[1])
            print(f"\n  argmax_xi (agregado) = {best[0]:.4f}  [EP={best[1]:.4f}]")

    print("\n# [la interpretación (calibración de xi) la hace el orquestador, NO este script]")


if __name__ == "__main__":
    main()
