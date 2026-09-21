"""Tests del gate de ingesta: separacion played/future, descarte de corrupcion,
defensa homoglyph (latino OK / cirilico rechazado), politica de formato y hash-pin.
"""
import hashlib
import json

import pandas as pd
import pytest

from wcprode import data_validation as dv

COLS = dv.RESULTS_SCHEMA


def _row(date="2026-01-01", h="England", a="Brazil", hs="2", as_="1",
         t="Friendly", c="London", co="England", n="FALSE"):
    return {"date": date, "home_team": h, "away_team": a, "home_score": hs,
            "away_score": as_, "tournament": t, "city": c, "country": co, "neutral": n}


def _df(rows):
    return pd.DataFrame(rows, columns=COLS)


def test_good_row_passes_played():
    out, rep = dv.validate_results(_df([_row()]))
    assert rep.rows_ok == 1 and rep.rows_played == 1 and rep.rows_future == 0
    assert bool(out.loc[0, "played"]) is True
    assert out.loc[0, "neutral"] == False  # noqa: E712  (numpy bool)


def test_na_score_is_future_not_dropped():
    out, rep = dv.validate_results(_df([_row(hs="NA", as_="NA")]))
    assert rep.rows_ok == 1 and rep.rows_future == 1 and rep.rows_played == 0
    assert not rep.dropped


def test_corrupt_scores_dropped():
    rows = [_row(hs="99"), _row(hs="x"), _row(hs="2.5"), _row(hs="-1")]
    out, rep = dv.validate_results(_df(rows))
    assert rep.rows_ok == 0 and len(rep.dropped) == 4


def test_bad_date_and_neutral_dropped():
    rows = [_row(date="2026-13-40"), _row(n="maybe")]
    _, rep = dv.validate_results(_df(rows))
    assert len(rep.dropped) == 2


def test_cyrillic_homoglyph_dropped_latin_kept():
    cyrillic = _row(h="Аrgentina")          # А cirilica
    latin = _row(c="Gəncə")            # Gəncə (azeri, latino legitimo)
    _, rep = dv.validate_results(_df([cyrillic, latin]))
    assert len(rep.dropped) == 1 and rep.rows_ok == 1


def test_formula_lead_dropped_by_charset():
    # '=' no es charset valido en un nombre -> la defensa primaria lo DROPEA
    # (con la whitelist latina, '=','+','@' nunca llegan al defang).
    _, rep = dv.validate_results(_df([_row(c="=cmd|calc")]))
    assert len(rep.dropped) == 1 and not rep.defanged


def test_hyphen_lead_is_defanged():
    # '-' es el unico formula-lead que pasa el charset -> ese SI se defangea.
    out, rep = dv.validate_results(_df([_row(c="-Foo")]))
    assert rep.rows_ok == 1 and len(rep.defanged) == 1
    assert out.loc[0, "city"].startswith("'-")


def test_unexpected_column_aborts():
    df = _df([_row()]).drop(columns=["city"])
    with pytest.raises(dv.SchemaError):
        dv.validate_results(df)


def test_format_policy():
    with pytest.raises(dv.FormatError):
        dv.assert_safe_format("model.pkl")
    with pytest.raises(dv.FormatError):
        dv.assert_safe_format("data.sqlite")
    dv.assert_safe_format("results.csv")   # no levanta


def test_name_is_safe():
    assert dv.name_is_safe("Bosnia and Herzegovina")
    assert dv.name_is_safe("Curaçao")
    assert dv.name_is_safe("Gəncə")
    assert not dv.name_is_safe("Аrgentina")   # cirilica
    assert not dv.name_is_safe("Εllas")       # griega Ε


def test_verify_hash_roundtrip_and_tamper(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text("a,b\n1,2\n", encoding="utf-8")
    digest = hashlib.sha256(f.read_bytes()).hexdigest()
    lock = tmp_path / "lock.json"
    lock.write_text(json.dumps({"src": {"files": {"x.csv": {"sha256": digest}}}}), encoding="utf-8")

    assert dv.verify_hash(f, "src", "x.csv", lock) == digest

    f.write_text("a,b\n9,9\n", encoding="utf-8")   # tamper
    with pytest.raises(dv.IntegrityError):
        dv.verify_hash(f, "src", "x.csv", lock)
