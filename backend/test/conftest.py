"""
Session-level DB hygiene shared by every test file in backend/test.

Why this exists: all four of us run pytest against ONE shared demo
database (Supabase Postgres). Test files have repeatedly left fixture
zones behind (create-if-missing fixtures without teardown), which then
shows up on the Dashboard as unlabelled fake zones and fails the canary
in test_demo_db_integrity.py.

Two duties:

1. Ordering -- run the demo-DB canary FIRST, before any test can write
   to the DB, so it verifies the state a judge would see rather than
   the state earlier fixtures happened to leave behind.

2. Sweep -- after ANY run (any file, any author), delete the known
   fixture zones (FORBIDDEN_ZONES from backend.data.cleanup_test_zones,
   single source of truth) and their children, so a run always ends
   with the clean 12-zone demo dataset. Results print in the terminal
   summary.

The sweep never fails the suite -- leaks are reported so the owning
test file can add a teardown; the canary remains the alarm for
pollution that already exists when the suite starts.
"""

from backend.app.db import SessionLocal
from backend.data.cleanup_test_zones import sweep_forbidden_zones

CANARY_FILE = "test_demo_db_integrity"

_sweep_result = {}


def pytest_collection_modifyitems(items):
    """Put the shared-DB canary ahead of everything else.

    Stable sort: everything not matching keeps its original relative
    order, so files still run in their natural sequence.
    """
    items.sort(key=lambda item: 0 if CANARY_FILE in item.nodeid else 1)


def pytest_sessionfinish(session, exitstatus):
    global _sweep_result
    if session.config.option.collectonly:
        return
    try:
        db = SessionLocal()
        try:
            _sweep_result = sweep_forbidden_zones(db)
        finally:
            db.close()
    except Exception as exc:  # a broken sweep must never break the suite
        _sweep_result = {"error": str(exc)}


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    if _sweep_result.get("error"):
        terminalreporter.write_line(
            f"[db-hygiene] fixture sweep FAILED: {_sweep_result['error']} "
            f"(run manually: python -m backend.data.cleanup_test_zones)"
        )
    elif _sweep_result:
        terminalreporter.write_line(
            f"[db-hygiene] swept leaked test fixtures from this run: "
            f"{_sweep_result} -- the test file that created them should "
            f"add a teardown"
        )
