"""Store non-authoritative attempts; authoritative receipts use managed builders.

This module deliberately has no path that promotes caller-authored
``current_pass`` JSON into terminal authority.  Use the builders in
``receipt_authority`` and resolve evidence only through
``resolve_current_receipt``.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from _common import ValidationError, dump_json, load_json, validation_result
from receipt_authority import validate_receipt
from schema_validation import SchemaValidationError


def store_receipt(value, root: str | Path):
    """Preserve a failed/non-pass attempt without granting authority."""

    receipt = validate_receipt(value)
    if receipt["status"] == "current_pass":
        raise ValidationError(
            "caller-authored current_pass cannot enter terminal authority; use a managed builder"
        )
    root_path = Path(root).resolve()
    digest = receipt["receipt_fingerprint"].split(":", 1)[1]
    destination = root_path / "untrusted-attempts" / f"{digest}.json"
    destination.parent.mkdir(parents=True, exist_ok=True)
    canonical = json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if destination.exists():
        if destination.read_text(encoding="utf-8") != canonical:
            raise ValidationError("content-addressed receipt collision")
        reused = True
    else:
        temporary = destination.with_name(destination.name + f".{os.getpid()}.tmp")
        temporary.write_text(canonical, encoding="utf-8")
        os.replace(temporary, destination)
        reused = False
    return validation_result(
        status="current_pass",
        stored_status=receipt["status"],
        receipt_fingerprint=receipt["receipt_fingerprint"],
        authoritative=False,
        terminal_success=False,
        reused=reused,
        relative_path=str(destination.relative_to(root_path)).replace("\\", "/"),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--output")
    args = parser.parse_args()
    try:
        result = store_receipt(load_json(args.input), args.root)
        dump_json(result, args.output)
        return 0
    except (ValidationError, SchemaValidationError, OSError, json.JSONDecodeError) as exc:
        dump_json(validation_result(status="blocked", errors=(str(exc),)), args.output)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["store_receipt", "validate_receipt"]
