# Phase 3 status — 2026-11-22

The user accepted the current Phase 2 baseline for handoff, while deferring retrieval improvements. This is not independent review or proof that Phase 2 quality gates are met. Independent evidence review, faculty clarification of page-as-document scope, and the separate evaluation approach for synthetic operational scenarios remain outstanding. The product specification gates graph development on human-reviewed frozen cases and a recorded baseline; no graph is implemented or claimed here.

## First backend milestone

`src/hr_navigator/tools/synthetic_hr.py` provides read-only, typed adapters for own profile and leave balance, the synthetic handbook's Karnataka 2027 holidays, and inclusive Monday–Friday leave calculation excluding those holidays. A balance check rejects insufficient balance and unsupported leave policies. Unknown policy versions, calendars, employees and balances fail closed. Every year in a date range requires a supported calendar. The synthetic handbook is illustrative, not law, and its other unspecified policy rules are not inferred.

`seed_scenario_fixtures` in `src/hr_navigator/db.py` loads the fictional scenario employees and balances separately from the original placeholder seed; use a fresh migrated database for these fixtures. It does not overwrite existing records and rejects a conflicting employee name. Scenario request records are not seeded by this milestone. No real employee data or external services are used.

`TrustedIdentity` is an internal trust boundary, not authentication: a future server must authenticate the session and construct it itself, never deserialize it from user text or model tool arguments. The adapters are not connected to an endpoint or graph. The check is a point-in-time calculation, not a reservation or approval, and makes no determination about overlapping requests, carry-forward, proration or other unspecified rules. SQLite access and policy file errors require future integration-level handling.

## Verification and remaining work

Focused tests cover identity scope, unavailable identities and balances, supported and unsupported calendars and policy versions, inclusive weekdays, holidays, weekends, invalid ranges and insufficient balance. See `tests/test_synthetic_hr.py`. Run with `.venv/bin/python -m pytest -q tests/test_synthetic_hr.py tests/test_phase0.py`; 12 passed. `.venv/bin/ruff check src/hr_navigator/db.py src/hr_navigator/tools/synthetic_hr.py tests/test_synthetic_hr.py` passed. The system Python lacks the project's dependencies; the project virtual environment was used. No API calls or model usage occurred.

Drafts, persistent requests, overlap handling, explicit action-bound confirmation, replay protection, idempotent submissions and tickets are not implemented. Graph nodes, routing, bounded execution, checkpointer and live smoke tests remain gated and unimplemented. Phase 3 exit criteria are not met.

The complete local suite also passed: `.venv/bin/python -m pytest -q` reported 95 passed, 2 skipped, with 9 dependency deprecation warnings.
