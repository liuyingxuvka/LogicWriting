"""pytest plugin: a test that ends skipped fails, so a swallowed error cannot hide as a skip."""
from __future__ import annotations

import pytest


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.skipped:
        reason = report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)
        report.outcome = "failed"
        report.longrepr = (f"{item.nodeid} ended skipped ({reason}); this suite allows no skips: "
                           "a skip hides why the test could not run")
