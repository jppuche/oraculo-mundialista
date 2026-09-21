"""backtest_logloss.py — calibración de la grilla P(h,a) por log-loss held-out (Fase 3, #10).

Experimento rolling-origin held-out sobre WC2018/14/10:
  - held_out = partidos FIFA World Cup de cada copa (rango verificado en CUP_RANGES).
  - Modelo A: DC-full (fit_rho=True), ξ operativo (default 0.0018).
  - Modelo B: ρ0 (fit_rho=False), mismo ξ.
  - Métrica: log-loss held-out = -log P[marcador real] sobre la grilla P(h,a) completa.
  - SE PAREADO (bootstrap sobre delta = ll_full - ll_rho0).
  - Guardrail: WC2022 (2022-11-20..2022-12-18) es RESERVADA VIRGEN, no toca held_out.
  - Seed del contrato: 20260615.

log-loss es DIAGNÓSTICO de calibración; NO se re-optimiza el modelo sobre él
(intención EP-pure del proyecto). Conecta con #8: ¿ρ mejora la calibración de la matriz
P(h,a) aunque no mueva el EP (decisión)?

CONVENCIÓN DE SIGNO: menor log-loss = mejor. delta = ll_full - ll_rho0;
  d_ll < 0  ⇒  DC-full calibra MEJOR la matriz que ρ0.

NOTA: La interpretación de los resultados la hace el orquestador, no este script.

Uso:
  # Corrida operativa (ξ=0.0018):
  .venv/Scripts/python.exe scripts/backtest_logloss.py

  # Robustez (varios ξ):
  .venv/Scripts/python.exe scripts/backtest_logloss.py --xi-grid 0.0 0.0018 0.003
"""
import argparse
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd

from wcprode import ingest
from wcprode.backtest import (
    paired_logloss_comparison,
    cup_held_out,
    assert_no_wc2022,
    CUP_RANGES,
    _align_records,
    _paired_bootstrap_se,
)


def _fmt(val, fmt=".4f"):
    """Formatea un float; 'nan' si nan."""
    if isinstance(val, float) and val != val:
        return "nan"
    return format(val, fmt)


def _fmt_signed(val, fmt=".4f"):
    """Formatea un float con signo explícito; 'nan' si nan."""
    if isinstance(val, float) and val != val:
        return "nan"
    return format(val, "+" + fmt)


def main():
    ap = argparse.ArgumentParser(
        description="Calibración de la grilla por log-loss (DC-full vs rho0, Fase 3 #10)"
    )
    ap.add_argument(
        "--cups", dest="cups", nargs="+", type=int,
        choices=[2018, 2014, 2010], default=[2018, 2014, 2010],
        metavar="YEAR",
        help="Copas a procesar (default: 2018 2014 2010).",
    )
    ap.add_argument(
        "--xi-grid", dest="xi_grid", nargs="+", type=float,
        default=[0.0018],
        metavar="XI",
        help="Grid de xi (default: [0.0018] operativo). Pasar varios para robustez.",
    )
    ap.add_argument(
        "--window-years", dest="window_years", type=float, default=8.0,
        help="Ventana de fit en años (default 8). 0 = todo el historial.",
    )
    ap.add_argument(
        "--n-boot", dest="n_boot", type=int, default=2000,
        help="Iteraciones bootstrap SE (default 2000).",
    )
    args = ap.parse_args()

    window_years = args.window_years if args.window_years > 0 else None
    xi_grid = sorted(args.xi_grid)
    cups = sorted(args.cups, reverse=True)  # más reciente primero
    seed = 20260615

    # ---- ingest
    df, _ = ingest.load_results()
    played = ingest.played_results(df)
    played = played.copy()
    played["date"] = pd.to_datetime(played["date"])

    print(
        f"# backtest_logloss.py — calibracion de la grilla P(h,a) por log-loss (Fase 3, #10)\n"
        f"# DIAGNOSTICO: el modelo NO se re-optimiza sobre log-loss (intencion EP-pure)\n"
        f"# CONVENCION: menor log-loss = mejor; d_ll = ll_full - ll_rho0 < 0  =>  full calibra MEJOR\n"
        f"# universo fit: {len(played)} partidos jugados\n"
        f"# copas held-out: {[str(c) for c in cups]}\n"
        f"# grid xi: {xi_grid}\n"
        f"# ventana: {window_years}a | bootstrap: {args.n_boot} iter | seed: {seed}"
    )

    header = (
        f"\n{'Copa':<6}  {'xi':>8}  {'LL_full':>8}  {'LL_rho0':>8}"
        f"  {'d_ll':>9}  {'SE_paired':>9}  {'z':>6}  {'n_common':>8}"
        f"  {'only_f/r0':>10}"
    )
    sep = "-" * len(header)

    for xi in xi_grid:
        print(f"\n{'='*70}")
        print(f"# xi = {xi:.4f}")
        print(header)
        print(sep)

        all_deltas = []
        all_lf = []
        all_lr = []

        for year in cups:
            cup_label = f"WC{year}"
            held = cup_held_out(played, year)

            # GUARDRAIL DURO — WC2022 VIRGEN
            assert_no_wc2022(held, cup_label)

            if len(held) == 0:
                print(f"  [WARN] {cup_label}: 0 partidos en held_out — verificar ingest.")
                continue

            pc = paired_logloss_comparison(
                played, held,
                xi=xi,
                window_years=window_years,
                n_boot=args.n_boot,
                seed=seed,
            )

            print(
                f"  {cup_label:<6}  {xi:>8.4f}  {_fmt(pc.mean_ll_full):>8}  {_fmt(pc.mean_ll_rho0):>8}"
                f"  {_fmt_signed(pc.d_ll):>9}  {_fmt(pc.se_paired):>9}  {_fmt(pc.z, '.2f'):>6}"
                f"  {pc.n_common:>8}  {pc.n_only_full:>5}/{pc.n_only_rho0:<5}"
            )

            # Acumular vectores para agregado pareado
            common_keys, lf_cup, lr_cup, _, _ = _align_records(
                pc.r_full.records, pc.r_rho0.records, value_key="ll"
            )
            all_deltas.append(pc.delta)
            all_lf.append(lf_cup)
            all_lr.append(lr_cup)

        # ---- Agregado pareado entre copas
        if len(all_deltas) > 1:
            delta_all = np.concatenate(all_deltas)
            lf_all = np.concatenate(all_lf)
            lr_all = np.concatenate(all_lr)
            n_total = len(delta_all)

            ll_full_agg = float(lf_all.mean()) if n_total else float("nan")
            ll_rho0_agg = float(lr_all.mean()) if n_total else float("nan")
            d_ll_agg = float(delta_all.mean()) if n_total else float("nan")
            se_agg = _paired_bootstrap_se(delta_all, n_boot=args.n_boot, seed=seed)
            z_agg = float(d_ll_agg / se_agg) if (se_agg and se_agg > 0) else float("nan")

            print(sep)
            print(
                f"  {'AGRE':<6}  {xi:>8.4f}  {_fmt(ll_full_agg):>8}  {_fmt(ll_rho0_agg):>8}"
                f"  {_fmt_signed(d_ll_agg):>9}  {_fmt(se_agg):>9}  {_fmt(z_agg, '.2f'):>6}"
                f"  {n_total:>8}  (3 copas agregadas)"
            )
            print(
                f"\n  => Δlog-loss_agregado = {_fmt_signed(d_ll_agg)} ± {_fmt(se_agg)} (SE_paired)"
                f"  z = {_fmt(z_agg, '.2f')}  N={n_total}"
                f"\n     (d_ll < 0 => full calibra mejor; d_ll > 0 => rho0 calibra mejor)"
            )

    print("\n# [la interpretacion (si ρ mejora la calibracion) la hace el orquestador, NO este script]")


if __name__ == "__main__":
    main()
