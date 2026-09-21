"""backtest.py — harness de backtest rolling-origin multi-copa (Fase 3).

Contrato de API (docs/backtest_design.md §Contrato): build_train, score_prediction,
BacktestResult (dataclass), rolling_origin_points, xi_grid_search.

Diseño:
  - No-leakage: build_train filtra date < target_date (frontera ESTRICTA). El loop
    de rolling_origin_points reconstruye el train desde played (universo completo)
    usando la misma frontera, garantizando que el marcador del target no entra en
    su propio fit (review A6).
  - Skip: on_predict_error='skip' captura ValueError (equipo no visto) Y
    AssertionError (grilla degenerada: masa < 0.999 con xi alto sobre data rala).
  - EP: media sobre n_predicted (skips EXCLUIDOS). Denominador = n_predicted.
  - Bootstrap SE: np.random.default_rng(seed) LOCAL (reproducible entre procesos).
  - base_date=D: OBLIGATORIO en el fit (ancla del decay en el día de predicción).
  - records: en orden temporal ascendente, alineados con points.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .engine import DixonColesEngine
from .optimizer import optimize_match
from .scoring import match_points

logger = logging.getLogger(__name__)


def _build_engine(xi, fit_rho, engine_factory):
    """Engine SIN fittear. Default = DixonColesEngine (backward-compat: el oráculo D6
    `test_backtest_oracle` no pasa engine_factory -> comportamiento idéntico, queda verde).
    engine_factory(xi) permite enchufar otro modelo con la misma API (Fase 3: bivariado)."""
    if engine_factory is None:
        return DixonColesEngine(xi=xi, fit_rho=fit_rho)
    return engine_factory(xi)


# --------------------------------------------------------------------------- #
# build_train                                                                  #
# --------------------------------------------------------------------------- #
def build_train(played: pd.DataFrame, target_date, *, window_years: float | None = 8) -> pd.DataFrame:
    """Partidos utilizables para predecir un partido en target_date.

    Frontera superior ESTRICTA: date < target_date (sin leakage).
    Borde inferior INCLUSIVO: date >= target_date - window_years*365.25 d
    (None = todo el historial).
    Subset, no muta.
    """
    d = pd.Timestamp(target_date)
    mask = played["date"] < d
    if window_years is not None:
        cutoff = d - pd.Timedelta(days=window_years * 365.25)
        mask = mask & (played["date"] >= cutoff)
    return played.loc[mask].reset_index(drop=True)


# --------------------------------------------------------------------------- #
# score_prediction                                                             #
# --------------------------------------------------------------------------- #
def score_prediction(grid: np.ndarray, actual: tuple[int, int], *,
                     knockout: bool = False, pen_win_prob: float = 0.55) -> int:
    """Puntos del prode = match_points(optimize_match(grid,...)['best'], actual).

    Usa la cadena YA oraculizada (optimizer + scoring); NO re-implementa el puntaje.
    """
    best = optimize_match(grid, knockout=knockout, pen_win_prob=pen_win_prob)["best"]
    return match_points(best, actual)


# --------------------------------------------------------------------------- #
# BacktestResult                                                               #
# --------------------------------------------------------------------------- #
@dataclass
class BacktestResult:
    points: np.ndarray   # pts por partido predicho; points[i] ALINEA con records[i]
    records: list        # por partido, EN ORDEN TEMPORAL ascendente:
                         # date (ISO str/Timestamp), home, away, neutral,
                         # pred (ph,pa), actual (ah,aa), pts
    n_predicted: int     # == len(points) == len(records)
    n_skipped: int       # saltados por fallo de predict (unseen + masa)
    ep: float            # media sobre n_predicted (skips EXCLUIDOS): points.sum()/n_predicted
    se: float            # SE bootstrap, np.random.default_rng(seed) LOCAL
    xi: float
    fit_rho: bool


# --------------------------------------------------------------------------- #
# rolling_origin_points                                                        #
# --------------------------------------------------------------------------- #
def rolling_origin_points(
    played: pd.DataFrame,
    held_out: pd.DataFrame,
    *,
    xi: float,
    fit_rho: bool = True,
    window_years: float | None = 8,
    knockout: bool = False,
    on_predict_error: str = "skip",
    n_boot: int = 2000,
    seed: int = 20260615,
    engine_factory=None,
) -> BacktestResult:
    """Backtest rolling-origin held-out por expected points.

    Precondición: held_out ⊆ played (los held-out alimentan los trains de fechas
    posteriores -> rolling REAL). Por cada fecha D distinta en held_out (asc):
      eng = DixonColesEngine(xi, fit_rho).fit(build_train(played, D, window_years), base_date=D)
      por cada partido de held_out en D: score_prediction(eng.predict(...).grid, actual).

    on_predict_error: 'skip' (default, cuenta en n_skipped) | 'raise'.
    predict puede fallar con ValueError (equipo no visto) O AssertionError (grilla
    degenerada: lam/mu explotan con xi alto sobre data rala -> engine.py:346).
    El skip cubre AMBAS.
    """
    if on_predict_error not in ("skip", "raise"):
        raise ValueError(f"on_predict_error debe ser 'skip' o 'raise', recibí: {on_predict_error!r}")

    # Normalizar columna date
    played = played.copy()
    played["date"] = pd.to_datetime(played["date"])
    held_out = held_out.copy()
    held_out["date"] = pd.to_datetime(held_out["date"])

    # Ordenar held_out por fecha ascendente para que records queden ordenados
    held_out = held_out.sort_values("date").reset_index(drop=True)

    # Fechas únicas del held_out, en orden ascendente
    unique_dates = sorted(held_out["date"].unique())

    all_points: list[int] = []
    all_records: list[dict] = []
    n_skipped = 0

    for D in unique_dates:
        train = build_train(played, D, window_years=window_years)

        if len(train) == 0:
            # Sin datos de entrenamiento: saltar todos los partidos de esta fecha
            day_matches = held_out[held_out["date"] == D]
            n_skipped += len(day_matches)
            logger.warning("Sin datos de entrenamiento para %s; saltando %d partidos",
                           D, len(day_matches))
            continue

        try:
            eng = _build_engine(xi, fit_rho, engine_factory).fit(train, base_date=D)
        except Exception as exc:
            day_matches = held_out[held_out["date"] == D]
            if on_predict_error == "raise":
                raise
            n_skipped += len(day_matches)
            logger.warning("Fallo el fit para fecha %s (%s: %s); saltando %d partidos",
                           D, type(exc).__name__, exc, len(day_matches))
            continue

        day_matches = held_out[held_out["date"] == D]
        for _, row in day_matches.iterrows():
            home = row["home_team"]
            away = row["away_team"]
            neutral = bool(row["neutral"])
            actual = (int(row["home_score"]), int(row["away_score"]))

            try:
                sg = eng.predict(home, away, neutral=neutral)
                pts = score_prediction(sg.grid, actual, knockout=knockout)
            except (ValueError, AssertionError) as exc:
                if on_predict_error == "raise":
                    raise
                n_skipped += 1
                logger.warning("Saltando %s vs %s en %s (%s: %s)",
                               home, away, D, type(exc).__name__, exc)
                continue

            pred = optimize_match(sg.grid, knockout=knockout)["best"]
            all_points.append(pts)
            all_records.append({
                "date": D,
                "home": home,
                "away": away,
                "neutral": neutral,
                "pred": pred,
                "actual": actual,
                "pts": pts,
            })

    points_arr = np.array(all_points, dtype=float)
    n_predicted = len(points_arr)

    if n_predicted == 0:
        ep = float("nan")
        se = float("nan")
    else:
        ep = float(points_arr.sum() / n_predicted)
        # Bootstrap SE — rng LOCAL con seed del contrato (reproducible entre procesos)
        rng = np.random.default_rng(seed)
        boot_means = np.array([
            points_arr[rng.integers(0, n_predicted, n_predicted)].mean()
            for _ in range(n_boot)
        ])
        se = float(boot_means.std(ddof=1))

    return BacktestResult(
        points=points_arr,
        records=all_records,
        n_predicted=n_predicted,
        n_skipped=n_skipped,
        ep=ep,
        se=se,
        xi=xi,
        fit_rho=fit_rho,
    )


# --------------------------------------------------------------------------- #
# xi_grid_search                                                               #
# --------------------------------------------------------------------------- #
def xi_grid_search(
    played: pd.DataFrame,
    held_out: pd.DataFrame,
    xi_grid: list[float],
    *,
    fit_rho: bool = True,
    **kw,
) -> dict:
    """rolling_origin_points por cada xi del grid.

    Devuelve:
      {
        'table': [(xi, ep, se, n_pred), ...],   # una entrada por xi, en orden del grid
        'argmax_xi': xi*,                        # xi con mayor EP
        'results': {xi: BacktestResult},         # acceso completo
      }
    """
    results: dict[float, BacktestResult] = {}
    table: list[tuple[float, float, float, int]] = []

    for xi in xi_grid:
        r = rolling_origin_points(played, held_out, xi=xi, fit_rho=fit_rho, **kw)
        results[xi] = r
        table.append((xi, r.ep, r.se, r.n_predicted))

    argmax_xi = max(table, key=lambda row: row[1])[0]

    return {
        "table": table,
        "argmax_xi": argmax_xi,
        "results": results,
    }


# --------------------------------------------------------------------------- #
# Guardrails de copas como API pública (movidos desde backtest_multicup.py)   #
# --------------------------------------------------------------------------- #
CUP_RANGES = {
    2018: ("2018-06-14", "2018-07-15"),
    2014: ("2014-06-12", "2014-07-13"),
    2010: ("2010-06-11", "2010-07-11"),
}

WC2022_START = "2022-11-20"
WC2022_END = "2022-12-18"


def cup_held_out(played: pd.DataFrame, year: int) -> pd.DataFrame:
    """FIFA World Cup matches del año dado (rango verificado en CUP_RANGES)."""
    ini, fin = CUP_RANGES[year]
    mask = (
        (played["tournament"] == "FIFA World Cup")
        & (played["date"] >= ini)
        & (played["date"] <= fin)
    )
    return played[mask].reset_index(drop=True)


def assert_no_wc2022(held_out: pd.DataFrame, cup_label: str) -> None:
    """GUARDRAIL DURO: WC2022 (2022-11-20..2022-12-18) es RESERVADA VIRGEN; no debe aparecer en held_out."""
    contaminated = held_out[
        (held_out["date"] >= WC2022_START) & (held_out["date"] <= WC2022_END)
    ]
    assert len(contaminated) == 0, (
        f"GUARDRAIL VIOLADO: {len(contaminated)} partidos de WC2022 ({WC2022_START}..{WC2022_END}) "
        f"en held_out de {cup_label}. WC2022 es RESERVADA VIRGEN (DECISIONS.md D2). "
        f"Primeros: {contaminated[['date','home_team','away_team']].head().to_dict('records')}"
    )


# --------------------------------------------------------------------------- #
# Helper de pareo por identidad                                                #
# --------------------------------------------------------------------------- #
def _align_records(records_a: list, records_b: list, value_key: str = "pts"):
    """Parea dos listas de records (de BacktestResult/LogLossResult) por identidad de partido.

    key = (isoformat(date), home, away). Preserva el orden de records_a.
    value_key: campo numérico a extraer ('pts' para EP, 'll' para log-loss).
    Devuelve: (common_keys, val_a, val_b, n_only_a, n_only_b)
      val_a, val_b: np.ndarray float alineadas a common_keys.
    """
    def key(rec):
        return (pd.Timestamp(rec["date"]).isoformat(), rec["home"], rec["away"])

    map_a = {key(r): r[value_key] for r in records_a}
    map_b = {key(r): r[value_key] for r in records_b}
    common_keys = [k for k in map_a if k in map_b]  # orden de records_a (temporal asc)
    val_a = np.array([map_a[k] for k in common_keys], dtype=float)
    val_b = np.array([map_b[k] for k in common_keys], dtype=float)
    n_only_a = len(map_a) - len(common_keys)
    n_only_b = len(map_b) - len(common_keys)
    return common_keys, val_a, val_b, n_only_a, n_only_b


# --------------------------------------------------------------------------- #
# Bootstrap pareado                                                            #
# --------------------------------------------------------------------------- #
def _paired_bootstrap_se(delta: np.ndarray, n_boot: int = 2000, seed: int = 20260615) -> float:
    """SE bootstrap de la media de delta. Mismo patrón que rolling_origin_points: default_rng(seed), ddof=1."""
    n = len(delta)
    if n == 0:
        return float("nan")
    rng = np.random.default_rng(seed)
    boot = np.array([delta[rng.integers(0, n, n)].mean() for _ in range(n_boot)])
    return float(boot.std(ddof=1))


# --------------------------------------------------------------------------- #
# PairedComparison + paired_model_comparison                                  #
# --------------------------------------------------------------------------- #
@dataclass
class PairedComparison:
    xi: float
    ep_full: float       # EP modo fit_rho=True sobre partidos comunes
    ep_rho0: float       # EP modo fit_rho=False sobre partidos comunes
    dep: float           # ep_full - ep_rho0 (media de delta)
    se_paired: float     # SE bootstrap PAREADO de dep
    se_full: float       # SE marginal del modo full (r_full.se)
    se_rho0: float       # SE marginal del modo rho0 (r_rho0.se)
    z: float             # dep / se_paired (nan si se_paired==0)
    n_common: int
    n_only_full: int
    n_only_rho0: int
    delta: np.ndarray
    r_full: "BacktestResult"
    r_rho0: "BacktestResult"


def paired_model_comparison(
    played: pd.DataFrame,
    held_out: pd.DataFrame,
    *,
    xi: float,
    window_years: float | None = 8,
    n_boot: int = 2000,
    seed: int = 20260615,
) -> PairedComparison:
    """Compara DC-full (fit_rho=True) vs ρ0 (fit_rho=False) sobre el MISMO held_out, EP held-out, SE PAREADO."""
    r_full = rolling_origin_points(
        played, held_out, xi=xi, fit_rho=True,
        window_years=window_years, n_boot=n_boot, seed=seed,
    )
    r_rho0 = rolling_origin_points(
        played, held_out, xi=xi, fit_rho=False,
        window_years=window_years, n_boot=n_boot, seed=seed,
    )
    common_keys, pf, pr, n_only_full, n_only_rho0 = _align_records(r_full.records, r_rho0.records)
    delta = pf - pr
    n_common = len(common_keys)
    ep_full = float(pf.mean()) if n_common else float("nan")
    ep_rho0 = float(pr.mean()) if n_common else float("nan")
    dep = float(delta.mean()) if n_common else float("nan")
    se_paired = _paired_bootstrap_se(delta, n_boot=n_boot, seed=seed)
    z = float(dep / se_paired) if (se_paired and se_paired > 0) else float("nan")
    return PairedComparison(
        xi=xi,
        ep_full=ep_full,
        ep_rho0=ep_rho0,
        dep=dep,
        se_paired=se_paired,
        se_full=r_full.se,
        se_rho0=r_rho0.se,
        z=z,
        n_common=n_common,
        n_only_full=n_only_full,
        n_only_rho0=n_only_rho0,
        delta=delta,
        r_full=r_full,
        r_rho0=r_rho0,
    )


# =========================================================================== #
# Log-loss sobre la grilla P(h,a) — DIAGNÓSTICO de calibración (Fase 3, #10)  #
# El modelo NO se re-optimiza sobre log-loss; el proyecto es EP-pure.         #
# =========================================================================== #
def log_loss_grid(grid: np.ndarray, actual: tuple[int, int]) -> float:
    """-log P[marcador real]. Clip a bordes del grid (marcadores > max_goals, imposibles en fútbol, no crashean)."""
    mg = grid.shape[0] - 1
    ah = min(max(int(actual[0]), 0), mg)
    aa = min(max(int(actual[1]), 0), mg)
    p = grid[ah, aa]
    return float(-np.log(p)) if p > 0 else float("inf")


def _bootstrap_se(values: np.ndarray, n_boot: int = 2000, seed: int = 20260615) -> float:
    """SE bootstrap de la media de `values`. Mismo patrón que el bootstrap inline de
    rolling_origin_points: np.random.default_rng(seed), resample n índices, std(ddof=1).
    """
    n = len(values)
    if n == 0:
        return float("nan")
    rng = np.random.default_rng(seed)
    boot = np.array([values[rng.integers(0, n, n)].mean() for _ in range(n_boot)])
    return float(boot.std(ddof=1))


@dataclass
class LogLossResult:
    log_losses: np.ndarray   # ll por partido predicho; log_losses[i] ALINEA con records[i]
    records: list            # por partido, EN ORDEN TEMPORAL ascendente:
                             # date, home, away, neutral, pred (ph,pa), actual (ah,aa), ll
    n_predicted: int         # == len(log_losses) == len(records)
    n_skipped: int           # saltados por fallo de predict (unseen + masa)
    mean_ll: float           # media sobre n_predicted (skips EXCLUIDOS)
    se: float                # SE bootstrap, np.random.default_rng(seed) LOCAL
    xi: float
    fit_rho: bool


def rolling_origin_logloss(
    played: pd.DataFrame,
    held_out: pd.DataFrame,
    *,
    xi: float,
    fit_rho: bool = True,
    window_years: float | None = 8,
    on_predict_error: str = "skip",
    n_boot: int = 2000,
    seed: int = 20260615,
    engine_factory=None,
) -> LogLossResult:
    """Backtest rolling-origin held-out por LOG-LOSS de la grilla P(h,a).

    DIAGNÓSTICO de calibración: -log P[marcador real] por partido. El modelo NO se
    re-optimiza sobre esta métrica (intención EP-pure del proyecto).

    MISMA estructura de loop que rolling_origin_points (mismo build_train, mismo fit,
    mismo manejo de skips ValueError/AssertionError, mismo orden temporal): predice/salta
    EXACTAMENTE el mismo conjunto de partidos. En vez de score_prediction acumula
    log_loss_grid(grid, actual). records con 'll'; pred incluido para trazabilidad.
    """
    if on_predict_error not in ("skip", "raise"):
        raise ValueError(f"on_predict_error debe ser 'skip' o 'raise', recibí: {on_predict_error!r}")

    # Normalizar columna date
    played = played.copy()
    played["date"] = pd.to_datetime(played["date"])
    held_out = held_out.copy()
    held_out["date"] = pd.to_datetime(held_out["date"])

    # Ordenar held_out por fecha ascendente para que records queden ordenados
    held_out = held_out.sort_values("date").reset_index(drop=True)

    # Fechas únicas del held_out, en orden ascendente
    unique_dates = sorted(held_out["date"].unique())

    all_ll: list[float] = []
    all_records: list[dict] = []
    n_skipped = 0

    for D in unique_dates:
        train = build_train(played, D, window_years=window_years)

        if len(train) == 0:
            day_matches = held_out[held_out["date"] == D]
            n_skipped += len(day_matches)
            logger.warning("Sin datos de entrenamiento para %s; saltando %d partidos",
                           D, len(day_matches))
            continue

        try:
            eng = _build_engine(xi, fit_rho, engine_factory).fit(train, base_date=D)
        except Exception as exc:
            day_matches = held_out[held_out["date"] == D]
            if on_predict_error == "raise":
                raise
            n_skipped += len(day_matches)
            logger.warning("Falló el fit para fecha %s (%s: %s); saltando %d partidos",
                           D, type(exc).__name__, exc, len(day_matches))
            continue

        day_matches = held_out[held_out["date"] == D]
        for _, row in day_matches.iterrows():
            home = row["home_team"]
            away = row["away_team"]
            neutral = bool(row["neutral"])
            actual = (int(row["home_score"]), int(row["away_score"]))

            try:
                sg = eng.predict(home, away, neutral=neutral)
                ll = log_loss_grid(sg.grid, actual)
            except (ValueError, AssertionError) as exc:
                if on_predict_error == "raise":
                    raise
                n_skipped += 1
                logger.warning("Saltando %s vs %s en %s (%s: %s)",
                               home, away, D, type(exc).__name__, exc)
                continue

            pred = optimize_match(sg.grid)["best"]
            all_ll.append(ll)
            all_records.append({
                "date": D,
                "home": home,
                "away": away,
                "neutral": neutral,
                "pred": pred,
                "actual": actual,
                "ll": ll,
            })

    ll_arr = np.array(all_ll, dtype=float)
    n_predicted = len(ll_arr)

    if n_predicted == 0:
        mean_ll = float("nan")
        se = float("nan")
    else:
        mean_ll = float(ll_arr.mean())
        se = _bootstrap_se(ll_arr, n_boot=n_boot, seed=seed)

    return LogLossResult(
        log_losses=ll_arr,
        records=all_records,
        n_predicted=n_predicted,
        n_skipped=n_skipped,
        mean_ll=mean_ll,
        se=se,
        xi=xi,
        fit_rho=fit_rho,
    )


@dataclass
class PairedLogLoss:
    xi: float
    mean_ll_full: float    # log-loss medio modo full sobre partidos comunes
    mean_ll_rho0: float    # log-loss medio modo rho0 sobre partidos comunes
    d_ll: float            # mean(ll_full - ll_rho0). CONVENCIÓN: d_ll < 0 ⇒ full calibra MEJOR
    se_paired: float       # SE bootstrap PAREADO de d_ll
    z: float               # d_ll / se_paired (nan si se_paired==0)
    n_common: int
    n_only_full: int
    n_only_rho0: int
    delta: np.ndarray
    r_full: "LogLossResult"
    r_rho0: "LogLossResult"


def paired_logloss_comparison(
    played: pd.DataFrame,
    held_out: pd.DataFrame,
    *,
    xi: float,
    window_years: float | None = 8,
    n_boot: int = 2000,
    seed: int = 20260615,
) -> PairedLogLoss:
    """Compara la CALIBRACIÓN de la grilla DC-full (fit_rho=True) vs ρ0 (fit_rho=False)
    por log-loss held-out, sobre el MISMO held_out, con SE PAREADO.

    CONVENCIÓN DE SIGNO: menor log-loss = mejor. delta = ll_full - ll_rho0;
    d_ll = mean(delta) < 0 ⇒ DC-full calibra MEJOR la matriz P(h,a) que ρ0.

    DIAGNÓSTICO: el modelo NO se re-optimiza sobre log-loss (intención EP-pure).
    """
    r_full = rolling_origin_logloss(
        played, held_out, xi=xi, fit_rho=True,
        window_years=window_years, n_boot=n_boot, seed=seed,
    )
    r_rho0 = rolling_origin_logloss(
        played, held_out, xi=xi, fit_rho=False,
        window_years=window_years, n_boot=n_boot, seed=seed,
    )
    common_keys, lf, lr, n_only_full, n_only_rho0 = _align_records(
        r_full.records, r_rho0.records, value_key="ll"
    )
    delta = lf - lr
    n_common = len(common_keys)
    mean_ll_full = float(lf.mean()) if n_common else float("nan")
    mean_ll_rho0 = float(lr.mean()) if n_common else float("nan")
    d_ll = float(delta.mean()) if n_common else float("nan")
    se_paired = _paired_bootstrap_se(delta, n_boot=n_boot, seed=seed)
    z = float(d_ll / se_paired) if (se_paired and se_paired > 0) else float("nan")
    return PairedLogLoss(
        xi=xi,
        mean_ll_full=mean_ll_full,
        mean_ll_rho0=mean_ll_rho0,
        d_ll=d_ll,
        se_paired=se_paired,
        z=z,
        n_common=n_common,
        n_only_full=n_only_full,
        n_only_rho0=n_only_rho0,
        delta=delta,
        r_full=r_full,
        r_rho0=r_rho0,
    )


# =========================================================================== #
# Rolling COMBINADO: un solo fit por fecha -> EP y log-loss juntos             #
# Optimización de costo para modelos de fit caro (bivariado, ~58s/fit): evita  #
# el doble fit de correr rolling_origin_points + rolling_origin_logloss aparte.#
# Debe REPRODUCIR bit a bit ambas funciones por separado (mismo loop/orden/seed)#
# — validado por el orquestador antes de la corrida (test cruzado vs separadas).#
# =========================================================================== #
def rolling_origin_combined(
    played: pd.DataFrame,
    held_out: pd.DataFrame,
    *,
    xi: float,
    fit_rho: bool = True,
    window_years: float | None = 8,
    knockout: bool = False,
    on_predict_error: str = "skip",
    n_boot: int = 2000,
    seed: int = 20260615,
    engine_factory=None,
) -> tuple[BacktestResult, LogLossResult]:
    """Fittea UNA vez por fecha y computa EP (score_prediction) y log-loss (log_loss_grid)
    sobre EXACTAMENTE los mismos partidos predichos (mismos skips). Devuelve
    (BacktestResult, LogLossResult). El SE usa el mismo bootstrap (default_rng(seed)) que
    las funciones separadas; con el mismo orden de partidos, reproduce sus EP/SE/ll bit a bit.
    """
    if on_predict_error not in ("skip", "raise"):
        raise ValueError(f"on_predict_error debe ser 'skip' o 'raise', recibí: {on_predict_error!r}")

    played = played.copy()
    played["date"] = pd.to_datetime(played["date"])
    held_out = held_out.copy()
    held_out["date"] = pd.to_datetime(held_out["date"])
    held_out = held_out.sort_values("date").reset_index(drop=True)
    unique_dates = sorted(held_out["date"].unique())

    pts_list: list[int] = []
    ll_list: list[float] = []
    rec_pts: list[dict] = []
    rec_ll: list[dict] = []
    n_skipped = 0

    for D in unique_dates:
        train = build_train(played, D, window_years=window_years)
        if len(train) == 0:
            n_skipped += len(held_out[held_out["date"] == D])
            continue
        try:
            eng = _build_engine(xi, fit_rho, engine_factory).fit(train, base_date=D)
        except Exception:
            day_matches = held_out[held_out["date"] == D]
            if on_predict_error == "raise":
                raise
            n_skipped += len(day_matches)
            continue

        for _, row in held_out[held_out["date"] == D].iterrows():
            home, away = row["home_team"], row["away_team"]
            neutral = bool(row["neutral"])
            actual = (int(row["home_score"]), int(row["away_score"]))
            try:
                sg = eng.predict(home, away, neutral=neutral)
                pts = score_prediction(sg.grid, actual, knockout=knockout)
                ll = log_loss_grid(sg.grid, actual)
            except (ValueError, AssertionError):
                if on_predict_error == "raise":
                    raise
                n_skipped += 1
                continue
            pred = optimize_match(sg.grid, knockout=knockout)["best"]
            base = {"date": D, "home": home, "away": away, "neutral": neutral,
                    "pred": pred, "actual": actual}
            pts_list.append(pts); rec_pts.append({**base, "pts": pts})
            ll_list.append(ll); rec_ll.append({**base, "ll": ll})

    pts_arr = np.array(pts_list, dtype=float)
    ll_arr = np.array(ll_list, dtype=float)
    n_pred = len(pts_arr)
    if n_pred == 0:
        ep = se_ep = mean_ll = se_ll = float("nan")
    else:
        ep = float(pts_arr.sum() / n_pred)
        se_ep = _bootstrap_se(pts_arr, n_boot=n_boot, seed=seed)
        mean_ll = float(ll_arr.mean())
        se_ll = _bootstrap_se(ll_arr, n_boot=n_boot, seed=seed)

    res_ep = BacktestResult(points=pts_arr, records=rec_pts, n_predicted=n_pred,
                            n_skipped=n_skipped, ep=ep, se=se_ep, xi=xi, fit_rho=fit_rho)
    res_ll = LogLossResult(log_losses=ll_arr, records=rec_ll, n_predicted=n_pred,
                           n_skipped=n_skipped, mean_ll=mean_ll, se=se_ll, xi=xi, fit_rho=fit_rho)
    return res_ep, res_ll
