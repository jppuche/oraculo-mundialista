"""ingest.py — descarga pineada + verificacion de hash + gate -> DataFrame.

Reproducible: re-baja los CSV del commit SHA registrado en data/raw/sources.lock.json,
verifica el SHA256 y pasa por el gate de data_validation. CSV/JSON-only.

Como los fixtures del WC2026 viven en el mismo martj42 (filas con score NA), NO hay
join entre dos fuentes -> sin tabla de normalizacion de nombres ni riesgo de join roto.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import pandas as pd

from . import data_validation as dv

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_RAW = REPO_ROOT / "data" / "raw"
LOCK = DATA_RAW / "sources.lock.json"
SOURCE = "martj42_international_results"


def read_csv_raw(path: str | Path) -> pd.DataFrame:
    """Lee TODO como string crudo: el gate controla el casting, no pandas.

    keep_default_na=False + na_filter=False evitan que pandas convierta 'NA' a NaN
    antes de que el gate decida (el 'NA' de martj42 = partido futuro, no dato sucio).
    """
    dv.assert_safe_format(path)
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_filter=False)


def download_pinned(name: str, *, lock_path: str | Path = LOCK,
                    dest_dir: str | Path = DATA_RAW) -> Path:
    """Re-baja un archivo desde el commit SHA del lock (idempotente) y verifica hash."""
    lock = dv.load_lock(lock_path)
    base = lock[SOURCE]["raw_base_url"]
    dest = Path(dest_dir) / name
    dv.assert_safe_format(dest)
    urllib.request.urlretrieve(f"{base}/{name}", dest)
    dv.verify_hash(dest, SOURCE, name, lock_path)
    return dest


def load_results(*, path: str | Path | None = None,
                 lock_path: str | Path = LOCK,
                 verify: bool = True) -> tuple[pd.DataFrame, dv.Report]:
    """results.csv -> (df_validado, Report). Verifica hash contra el lock por defecto."""
    path = Path(path) if path else DATA_RAW / "results.csv"
    if verify:
        dv.verify_hash(path, SOURCE, "results.csv", lock_path)
    return dv.validate_results(read_csv_raw(path))


def load_shootouts(*, path: str | Path | None = None,
                   lock_path: str | Path = LOCK,
                   verify: bool = True) -> pd.DataFrame:
    """shootouts.csv -> DataFrame (date, home_team, away_team, winner, first_shooter).

    Tandas de penales de martj42 (mismo pin que results.csv). El scorer las usa para
    acreditar el +5 de penales a un pick de empate que fue a la tanda (prode_rules §1.4).
    NO pasa por validate_results (otro esquema); se verifica hash contra el lock + formato.
    """
    path = Path(path) if path else DATA_RAW / "shootouts.csv"
    if verify:
        dv.verify_hash(path, SOURCE, "shootouts.csv", lock_path)
    return read_csv_raw(path)


def wc2026_group_fixtures(results_df: pd.DataFrame) -> pd.DataFrame:
    """Extrae los 72 partidos de fase de grupos del WC2026 (no jugados) desde results."""
    mask = (
        (results_df["tournament"] == "FIFA World Cup")
        & (results_df["date"] >= "2026-06-11")
        & (results_df["date"] <= "2026-06-27")
        & (~results_df["played"])
    )
    return results_df.loc[mask].reset_index(drop=True)


def wc2026_knockout_fixtures(results_df: pd.DataFrame, *,
                             dfrom: str = "2026-06-28",
                             dto: str = "2026-07-19") -> pd.DataFrame:
    """Extrae los fixtures de eliminatorias del WC2026 (no jugados) desde results.

    KO arranca el 2026-06-28 (Round of 32). Identico a wc2026_group_fixtures pero
    en la ventana de eliminatorias: los cruces aparecen en martj42 a medida que se
    definen (NA-NA hasta jugarse). El resto del pipeline es el mismo; lo unico que
    cambia rio abajo es optimize_match(knockout=True) (draw-option-value por penales).
    Filtra por ventana de fechas para aislar una ronda (R32: 06-28..07-03).
    """
    mask = (
        (results_df["tournament"] == "FIFA World Cup")
        & (results_df["date"] >= dfrom)
        & (results_df["date"] <= dto)
        & (~results_df["played"])
    )
    return results_df.loc[mask].reset_index(drop=True)


def played_results(results_df: pd.DataFrame) -> pd.DataFrame:
    """Subset de partidos efectivamente jugados (insumo del fit)."""
    return results_df.loc[results_df["played"]].reset_index(drop=True)
