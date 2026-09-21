from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import check_writing_quality_run as consumer
import run_reader_acceptance_owner as owner
from _common import fingerprint


PRODUCER = "check.reader.execution-quality-producer"


def _write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _producer_index(run_root: Path) -> tuple[dict[str, object], dict[str, object]]:
    manifest: dict[str, object] = {
        "schema_version": "logic-writing.execution-quality-output.v1",
        "producer_check_id": PRODUCER,
        "unit_id": "unit:logic-writing",
        "source_manifest_fingerprint": "sha256:" + "1" * 64,
        "toolchain_fingerprint": "sha256:" + "2" * 64,
        "terminal_status": "completed",
        "evidence_mode": "real_execution",
        "files": [],
    }
    manifest["manifest_fingerprint"] = fingerprint(
        {key: value for key, value in manifest.items() if key != "manifest_fingerprint"}
    )
    index: dict[str, object] = {
        "schema_version": "logic-writing.validation-dependency-index.v1",
        "consumer_check_id": PRODUCER,
        "unit_id": "unit:logic-writing",
        "current_source_fingerprint": manifest["source_manifest_fingerprint"],
        "current_toolchain_fingerprint": manifest["toolchain_fingerprint"],
        "dependencies": [],
        "producer_output_manifest_path": "output-manifest.json",
        "producer_output_manifest_fingerprint": manifest["manifest_fingerprint"],
    }
    index["index_fingerprint"] = fingerprint(
        {key: value for key, value in index.items() if key != "index_fingerprint"}
    )
    _write(run_root / "output-manifest.json", manifest)
    _write(run_root / "dependency-index.json", index)
    return manifest, index


def test_quality_consumer_reads_and_binds_the_producer_dependency_index(tmp_path: Path):
    manifest, index = _producer_index(tmp_path)

    report = consumer._validate_dependency_index(
        tmp_path,
        producer_id=PRODUCER,
        manifest=manifest,
    )

    assert report["status"] == "passed"
    assert report["fingerprint"] == index["index_fingerprint"]
    assert report["producer_output_manifest_fingerprint"] == manifest["manifest_fingerprint"]


@pytest.mark.parametrize(
    "mutation, expected",
    [
        (lambda index: index.update({"current_source_fingerprint": "sha256:" + "9" * 64}), "fingerprint is stale"),
        (lambda index: index.update({"consumer_check_id": "check.reader.other"}), "belongs to another producer"),
        (lambda index: index.update({"producer_output_manifest_fingerprint": "sha256:" + "8" * 64}), "fingerprint is stale"),
    ],
)
def test_quality_consumer_rejects_tampered_dependency_index(tmp_path: Path, mutation, expected: str):
    manifest, index = _producer_index(tmp_path)
    mutation(index)
    # Keep the old fingerprint deliberately: a consumer must reject both a
    # changed body and a changed producer binding before reading any rows.
    _write(tmp_path / "dependency-index.json", index)

    with pytest.raises(ValueError, match=expected):
        consumer._validate_dependency_index(tmp_path, producer_id=PRODUCER, manifest=manifest)


def test_quality_consumer_rejects_rebound_manifest_after_valid_rehash(tmp_path: Path):
    manifest, index = _producer_index(tmp_path)
    index["producer_output_manifest_fingerprint"] = "sha256:" + "8" * 64
    index["index_fingerprint"] = fingerprint(
        {key: value for key, value in index.items() if key != "index_fingerprint"}
    )
    _write(tmp_path / "dependency-index.json", index)

    with pytest.raises(ValueError, match="does not match"):
        consumer._validate_dependency_index(tmp_path, producer_id=PRODUCER, manifest=manifest)


@pytest.mark.parametrize("field", ["manifest_fingerprint", "source_manifest_fingerprint", "toolchain_fingerprint"])
def test_quality_consumer_rejects_incomplete_manifest_identity(tmp_path: Path, field: str):
    manifest, index = _producer_index(tmp_path)
    manifest.pop(field)
    _write(tmp_path / "output-manifest.json", manifest)
    # The index itself remains immutable; the direct validator must reject the
    # incomplete loaded manifest before treating the index as current.

    with pytest.raises(ValueError, match="(fingerprint|incomplete)"):
        consumer._validate_dependency_index(tmp_path, producer_id=PRODUCER, manifest=manifest)


def test_quality_consumer_rejects_dependency_index_outside_selected_run(tmp_path: Path):
    manifest, _ = _producer_index(tmp_path)
    foreign_root = tmp_path.parent / "foreign-quality-run"
    foreign_root.mkdir()
    _write(foreign_root / "dependency-index.json", {})

    with pytest.raises(ValueError, match="escaped"):
        consumer._validate_dependency_index(
            tmp_path,
            producer_id=PRODUCER,
            manifest=manifest,
            explicit_path=foreign_root / "dependency-index.json",
        )


def test_held_out_gate_binds_current_implementation_and_policy(monkeypatch, tmp_path: Path):
    backend_plan = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "writing_quality" / "local-backend-plan.json"
    expected = {
        "plan": {
            "backend_id": "local-backend",
            "model_id": "gpt-6-astra",
            "reasoning_effort": "xhigh",
            "cli_version": "0.155.0",
            "cli_sha256": "sha256:cli",
        },
        "implementation_fingerprint": "sha256:" + "a" * 64,
        "execution_policy_fingerprint": "sha256:" + "b" * 64,
    }
    monkeypatch.setattr(owner, "_current_preflight_identity", lambda *_args, **_kwargs: expected)

    captured: dict[str, object] = {}

    def fake_check(*_args, **kwargs):
        captured["pair_plan"] = kwargs["pair_plan"]
        return {"status": "passed", "held_out_passed": True, "summary_fingerprint": "sha256:summary"}

    monkeypatch.setattr(consumer, "_check_held_out_run", fake_check)
    result = owner._validate_held_out_dependency(
        Path(__file__).resolve().parents[2],
        tmp_path,
        backend_plan,
    )

    assert result["status"] == "passed"
    assert captured["pair_plan"]["implementation_fingerprint"] == expected["implementation_fingerprint"]
    assert captured["pair_plan"]["execution_policy_fingerprint"] == expected["execution_policy_fingerprint"]
