"""test_tournament_oracle.py — ORÁCULO del Monte Carlo de torneo (Final Soñada).

INTOCABLE (DECISIONS.md D2): los builders NO editan este archivo. Bugs en el oráculo
los corrige solo el orquestador, logueado en DECISIONS. Aprobado por JP 2026-06-15
(docs/final_sonada_design.md §5; +6b por el knob de penales 0.55).

Filosofía (igual que test_engine_oracle): reducir a forma cerrada o a invariante exacta.
  Tier 1: sub-componentes deterministas (aserción exacta).
  Tier 2: core estocástico vs forma cerrada (mini-bracket analítico) + degenerado.
  Tier 3: invariantes de conteo (suma=1, descomposición, reproducibilidad).
  Tier 4: condicionamiento en resultados parciales.

Las cuentas a mano están en los comentarios de cada test (verificables).
"""
import numpy as np
import pytest

from wcprode import tournament as T
from wcprode.tournament import (
    TournamentSimulator,
    assign_thirds_to_slots,
    best_thirds,
    final_sonada_pick,
    group_standings,
    load_thirds_table,
    resolve_penalties,
    simulate_bracket,
)

GROUP_LETTERS = list("ABCDEFGHIJKL")


# =========================================================================== #
# Tier 1 — sub-componentes deterministas                                      #
# =========================================================================== #
def test_group_table_basic():
    # T1>T2>T3>T4 por puntos puros: T1=9, T2=6, T3=3, T4=0.
    matches = [
        ("T1", "T2", 1, 0), ("T1", "T3", 1, 0), ("T1", "T4", 1, 0),
        ("T2", "T3", 1, 0), ("T2", "T4", 1, 0), ("T3", "T4", 1, 0),
    ]
    assert group_standings(matches, ["T1", "T2", "T3", "T4"]) == ["T1", "T2", "T3", "T4"]


def test_group_tiebreak_head_to_head_first():
    # CLAVE: 2026 usa head-to-head ANTES que GD global (cambio vs 2022).
    # T1 y T2 empatan en 6 pts. T2 le ganó a T1 (H2H), pero T1 tiene MEJOR GD global (+9 vs +1).
    #   Regla 2026 (H2H primero) -> T2 va 1°, T1 2°.
    #   Regla vieja (GD global primero) daría [T1, T2, ...] -> este test la falsa.
    # T3 y T4 empatan en 3 pts, mismo GD (-5) y GF (1); T3 le ganó a T4 -> T3 3°, T4 4°.
    matches = [
        ("T1", "T2", 0, 1),   # T2 gana el H2H
        ("T1", "T3", 5, 0), ("T1", "T4", 5, 0),
        ("T2", "T3", 1, 0), ("T2", "T4", 0, 1),
        ("T3", "T4", 1, 0),   # T3 gana el H2H
    ]
    # T1: 6pts GD+9 ; T2: 6pts GD+1 ; T3: 3pts GD-5 GF1 ; T4: 3pts GD-5 GF1
    assert group_standings(matches, ["T1", "T2", "T3", "T4"]) == ["T2", "T1", "T3", "T4"]


def test_group_standings_deterministic():
    # Sin empates profundos -> sin rng -> reproducible.
    matches = [
        ("T1", "T2", 2, 0), ("T1", "T3", 1, 0), ("T1", "T4", 3, 0),
        ("T2", "T3", 1, 0), ("T2", "T4", 2, 0), ("T3", "T4", 1, 0),
    ]
    a = group_standings(matches, ["T1", "T2", "T3", "T4"])
    b = group_standings(matches, ["T1", "T2", "T3", "T4"])
    assert a == b == ["T1", "T2", "T3", "T4"]


def test_best_thirds_selection():
    # 12 terceros; los 8 mejores por pts -> GD -> GF. Frontera 8°/9° entre G,H,I (3 pts):
    # G(gd2) H(gd1) avanzan, I(gd0) queda 9° y FUERA.
    records = {
        "A": (6, 5, 9), "B": (6, 3, 7), "C": (5, 4, 8), "D": (5, 2, 5),
        "E": (4, 3, 6), "F": (4, 1, 4), "G": (3, 2, 5), "H": (3, 1, 3),
        "I": (3, 0, 2), "J": (2, -1, 2), "K": (2, -3, 1), "L": (1, -5, 1),
    }
    got = best_thirds(records)
    assert got == ["A", "B", "C", "D", "E", "F", "G", "H"]
    assert "I" not in got


def test_bracket_slotting_verified_scenario():
    # Fila 1 de Annex C (verificada): terceros de {E,F,G,H,I,J,K,L} ->
    # 1A:3E 1B:3J 1D:3I 1E:3F 1G:3H 1I:3G 1K:3L 1L:3K
    table = load_thirds_table()
    got = assign_thirds_to_slots(set("EFGHIJKL"), table)
    assert got == {"A": "E", "B": "J", "D": "I", "E": "F",
                   "G": "H", "I": "G", "K": "L", "L": "K"}


def test_thirds_table_is_complete():
    # Las 495 combinaciones C(12,8) presentes y bien formadas.
    table = load_thirds_table()
    assert len(table) == 495
    for key, assign in table.items():
        assert len(key) == 8
        assert len(assign) == 8
        assert set(assign.values()) == set(key)


def test_pick_distinct():
    # argmax campeón = X, argmax subcampeón = Y, distintos -> (X, Y), val=10*(0.4+0.35)=7.5
    p_champ = {"X": 0.40, "Y": 0.30, "Z": 0.20, "W": 0.10}
    p_run = {"Y": 0.35, "Z": 0.30, "X": 0.20, "W": 0.15}
    r = final_sonada_pick(p_champ, p_run)
    assert r["champion"] == "X"
    assert r["runnerup"] == "Y"
    assert r["expected_points"] == pytest.approx(7.5)


def test_pick_conflict():
    # argmax de ambos = T -> hay que partir.
    #   T-campeón + mejor-subcampeón≠T (X=.35): 10*(.5+.35)=8.5
    #   mejor-campeón≠T (X=.2) + T-subcampeón: 10*(.2+.4)=6.0
    # Óptimo: (T, X), 8.5.
    p_champ = {"T": 0.50, "X": 0.20, "Y": 0.20, "Z": 0.10}
    p_run = {"T": 0.40, "X": 0.35, "Y": 0.15, "Z": 0.10}
    r = final_sonada_pick(p_champ, p_run)
    assert r["champion"] == "T"
    assert r["runnerup"] == "X"
    assert r["expected_points"] == pytest.approx(8.5)


class _FakeRng:
    """rng con .random() forzado (para fijar el umbral de penales)."""
    def __init__(self, value):
        self._v = value

    def random(self):
        return self._v


def test_penalty_resolution_favorite_tilt():
    # Convención: favorito si rng.random() < p (p=0.55).
    assert resolve_penalties("FAV", "DOG", _FakeRng(0.50), p=0.55) == "FAV"
    assert resolve_penalties("FAV", "DOG", _FakeRng(0.60), p=0.55) == "DOG"
    # Borde: 0.55 NO es < 0.55 -> underdog.
    assert resolve_penalties("FAV", "DOG", _FakeRng(0.55), p=0.55) == "DOG"


# =========================================================================== #
# Tier 2 — core estocástico vs forma cerrada                                  #
# =========================================================================== #
# Matriz de victorias P(fila vence a columna), sin empates (no hay penales).
_PWIN = {
    ("A", "B"): 0.70, ("A", "C"): 0.65, ("A", "D"): 0.80,
    ("B", "A"): 0.30, ("B", "C"): 0.55, ("B", "D"): 0.70,
    ("C", "A"): 0.35, ("C", "B"): 0.45, ("C", "D"): 0.60,
    ("D", "A"): 0.20, ("D", "B"): 0.30, ("D", "C"): 0.40,
}


def _no_draw_provider(home, away, neutral=True):
    """grid 2x2 sin empates: grid[1,0]=P(home gana), grid[0,1]=P(away gana)."""
    p = _PWIN[(home, away)]
    return np.array([[0.0, 1.0 - p], [p, 0.0]])


def test_mini_bracket_champion_analytic():
    # Bracket de 4: SF (A,B) y (C,D); final entre ganadores. Forma cerrada:
    #   P(A campeón) = P(A>B) * [P(C>D)*P(A>C) + P(D>C)*P(A>D)]
    #               = 0.7 * [0.6*0.65 + 0.4*0.80] = 0.7*0.71 = 0.497
    #   P(A subcampeón) = P(A>B) * [P(C>D)*P(C>A) + P(D>C)*P(D>A)]
    #               = 0.7 * [0.6*0.35 + 0.4*0.20] = 0.7*0.29 = 0.203
    #   P(C campeón) = P(C>D) * [P(A>B)*P(C>A) + P(B>A)*P(C>B)]
    #               = 0.6 * [0.7*0.35 + 0.3*0.45] = 0.6*0.38 = 0.228
    N = 50_000
    tol = 0.012
    rng = np.random.default_rng(20260615)
    champ = {t: 0 for t in "ABCD"}
    runr = {t: 0 for t in "ABCD"}
    for _ in range(N):
        c, r = simulate_bracket([("A", "B"), ("C", "D")], _no_draw_provider, rng)
        champ[c] += 1
        runr[r] += 1
    assert sum(champ.values()) == N            # cada sim tiene un campeón
    assert champ["A"] / N == pytest.approx(0.497, abs=tol)
    assert runr["A"] / N == pytest.approx(0.203, abs=tol)
    assert champ["C"] / N == pytest.approx(0.228, abs=tol)


def test_mini_bracket_degenerate_dominant():
    # A vence a todos con P=1 -> A campeón SIEMPRE; A nunca subcampeón.
    def dom_provider(home, away, neutral=True):
        if home == "A":
            return np.array([[0.0, 0.0], [1.0, 0.0]])   # home(A) gana
        if away == "A":
            return np.array([[0.0, 1.0], [0.0, 0.0]])   # away(A) gana
        return np.array([[0.0, 0.5], [0.5, 0.0]])
    rng = np.random.default_rng(1)
    for _ in range(1000):
        c, r = simulate_bracket([("A", "B"), ("C", "D")], dom_provider, rng)
        assert c == "A"
        assert r != "A"


# =========================================================================== #
# Tier 3 — invariantes de conteo (sim completo, provider stub)                #
# =========================================================================== #
def _synthetic_groups():
    return {g: [f"{g}1", f"{g}2", f"{g}3", f"{g}4"] for g in GROUP_LETTERS}


def _round_robin(teams):
    t = teams
    return [(t[0], t[1]), (t[0], t[2]), (t[0], t[3]),
            (t[1], t[2]), (t[1], t[3]), (t[2], t[3])]


def _all_remaining_fixtures(groups, skip=()):
    fx = []
    for g, teams in groups.items():
        if g in skip:
            continue
        for h, a in _round_robin(teams):
            fx.append((g, h, a))
    return fx


# grid fijo con ventaja de local + masa de empate (mismo para todo matchup).
_FIXED = np.array([[0.08, 0.06, 0.03], [0.10, 0.09, 0.04], [0.07, 0.06, 0.05]])
_FIXED = _FIXED / _FIXED.sum()


def _fixed_provider(home, away, neutral=True):
    return _FIXED


def _make_sim(played=None, skip_groups=()):
    groups = _synthetic_groups()
    return TournamentSimulator(
        groups=groups,
        played_results=played or [],
        remaining_fixtures=_all_remaining_fixtures(groups, skip=skip_groups),
        thirds_table=load_thirds_table(),
        prob_provider=_fixed_provider,
    )


def test_champion_marginals_sum_to_one():
    res = _make_sim().run(n_sims=3000, seed=7)
    assert sum(res["champion"].values()) == pytest.approx(1.0, abs=1e-9)
    assert sum(res["runnerup"].values()) == pytest.approx(1.0, abs=1e-9)


def test_reach_final_decomposition():
    res = _make_sim().run(n_sims=3000, seed=7)
    # identidad de conteo: campeón + subcampeón == llega a la final (exacto)
    for team in res["reach_final"]:
        assert res["champion"].get(team, 0.0) + res["runnerup"].get(team, 0.0) == \
            pytest.approx(res["reach_final"][team], abs=1e-9)
    assert sum(res["reach_final"].values()) == pytest.approx(2.0, abs=1e-9)


def test_reproducible_seed():
    a = _make_sim().run(n_sims=2000, seed=42)
    b = _make_sim().run(n_sims=2000, seed=42)
    assert a["champion"] == b["champion"]
    assert a["runnerup"] == b["runnerup"]


# =========================================================================== #
# Tier 4 — condicionamiento en resultados parciales                           #
# =========================================================================== #
def test_eliminated_team_zero_champion():
    # Grupo A totalmente jugado: A1>A2>A3>A4. A4 termina 4° -> NUNCA clasifica
    # (solo 1°/2° + mejores terceros) -> P(campeón)=P(subcampeón)=0 EXACTO.
    played_A = [
        ("A1", "A2", 1, 0), ("A1", "A3", 1, 0), ("A1", "A4", 1, 0),
        ("A2", "A3", 1, 0), ("A2", "A4", 1, 0), ("A3", "A4", 1, 0),
    ]
    res = _make_sim(played=played_A, skip_groups=("A",)).run(n_sims=3000, seed=3)
    assert res["champion"].get("A4", 0.0) == 0.0
    assert res["runnerup"].get("A4", 0.0) == 0.0
    # sanity: el ganador del grupo (A1) sí puede ser campeón con prob > 0
    assert res["champion"].get("A1", 0.0) > 0.0
