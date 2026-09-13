"""Run the bounded reader-projection conformance owner.

This owner emits one independently addressable reader-projection.v1 result.
Its input is a deterministic protocol fixture; it exercises the current
production reader-spine builder and validator through the shared FlowGuard
replay_trace API.  It does not run a provider, writer, judge, or quality
benchmark and cannot claim those surfaces.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Any


OWNER_SCHEMA = "logic-writing.reader-projection-owner-result.v1"
OWNER_ID = "logic-writing.reader-projection.v1"
READER_PROJECTION_CLAIM = "reader-projection.v1"


def _configure_imports(root: Path) -> None:
    """Make the selected checkout's ordinary test and skill imports visible."""

    root = root.resolve()
    scripts = root / "skills" / "logic-writing" / "scripts"
    if not scripts.is_dir():
        raise RuntimeError("logic-writing skill scripts directory is missing")
    # Insert the canonical checkout path first.  In the isolated draft it does
    # not contain the candidate adapter, so Python may continue to a candidate
    # path supplied by the test command's PYTHONPATH.  After application the
    # same line resolves to the formal adapter.
    for value in (root, scripts):
        if str(value) not in sys.path:
            sys.path.insert(0, str(value))


def _protocol_case() -> tuple[Any, Any]:
    """Build one protocol-only ReaderBrief/CompositionPlan pair.

    The fixture is deliberately not a quality corpus and no fixture score is
    emitted.  The expected projection is derived from declared plan fields,
    independently of the production builder output.
    """

    from tests.v2_support import make_reader_chain
    from reader_projection_conformance import (
        ReaderProjectionRequest,
        _abstract_projection_from_plan,
    )

    with tempfile.TemporaryDirectory(prefix="logic-writing-reader-projection-") as temp:
        chain = make_reader_chain(Path(temp) / "chain", owner="investigation")
        brief = chain["reader_brief"]
        plan = chain["plan"]
        request = ReaderProjectionRequest(
            reader_brief=brief,
            composition_plan=plan,
        )
        expectation = _abstract_projection_from_plan(
            plan,
            root_question=str(plan["central_question"]),
            root_conclusion=str(plan["central_throughline"]),
            owner=str(plan["final_owner"]),
            artifact_form=str(plan["artifact_form"]),
        )
        # The dataclasses contain only mappings and do not retain a required
        # file handle, so the temporary fixture is safe to clean up here.
        return request, expectation


def run_owner(root: Path) -> dict[str, Any]:
    """Execute exactly one bounded production reader-projection owner."""

    _configure_imports(root)
    from reader_projection_conformance import (
        build_reader_projection_trace,
        conformance_result,
        replay_reader_projection,
    )

    request, expectation = _protocol_case()
    trace = build_reader_projection_trace(request, expectation)
    report = replay_reader_projection(trace)
    payload = conformance_result(report)

    # Keep the owner result explicit about what it did and did not execute.
    # These fields are evidence metadata, not a quality score.
    payload.update(
        {
            "schema_version": OWNER_SCHEMA,
            "owner_id": OWNER_ID,
            "evidence_mode": "protocol_only",
            "provider_status": "not_run",
            "quality_claim_status": "not_claimed",
            "quality_evidence": False,
            "real_provider_executed": False,
        }
    )
    if payload.get("claim") != "production_reader_conformance":
        raise RuntimeError("reader projection owner produced the wrong claim")
    if payload.get("claim_boundary") != READER_PROJECTION_CLAIM:
        raise RuntimeError("reader projection owner produced the wrong claim boundary")
    if payload.get("observation_boundary_id") != READER_PROJECTION_CLAIM:
        raise RuntimeError("reader projection owner produced the wrong observation boundary")
    if payload.get("expected_trace") is not None:
        raise RuntimeError("reader projection owner exposed its expected trace")
    return payload


def _failure(exc: BaseException) -> dict[str, Any]:
    return {
        "schema_version": OWNER_SCHEMA,
        "owner_id": OWNER_ID,
        "status": "failed",
        "claim": "production_reader_conformance",
        "claim_boundary": READER_PROJECTION_CLAIM,
        "evidence_mode": "protocol_only",
        "provider_status": "not_run",
        "quality_claim_status": "not_claimed",
        "quality_evidence": False,
        "real_provider_executed": False,
        "error_type": type(exc).__name__,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        payload = run_owner(args.root)
        status = (
            "passed"
            if payload.get("ok") is True
            and payload.get("production_conformance") is True
            else "failed"
        )
        payload["status"] = status
    except (OSError, RuntimeError, TypeError, ValueError, ImportError, KeyError) as exc:
        payload = _failure(exc)
        status = "failed"

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"reader projection owner: {status}")
    return 0 if status == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
