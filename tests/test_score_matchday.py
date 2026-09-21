"""Tests del CABLEADO de score_matchday (NO oráculo) — review R16/QF, fix M1.

`match_points` en sí está oraculizado en test_match_points.py (celdas de prode_rules §1.3/1.4).
Acá validamos SOLO el wiring nuevo que conecta el +5 de penales al scorer:
  - parse_predictions captura las probabilidades 1X2 (para derivar el favorito de la tanda),
  - parse_actuals captura el ganador de la tanda de la Nota "pen: X",
  - penalty_pred_actual deriva (pen_pred, pen_actual) con el criterio "solo un pick de empate
    accede al +5, con el favorito como pen_pred".
Antes de este fix el scorer llamaba match_points sin pen_pred/pen_actual → un pick de empate a
penales quedaba mal scoreado (asimetría vs el EV del optimizer, que sí cobra el +5).
"""
import importlib.util
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

_spec = importlib.util.spec_from_file_location(
    "score_matchday", REPO / "scripts" / "score_matchday.py")
sm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sm)

from wcprode.scoring import match_points  # noqa: E402


def _write(tmp_path, name, text):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


# --- parse_predictions: probabilidades 1X2 -------------------------------------------------
def test_parse_predictions_captura_probs(tmp_path):
    txt = ("2026-07-11        Norway 1-2 England        EV=4.21  "
           "[H 0.34 D 0.13 A 0.52]  modal 1-2 (P=0.12)  alt: 0-1, 0-2  (neutral)\n")
    preds = sm.parse_predictions(_write(tmp_path, "pred.txt", txt))
    d = preds[("Norway", "England")]
    assert d["pred_h"] == 1 and d["pred_a"] == 2
    assert d["p_home"] == 0.34 and d["p_away"] == 0.52


def test_parse_predictions_sin_probs_queda_none(tmp_path):
    # Retrocompat: una línea sin bloque [H D A] no rompe; probs quedan None.
    txt = "2026-06-15        Argentina 2-0 Panama        EV=6.10\n"
    preds = sm.parse_predictions(_write(tmp_path, "pred.txt", txt))
    d = preds[("Argentina", "Panama")]
    assert d["p_home"] is None and d["p_away"] is None


# --- parse_actuals: ganador de la tanda ----------------------------------------------------
_MD_HEAD = ("## Resultados\n\n"
            "| Fecha | Grupo | Local | GL | GV | Visitante | Nota |\n"
            "|-------|-------|-------|----|----|-----------|------|\n")


def test_parse_actuals_captura_pen_winner(tmp_path):
    md = _MD_HEAD + "| 07-07 | B | Switzerland | 0 | 0 | Colombia | pen: Switzerland |\n"
    rows = sm.parse_actuals(_write(tmp_path, "act.md", md))
    assert rows[0]["pen_winner"] == "Switzerland"


def test_parse_actuals_sin_pen_queda_vacio(tmp_path):
    md = _MD_HEAD + "| 07-04 | B | Canada | 0 | 3 | Morocco | |\n"
    rows = sm.parse_actuals(_write(tmp_path, "act.md", md))
    assert rows[0]["pen_winner"] == ""


# --- penalty_pred_actual + integración con match_points ------------------------------------
def test_pen_empate_acierta_ganador_cobra_5():
    # pick empate 0-0, favorito = home (0.55 > 0.25), ganó la tanda el home -> +5.
    pp, pa = sm.penalty_pred_actual(0, 0, 0.55, 0.25, "Spain", "Spain", "France")
    assert (pp, pa) == ("H", "H")
    # real 1-1 (empate no exacto) + tanda al favorito acertado = 5 (resultado) + 5 (pen).
    assert match_points((0, 0), (1, 1), pen_pred=pp, pen_actual=pa) == 10


def test_pen_empate_erra_ganador_no_cobra_5():
    pp, pa = sm.penalty_pred_actual(0, 0, 0.55, 0.25, "France", "Spain", "France")
    assert (pp, pa) == ("H", "A")            # predijimos el favorito, ganó el otro
    assert match_points((0, 0), (1, 1), pen_pred=pp, pen_actual=pa) == 5


def test_pen_pick_no_empate_no_accede_al_5():
    # Caso real Switzerland 0-1 Colombia: pick no-empate; aunque hubo tanda, pen_* = None.
    pp, pa = sm.penalty_pred_actual(0, 1, 0.36, 0.49, "Switzerland", "Switzerland", "Colombia")
    assert (pp, pa) == (None, None)
    assert match_points((0, 1), (0, 0), pen_pred=pp, pen_actual=pa) == 2


def test_pen_empate_pero_no_fue_a_penales():
    # pick empate pero el partido NO fue a la tanda (pen_winner vacío) -> pen_actual None.
    pp, pa = sm.penalty_pred_actual(1, 1, 0.55, 0.25, "", "Spain", "France")
    assert pp == "H" and pa is None
    assert match_points((1, 1), (2, 0), pen_pred=pp, pen_actual=pa) == 0
