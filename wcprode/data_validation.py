"""data_validation.py — gate de ingesta. Read-once, fail-loud.

NO ejecuta nada de la data: valida, sanitiza, reporta. Implementa el esbozo de
docs/data_security.md seccion 4 con tres refinamientos respecto al borrador:

  1. verify_hash lee el SHA esperado del lock (data/raw/sources.lock.json), que es
     la unica fuente de verdad del hash. No se hardcodea en codigo (evita el
     anti-patron de sincronizar el mismo hash en dos lugares a mano).
  2. validate_results NO descarta los partidos con score ausente ("NA"): martj42
     incluye los fixtures futuros del WC2026 como filas sin resultado. Se marcan
     played=False (fixtures legitimos), no como corrupcion. Solo se descarta la
     corrupcion real (score presente pero no entero / fuera de rango / fecha /
     charset homoglyph).
  3. assert_safe_format hace cumplir la politica CSV/JSON-only en codigo
     (lista negra de pickle/.db/.parquet/... = vectores de deserializacion/RCE).

Threat model completo: docs/data_security.md.
"""
from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import pandas as pd


# --------------------------------------------------------------------------- #
# Excepciones                                                                  #
# --------------------------------------------------------------------------- #
class IntegrityError(Exception):
    """SHA del archivo != lock. Posible poisoning o re-fetch sin pin."""


class SchemaError(Exception):
    """Columnas inesperadas. Cambio de schema upstream: revisar a mano (aborta)."""


class FormatError(Exception):
    """Formato de archivo prohibido (pickle/.db/...). CSV/JSON-only."""


# --------------------------------------------------------------------------- #
# Politica de formato: CSV/JSON-only (defensa contra deserializacion = RCE)    #
# --------------------------------------------------------------------------- #
ALLOWED_SUFFIXES = {".csv", ".json", ".tsv"}
FORBIDDEN_SUFFIXES = {
    ".pkl", ".pickle", ".db", ".sqlite", ".sqlite3", ".parquet",
    ".feather", ".h5", ".hdf5", ".npy", ".npz", ".joblib", ".dill",
}


def assert_safe_format(path: str | Path) -> None:
    """Rechaza formatos deserializables de terceros. CSV/JSON/TSV-only."""
    suf = Path(path).suffix.lower()
    if suf in FORBIDDEN_SUFFIXES:
        raise FormatError(
            f"{path}: formato {suf!r} prohibido (deserializacion = RCE). CSV/JSON-only."
        )
    if suf not in ALLOWED_SUFFIXES:
        raise FormatError(
            f"{path}: formato {suf!r} no permitido. Permitidos: {sorted(ALLOWED_SUFFIXES)}."
        )


# --------------------------------------------------------------------------- #
# Hash / pin (el lock es la fuente de verdad)                                  #
# --------------------------------------------------------------------------- #
def sha256_of(path: str | Path) -> str:
    """SHA256 streaming (no carga el archivo entero en memoria)."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_lock(lock_path: str | Path) -> dict:
    assert_safe_format(lock_path)
    with open(lock_path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def verify_hash(path: str | Path, source: str, name: str, lock_path: str | Path) -> str:
    """Compara SHA256(archivo) contra el lock. Fail-loud. Devuelve el digest."""
    assert_safe_format(path)
    lock = load_lock(lock_path)
    try:
        expected = lock[source]["files"][name]["sha256"]
    except (KeyError, TypeError) as e:
        raise IntegrityError(f"{source}/{name} ausente en {lock_path}: {e}")
    digest = sha256_of(path)
    if digest != expected:
        raise IntegrityError(
            f"{name}: SHA mismatch {digest[:12]} != {expected[:12]}. "
            f"Re-fetch del commit pineado o revisar poisoning (data_security.md P2)."
        )
    return digest


# --------------------------------------------------------------------------- #
# Constantes de validacion (results de martj42)                               #
# --------------------------------------------------------------------------- #
RESULTS_SCHEMA = [
    "date", "home_team", "away_team", "home_score",
    "away_score", "tournament", "city", "country", "neutral",
]
TEXT_COLS = ("home_team", "away_team", "tournament", "city", "country")

MAX_GOALS = 31                       # record real: Australia 31-0 American Samoa (2001)
MIN_DATE, MAX_DATE = "1872-01-01", "2027-12-31"
NA_TOKENS = {"", "NA", "N/A", "NAN", "NONE", "NULL"}
FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")

# Defensa homoglyph por SCRIPT, no por rango enumerado: se permiten letras cuyo
# nombre unicode empieza con "LATIN" (cubre azeri 'ə', vietnamita 'ị', etc. sin
# listar bloques) y se rechaza cirilico/griego/han que imitan latinas. La
# puntuacion tipografica real del dataset (en-dash, okina) va en el set explicito.
_ALLOWED_NONLETTER = set("0123456789 .,'’‘()-–/&")


def _nfkc(s) -> str:
    return unicodedata.normalize("NFKC", str(s)).strip()


@lru_cache(maxsize=8192)
def _char_ok(ch: str) -> bool:
    if ch.isspace() or ch in _ALLOWED_NONLETTER:
        return True
    try:
        return unicodedata.name(ch).startswith("LATIN")
    except ValueError:
        return False  # control char / sin nombre -> rechazar


def name_is_safe(s: str) -> bool:
    """True si s tiene solo letras latinas + puntuacion permitida (anti-homoglyph)."""
    return all(_char_ok(c) for c in s)


def _defang(cell: str, rep: "Report", idx: int, col: str) -> str:
    """Prefija ' a celdas que abririan como formula en Excel (= + - @ tab cr)."""
    if cell and cell[0] in FORMULA_LEAD:
        rep.defanged.append((idx, col))
        return "'" + cell
    return cell


def _parse_score(v):
    """Devuelve (is_present, value_int_or_None).

    is_present=False si el score esta ausente (NA/vacio) -> partido NO jugado
    (fixture futuro legitimo). Lanza ValueError si el score esta presente pero
    es invalido (no entero / fuera de rango) -> corrupcion, se descarta la fila.
    """
    s = str(v).strip()
    if s.upper() in NA_TOKENS or pd.isna(v):
        return False, None
    f = float(s)                      # ValueError si no es numerico
    if f != int(f):
        raise ValueError(f"score no entero: {v!r}")
    iv = int(f)
    if not (0 <= iv <= MAX_GOALS):
        raise ValueError(f"score fuera de rango [0,{MAX_GOALS}]: {iv}")
    return True, iv


# --------------------------------------------------------------------------- #
# Reporte                                                                      #
# --------------------------------------------------------------------------- #
@dataclass
class Report:
    rows_in: int = 0
    rows_ok: int = 0          # filas que pasan el gate (jugadas + futuras validas)
    rows_played: int = 0      # subset con score valido (insumo del fit)
    rows_future: int = 0      # subset con score ausente (fixtures / no jugados)
    dropped: list = field(default_factory=list)   # (idx, motivo) corrupcion real
    defanged: list = field(default_factory=list)  # (idx, col) celdas neutralizadas

    def summary(self) -> str:
        return (
            f"rows_in={self.rows_in} ok={self.rows_ok} "
            f"(played={self.rows_played} future={self.rows_future}) "
            f"dropped={len(self.dropped)} defanged={len(self.defanged)}"
        )


# --------------------------------------------------------------------------- #
# Validacion de results                                                        #
# --------------------------------------------------------------------------- #
def validate_results(df: pd.DataFrame) -> tuple[pd.DataFrame, Report]:
    """Valida schema + integridad + sanitiza el results.csv de martj42.

    Lee mejor con dtype=str (ver ingest.read_csv_raw): el gate controla el casting,
    no pandas. Devuelve (df_limpio, Report). El df de salida agrega columna bool
    `played`; `neutral` queda bool; scores quedan Int64 nullable (NA para futuros).

    Columna inesperada -> SchemaError (aborta). Una fila corrupta NO mata el archivo
    (se descarta con motivo en Report.dropped).
    """
    rep = Report(rows_in=len(df))
    cols = list(df.columns)
    if cols != RESULTS_SCHEMA:
        raise SchemaError(f"cols inesperadas: {cols} != {RESULTS_SCHEMA}")

    rows: list[dict] = []
    for idx, r in df.iterrows():
        try:
            h_present, h_val = _parse_score(r["home_score"])
            a_present, a_val = _parse_score(r["away_score"])

            ds = _nfkc(r["date"])
            pd.to_datetime(ds, format="%Y-%m-%d", errors="raise")  # valida formato
            if not (MIN_DATE <= ds <= MAX_DATE):                   # ISO -> orden lexico
                raise ValueError(f"fecha fuera de ventana: {ds}")

            neutral_raw = _nfkc(r["neutral"]).upper()
            if neutral_raw not in ("TRUE", "FALSE"):
                raise ValueError(f"neutral no booleano: {r['neutral']!r}")

            clean = {"date": ds}
            for c in TEXT_COLS:
                val = _nfkc(r[c])
                if not name_is_safe(val):
                    raise ValueError(f"{c} fuera de charset (homoglyph?): {r[c]!r}")
                clean[c] = _defang(val, rep, idx, c)

            clean["home_score"] = h_val
            clean["away_score"] = a_val
            clean["neutral"] = (neutral_raw == "TRUE")
            clean["played"] = h_present and a_present
            rows.append(clean)
        except (ValueError, TypeError) as e:
            rep.dropped.append((idx, str(e)))

    out = pd.DataFrame(rows, columns=RESULTS_SCHEMA + ["played"])
    out["home_score"] = out["home_score"].astype("Int64")
    out["away_score"] = out["away_score"].astype("Int64")
    out["neutral"] = out["neutral"].astype(bool)
    out["played"] = out["played"].astype(bool)

    rep.rows_ok = len(out)
    rep.rows_played = int(out["played"].sum())
    rep.rows_future = rep.rows_ok - rep.rows_played
    return out, rep


# --------------------------------------------------------------------------- #
# Validacion estructural de fixtures (subset WC2026 desde martj42)             #
# --------------------------------------------------------------------------- #
def validate_wc2026_groups(
    df: pd.DataFrame,
    *,
    expected_matches: int = 72,
    expected_teams: int = 48,
    matches_per_team: int = 3,
    date_min: str = "2026-06-11",
    date_max: str = "2026-06-27",
) -> dict:
    """Cross-validacion de la fase de grupos del WC2026 extraida de martj42.

    martj42 trae los 72 partidos de grupos (12 grupos x 4 equipos x 3 fechas / 2);
    los knockouts (hasta 104) dependen de quien clasifica y NO estan aun. Valida la
    estructura verificable hoy. Lanza AssertionError si algo no cuadra.
    """
    assert len(df) == expected_matches, f"esperaba {expected_matches} partidos, hay {len(df)}"
    teams = pd.unique(df[["home_team", "away_team"]].values.ravel())
    assert len(teams) == expected_teams, f"esperaba {expected_teams} equipos, hay {len(teams)}"

    appearances = pd.concat([df["home_team"], df["away_team"]]).value_counts()
    bad = appearances[appearances != matches_per_team]
    assert bad.empty, f"equipos con != {matches_per_team} partidos de grupo: {bad.to_dict()}"

    dmin, dmax = df["date"].min(), df["date"].max()
    assert date_min <= dmin and dmax <= date_max, f"fechas fuera de ventana: {dmin}..{dmax}"

    return {
        "matches": int(len(df)),
        "teams": int(len(teams)),
        "date_range": (str(dmin), str(dmax)),
    }


# --------------------------------------------------------------------------- #
# Capa 3 (overlay Fase 6): unico borde hacia riesgo de prompt injection        #
# --------------------------------------------------------------------------- #
def to_llm_safe(name: str) -> str:
    """Sanitiza un campo de texto antes de que cruce a un prompt LLM (Fase 6).

    El caller envuelve el resultado en <untrusted-content>. Texto que NO sea de
    martj42 (p.ej. noticias) no deberia pasar por aca crudo: el whitelist lo
    redacta si trae caracteres fuera de charset.
    """
    clean = _nfkc(name)
    return clean if name_is_safe(clean) else "[REDACTED_UNSAFE_FIELD]"
