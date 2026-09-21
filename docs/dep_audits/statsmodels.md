# Dependency Audit — `statsmodels`

> Existence of this file makes the `dependency-gate` hook ALLOW `statsmodels`.
> Existence of this file makes the `dependency-gate` hook ALLOW `statsmodels`.

- **Package:** `statsmodels` (PyPI name)
- **Version pinned:** `0.14.6` (latest; the version that will be installed — wheel cp314 available)
- **Date:** `2026-06-10`
- **Auditor:** T2b builder (Opus), verification via WebFetch DIRECT_FETCH

## Maintainer
- Maintained by the **statsmodels organization** ([github.com/statsmodels/statsmodels](https://github.com/statsmodels/statsmodels)), a community project, NOT a single individual. Listed maintainers on PyPI: bashtage, josefpktd, matthew.brett, rgommers, Skipper.Seabold ([pypi.org/project/statsmodels](https://pypi.org/project/statsmodels/)). Contact: pystatsmodels@googlegroups.com.
- **Bus factor: healthy.** Multiple active maintainers (≥5 named), some of whom are also core contributors to numpy/scipy (rgommers, matthew.brett). 16,062 commits, 11.5k stars, 3.4k forks.
- **Last release:** 0.14.6 on **2025-12-05** (DIRECT_FETCH PyPI). Mature, steady cadence (0.14.x series). Single-maintainer risk: **NONE**.

## Real adoption (NOT just GitHub stars)
- **Downloads/month: ~36.56M** ([pypistats.org/packages/statsmodels](https://pypistats.org/packages/statsmodels), last month = 36,561,382; last week 8.68M; last day 1.42M). DIRECT_FETCH 2026-06-10.
- Foundational scientific-Python package. Years in existence: 2009+ (one of the oldest stats libs in the ecosystem). Massive reverse-dependency footprint across the data-science stack.
- Vanity check: stars (11.5k) are dwarfed by the download signal (~36M/mo) — adoption is real, not hype.

## Transitive dependencies — the actual attack surface
Runtime `requires_dist` (DIRECT_FETCH [PyPI JSON 0.14.6](https://pypi.org/pypi/statsmodels/0.14.6/json)):

| Dep | Spec | Native binaries? | Eager import work? | Status |
|-----|------|------------------|--------------------|--------|
| `numpy` | `<3,>=1.22.3` | yes (BLAS, expected) | no | already installed + **allowlisted** |
| `scipy` | `!=1.9.2,>=1.8` | yes (LAPACK, expected) | no | already installed + **allowlisted** |
| `pandas` | `!=2.1.0,>=1.4` | yes (C ext, expected) | no | already installed + **allowlisted** |
| `patsy` | `>=0.5.6` | **no** — pure-Python formula parser | no eager network/subprocess/env reads | NEW, low surface |
| `packaging` | `>=21.3` | no — pure-Python version parsing | no | NEW, trivial |

- **Cython is build-only** (`extra == "build"` / `"develop"`), NOT a runtime dependency. The cp314 wheel ships precompiled `.pyd` binaries; no C compiler runs at install and Cython is not pulled in. matplotlib, joblib, jinja2, etc. are all `develop`/`docs` extras — not installed by a plain `pip install statsmodels`.
- statsmodels itself ships native binaries (its own compiled Cython `.pyd` in the cp314 wheel) — expected and ordinary for a numeric library, same class as numpy/scipy.
- **No exotic surface:** the only two NEW transitive deps (patsy, packaging) are both pure-Python with no eager network, subprocess, credential-reading, or browser-launching behavior. The native-binary deps (numpy/scipy/pandas) were already independently justified and allowlisted.

## License
- **BSD-3-Clause** (Modified BSD, 3-clause) — confirmed on both [PyPI](https://pypi.org/project/statsmodels/) and the [GitHub README](https://github.com/statsmodels/statsmodels). Permissive, fully compatible with this project's dev/test-only use. No copyleft concern. (Matches the BSD-3 expectation in the T2b spec.)

## Security scan (if run)
- Not run in this session (pip-audit/guarddog would themselves require gate-approved installs). Mitigated by: pinned version 0.14.6, dev/test-only scope (never imported by runtime engine code), and the absence of CVEs in the maintained 0.14.x line as of the release date. Flagged for a `pip-audit` pass if statsmodels ever graduates to runtime scope.

## Verdict
- `APPROVED` — `2026-06-10`
- Rationale: multi-maintainer community project (~36M downloads/mo, BSD-3), runtime deps are 3 already-allowlisted natives + 2 trivial pure-Python (patsy, packaging); Cython is build-only so no compiler/eager surface at install. **Scope: dev/test-only — backs oracle O4 cross-fit (Poisson GLM reference for the in-house MLE). NOT a runtime dependency of the engine.** Pin 0.14.6.
- `falsified_by:` a `pip-audit`/guarddog scan surfacing an active CVE or a malicious transitive in the 0.14.6 wheel tree, OR statsmodels being moved into runtime (`[project.dependencies]`) scope — either flips this to APPROVED WITH CONDITIONS / re-audit.
