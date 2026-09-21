"""sanity_backtest_wc2018.py — O7 sanity backtest seed (REPORT-ONLY, spec §4 O7).

Held-out: los 64 partidos del WC2018 (WC2022 queda virgen para Fase 3, L2). Fit con
TODO lo jugado ANTES de 2018-06-14 (arranque del WC2018) -> sin leakage temporal.
Predecir los 64 partidos en modo full (DC completo) y rho0 (Poisson indep. ponderado),
puntuar la prediccion EV-optima contra el resultado real 90'/120' (match_points VERBATIM)
y reportar expected points (EP) realizados por partido de cada modo + la diferencia, con
SE bootstrap (resample de los 64 con reemplazo, 2000 iter).

NO DECIDE NADA: el trigger (si EP(full) < EP(rho0) - 1 SE -> shipear modo rho0 y poner DC
en cuarentena) lo evalua el ORQUESTADOR (spec §4 O7). Esto solo imprime las cifras.

Notas de modelado:
  - neutral: martj42 marca FALSE solo para Rusia (anfitrion). Se respeta la columna.
  - Penales: el optimizer de grupos (knockout=False) se usa para todos los partidos. El
    bonus +5 de penales requiere predecir empate Y que vaya a penales; al puntuar contra
    el resultado 90'/120' registrado (sin pen_pred/pen_actual), el bonus no aplica. Es la
    metrica de sanity pedida (EP realizados vs resultado 90'), no la prediccion de torneo
    completa con overlay de penales (eso es T4/Fase 3).
"""
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np

from wcprode import ingest
from wcprode.engine import DixonColesEngine
from wcprode.optimizer import optimize_match
from wcprode.scoring import match_points

WC2018_START = "2018-06-14"
WC2018_END = "2018-07-15"
N_BOOT = 2000
BOOT_SEED = 20260610


def _wc2018_matches(played):
    m = (
        (played["tournament"] == "FIFA World Cup")
        & (played["date"] >= WC2018_START)
        & (played["date"] <= WC2018_END)
    )
    return played[m].reset_index(drop=True)


def _realized_points(eng, matches):
    """Puntos realizados por partido: prediccion EV-optima vs resultado real 90'."""
    pts = []
    for _, row in matches.iterrows():
        grid = eng.predict(row["home_team"], row["away_team"],
                           neutral=bool(row["neutral"])).grid
        best = optimize_match(grid)["best"]
        actual = (int(row["home_score"]), int(row["away_score"]))
        pts.append(match_points(best, actual))
    return np.array(pts, dtype=float)


def _bootstrap_se(pts, n_boot=N_BOOT, seed=BOOT_SEED):
    rng = np.random.default_rng(seed)
    n = len(pts)
    means = np.array([pts[rng.integers(0, n, n)].mean() for _ in range(n_boot)])
    return means.std(ddof=1), means


def _bootstrap_diff_se(pts_a, pts_b, n_boot=N_BOOT, seed=BOOT_SEED):
    """SE de la diferencia pareada (mismo resample de partidos para ambos modos)."""
    rng = np.random.default_rng(seed)
    n = len(pts_a)
    diffs = []
    for _ in range(n_boot):
        idx = rng.integers(0, n, n)
        diffs.append(pts_a[idx].mean() - pts_b[idx].mean())
    diffs = np.array(diffs)
    return diffs.std(ddof=1), diffs


def main():
    df, _ = ingest.load_results()
    played = ingest.played_results(df)

    # fit set: TODO lo jugado antes del arranque del WC2018 (sin leakage)
    train = played[played["date"] < WC2018_START].reset_index(drop=True)
    matches = _wc2018_matches(played)

    print(f"# O7 sanity backtest WC2018 (report-only) — train={len(train)} partidos "
          f"(< {WC2018_START}) | held-out={len(matches)} partidos\n")

    eng_full = DixonColesEngine(xi=0.0018, fit_rho=True).fit(train, base_date=WC2018_START)
    eng_rho0 = DixonColesEngine(xi=0.0018, fit_rho=False).fit(train, base_date=WC2018_START)
    print(f"  full: rho={eng_full.rho_:.4f} gamma={eng_full.home_adv_:.4f}")
    print(f"  rho0: rho={eng_rho0.rho_:.4f} gamma={eng_rho0.home_adv_:.4f}\n")

    pts_full = _realized_points(eng_full, matches)
    pts_rho0 = _realized_points(eng_rho0, matches)

    ep_full = pts_full.mean()
    ep_rho0 = pts_rho0.mean()
    se_full, _ = _bootstrap_se(pts_full)
    se_rho0, _ = _bootstrap_se(pts_rho0)
    diff = ep_full - ep_rho0
    se_diff, _ = _bootstrap_diff_se(pts_full, pts_rho0)

    print(f"EP medio por partido (sobre {len(matches)} partidos, {N_BOOT} iter bootstrap):")
    print(f"  modo full (DC completo) : {ep_full:.4f}  +/- {se_full:.4f} SE  "
          f"(total {pts_full.sum():.0f} pts)")
    print(f"  modo rho0 (Poisson pond): {ep_rho0:.4f}  +/- {se_rho0:.4f} SE  "
          f"(total {pts_rho0.sum():.0f} pts)")
    print(f"  diferencia full - rho0  : {diff:+.4f}  +/- {se_diff:.4f} SE (pareado)")
    print()
    print(f"  [trigger spec §4 O7, lo evalua el orquestador, NO este script]:")
    print(f"   EP(full) < EP(rho0) - 1*SE_bootstrap ?  "
          f"{ep_full:.4f} < {ep_rho0 - se_rho0:.4f} ?  -> {ep_full < ep_rho0 - se_rho0}")


if __name__ == "__main__":
    main()
