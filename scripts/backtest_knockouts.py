"""backtest_knockouts.py - backtest KO held-out: modelo a 120' (c=1/3) vs sin alargue (c=0).

CONFIRMATORIO (N chico: 48 KO en WC2018/14/10, ~10 a penales). El gate del modelo de penales/ET
es correccion teorica + oraculo (D14), NO este backtest (poca potencia). WC2022 RESERVADA VIRGEN.

KO = ultimos 16 por fecha de cada WC (64 = 48 grupos + 16 KO; verificado: empate-120' == a-penales).
Scoring KO COMPLETO: marcador a 120' (results) + penales (shootouts): si el pick es empate y el
partido fue a penales, +5 si pen_pred (favorito del modelo) == pen_actual (ganador real de la tanda).
Pareado por partido (mismo grid, distinto c). Uso:
  .venv/Scripts/python.exe scripts/backtest_knockouts.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wcprode import ingest  # noqa: E402
from wcprode.backtest import _paired_bootstrap_se, assert_no_wc2022, build_train, cup_held_out  # noqa: E402
from wcprode.engine import DixonColesEngine  # noqa: E402
from wcprode.optimizer import optimize_match  # noqa: E402
from wcprode.penalty import ET_TIME_SCALE  # noqa: E402
from wcprode.scoring import match_points  # noqa: E402

XI = 0.0018
YEARS = [2018, 2014, 2010]
REPO = Path(__file__).resolve().parent.parent


def pen_actual_for(sh, date, home, away):
    m = sh[(sh["date"] == date) & (sh["home_team"] == home) & (sh["away_team"] == away)]
    if not len(m):
        return None
    w = m.iloc[0]["winner"]
    return "H" if w == home else ("A" if w == away else None)


def main():
    df, _ = ingest.load_results()
    played = ingest.played_results(df).copy()
    played["date"] = pd.to_datetime(played["date"])      # build_train compara con Timestamp (patron rolling_origin)
    sh = pd.read_csv(REPO / "data" / "raw" / "shootouts.csv", dtype=str,
                     keep_default_na=False, na_filter=False)

    rows = []
    for year in YEARS:
        cup = cup_held_out(played, year).sort_values("date").reset_index(drop=True)
        assert_no_wc2022(cup, f"WC{year}")
        ko = cup.tail(16)
        for _, r in ko.iterrows():
            train = build_train(played, r["date"])
            if len(train) == 0:
                continue
            try:
                eng = DixonColesEngine(xi=XI, fit_rho=True).fit(train, base_date=r["date"])
                grid = eng.predict(r["home_team"], r["away_team"], neutral=bool(r["neutral"])).grid
            except Exception:
                continue
            actual = (int(r["home_score"]), int(r["away_score"]))
            date_s = pd.Timestamp(r["date"]).strftime("%Y-%m-%d")
            pa = pen_actual_for(sh, date_s, r["home_team"], r["away_team"])
            rec = {"year": year, "match": f"{r['home_team']}-{r['away_team']}",
                   "actual": f"{actual[0]}-{actual[1]}", "pen": pa or "-"}
            for tag, c in (("c0", 0.0), ("cET", ET_TIME_SCALE)):
                res = optimize_match(grid, knockout=True, pen_win_prob=0.55, c=c)
                pick = res["best"]
                pen_pred = ("H" if res["p_home"] >= res["p_away"] else "A") if pick[0] == pick[1] else None
                pts = match_points(pick, actual, pen_pred=pen_pred, pen_actual=pa)
                rec[f"{tag}_pick"] = f"{pick[0]}-{pick[1]}"
                rec[f"{tag}_pts"] = pts
            rows.append(rec)

    res = pd.DataFrame(rows)
    p0, pET = res["c0_pts"].to_numpy(), res["cET_pts"].to_numpy()
    delta = pET - p0
    se = _paired_bootstrap_se(delta.astype(float))
    z = float(delta.mean() / se) if se > 0 else 0.0

    print(f"# Backtest KO held-out (WC2018/14/10) | N={len(res)} KO | a-penales={ (res['pen']!='-').sum() }")
    print(f"# c=0 (sin alargue, draw-option sobre 90') vs c={ET_TIME_SCALE:.3f} (grid a 120')\n")
    hdr = f"{'year':>4} {'match':<34} {'real':>5} {'pen':>3} {'c0':>5} {'pts':>3} {'cET':>5} {'pts':>3} {'d':>3}"
    print(hdr); print("-" * len(hdr))
    for _, r in res.iterrows():
        d = r["cET_pts"] - r["c0_pts"]
        flag = "  <-" if r["c0_pick"] != r["cET_pick"] else ""
        print(f"{r['year']:>4} {r['match'][:34]:<34} {r['actual']:>5} {r['pen']:>3} "
              f"{r['c0_pick']:>5} {r['c0_pts']:>3} {r['cET_pick']:>5} {r['cET_pts']:>3} {d:>+3}{flag}")
    print("-" * len(hdr))
    nflip = int((res["c0_pick"] != res["cET_pick"]).sum())
    print(f"\nEP c=0    : {p0.mean():.3f}  (total {int(p0.sum())})")
    print(f"EP c=1/3  : {pET.mean():.3f}  (total {int(pET.sum())})")
    print(f"Delta EP  : {delta.mean():+.3f}  SE(pareado) {se:.3f}  z={z:+.2f}   (picks distintos: {nflip}/{len(res)})")
    print(f"\nN={len(res)} -> CONFIRMATORIO, no concluyente. El gate del modelo es correccion + oraculo (D14).")


if __name__ == "__main__":
    main()
