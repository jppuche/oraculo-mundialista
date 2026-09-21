"""test_backtest_oracle.py — ORÁCULO del harness de backtest multi-copa (Fase 3).

INTOCABLE (DECISIONS.md D2): los builders NO editan este archivo. Bugs en el oráculo
los corrige solo el orquestador, logueado en DECISIONS. Aprobado por JP 2026-06-15
(docs/backtest_design.md). Ancla de inmutabilidad: commit pre-build.

Filosofía (igual que test_engine_oracle / test_tournament_oracle): reducir a invariante
exacta o a DIRECCIÓN anclada en teoría (no a un valor numérico mágico).
  Tier 1: frontera temporal del split (aserción exacta) — el no-leakage por construcción.
  Tier 2: no-leakage CONDUCTUAL (el veneno futuro no mueve el pasado; el pasado sí).
  Tier 3: calibración de ξ DIRECCIONAL (estacionario → memoria larga; régimen → memoria
          corta). Márgenes calibrados empíricamente (barrido 2 escenarios × signal × 5
          seeds, 2026-06-15; ver docs/backtest_design.md §Calibración).
  Tier 4: determinismo + uso de la cadena oraculizada (optimizer+scoring) + cotas.

API bajo contrato (docs/backtest_design.md §Contrato): wcprode.backtest.{build_train,
score_prediction, rolling_origin_points, BacktestResult}. EP = expected points realizados
por partido bajo match_points (ya oraculizado); NO se re-implementa el puntaje.
"""
import numpy as np
import pandas as pd
import pytest

from wcprode.backtest import (
    build_train,
    rolling_origin_points,
    score_prediction,
    xi_grid_search,
)
from wcprode.optimizer import optimize_match
from wcprode.scoring import match_points

SEED = 1
COLS = ["date", "home_team", "away_team", "home_score", "away_score", "neutral"]


def _df(rows):
    """rows: (date, home, away, home_score, away_score, neutral) -> DataFrame schema played."""
    df = pd.DataFrame(rows, columns=COLS)
    df["date"] = pd.to_datetime(df["date"])
    return df


# =====================================================================
# Generador sintético — fuerzas que pueden variar en el tiempo.
# IDÉNTICO al usado para calibrar los márgenes del Tier 3 (mismo orden de
# llamadas al rng -> reproduce los EP medidos). NO importa nada de wcprode.
# =====================================================================
def _synth(seed, regime, signal, n_teams=14, n_dates=72, days_step=30, gamma=0.25):
    """Liga sintética de n_teams a lo largo de n_dates fechas mensuales.

    regime=False: fuerzas constantes (estacionario). regime=True: en la mitad del
    período (di>=t_mid) los ataques se invierten (el pasado lejano pasa a ENGAÑAR).
    Goles ~ Poisson independiente (sin tau; el Tier 3 corre fit_rho=False para aislar ξ).
    Devuelve (df_completo, held_out) con held_out = las últimas 12 fechas (post-régimen).
    """
    rng = np.random.default_rng(seed)
    teams = [f"T{i}" for i in range(n_teams)]
    attack_base = np.linspace(-signal, signal, n_teams); attack_base -= attack_base.mean()
    defence = np.linspace(signal / 2, -signal / 2, n_teams); defence -= defence.mean()
    d0 = pd.Timestamp("2018-01-01")
    dates = [d0 + pd.Timedelta(days=i * days_step) for i in range(n_dates)]
    t_mid = n_dates // 2
    rows = []
    for di, date in enumerate(dates):
        attack = (-attack_base) if (regime and di >= t_mid) else attack_base
        for _ in range(n_teams):                       # ~n_teams partidos por fecha
            i, j = rng.choice(n_teams, 2, replace=False)
            lam = np.exp(attack[i] - defence[j] + gamma)   # i es local
            mu = np.exp(attack[j] - defence[i])
            rows.append((date, teams[i], teams[j],
                         int(rng.poisson(lam)), int(rng.poisson(mu)), False))
    df = pd.DataFrame(rows, columns=COLS)
    df["date"] = pd.to_datetime(df["date"])
    held_out = df[df["date"] >= dates[n_dates - 12]].reset_index(drop=True)
    return df, held_out


def _ep_at_xi(df, held_out, xi):
    return rolling_origin_points(df, held_out, xi=xi, fit_rho=False, window_years=None).ep


# =====================================================================
# Tier 1 — frontera temporal del split (no-leakage POR CONSTRUCCIÓN)
# =====================================================================
def test_train_split_strictly_before():
    # d1<d2<d3 < D(target, mismo día) < d5(futuro). build_train(D) = {d1,d2,d3} EXACTO.
    df = _df([
        ("2020-01-01", "A", "B", 1, 0, False),
        ("2020-02-01", "B", "C", 2, 1, False),
        ("2020-03-01", "A", "C", 0, 0, False),
        ("2020-06-01", "A", "B", 3, 3, False),   # D (target)
        ("2020-09-01", "C", "A", 5, 0, False),   # futuro
    ])
    train = build_train(df, "2020-06-01", window_years=None)
    got = set(train["date"].astype(str))
    assert got == {"2020-01-01", "2020-02-01", "2020-03-01"}, got  # ni D ni futuro


def test_same_day_excluded():
    # Frontera ESTRICTA (< no <=): dos partidos el mismo día D no entran al train de D.
    df = _df([
        ("2020-01-01", "A", "B", 1, 0, False),
        ("2020-06-01", "A", "C", 2, 0, False),   # mismo día D
        ("2020-06-01", "B", "C", 0, 1, False),   # mismo día D
    ])
    train = build_train(df, "2020-06-01", window_years=None)
    assert (train["date"] < pd.Timestamp("2020-06-01")).all()
    assert len(train) == 1                       # solo 2020-01-01


def test_window_excludes_old():
    # window_years acota por ABAJO: lo de > window_years antes de D queda fuera.
    df = _df([
        ("2005-01-01", "A", "B", 1, 0, False),   # > 8a antes de D -> fuera
        ("2015-01-01", "A", "B", 1, 0, False),   # dentro de 8a -> dentro
    ])
    train = build_train(df, "2020-06-01", window_years=8)
    assert set(train["date"].astype(str)) == {"2015-01-01"}


# =====================================================================
# Tier 2 — no-leakage CONDUCTUAL (el test crítico del handoff)
# =====================================================================
def _leakage_base():
    """Historia mínima para A,B,C,D con un target A-B held-out el 2020-06-01."""
    return _df([
        ("2020-01-01", "A", "C", 2, 0, False), ("2020-01-08", "A", "D", 2, 1, False),
        ("2020-01-15", "B", "C", 1, 1, False), ("2020-01-22", "B", "D", 0, 1, False),
        ("2020-02-01", "C", "D", 1, 1, False), ("2020-02-08", "D", "C", 1, 0, False),
        ("2020-06-01", "A", "B", 1, 1, False),   # TARGET held-out
    ])


def _predict_target(played):
    held = played[played["date"] == "2020-06-01"]
    r = rolling_origin_points(played, held, xi=0.0, fit_rho=False, window_years=None)
    return r.records[0]["pred"], r


def test_future_poison_no_change():
    # El veneno (A pierde 0-10) en el FUTURO de D no puede tocar la predicción de D.
    base = _leakage_base()
    pred0, r0 = _predict_target(base)
    poison = _df([("2020-09-01", "A", "E", 0, 10, False),
                  ("2020-09-08", "A", "E", 0, 9, False)])      # FUTURO (> D)
    pred1, r1 = _predict_target(pd.concat([base, poison], ignore_index=True))
    assert pred1 == pred0, f"veneno futuro cambió la predicción: {pred0} -> {pred1}"
    assert r1.points[0] == r0.points[0]


def test_past_poison_does_change():
    # Control de PODER: el mismo veneno en el PASADO de D sí cambia la predicción.
    # (Si no cambiara, test_future_poison pasaría por un harness que ignora datos.)
    base = _leakage_base()
    pred0, _ = _predict_target(base)
    poison = _df([("2020-03-01", "A", "C", 0, 10, False),
                  ("2020-03-08", "A", "D", 0, 9, False)])      # PASADO (< D)
    pred1, _ = _predict_target(pd.concat([base, poison], ignore_index=True))
    assert pred1 != pred0, f"veneno pasado no movió la predicción ({pred0}): test sin poder"


def test_target_result_does_not_leak():
    # A6 (review): el MARCADOR del propio partido target no debe entrar en su fit. Esto vive
    # en el rolling INTEGRADO, no sólo en build_train aislado (Tier 1): un harness que filtra
    # `<= D` en el loop interno pasa Tier 1 pero mete el target en su propio train. Dos
    # escenarios idénticos salvo el resultado del target -> la predicción debe ser IDÉNTICA.
    hist = [
        ("2020-01-01", "A", "C", 2, 0, False), ("2020-01-08", "A", "D", 2, 1, False),
        ("2020-01-15", "B", "C", 1, 1, False), ("2020-01-22", "B", "D", 0, 1, False),
        ("2020-02-01", "C", "D", 1, 1, False), ("2020-02-08", "D", "C", 1, 0, False),
    ]

    def _pred(hs, away_s):
        played = _df(hist + [("2020-06-01", "A", "B", hs, away_s, False)])
        held = played[played["date"] == "2020-06-01"]
        return rolling_origin_points(played, held, xi=0.0, fit_rho=False, window_years=None).records[0]["pred"]

    assert _pred(5, 0) == _pred(0, 5), "el marcador del target filtró a su propia predicción (frontera <= D)"


def test_records_aligned_and_ordered():
    # M1/M4 (review): records[i] corresponde a points[i] (alineación) y las fechas van en
    # orden ascendente. Un diagnóstico desalineado daría EP correcto pero records engañosos.
    df, held = _synth(SEED, regime=False, signal=0.9)
    r = rolling_origin_points(df, held, xi=0.001, fit_rho=False, window_years=None)
    assert len(r.records) == len(r.points) == r.n_predicted
    assert all(r.records[i]["pts"] == r.points[i] for i in range(len(r.points)))
    dates = [rec["date"] for rec in r.records]
    assert dates == sorted(dates), "records no están en orden temporal ascendente"


# =====================================================================
# Tier 3 — calibración de ξ DIRECCIONAL (márgenes calibrados 2026-06-15)
# =====================================================================
def test_stationary_prefers_low_xi():
    # Fuerzas constantes: decaer sólo tira información -> memoria larga (ξ bajo) gana.
    # ξ=0.1 (half-life 7d) deja el fit tan ralo que en algunos partidos la grilla degenera
    # (lam explota, el engine hace fail-loud) y el harness DEBE saltarlos; aun dándole a
    # ξ=0.1 la ventaja de no contar sus peores partidos, pierde contra ξ=0.
    # Margen medido (signal=0.9): seed=1 -> 1.36 ; mínimo sobre 5 seeds -> 0.42. Umbral 0.20.
    df, held = _synth(SEED, regime=False, signal=0.9)
    ep_low, ep_high = _ep_at_xi(df, held, 0.0), _ep_at_xi(df, held, 0.1)
    assert ep_low > ep_high + 0.20, f"EP(ξ=0)={ep_low:.3f} no supera EP(ξ=0.1)={ep_high:.3f}+0.20"


def test_regime_change_prefers_higher_xi():
    # Cambio de régimen: el pasado lejano engaña -> memoria corta (ξ>0) gana sobre ξ=0.
    # Margen medido (signal=1.2): seed=1 -> 1.37 ; mínimo sobre 5 seeds -> 0.75. Umbral 0.40.
    df, held = _synth(SEED, regime=True, signal=1.2)
    ep_zero, ep_mid = _ep_at_xi(df, held, 0.0), _ep_at_xi(df, held, 0.003)
    assert ep_mid > ep_zero + 0.40, f"EP(ξ=0.003)={ep_mid:.3f} no supera EP(ξ=0)={ep_zero:.3f}+0.40"


# =====================================================================
# Tier 4 — determinismo + cadena oraculizada + cotas
# =====================================================================
def test_deterministic():
    df, held = _synth(SEED, regime=False, signal=0.9)
    kw = dict(xi=0.001, fit_rho=False, window_years=None)
    r1, r2 = rolling_origin_points(df, held, **kw), rolling_origin_points(df, held, **kw)
    assert np.array_equal(r1.points, r2.points)
    assert r1.ep == r2.ep and r1.se == r2.se


def test_score_prediction_uses_oracled_chain():
    # A4 (review): en MÚLTIPLES casos (exacto 12 / outcome 5 / un-equipo 2 / nada 0) y en
    # knockout, score_prediction == match_points(optimize_match(grid, knockout,...)['best'],
    # actual). Ancla la cadena oraculizada Y la propagación de knockout/pen_win_prob; un solo
    # caso dejaba pasar reimplementaciones con bug sutil que coinciden por azar.
    rng = np.random.default_rng(0)
    actuals = [(1, 2), (0, 0), (3, 1), (2, 2), (5, 0), (1, 1)]
    for _ in range(6):
        grid = rng.random((7, 7)); grid /= grid.sum()
        for actual in actuals:
            for ko in (False, True):
                best = optimize_match(grid, knockout=ko, pen_win_prob=0.55)["best"]
                assert score_prediction(grid, actual, knockout=ko) == match_points(best, actual)


def test_ep_and_points_consistency():
    # Cotas + EP "vivo" + denominador inequívoco.
    df, held = _synth(SEED, regime=False, signal=0.9)
    r = rolling_origin_points(df, held, xi=0.001, fit_rho=False, window_years=None)
    assert ((r.points >= 0) & (r.points <= 12)).all()              # grupos: match_points ∈ [0,12]
    assert r.ep > 1.0                                              # A5: EP vivo (un harness que da 0 falla)
    assert r.ep == pytest.approx(r.points.sum() / r.n_predicted)   # H2: ep = media sobre PREDICHOS


def test_predict_error_skips_and_counts():
    # predict puede fallar: equipo no visto -> ValueError; grilla degenerada (ξ alto, data
    # rala) -> AssertionError de masa. on_predict_error='skip' (default) los cuenta en
    # n_skipped y sigue; 'raise' los propaga. Determinista: held-out con 'Z' ausente del train.
    df = _df([
        ("2020-01-01", "A", "B", 1, 0, False),
        ("2020-02-01", "A", "B", 2, 1, False),
        ("2020-06-01", "A", "Z", 1, 0, False),   # Z nunca visto antes de D
    ])
    held = df[df["date"] == "2020-06-01"]
    r = rolling_origin_points(df, held, xi=0.0, fit_rho=False, window_years=None, on_predict_error="skip")
    assert r.n_skipped == 1 and r.n_predicted == 0
    with pytest.raises((ValueError, AssertionError)):
        rolling_origin_points(df, held, xi=0.0, fit_rho=False, window_years=None, on_predict_error="raise")


def test_xi_grid_search():
    # H1 (review): xi_grid_search produce el veredicto de Fase 3 (tabla ξ->EP + argmax). Sin
    # test, un bug en el argmax o la tabla contaminaría la conclusión sin que nada lo detecte.
    df, held = _synth(SEED, regime=False, signal=0.9)
    grid = [0.0, 0.1]
    res = xi_grid_search(df, held, grid, fit_rho=False, window_years=None)
    table = {row[0]: row[1] for row in res["table"]}            # row = (xi, ep, se, n_pred)
    assert set(table) == set(grid)                              # una entrada por ξ del grid
    assert res["argmax_xi"] == max(res["table"], key=lambda r: r[1])[0]   # argmax = mayor EP
    assert res["argmax_xi"] == 0.0                              # estacionario -> ξ bajo (consistente con Tier 3)
    ep0 = rolling_origin_points(df, held, xi=0.0, fit_rho=False, window_years=None).ep
    assert table[0.0] == pytest.approx(ep0)                     # la tabla refleja el rolling real
