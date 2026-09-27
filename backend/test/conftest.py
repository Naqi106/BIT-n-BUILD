"""
Session-level DB hygiene shared by every test file in backend/test.

Why this exists: all four of us run pytest against ONE shared demo
database (Supabase Postgres). Test files have repeatedly left fixture
zones behind (create-if-missing fixtures without teardown), which then
shows up on the Dashboard as unlabelled fake zones and fails the canary
in test_demo_db_integrity.py.

Three duties, in order:

1. Pre-run sweep (pytest_sessionstart) -- repair fixture zones leaked
   by an EARLIER run (someone else's, or a killed one) before any test
   executes, so the canary verifies the state a judge would see rather
   than screaming about someone else's leftovers.

2. Ordering (pytest_collection_modifyitems) -- run the demo-DB canary
   FIRST, before any test can write to the DB. Stable sort: everything
   else keeps its original relative order.

3. Post-run sweep (pytest_sessionfinish) -- delete fixture zones this
   run created (any file, any author), so the DB is clean for the next
   person. Both sweeps print in the terminal summary; neither fails the
   suite -- leaks are reported so the owning test file can add a
   teardown.

Deliberately NOT repaired automatically: missing/wiped demo zones or
corrupted snapshot history. That is real damage with an unknown cause
(see the canary's Sep 26 wipe incidents) and needs a human to run
    python -m backend.data.lucknow_seed
The canary stays red until they do -- that alarm is the point.
"""

from backend.app.db import SessionLocal
from backend.data.cleanup_test_zones import sweep_forbidden_zones

CANARY_FILE = "test_demo_db_integrity"

_pre_sweep = {}
_post_sweep = {}


def _sweep() -> dict:
    """Run the shared fixture sweep; never raise."""
    try:
        db = SessionLocal()
        try:
            return sweep_forbidden_zones(db)
        finally:
            db.close()
    except Exception as exc:
        return {"error": str(exc)}


def pytest_sessionstart(session):
    """Repair fixture pollution from earlier runs BEFORE the canary runs."""
    if session.config.option.collectonly:
        return
    global _pre_sweep
    _pre_sweep = _sweep()


def pytest_collection_modifyitems(items):
    """Put the shared-DB canary ahead of everything else.

    Stable sort: everything not matching keeps its original relative
    order, so files still run in their natural sequence.
    """
    items.sort(key=lambda item: 0 if CANARY_FILE in item.nodeid else 1)


def pytest_sessionfinish(session, exitstatus):
    """Leave the DB clean for whoever runs tests next."""
    if session.config.option.collectonly:
        return
    global _post_sweep
    _post_sweep = _sweep()


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    _report(
        terminalreporter, "pre-run", _pre_sweep,
        note="leaked by an earlier run -- swept before tests so the "
             "canary sees a judge's view",
    )
    _report(
        terminalreporter, "post-run", _post_sweep,
        note="leaked during this run -- the test file that created "
             "them should add a teardown",
    )


def _report(terminalreporter, label, result, note):
    if not result:
        return
    if result.get("error"):
        terminalreporter.write_line(
            f"[db-hygiene] {label} sweep FAILED: {result['error']} "
            f"(run manually: python -m backend.data.cleanup_test_zones)"
        )
    else:
        terminalreporter.write_line(
            f"[db-hygiene] {label} swept leaked test fixtures: {result} -- {note}"
        )
