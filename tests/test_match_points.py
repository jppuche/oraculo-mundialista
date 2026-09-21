"""Reproduce VERBATIM las 12 celdas de docs/prode_rules.md seccion 1.3/1.4.

Esas celdas SON los ejemplos oficiales de la pagina de reglas del prode (no incluida
en el repo publico), asi que esto valida
match_points contra la fuente, no solo contra el doc derivado. Criterio falsable
del doc: cualquier celda no reproducida = bug.
"""
import pytest

from wcprode.scoring import match_points, outcome

# seccion 1.3 — resultado real Argentina 3-1 Francia (home=Argentina)
GROUP_CASES = [
    ((3, 1), 12),  # marcador exacto (A)
    ((3, 0), 7),   # ganador (5) + goles de Argentina (2)
    ((2, 1), 7),   # ganador (5) + goles de Francia (2)
    ((2, 0), 5),   # solo ganador (5)
    ((0, 1), 2),   # ganador equivocado; goles de Francia (2)
    ((3, 3), 2),   # resultado equivocado (empate); goles de Argentina (2)
    ((0, 2), 0),   # nada
    ((0, 0), 0),   # nada
]


@pytest.mark.parametrize("pred,expected", GROUP_CASES)
def test_group_scoring_cells(pred, expected):
    assert match_points(pred, (3, 1)) == expected


# seccion 1.4 — Argentina 1-1 Francia, Argentina gana por penales (pen_actual="H")
KO_CASES = [
    ((1, 1), "H", 17),  # exacto (12) + ganador penales (5)
    ((1, 1), "A", 12),  # exacto (12); penales mal (0)
    ((0, 0), "H", 10),  # empate correcto (5) + penales (5)
    ((0, 0), "A", 5),   # empate correcto (5); penales mal (0)
]


@pytest.mark.parametrize("pred,pen_pred,expected", KO_CASES)
def test_knockout_penalty_cells(pred, pen_pred, expected):
    assert match_points(pred, (1, 1), pen_pred=pen_pred, pen_actual="H") == expected


def test_penalty_bonus_only_on_draw_prediction():
    # Una prediccion no-empate nunca recibe el +5 de penales: el puntaje es el
    # mismo con o sin datos de penales (el +2 de un-equipo, si lo hay, es aparte).
    assert (match_points((2, 1), (1, 1), pen_pred="H", pen_actual="H")
            == match_points((2, 1), (1, 1)) == 2)


def test_penalty_ignored_if_no_shootout():
    # Empate predicho y acertado, pero el partido no fue a penales (pen_actual None).
    assert match_points((1, 1), (1, 1), pen_pred="H", pen_actual=None) == 12


def test_outcome_helper():
    assert outcome(2, 0) == "H"
    assert outcome(0, 2) == "A"
    assert outcome(1, 1) == "D"
