"""backtest_bivariado.py — bivariado (Karlis-Ntzoufras) vs DC-full vs ρ0 (Fase 3, "otra mitad de #8").

Mide si una dependencia EXPLÍCITA (Poisson bivariado, λ3≥0) se gana su lugar en EP held-out
y log-loss. Rolling-origin held-out sobre WC2018/14/10 (WC2022 RESERVADA virgen). SE PAREADO.
Un solo fit por fecha (combinado EP+log-loss). El engine usa GRADIENTE ANALÍTICO (el numérico
no converge con cientos de equipos — DECISIONS D10).

Cuatro modelos, mismo ξ/ventana/decay:
  bivF = bivariado λ3 libre | bivI = bivariado λ3=0 (MISMO optimizador) | full = DC-full | rho0 = DC ρ0
Comparaciones (SE pareado):
  PRIMARIA   bivF vs bivI : efecto NETO de λ3 (intra-engine, sin confound de optimizador).
  contexto   bivF vs full / bivF vs rho0 : vs modelo de producción / Poisson independiente.
  diagnóstico bivI vs rho0 : convergencia equivalente (debe ≈0).

CHECKPOINT por copa (_biv_ckpt_<year>.npz): si un run muere a mitad, re-lanzarlo reanuda
desde las copas ya completas (la muerte del run anterior fue externa, no de cómputo).

Alcance (D2/JP): KN solo captura correlación positiva. Interpretación = orquestador, NO el script (D9).
Uso: .venv/Scripts/python.exe scripts/backtest_bivariado.py
"""
import argparse
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

import numpy as np
import pandas as pd

from wcprode import ingest
from wcprode.bivariate import BivariatePoissonEngine
from wcprode.backtest import (
    rolling_origin_combined,
    build_train,
    cup_held_out,
    assert_no_wc2022,
    _align_records,
    _paired_bootstrap_se,
)

SEED = 20260615
KEYS = ("ep_lam3", "ll_lam3", "ep_full", "ll_full", "ep_rho0", "ll_rho0")


def _fmt(v, f=".4f"):
    return "nan" if (isinstance(v, float) and v != v) else format(v, f)


def _paired(records_a, records_b, value_key, *, n_boot, seed):
    keys, va, vb, _, _ = _align_records(records_a, records_b, value_key=value_key)
    delta = va - vb
    n = len(keys)
    dep = float(delta.mean()) if n else float("nan")
    se = _paired_bootstrap_se(delta, n_boot=n_boot, seed=seed)
    z = float(dep / se) if (se and se > 0) else float("nan")
    return {"mean_a": float(va.mean()) if n else float("nan"),
            "mean_b": float(vb.mean()) if n else float("nan"),
            "dep": dep, "se": se, "z": z, "n": n, "delta": delta}


def _print_pair(label, p):
    print(f"    {label:<16}  A={_fmt(p['mean_a']):>8}  B={_fmt(p['mean_b']):>8}"
          f"  Δ(A-B)={_fmt(p['dep'], '+.4f'):>9}  SE={_fmt(p['se']):>7}  z={_fmt(p['z'], '.2f'):>6}  n={p['n']}",
          flush=True)


def _compute_cup(played, held, *, xi, window_years, n_boot):
    """Corre los 4 modelos + 6 comparaciones de una copa. Devuelve dict de deltas + λ3 + medias."""
    bivF_ep, bivF_ll = rolling_origin_combined(played, held, xi=xi, window_years=window_years,
        n_boot=n_boot, seed=SEED, engine_factory=lambda x_: BivariatePoissonEngine(xi=x_, fit_lambda3=True))
    bivI_ep, bivI_ll = rolling_origin_combined(played, held, xi=xi, window_years=window_years,
        n_boot=n_boot, seed=SEED, engine_factory=lambda x_: BivariatePoissonEngine(xi=x_, fit_lambda3=False))
    full_ep, full_ll = rolling_origin_combined(played, held, xi=xi, fit_rho=True,
        window_years=window_years, n_boot=n_boot, seed=SEED)
    rho0_ep, rho0_ll = rolling_origin_combined(played, held, xi=xi, fit_rho=False,
        window_years=window_years, n_boot=n_boot, seed=SEED)
    last_D = pd.Timestamp(sorted(held["date"].unique())[-1])
    eng_last = BivariatePoissonEngine(xi=xi, fit_lambda3=True).fit(
        build_train(played, last_D, window_years=window_years), base_date=last_D)
    pairs = {
        "ep_lam3": _paired(bivF_ep.records, bivI_ep.records, "pts", n_boot=n_boot, seed=SEED),
        "ep_full": _paired(bivF_ep.records, full_ep.records, "pts", n_boot=n_boot, seed=SEED),
        "ep_rho0": _paired(bivF_ep.records, rho0_ep.records, "pts", n_boot=n_boot, seed=SEED),
        "ll_lam3": _paired(bivF_ll.records, bivI_ll.records, "ll", n_boot=n_boot, seed=SEED),
        "ll_full": _paired(bivF_ll.records, full_ll.records, "ll", n_boot=n_boot, seed=SEED),
        "ll_rho0": _paired(bivF_ll.records, rho0_ll.records, "ll", n_boot=n_boot, seed=SEED),
    }
    diag = _paired(bivI_ep.records, rho0_ep.records, "pts", n_boot=n_boot, seed=SEED)
    means = {"ep": (bivF_ep.ep, bivI_ep.ep, full_ep.ep, rho0_ep.ep),
             "ll": (bivF_ll.mean_ll, bivI_ll.mean_ll, full_ll.mean_ll, rho0_ll.mean_ll),
             "n": bivF_ep.n_predicted, "skip": bivF_ep.n_skipped}
    return pairs, diag, means, eng_last.lambda3_


def main():
    ap = argparse.ArgumentParser(description="Bivariado vs DC-full vs ρ0 (Fase 3)")
    ap.add_argument("--cups", nargs="+", type=int, choices=[2018, 2014, 2010],
                    default=[2018, 2014, 2010], metavar="YEAR")
    ap.add_argument("--xi", type=float, default=0.0018)
    ap.add_argument("--window-years", type=float, default=8.0)
    ap.add_argument("--n-boot", type=int, default=2000)
    args = ap.parse_args()

    xi = args.xi
    window_years = args.window_years if args.window_years > 0 else None
    cups = sorted(args.cups, reverse=True)
    n_boot = args.n_boot

    df, _ = ingest.load_results()
    played = ingest.played_results(df).copy()
    played["date"] = pd.to_datetime(played["date"])

    print(f"# backtest_bivariado.py — bivariado vs DC (Fase 3, gradiente analítico)")
    print(f"# universo: {len(played)} jugados | copas: {cups} | xi={xi} | ventana={window_years}a"
          f" | bootstrap={n_boot} | seed={SEED}", flush=True)

    agg = {k: [] for k in KEYS}
    lam3_samples = []

    for year in cups:
        cup = f"WC{year}"
        ckpt = f"_biv_ckpt_{year}.npz"
        held = cup_held_out(played, year)
        assert_no_wc2022(held, cup)
        if len(held) == 0:
            print(f"  [WARN] {cup}: 0 partidos held-out", flush=True)
            continue

        if os.path.exists(ckpt):
            d = np.load(ckpt)
            for k in KEYS:
                agg[k].append(d[k])
            lam3_samples.append(float(d["lam3"]))
            print(f"\n# {cup}: CARGADO de checkpoint ({ckpt})", flush=True)
            continue

        print(f"\n{'='*74}\n# {cup}: {len(held)} partidos held-out, {held['date'].nunique()} fechas", flush=True)
        t0 = time.perf_counter()
        pairs, diag, means, lam3 = _compute_cup(played, held, xi=xi, window_years=window_years, n_boot=n_boot)
        np.savez(ckpt, lam3=lam3, **{k: pairs[k]["delta"] for k in KEYS})
        for k in KEYS:
            agg[k].append(pairs[k]["delta"])
        lam3_samples.append(lam3)

        eF, eI, eFu, eR = means["ep"]; lF, lI, lFu, lR = means["ll"]
        print(f"  EP: bivF={_fmt(eF)} bivI={_fmt(eI)} full={_fmt(eFu)} rho0={_fmt(eR)}"
              f"  | ll: bivF={_fmt(lF)} bivI={_fmt(lI)} full={_fmt(lFu)} rho0={_fmt(lR)}", flush=True)
        print(f"  λ3(última fecha)={lam3:.5f}  n={means['n']} skip={means['skip']}  ({time.perf_counter()-t0:.0f}s)", flush=True)
        print(f"  EP held-out (Δ>0 ⇒ A mejor):", flush=True)
        for lab, key in [("bivF vs bivI", "ep_lam3"), ("bivF vs full", "ep_full"), ("bivF vs rho0", "ep_rho0")]:
            _print_pair(lab, pairs[key])
        print(f"    [diag bivI vs rho0 (debe ≈0): Δ={_fmt(diag['dep'], '+.4f')} z={_fmt(diag['z'], '.2f')}]", flush=True)
        print(f"  log-loss (Δ<0 ⇒ A mejor):", flush=True)
        for lab, key in [("bivF vs bivI", "ll_lam3"), ("bivF vs full", "ll_full"), ("bivF vs rho0", "ll_rho0")]:
            _print_pair(lab, pairs[key])

    print(f"\n{'='*74}\n# AGREGADO (3 copas) — SE pareado bootstrap", flush=True)
    labels = {"ep_lam3": "EP  bivF vs bivI (λ3 neto)", "ep_full": "EP  bivF vs DC-full",
              "ep_rho0": "EP  bivF vs DC-rho0", "ll_lam3": "ll  bivF vs bivI (λ3 neto)",
              "ll_full": "ll  bivF vs DC-full", "ll_rho0": "ll  bivF vs DC-rho0"}
    for key, lab in labels.items():
        if not agg[key]:
            continue
        delta = np.concatenate(agg[key])
        dep = float(delta.mean()); se = _paired_bootstrap_se(delta, n_boot=n_boot, seed=SEED)
        z = float(dep / se) if se > 0 else float("nan")
        sign = "Δ>0⇒bivF mejor" if key.startswith("ep") else "Δ<0⇒bivF mejor"
        print(f"  {lab:<28}  Δ={_fmt(dep, '+.4f'):>9}  SE={_fmt(se):>7}  z={_fmt(z,'.2f'):>6}  N={len(delta)}   [{sign}]",
              flush=True)
    print(f"\n  λ3 muestreado (1 por copa): {[round(x,4) for x in lam3_samples]}", flush=True)
    print("\n# [interpretación = orquestador. EP = métrica de decisión; log-loss = diagnóstico (D9).]", flush=True)


if __name__ == "__main__":
    main()
