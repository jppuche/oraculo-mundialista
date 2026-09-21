"""wcprode — World Cup 2026 prode predictor.

Layers:
  1. data_validation : gate de ingesta (read-once, fail-loud). NO ejecuta data.
  2. ingest          : descarga pineada al commit SHA + hash + gate -> DataFrame.
  3. engine          : Dixon-Coles + time-decay (in-house) -> grilla P(h,a).
  4. scoring         : match_points VERBATIM (docs/prode_rules.md seccion 2).
  5. optimizer       : argmax E[match_points] sobre la grilla de marcadores.

Metrica de decision = expected points bajo match_points (RPS = diagnostico).
"""

__version__ = "0.0.1"
