"""pytest plugin: a test or a test module that ends skipped fails, so a swallowed error cannot hide as a skip.

A skip inside a test (pytest.skip, skipif, xfail) is a test report; a skip while a module is collected
(pytest.importorskip or pytest.skip(allow_module_level=True) at module level) is a collection report. Both fail.
"""
from __future__ import annotations

import pytest

_NO_SKIPS = 'this suite allows no skips: a skip hides why the test could not run'


def _reason(report) -> str:
    return report.longrepr[2] if isinstance(report.longrepr, tuple) else str(report.longrepr)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if report.skipped:
        report.outcome = "failed"
        report.longrepr = f"{item.nodeid} ended skipped ({_reason(report)}); {_NO_SKIPS}"


@pytest.hookimpl(hookwrapper=True)
def pytest_make_collect_report(collector):
    outcome = yield
    report = outcome.get_result()
    if report.skipped:
        report.outcome = "failed"
        report.longrepr = f"{collector.nodeid} was skipped while it was collected ({_reason(report)}); {_NO_SKIPS}"
