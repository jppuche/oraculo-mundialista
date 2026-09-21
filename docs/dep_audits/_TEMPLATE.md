# Dependency Audit — `<pkg>`

> Copy this file to `docs/dep_audits/<pkg>.md` (lowercase, PyPI-normalized name:
> hyphens not underscores). Its mere existence makes the `dependency-gate` hook
> ALLOW `<pkg>`, so fill it honestly — an empty audit doc is a bypass, not an audit.

- **Package:** `<pkg>` (PyPI name)
- **Version pinned:** `<x.y.z>` (the version actually installed)
- **Date:** `YYYY-MM-DD`
- **Auditor:** `<who>`

## Maintainer
- Who maintains it (org / individual)? Single-maintainer risk? Last release date,
  release cadence. Bus factor.

## Real adoption (NOT just GitHub stars)
- Downloads/month (pypistats). Stars are vanity; downloads + dependents are signal.
- Who else depends on it (reverse deps)? Years in existence.

## Transitive dependencies — the actual attack surface
- List transitive deps that ship **native binaries** (`.so`/`.dll`/`.dylib`,
  ctypes/cffi loads) or do **eager work at import time** (network, subprocess,
  reading env vars / credentials, launching browsers).
- For each: is the dangerous path lazy (only on an unused feature) or eager
  (runs on `import <pkg>`)? Eager = present in-process from the first import.
- Hard deps vs optional extras (`[project.dependencies]` vs
  `[project.optional-dependencies]`). Can the heavy surface be avoided?

## License
- SPDX identifier. Compatible with this project's use? Any copyleft concerns.

## Security scan (if run)
- `pip-audit` CVEs, guarddog / malware scan results. Persist the raw output
  (don't leave it in an ephemeral gitignored dir — the 2026-06-05 lesson #5).

## Verdict
- `APPROVED` / `APPROVED WITH CONDITIONS` / `REJECTED` — `YYYY-MM-DD`
- One-line rationale + any conditions (pin version, deny extras, sandbox, etc.).
- `falsified_by:` one sentence — what evidence would flip this verdict.
