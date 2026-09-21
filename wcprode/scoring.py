"""scoring.py — funcion de puntaje del prode, transcrita VERBATIM de
docs/prode_rules.md seccion 2. NO modificar sin actualizar el doc fuente.

Validacion: las 12 celdas de prode_rules.md seccion 1.3/1.4 deben reproducirse
exactamente (ver tests/test_match_points.py). Esas celdas SON los ejemplos
oficiales de la pagina de reglas del prode (no incluida en el repo publico), asi
que esto se valida contra la fuente.
"""
from __future__ import annotations


def outcome(h: int, a: int) -> str:
    return "H" if h > a else ("A" if a > h else "D")


def match_points(pred, actual, pen_pred=None, pen_actual=None) -> int:
    """
    pred, actual: (home_goals, away_goals) over 90/120 min (penalties excluded).
    pen_pred:   team you predicted to win the shootout ("H"/"A"), or None. Only
                meaningful (and only offered by the platform) when pred is a draw.
    pen_actual: team that actually won the shootout ("H"/"A"), or None if the match
                did not go to penalties.
    """
    ph, pa = pred
    ah, aa = actual

    if ph == ah and pa == aa:
        pts = 12                                   # A: exact scoreline
    else:
        pts = 0
        if outcome(ph, pa) == outcome(ah, aa):
            pts += 5                               # B: correct outcome (non-exact)
        if ph == ah or pa == aa:                   # C: one team's goal count
            pts += 2                               # (in non-exact branch, at most one can match)

    # Penalty bonus: knockouts only, requires a DRAW prediction AND the match
    # actually went to penalties (i.e., real result was a draw).
    if ph == pa and pen_pred is not None:
        if ah == aa and pen_actual is not None and pen_pred == pen_actual:
            pts += 5

    return pts
