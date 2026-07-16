# Tests

This project has two tiers of tests.

## 1. Safe subset (no heavy deps) — recommended for quick checks / minimal envs

`tests/run_safe.py` runs the test modules that depend only on the standard
library plus pure Cocoa modules. They work even when `pytest`, the
`cryptography` native binding, `torch`, `flask`, etc. are unavailable.

```bash
python3 tests/run_safe.py        # or: python3 -m unittest <module> ...
```

Covered modules (see each file's docstring for the spec it verifies):

| Test module | Subject | Spec |
|---|---|---|
| `test_repairs` | i18n dedup, preset repair, run_tests exit code | FIX_REPORT |
| `test_validation` | `ConfigValidator` (incl. nested schema) | — |
| `test_preset_diff` | `preset_diff_core` | — |
| `test_vrchat_budget` | `vrchat_parameter_budget` | SPEC_PRESET_PARAMETERS (REQ-PM-09/10/11) |
| `test_preset_schema` | `preset_schema` | SPEC_PRESET_PARAMETERS (REQ-PM-07/12) |
| `test_template_filters` | `template_filters` (incl. path-traversal) | SPEC_TEMPLATE_LIBRARY |
| `test_preset_history` | `preset_change_history` rollback/robustness | SPEC_PRESET_HISTORY (REQ-PH-03..07) |
| `test_preset_history_diff` | `preset_history_diff_and_rollback` helpers | SPEC_PRESET_HISTORY (REQ-PH-08/09) |

## 2. Full suite (requires the full dependency stack)

The complete suite under `tests/` plus `run_tests.py` exercises modules that
need the full dependency stack (cryptography, fastapi/flask, torch, psutil,
…). Run it once those are installed:

```bash
python -m pytest tests/ -v        # as in .github/workflows/ci-cd.yml
```
