---
doc_type: guide
purpose: Threat model + defensas para la ingesta de datos externos del predictor (martj42 results, fixtures aggregators). Guía la implementación del gate de validación (data_validation.py) en Fase 2.
audience: [agents, humans]
when_to_use:
  - Antes de escribir el pipeline de ingesta (Fase 2) — implementar data_validation.py desde el esbozo de acá
  - Antes de conectar cualquier fuente de datos nueva
  - Antes de que un agente (overlay Fase 6) consuma campos de texto provenientes de la data
last_verified: 2026-06-05
maintenance: living
related_docs:
  - data_sources.md
---

# Data Security — Threat Model + Ingestion Gate

**Revisión de seguridad pre-pipeline (agente sec-data, 2026-06-05). Encuadre verificado por el orquestador (DIRECT_FETCH, §5).** Define la postura de seguridad ANTES de ingerir un byte.

## TL;DR
- **El riesgo dominante NO es prompt injection.** En el camino de cómputo (pandas → Dixon-Coles/Elo → grilla `P(h,a)` → optimizer, **sin LLM**) no hay modelo que instruir; los vectores reales son **data integrity, formula injection de CSV y data poisoning**. La prompt injection clásica aplica a **un solo nodo**: el overlay (Fase 6, agentes).
- **martj42 VERIFICADO seguro** (CC0 + CSV plano, DIRECT_FETCH 2026-06-05). Único requisito duro: **pinear a commit SHA** (commits diarios = superficie de poisoning incremental).
- **Kaggle: rechazar pickle/.db** (deserialización = RCE, no solo data sucia). **CSV/JSON-only.**
- **fixturedownload.com: términos no verificables** (403 a WebFetch) → hash propio + cross-val vs oráculo FIFA (104 partidos / 48 equipos / 12 grupos).
- **Defensas P0 (baratas, obligatorias):** hash-pin + schema/range validation + política CSV-only. Esbozo de `data_validation.py` en §4, listo para Fase 2.

## 1. Encuadre afinado
La preocupación inicial ("prompt injection en la data") está **mal dirigida para el ~80% del flujo**:
- **Capas 1-2 (cómputo, sin LLM):** una celda `"England; ignore previous instructions"` es solo un string que pandas nunca interpreta como instrucción. Prompt injection **no aplica**. Los vectores son data integrity + formula injection + poisoning.
- **Capa 3 (overlay Fase 6, agentes) y logs leídos por agentes:** acá los campos de texto (`home_team`, `city`, `tournament`) SÍ pueden cruzar a un prompt LLM. Es el **único** nodo con prompt injection real, y se blinda con **un** control.

Gastar el grueso del esfuerzo en "injection" sería pólvora mal puesta. El cuello de botella es **data integrity en la ingesta** + **un único choke point LLM**.

## 2. Threat model map

```
[Fuente]→[descarga/pin]→[pandas read_csv]→[fit DC/Poisson/Elo]→[grilla P(h,a)]→[optimizer]→[overlay Fase 6 AGENTES]→[tracking Fase 7]
```

| Nodo | ¿Toca LLM? | Vector | Severidad |
|---|---|---|---|
| Fuente martj42 | No | Supply chain: poisoning vía commit diario; license drift | Media |
| Fuente fixtures (aggregator) | No | Supply chain: términos no verificables; SQLite/pickle si Kaggle | Media |
| Descarga / pin | No | Sin pin → fetch no-determinístico, archivo cambia entre runs | Media |
| pandas read_csv | No | Data integrity: filas malformadas, scores fuera de rango; formula-injection latente (ejecuta si se abre en Excel) | Media |
| fit DC/Poisson/Elo | No | Poisoning: fila alterada sesga parámetros; mal-uso de `neutral`; join roto por nombres | Media |
| grilla P(h,a) | No | Propagación de fit corrupto. Sin vector propio | Baja |
| optimizer argmax | No | Ninguno. **Prompt injection NO aplica** | Baja |
| **overlay Fase 6 (AGENTES)** | **Sí** | **Prompt injection real** si campos de texto cruzan crudos al prompt | **Alta** |
| tracking Fase 7 | Depende | Injection vía log si un agente lee resultados con texto crudo; Baja si solo computa sobre números | Media |
| CSV abierto en Excel por humano | No | Formula injection si una celda futura abre con `= + - @` | Media |

**Un solo nodo Alta** (overlay con LLM). El resto se cubre con validación determinística.

## 3. Defensas priorizadas (por ROI)

| Defensa | Cubre | Costo | Prioridad |
|---|---|---|---|
| Hash-pin de fuentes (SHA256 del CSV + pin a commit SHA de martj42, NO `master`) | poisoning, drift, no-determinismo | Bajo | **P0** |
| Schema + range validation al ingerir (9 cols, dtypes, score entero ∈ [0,30], fecha ISO, neutral ∈ {TRUE,FALSE}) | data integrity | Bajo | **P0** |
| Política de formato: **CSV/JSON-only, prohibido pickle/.db de terceros** | deserialización/RCE (Kaggle) | Trivial | **P0** |
| Tratar campos de texto como `untrusted` en capa 3 (no interpolar `home_team`/`city`/`tournament` crudos en prompts; usar IDs/enums o wrappear en `<untrusted-content>` + signal-scan) | prompt injection (único nodo Alto) | Medio | **P1** |
| Normalización NFKC + whitelist Latin (bloquea homoglyph cirílico/griego; **preserva acentos legítimos** tipo Lwów, Cernăuţi) | identity split / homoglyph | Bajo | **P1** |
| Defang formula-injection (prefijar `'` a celdas que abran con `= + - @`) al re-exportar cualquier CSV que un humano pueda abrir | formula injection en Excel | Bajo | **P1** |
| Cross-val fixtures vs oráculo FIFA (assert 104 / 48 / 12×4, ventana 11-Jun/19-Jul) | fixtures corruptos/incompletos | Bajo | **P1** |
| Tabla de normalización de nombres martj42↔fixtures (48 selecciones, join sin colisión) | join roto / doble conteo | Medio | **P1** |
| Fit robusto a outliers (trimming/cap de goles) | poisoning residual post-pin | Medio | **P2** |
| Quarantine + diff en re-fetch (si el SHA cambia, no auto-ingerir: diff antes de re-fit) | poisoning en updates incrementales | Medio | **P2** |

**Proporcionalidad:** las P0 son baratas y cubren los vectores reales del cómputo. La defensa de prompt injection es **una sola** y aplica a **un solo nodo** — no hace falta sanitizar toda la ingesta contra injection.

## 4. `data_validation.py` (esbozo para Fase 2)
Gate de ingesta reutilizable. Read-once, fail-loud. **No ejecuta nada de la data**: valida, sanitiza, reporta. Fila inválida se descarta con motivo (un CSV de 49k no muere por una fila futura mala); columna inesperada **sí** aborta (cambio de schema = revisar a mano).

> **PROTOTIPADO 2026-06-05** en `wcprode/data_validation.py` (corrió limpio: `rows_ok=49378, dropped=0`) y conservado en el build actual. Los cuatro ajustes de abajo, basados en evidencia del CSV real, son parte del gate vigente:
> 1. **`MAX_GOALS` 30 → 31.** El récord real (Australia 31-0 American Samoa, 2001) era descartado por la cota 30. La cota defensiva real es contra órdenes de magnitud (poisoning), no contra el récord legítimo.
> 2. **Whitelist por SCRIPT, no por rango.** El regex `À-ɏ` descartaba latinos legítimos (azerí `Gəncə`, vietnamita `Việt Trì`, okina tongano `‘Atele`, en-dash de la Finalissima). Se reemplazó por `name_is_safe()`: permite letras cuyo nombre unicode empieza con `LATIN` + puntuación tipográfica observada; sigue bloqueando cirílico/griego (homoglyph). 23 falsos positivos → 0.
> 3. **`played` / `future` split.** martj42 trae los 72 fixtures del WC2026 con `score=NA`. El gate NO los descarta (no son corrupción): los marca `played=False`. Sólo se descarta score presente-pero-inválido.
> 4. **`verify_hash` lee el lock** (`data/raw/sources.lock.json`), única fuente de verdad del hash — no se hardcodea (evita sync-by-discipline). Se agregó `assert_safe_format` (lista negra pickle/.db/.parquet/... en código).

```python
"""data_validation.py — gate de ingesta. Read-once, fail-loud."""
from __future__ import annotations
import hashlib, re, unicodedata
from dataclasses import dataclass, field
import pandas as pd

EXPECTED_SHA256 = {}   # {"results.csv": "<hash tras pin a commit SHA>"}

def verify_hash(path: str, name: str) -> str:
    digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
    exp = EXPECTED_SHA256.get(name)
    if exp and digest != exp:
        raise IntegrityError(f"{name}: SHA mismatch {digest[:12]} != {exp[:12]}. Re-fetch del commit pineado.")
    return digest   # sin expected aún → devolver para registrar

RESULTS_SCHEMA = ["date","home_team","away_team","home_score",
                  "away_score","tournament","city","country","neutral"]
MAX_GOALS = 30
MIN_DATE, MAX_DATE = "1872-01-01", "2027-12-31"
# Latin + acentos legítimos (Lwów, Cernăuţi); excluye cirílico/griego (homoglyph)
NAME_OK = re.compile(r"^[A-Za-zÀ-ɏ0-9 .,'()\-/&]+$")
FORMULA_LEAD = ("=", "+", "-", "@", "\t", "\r")

class IntegrityError(Exception): ...
class SchemaError(Exception): ...

@dataclass
class Report:
    rows_in: int = 0; rows_ok: int = 0
    dropped: list = field(default_factory=list)
    defanged: list = field(default_factory=list)

def _nfkc(s) -> str:
    return unicodedata.normalize("NFKC", str(s)).strip()

def _defang(cell: str, rep: Report, idx: int, col: str) -> str:
    s = str(cell)
    if s and s[0] in FORMULA_LEAD:
        rep.defanged.append((idx, col)); return "'" + s
    return s

def validate_results(df: pd.DataFrame) -> tuple[pd.DataFrame, Report]:
    rep = Report(rows_in=len(df))
    if list(df.columns) != RESULTS_SCHEMA:
        raise SchemaError(f"cols inesperadas: {list(df.columns)}")
    keep = []
    for idx, r in df.iterrows():
        try:
            for c in ("home_score", "away_score"):
                v = r[c]
                if pd.isna(v) or float(v) != int(v) or not (0 <= int(v) <= MAX_GOALS):
                    raise ValueError(f"{c}={v!r} fuera de rango")
            d = pd.to_datetime(r["date"], format="%Y-%m-%d", errors="raise")
            if not (MIN_DATE <= d.strftime("%Y-%m-%d") <= MAX_DATE):
                raise ValueError(f"fecha {r['date']} fuera de ventana")
            if str(r["neutral"]).upper() not in ("TRUE", "FALSE"):
                raise ValueError(f"neutral={r['neutral']!r} no booleano")
            for c in ("home_team","away_team","tournament","city","country"):
                val = _nfkc(r[c])
                if not NAME_OK.match(val):
                    raise ValueError(f"{c}={r[c]!r} fuera de charset (homoglyph?)")
                df.at[idx, c] = _defang(val, rep, idx, c)
            keep.append(idx)
        except (ValueError, TypeError) as e:
            rep.dropped.append((idx, str(e)))
    rep.rows_ok = len(keep)
    return df.loc[keep].reset_index(drop=True), rep

WC2026 = dict(matches=104, teams=48, groups=12, start="2026-06-11", end="2026-07-19")

def validate_fixtures(df: pd.DataFrame) -> None:
    assert len(df) == WC2026["matches"], f"esperaba 104, hay {len(df)}"
    teams = pd.unique(df[["home_team", "away_team"]].values.ravel())
    assert len(teams) == WC2026["teams"], f"esperaba 48 equipos, hay {len(teams)}"
    # + ventana de fechas + defang/whitelist igual que results

def to_llm_safe(name: str) -> str:
    """Único borde hacia el riesgo de injection (capa 3). El caller envuelve el
    resultado en <untrusted-content>. Texto de NOTICIAS (no del CSV) nunca pasa el whitelist."""
    clean = _nfkc(name)
    return clean if NAME_OK.match(clean) else "[REDACTED_UNSAFE_FIELD]"
```

**Notas:** (a) `MAX_GOALS=30` es cota defensiva contra scores inflados (record real ~31); (b) `neutral` tiene semántica no-trivial (un partido puede ser `neutral=FALSE` por contexto histórico) — el **fit** debe aplicarlo con la semántica del README de martj42, mal-usarlo invierte la ventaja de localía y mueve `P(h,a)` materialmente; (c) los nombres son ACTUALES (no históricos) → la tabla de normalización martj42↔fixtures es necesaria para el join de las 48 selecciones.

## 5. Verification Log (orchestrator DIRECT_FETCH, 2026-06-05)

| # | Claim | Provenance | Verdict | Source |
|---|-------|------------|---------|--------|
| 1 | martj42 LICENSE = CC0 1.0 Universal (public domain, uso/redistribución libre) | DIRECT_FETCH | CONFIRMED | [LICENSE](https://raw.githubusercontent.com/martj42/international_results/master/LICENSE) |
| 2 | results.csv = 9 cols declaradas, scores enteros no-negativos, ISO dates, sin formula-injection en muestra | DIRECT_FETCH | CONFIRMED (head) | [results.csv](https://raw.githubusercontent.com/martj42/international_results/master/results.csv) |
| 3 | fixturedownload.com términos/licencia | DIRECT_FETCH | UNVERIFIABLE (403 bot-block) | [fixturedownload](https://fixturedownload.com/results/fifa-world-cup-2026) |
| 4 | martj42 credencial comunitaria (los 176★ de GitHub engañan; la adopción vive en Kaggle) | DIRECT_FETCH (Playwright/browser) | CONFIRMED | [Kaggle](https://www.kaggle.com/datasets/martj42/international-football-results-from-1872-to-2017): **2539 votos, Usability 10.00, 382 notebooks, 40 discusiones, CC0, autor Mart Jürisoo, updated ~21h** |

**No verificado (pendiente del validador):** las 49k filas completas (el head es de 1872; un poisoning estaría en filas recientes). La pasada exhaustiva es `data_validation.py` sobre el archivo entero en Fase 2, no un fetch.

## 6. Veredicto
**Ingesta SEGURA con las P0 mínimas** (hash-pin a commit SHA + schema/range validation + CSV/JSON-only). **Sin red flag para descartar martj42** (CC0 verificado, CSV plano, **credencial comunitaria ALTA verificada por DIRECT_FETCH**: 2539 votos Kaggle + Usability 10.00 + 382 notebooks + maintainer Mart Jürisoo identificable. Los 176★ de GitHub subestiman — la adopción de este dataset vive en Kaggle, no en GitHub). **Pin a SHA es obligatorio, no opcional** — sin él, el fit es no-determinístico y la superficie de poisoning queda abierta.

**Red flags condicionales:**
- **fixturedownload:** términos UNVERIFIABLE → no pinear sin hash propio + cross-val vs FIFA. Si se necesita certeza legal de redistribución (portfolio público), leer sus ToS antes de publicar derivados.
- **Kaggle:** rechazar cualquier dataset con SQLite/pickle (único vector de severidad alta: deserialización = RCE). CSV/JSON pasa el mismo gate que martj42.
