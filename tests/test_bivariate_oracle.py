"""test_bivariate_oracle.py — ORÁCULO del Poisson bivariado de Karlis-Ntzoufras (Fase 3).

INTOCABLE (DECISIONS.md D2): los builders NO editan este archivo. Bugs en el oráculo los
corrige solo el orquestador, logueado en DECISIONS. Aprobado por JP 2026-06-15
(docs/bivariate_design.md). Ancla de inmutabilidad: commit pre-build. v2 = tras red-team
adversarial de 2 revisores en frío (R1 poder, R2 cobertura/contrato); 9 findings aceptados.

Es la OTRA MITAD de #8: #8 (EP) y #10 (log-loss) midieron que la corrección ρ de Dixon-Coles
no se gana su lugar; este modelo mide si una dependencia EXPLÍCITA (KN) aporta. Alcance
declarado (D2/JP): KN solo captura correlación POSITIVA (λ3≥0); DC estimó ρ<0 — el colapso
a doble-Poisson cuando la data prefiere dependencia negativa ES parte del resultado
(test_t3e lo ancla conductualmente).

Filosofía (igual que test_engine_oracle / test_tournament_oracle / test_backtest_oracle):
reducir a INVARIANTE EXACTA o a DIRECCIÓN anclada en teoría, no a número mágico.
  Tier 1: reduce-to-independent (λ3=0). Ancla dura + cross-fit contra DC-ρ0 ya oraculizado.
  Tier 2: recovery sintético + discriminador de log-lik + time-decay (O9b-style).
  Tier 3: dependencia conductual — Cov(grilla)=λ3, límite estructural (Cov≥0; colapso si <0),
          y WIRING de predict (γ y orden local/visita) vs ensamblaje manual.
  Tier 4: invariantes de la pmf (cerrada vs CONVOLUCIÓN, marginales Poisson, masa) + CONTRATO
          con el harness D6 (equipo no visto, masa degenerada, firma .fit/.predict, atributos).

API bajo contrato (docs/bivariate_design.md §Interfaz): wcprode.bivariate.{bivariate_pmf_grid,
BivariatePoissonEngine(xi, max_goals, lambda3_bounds, fit_lambda3).fit(df, base_date, fit_since)
.predict(h, a, neutral)} con fitted attrs .attack_ .defence_ .home_adv_ .lambda3_ .loglik_ .teams_
MISMA interfaz que DixonColesEngine (reusa ScorelineGrid). El harness D6 se generaliza de forma
backward-compatible (engine_factory opcional, default DC) — el oráculo del backtest queda intacto.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.stats import poisson

from wcprode.bivariate import BivariatePoissonEngine, bivariate_pmf_grid
from wcprode.engine import DixonColesEngine, dixon_coles_weights

RNG_SEED = 20260615
DATA_RAW = Path(__file__).resolve().parents[1] / "data" / "raw"


# =====================================================================
# Referencia INDEPENDIENTE de la pmf = CONVOLUCIÓN DIRECTA.
# Deriva de la construcción X=W1+W3, Y=W2+W3 (suma de Poissons indep.), NO de la
# fórmula cerrada algebraica del paper. Dos derivaciones distintas del mismo número:
# si la implementación (cerrada) y esta (convolución) coinciden, la pmf está bien.
#   P(X=x,Y=y) = Σ_{k=0}^{min(x,y)} P(W3=k) P(W1=x-k) P(W2=y-k)
# =====================================================================
def _pmf_conv(x: int, y: int, l1: float, l2: float, l3: float) -> float:
    s = 0.0
    for k in range(min(x, y) + 1):
        s += poisson.pmf(k, l3) * poisson.pmf(x - k, l1) * poisson.pmf(y - k, l2)
    return float(s)


def _grid_conv(l1: float, l2: float, l3: float, max_goals: int) -> np.ndarray:
    return np.array([[_pmf_conv(x, y, l1, l2, l3) for y in range(max_goals + 1)]
                     for x in range(max_goals + 1)])


def _loglik_ref(df: pd.DataFrame, attack: dict, defence: dict, gamma: float,
                lambda3: float, weights: np.ndarray) -> float:
    """Log-lik ponderada de referencia, VECTORIZADA por convolución sobre los partidos.

    Misma fórmula que _pmf_conv (celda-a-celda, obvia): P(x,y)=Σ_{k=0}^{min(x,y)}
    Pois(k;λ3)Pois(x-k;λ1)Pois(y-k;λ2), pero acumulada por k (una llamada poisson.pmf
    vectorizada por k, no un loop Python sobre miles de partidos). Incluye log(x!y!): por
    eso NO es comparable al loglik_ crudo de DC (que lo omite). Se usa O4-style — comparar
    dos sets de params bajo la MISMA función, inmune a direcciones planas y a esa convención.
    """
    home = df["home_team"].to_numpy()
    away = df["away_team"].to_numpy()
    x = df["home_score"].to_numpy(dtype=int)
    y = df["away_score"].to_numpy(dtype=int)
    neu = df["neutral"].to_numpy(dtype=bool)
    att_h = np.array([attack[t] for t in home]); att_a = np.array([attack[t] for t in away])
    def_h = np.array([defence[t] for t in home]); def_a = np.array([defence[t] for t in away])
    l1 = np.exp(att_h - def_a + np.where(neu, 0.0, gamma))
    l2 = np.exp(att_a - def_h)
    mn = np.minimum(x, y)
    p = np.zeros(len(x))
    for k in range(int(mn.max()) + 1 if len(mn) else 0):
        m = k <= mn  # partidos cuya suma incluye el término k
        p[m] += poisson.pmf(k, lambda3) * poisson.pmf(x[m] - k, l1[m]) * poisson.pmf(y[m] - k, l2[m])
    return float((np.asarray(weights) * np.log(np.maximum(p, 1e-300))).sum())


def _grid_cov(grid: np.ndarray) -> float:
    """Cov(X,Y) de una grilla de probabilidad (normalizada)."""
    g = grid / grid.sum()
    xs = np.arange(g.shape[0])
    EX = (g.sum(axis=1) * xs).sum()
    EY = (g.sum(axis=0) * xs).sum()
    EXY = (g * np.outer(xs, xs)).sum()
    return float(EXY - EX * EY)


# =====================================================================
# Generador sintético PROPIO — muestrea de la construcción KN (X=W1+W3, Y=W2+W3).
# NO importa nada de wcprode. Fuerzas fijas por equipo (att/def lineales).
# =====================================================================
def _make_synthetic_biv(rng, attack, defence, gamma, lambda3, n_home, n_neutral, date):
    teams = list(attack)
    rows = []
    for home in teams:
        for away in teams:
            if home == away:
                continue
            for neutral, n in ((False, n_home), (True, n_neutral)):
                if n == 0:
                    continue
                l1 = np.exp(attack[home] - defence[away] + (0.0 if neutral else gamma))
                l2 = np.exp(attack[away] - defence[home])
                w1 = rng.poisson(l1, n)
                w2 = rng.poisson(l2, n)
                w3 = rng.poisson(lambda3, n)
                for h, a in zip(w1 + w3, w2 + w3):
                    rows.append({"date": date, "home_team": home, "away_team": away,
                                 "home_score": int(h), "away_score": int(a), "neutral": neutral})
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    return df


def _true_params(n_teams=8):
    teams = [f"T{i}" for i in range(n_teams)]
    att = np.linspace(-0.4, 0.4, n_teams); att -= att.mean()
    dfc = np.linspace(0.35, -0.35, n_teams); dfc -= dfc.mean()
    return teams, dict(zip(teams, att)), dict(zip(teams, dfc))


@pytest.fixture(scope="module")
def fitted_biv():
    """Engine fitted sobre sintéticos KN con λ3>0 conocido (Tier 2/3)."""
    teams, attack, defence = _true_params()
    gamma, lambda3 = 0.25, 0.30
    rng = np.random.default_rng(RNG_SEED)
    df = _make_synthetic_biv(rng, attack, defence, gamma, lambda3,
                             n_home=300, n_neutral=75, date="2026-01-01")
    eng = BivariatePoissonEngine(xi=0.0, fit_lambda3=True).fit(
        df, base_date=pd.Timestamp("2026-01-01"))
    return eng, df, attack, defence, gamma, lambda3


# =====================================================================
# Tier 1 — reduce-to-independent (λ3=0). Ancla dura + cross-fit contra DC-ρ0.
# =====================================================================
def test_t1a_lambda3_zero_is_outer_poisson():
    # λ3=0 -> grilla idéntica al outer product de dos Poisson independientes.
    # La raíz del modelo: si esto falla, KN está mal implementado. (Tb ancla que la grilla
    # es RAW, no normalizada: el outer truncado suma <1; normalizar haría fallar este test.)
    l1, l2, mg = 1.45, 1.10, 15
    g = bivariate_pmf_grid(l1, l2, 0.0, mg)
    expected = np.outer(poisson.pmf(np.arange(mg + 1), l1), poisson.pmf(np.arange(mg + 1), l2))
    np.testing.assert_allclose(g, expected, rtol=1e-12, atol=1e-15)


def test_t1b_engine_lambda3_zero_equals_rho0():
    # Con λ3≡0 el bivariado ES doble-Poisson ponderado = DixonColesEngine(fit_rho=False).
    # MISMO modelo, MISMO gauge (mean(attack)=0) -> MISMO óptimo salvo ruido de convergencia.
    # Cross-fit GRATIS contra un engine YA ORACULIZADO: ancla que el caso límite = producción.
    # NB: NO se comparan los loglik_ crudos — DC OMITE el término constante log(x!y!) de la
    # log-lik Poisson y el bivariado lo INCLUYE; difieren por esa constante aunque el argmax
    # sea idéntico. Se comparan PARÁMETROS y PREDICCIONES, que sí coinciden.
    # Márgenes verificados (orquestador 2026-06-15): params ~1e-7, grilla ~1.5e-8 (umbral 1e-5).
    teams, attack, defence = _true_params()
    rng = np.random.default_rng(RNG_SEED)
    df = _make_synthetic_biv(rng, attack, defence, 0.25, 0.0, 200, 50, "2026-01-01")
    base = pd.Timestamp("2026-01-01")
    biv = BivariatePoissonEngine(xi=0.0, fit_lambda3=False).fit(df, base_date=base)
    dc0 = DixonColesEngine(xi=0.0, fit_rho=False).fit(df, base_date=base)
    # fit_lambda3=False fija λ3_=0.0 EXACTO (no el bound inferior ni el init) — R2-M5
    assert biv.lambda3_ == 0.0, f"fit_lambda3=False debe fijar lambda3_=0.0, dio {biv.lambda3_}"
    # gauge mean(attack)=0 impuesto por el propio fit (no heredado) — R1-F8
    assert abs(np.mean(list(biv.attack_.values()))) < 1e-8, "gauge mean(attack)=0 violado"
    # parámetros (mismo gauge): coinciden salvo ruido de convergencia (umbral 1e-5, real ~1e-7)
    assert abs(biv.home_adv_ - dc0.home_adv_) < 1e-5, f"γ: {biv.home_adv_} vs {dc0.home_adv_}"
    for t in teams:
        assert abs(biv.attack_[t] - dc0.attack_[t]) < 1e-5, f"attack[{t}]"
        assert abs(biv.defence_[t] - dc0.defence_[t]) < 1e-5, f"defence[{t}]"
    # predicciones idénticas, neutral Y con localía (ancla γ en el caso límite) — R1-F6
    for neutral in (True, False):
        for h, a in [(teams[0], teams[3]), (teams[5], teams[1]), (teams[2], teams[6])]:
            np.testing.assert_allclose(biv.predict(h, a, neutral=neutral).grid,
                                       dc0.predict(h, a, neutral=neutral).grid, atol=1e-5)


def test_t1c_convergence_at_scale():
    # BLINDSPOT descubierto por el orquestador (2026-06-16, DECISIONS D10): los demás tests usan
    # 8 equipos con data DENSA/balanceada, donde cualquier optimizador converge. El problema real
    # aparece en el universo de SELECCIONES: cientos de equipos con datos RALOS y DESBALANCEADOS
    # (muchos equipos con pocos partidos, fuerzas dispares -> Hessiano mal condicionado). Ahí un
    # gradiente numérico se quedó Δlog-lik≈43 del óptimo (ratings off por ~5 en log-escala) y el
    # backtest mediría el OPTIMIZADOR, no el modelo. Este test exige que biv(λ3=0) sobre el
    # universo real (ventana ~8a, ~300 equipos) CONVERJA a la log-lik de DC-ρ0 (mismo modelo,
    # gradiente analítico). Edición del orquestador al oráculo congelado (D2 lo permite, logueado).
    # Usa datos reales como O4/O5 (precedente); skip declarado si el CSV pineado no está.
    path = DATA_RAW / "results.csv"
    if not path.exists():
        pytest.skip("results.csv ausente — t1c (convergencia a escala) necesita el universo real "
                    "(re-fetch por pin de sources.lock.json). El veredicto lo sostienen t1b + t2.")
    raw = pd.read_csv(path).dropna(subset=["home_score", "away_score"])
    raw["date"] = pd.to_datetime(raw["date"])
    train = raw[(raw["date"] >= "2010-06-20") & (raw["date"] < "2018-06-20")].copy()
    train["neutral"] = train["neutral"].astype(str).str.upper().eq("TRUE")
    train["home_score"] = train["home_score"].astype(int)
    train["away_score"] = train["away_score"].astype(int)
    base = train["date"].max()
    n_teams = len(set(train["home_team"]) | set(train["away_team"]))
    assert n_teams > 150, f"t1c necesita el universo grande/ralo, hay {n_teams} equipos"
    xi = 0.0018
    biv = BivariatePoissonEngine(xi=xi, fit_lambda3=False).fit(train, base_date=base)
    dc0 = DixonColesEngine(xi=xi, fit_rho=False).fit(train, base_date=base)
    w = dixon_coles_weights(train["date"], xi, base)
    ll_biv = _loglik_ref(train, biv.attack_, biv.defence_, biv.home_adv_, 0.0, w)
    ll_dc0 = _loglik_ref(train, dc0.attack_, dc0.defence_, dc0.home_adv_, 0.0, w)
    # convergencia: biv debe ALCANZAR la log-lik de DC-ρ0 (gradiente numérico: Δ≈-43, FALLA)
    assert ll_biv >= ll_dc0 - 1e-3 * abs(ll_dc0), (
        f"biv no converge a escala real ({n_teams} equipos): ll_biv={ll_biv:.2f} vs "
        f"ll_dc0={ll_dc0:.2f} (Δ={ll_biv - ll_dc0:.2f}) -> el optimizador no escala")


# =====================================================================
# Tier 2 — recovery + discriminador de log-lik + time-decay.
# =====================================================================
def test_t2a_parameter_recovery(fitted_biv):
    eng, df, attack, defence, gamma, lambda3 = fitted_biv
    assert abs(eng.lambda3_ - lambda3) < 0.05, f"λ3 no recuperado: {eng.lambda3_} vs {lambda3}"
    assert abs(eng.home_adv_ - gamma) < 0.06, f"γ no recuperado: {eng.home_adv_} vs {gamma}"
    for t in attack:
        assert abs(eng.attack_[t] - attack[t]) < 0.09, f"attack[{t}]: {eng.attack_[t]} vs {attack[t]}"
        assert abs(eng.defence_[t] - defence[t]) < 0.09, f"defence[{t}]: {eng.defence_[t]} vs {defence[t]}"


def test_t2b_loglik_discriminator(fitted_biv):
    # Bajo la log-lik de REFERENCIA (convolución), los params fitted deben puntuar >= que los
    # TRUE (el MLE correcto maximiza ESTA función). Un engine que maximiza una likelihood
    # equivocada (pmf mal sumada, swap λ1/λ2, k mal indexado) produce un argmax subóptimo y FALLA.
    eng, df, attack, defence, gamma, lambda3 = fitted_biv
    w = np.ones(len(df))
    ll_fit = _loglik_ref(df, eng.attack_, eng.defence_, eng.home_adv_, eng.lambda3_, w)
    ll_true = _loglik_ref(df, attack, defence, gamma, lambda3, w)
    assert ll_fit >= ll_true - 1e-6 * abs(ll_true), \
        f"params fitted subóptimos bajo la likelihood de referencia: {ll_fit} < {ll_true}"


def test_t2c_decay_enters_loglik():
    # O9b-style (R2-H3): equipo X fuerte en era vieja, débil en la reciente. Con decay el fit
    # debe verlo DÉBIL; sin decay (xi=0) lo ve promedio. Si el builder reimplementa el decay e
    # ignora los pesos w_m en la log-lik del bivariado (o invierte el signo del exponente), el
    # bivariado quedaría silenciosamente plano y la comparación EP vs DC(xi=0.0018) sería inválida.
    teams, attack, defence = _true_params()
    x = teams[0]
    rng = np.random.default_rng(RNG_SEED + 99)
    att_old = dict(attack, **{x: 0.5})
    att_new = dict(attack, **{x: -0.5})
    df_old = _make_synthetic_biv(rng, att_old, defence, 0.25, 0.0, 80, 0, "2010-06-01")
    df_new = _make_synthetic_biv(rng, att_new, defence, 0.25, 0.0, 80, 0, "2025-06-01")
    df = pd.concat([df_old, df_new], ignore_index=True)
    base = pd.Timestamp("2026-06-10")
    flat = BivariatePoissonEngine(xi=0.0, fit_lambda3=False).fit(df, base_date=base)
    decay = BivariatePoissonEngine(xi=0.0018, fit_lambda3=False).fit(df, base_date=base)
    # peso era vieja ~ e^{-0.0018*5844} ~ 3e-5 -> decay ve X débil; margen medido 0.51, umbral 0.3
    assert decay.attack_[x] < flat.attack_[x] - 0.3, (
        f"decay no pondera lo reciente: flat={flat.attack_[x]:.3f} decay={decay.attack_[x]:.3f}")


# =====================================================================
# Tier 3 — dependencia conductual + límite estructural + wiring de predict.
# =====================================================================
def test_t3a_grid_covariance_equals_lambda3(fitted_biv):
    # La dependencia que el modelo PONE en la grilla predictiva es la que DICE poner: Cov=λ3.
    # Umbral 1e-6 (margen real ~1e-10; el truncamiento a max_goals es despreciable).
    eng, *_ = fitted_biv
    teams = eng.teams_
    for h, a in [(teams[2], teams[5]), (teams[0], teams[7])]:
        cov = _grid_cov(eng.predict(h, a, neutral=True).grid)
        assert abs(cov - eng.lambda3_) < 1e-6, f"Cov(grilla)={cov:.6f} != λ3_={eng.lambda3_:.6f}"


def test_t3b_positive_dependence_only():
    # λ3>0 -> Cov(grilla) ESTRICTAMENTE positiva y CRECIENTE en λ3; λ3=0 -> Cov exactamente 0.
    # KN NUNCA produce Cov<0. Ancla numérica dura Cov(grilla)==λ3 (verificado a 1e-10), inclусo
    # para λ3 grande con max_goals suficiente (R2-M3: el truncamiento no rompe el invariante).
    def cov_at(l3, mg=20):
        return _grid_cov(bivariate_pmf_grid(1.5, 1.2, l3, mg))
    c0, c1, c2 = cov_at(0.0), cov_at(0.2), cov_at(0.5)
    assert abs(c0) < 1e-9, f"λ3=0 debe dar Cov=0, dio {c0}"
    assert c1 > 1e-6, f"λ3=0.2 debe dar Cov>0, dio {c1}"
    assert c2 > c1, f"Cov debe crecer con λ3: c(0.5)={c2} <= c(0.2)={c1}"
    assert abs(c1 - 0.2) < 1e-6 and abs(c2 - 0.5) < 1e-6
    assert abs(cov_at(1.0, mg=30) - 1.0) < 1e-6, "Cov(grilla)=λ3 debe valer también para λ3=1.0"


def test_t3c_fit_directional_invariants(fitted_biv):
    # Valida el cableado de la regresión att/def/γ (independiente de λ3), análogo a O6.
    eng, _, attack, *_ = fitted_biv
    strong = max(attack, key=attack.get)
    weak = min(attack, key=attack.get)
    assert eng.predict(strong, weak, neutral=True).p_home_win() > \
           eng.predict(weak, strong, neutral=True).p_home_win()
    assert eng.predict(strong, weak, neutral=False).p_home_win() > \
           eng.predict(strong, weak, neutral=True).p_home_win()
    g = eng.predict(strong, weak, neutral=True).grid
    assert abs(g.sum() - 1.0) < 1e-9 and (g >= 0).all()


def test_t3d_predict_wiring_matches_manual_assembly(fitted_biv):
    # R1-F1/F3/F6: predict() debe ensamblar la grilla desde los attrs con el orden y γ
    # correctos. Comparar contra el ensamblaje MANUAL mata de un saque: swap λ1↔λ2 (orden
    # local/visita), signo/ausencia de γ, y λ3 mal pasado a la grilla. Margen real: 0.0 exacto.
    eng, _, attack, *_ = fitted_biv
    teams = eng.teams_
    for h, a in [(teams[2], teams[5]), (teams[6], teams[0])]:   # asimétricos (att distintos)
        for neutral in (True, False):
            home_term = 0.0 if neutral else eng.home_adv_
            l1 = np.exp(eng.attack_[h] - eng.defence_[a] + home_term)
            l2 = np.exp(eng.attack_[a] - eng.defence_[h])
            g_manual = bivariate_pmf_grid(l1, l2, eng.lambda3_, eng.max_goals)
            g_manual = g_manual / g_manual.sum()
            np.testing.assert_allclose(eng.predict(h, a, neutral=neutral).grid, g_manual, atol=1e-12)


def test_t3e_negative_dependence_collapses_to_independent():
    # LÍMITE ESTRUCTURAL (el corazón del experimento): data con goles local/visita
    # ANTI-correlacionados (Cov muestral < 0). KN solo modela λ3≥0, así que NO puede capturar
    # dependencia negativa y el MLE se CLAVA en la frontera λ3=0 (colapsa a independiente).
    # Esto ancla a la vez (a) el bound inferior 0 (R1-F2/R2-M4: un engine sin bound iría a
    # λ3<0 y rompería la pmf) y (b) que el bivariado replica la conclusión esperada en datos de
    # selecciones (DC estimó ρ<0). Control de poder: t2a muestra que el MISMO engine SÍ
    # recupera λ3≈0.30 sobre data con dependencia positiva -> no es un engine que da 0 siempre.
    teams, attack, defence = _true_params()
    rng = np.random.default_rng(7)
    rows = []
    for home in teams:
        for away in teams:
            if home == away:
                continue
            for _ in range(80):
                h = rng.poisson(np.exp(attack[home] - defence[away] + 0.25))
                a = rng.poisson(max(0.15, np.exp(attack[away] - defence[home]) - 0.5 * h))  # anti-corr
                rows.append(("2026-01-01", home, away, int(h), int(a), False))
    df = pd.DataFrame(rows, columns=["date", "home_team", "away_team",
                                     "home_score", "away_score", "neutral"])
    df["date"] = pd.to_datetime(df["date"])
    assert np.cov(df.home_score, df.away_score)[0, 1] < -0.05, "la data sintética debe ser anti-correlacionada"
    eng = BivariatePoissonEngine(xi=0.0, fit_lambda3=True, lambda3_bounds=(0.0, 2.0)).fit(
        df, base_date=pd.Timestamp("2026-01-01"))
    assert eng.lambda3_ < 1e-3, f"ante dependencia negativa λ3 debe clavarse en 0, dio {eng.lambda3_}"
    # corolario: la grilla nunca tiene celdas negativas (bound respetado)
    assert (eng.predict(teams[0], teams[1], neutral=False).grid >= 0).all()


# =====================================================================
# Tier 4 — invariantes de la pmf + CONTRATO con el harness D6.
# =====================================================================
def test_t4a_closed_form_equals_convolution():
    # La pmf de la implementación (fórmula cerrada) == convolución directa (referencia
    # independiente). Dos derivaciones algebraicamente distintas del mismo número. Incluye un
    # caso SIMÉTRICO λ1=λ2 (R2-L1) y casos asimétricos / λ chicos.
    for l1, l2, l3 in [(1.45, 1.10, 0.30), (2.5, 1.8, 0.5), (0.9, 0.7, 0.2),
                       (0.3, 0.4, 0.1), (3.5, 0.5, 0.05), (1.2, 1.2, 0.3)]:
        g_impl = bivariate_pmf_grid(l1, l2, l3, 15)
        g_ref = _grid_conv(l1, l2, l3, 15)
        np.testing.assert_allclose(g_impl, g_ref, rtol=1e-12, atol=1e-15)


def test_t4b_marginals_are_poisson():
    # Marginales de la grilla = Poisson(λ1+λ3) y Poisson(λ2+λ3) (propiedad fundamental KN:
    # X~Poisson(λ1+λ3) por construcción). Ancla la distribución marginal COMPLETA (media Y
    # varianza, no solo la media): la Poisson tiene un único parámetro.
    for l1, l2, l3 in [(1.45, 1.10, 0.30), (2.5, 1.8, 0.5)]:
        g = bivariate_pmf_grid(l1, l2, l3, 25)
        xs = np.arange(26)
        np.testing.assert_allclose(g.sum(axis=1), poisson.pmf(xs, l1 + l3), atol=1e-9)
        np.testing.assert_allclose(g.sum(axis=0), poisson.pmf(xs, l2 + l3), atol=1e-9)


def test_t4c_grid_mass_and_normalization(fitted_biv):
    # RAW: la pmf preserva masa (suma <=1, solo pierde truncamiento -> >=0.999). Mismo
    # contrato que el assert de DC (engine.py:346). Normalizada: suma 1, no-negativa.
    for l1, l2, l3 in [(2.5, 1.8, 0.5), (0.9, 0.7, 0.2), (1.45, 1.10, 0.3)]:
        raw = bivariate_pmf_grid(l1, l2, l3, 15)
        s = raw.sum()
        assert 0.999 <= s <= 1.0 + 1e-12, f"masa {s} fuera de rango para {(l1, l2, l3)}"
        assert (raw >= 0).all()
    eng = fitted_biv[0]
    g = eng.predict(eng.teams_[0], eng.teams_[1], neutral=True).grid
    assert abs(g.sum() - 1.0) < 1e-9 and (g >= 0).all()


def test_t4d_unknown_team_contract(fitted_biv):
    # Contrato con el harness D6: equipo no visto -> ValueError (igual que DC), para que
    # rolling_origin_points lo skipee (on_predict_error='skip').
    eng = fitted_biv[0]
    with pytest.raises(ValueError):
        eng.predict("EQUIPO_INEXISTENTE", eng.teams_[0], neutral=True)


def test_t4e_degenerate_grid_raises_assertion():
    # R2-H2/R1-F10: el harness D6 captura (ValueError, AssertionError) para skipear. Si predict
    # NO hace fail-loud cuando λ explota (masa truncada < 0.999), una grilla degenerada
    # contaminaría el EP sin skip. Forzar attack_ enorme -> la masa colapsa -> AssertionError.
    teams, attack, defence = _true_params()
    rng = np.random.default_rng(RNG_SEED)
    df = _make_synthetic_biv(rng, attack, defence, 0.25, 0.0, 60, 0, "2026-01-01")
    eng = BivariatePoissonEngine(xi=0.0, fit_lambda3=False).fit(df, base_date=pd.Timestamp("2026-01-01"))
    eng.attack_[teams[0]] = 25.0   # lam ~ e^25 -> el truncamiento a max_goals destruye la masa
    with pytest.raises(AssertionError):
        eng.predict(teams[0], teams[1], neutral=True)


def test_t4f_interface_contract():
    # R2-H1/H4: ancla la firma que el harness D6 invoca (sin correr el harness, que se
    # generaliza aparte). .fit(df, base_date, fit_since) con fit_since que FILTRA; atributos
    # fitted presentes; .predict(h,a,neutral) -> objeto con .grid normalizada y p_home/draw/away.
    teams, attack, defence = _true_params()
    rng = np.random.default_rng(RNG_SEED)
    df_old = _make_synthetic_biv(rng, attack, defence, 0.25, 0.0, 60, 0, "2010-06-01")
    df_new = _make_synthetic_biv(rng, dict(attack, **{teams[0]: 0.6}), defence, 0.25, 0.0, 60, 0, "2025-06-01")
    df = pd.concat([df_old, df_new], ignore_index=True)
    base = pd.Timestamp("2026-06-10")
    eng_all = BivariatePoissonEngine(xi=0.0, fit_lambda3=True).fit(df, base_date=base)
    eng_recent = BivariatePoissonEngine(xi=0.0, fit_lambda3=True).fit(df, base_date=base, fit_since="2020-01-01")
    # fit_since recorta: con solo la era reciente, attack_[T0] difiere materialmente
    assert abs(eng_recent.attack_[teams[0]] - eng_all.attack_[teams[0]]) > 0.1, "fit_since no filtró"
    # atributos del contrato presentes
    for attr in ("attack_", "defence_", "home_adv_", "lambda3_", "loglik_", "teams_"):
        assert getattr(eng_all, attr) is not None, f"falta atributo {attr}"
    # predict devuelve grilla normalizada + las 3 probabilidades de resultado (que usa el optimizer)
    sg = eng_all.predict(teams[1], teams[2], neutral=False)
    assert abs(sg.grid.sum() - 1.0) < 1e-9
    assert abs(sg.p_home_win() + sg.p_draw() + sg.p_away_win() - 1.0) < 1e-9
