"""Report provider availability without persisting machine-specific paths."""

from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import re
import shutil
import subprocess
from pathlib import Path

from _common import dump_json, fingerprint, validation_result


RESEARCHGUARD_MEMBERS = {
    "sourceguard": {
        "member_command": "source",
        "primary_path_id": "primary:researchguard:source",
    },
    "logicguard": {
        "member_command": "logic",
        "primary_path_id": "primary:researchguard:logic",
    },
    "traceguard": {
        "member_command": "trace",
        "primary_path_id": "primary:researchguard:trace",
    },
}
MODULE_PROVIDERS = {
    "flowguard": ("flowguard", ("SCHEMA_VERSION", "FlowGuardCheckPlan")),
}
SKILL_PROVIDERS = {
    "documents": ("documents", ("docx", "render")),
    "pdf": ("pdf", ("pdf", "render")),
}
PROBE_TIMEOUT_SECONDS = 60


def _researchguard_console() -> str | None:
    try:
        distribution = importlib.metadata.distribution("researchguard")
    except importlib.metadata.PackageNotFoundError:
        return None
    entries = [
        entry
        for entry in distribution.entry_points
        if entry.group == "console_scripts"
        and entry.name == "researchguard"
        and entry.value == "researchguard.cli:main"
    ]
    if len(entries) != 1:
        return None
    candidates = sorted(
        {
            Path(distribution.locate_file(relative)).resolve()
            for relative in distribution.files or ()
            if Path(str(relative)).name.lower() in {"researchguard", "researchguard.exe"}
            and Path(distribution.locate_file(relative)).resolve().is_file()
        }
    )
    return str(candidates[0]) if len(candidates) == 1 else None


def _run_console_probe(console: str, args: tuple[str, ...]) -> dict[str, object]:
    command = ["researchguard", *args]
    try:
        completed = subprocess.run(
            [console, *args],
            capture_output=True,
            text=True,
            timeout=PROBE_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "command": command,
            "passed": False,
            "timed_out": True,
            "timeout_seconds": PROBE_TIMEOUT_SECONDS,
        }
    except OSError as exc:
        return {
            "command": command,
            "passed": False,
            "timed_out": False,
            "probe_error": f"{type(exc).__name__}: {exc}",
        }
    return {
        "command": command,
        "passed": completed.returncode == 0,
        "timed_out": False,
        "exit_code": completed.returncode,
        "stdout": completed.stdout.strip(),
    }


def _skill_manifest(root: Path):
    path = root / "SKILL.md"
    if not path.is_file():
        return None, ""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\s*\n(?P<header>.*?)\n---\s*\n", text, flags=re.DOTALL)
    if not match:
        return None, text
    name_match = re.search(r'^name:\s*["\']?([^"\'\n]+)["\']?\s*$', match.group("header"), flags=re.MULTILINE)
    return (name_match.group(1).strip() if name_match else None), text


def preflight(provider: str, *, provider_root: str | None = None, require_render: bool = False):
    original_provider = provider
    provider = provider.strip()
    evidence: dict[str, object] = {"provider": provider, "require_render": require_render}

    if provider != original_provider or provider != provider.lower():
        status = "blocked"
        evidence["reason"] = "provider id must be the exact canonical lowercase id"
    elif provider in RESEARCHGUARD_MEMBERS:
        binding = RESEARCHGUARD_MEMBERS[provider]
        evidence.update(
            {
                "provider_console_id": "researchguard",
                "member_id": provider,
                "member_command": binding["member_command"],
                "primary_path_id": binding["primary_path_id"],
            }
        )
        if provider_root:
            status = "blocked"
            evidence["reason"] = (
                "ResearchGuard members use the installed researchguard console; "
                "provider-root overrides are not an execution path"
            )
        else:
            console = _researchguard_console()
            evidence["console_resolved"] = bool(console)
            if not console:
                status = "provider_unavailable"
            else:
                version_probe = _run_console_probe(console, ("--version",))
                member_probe = _run_console_probe(
                    console,
                    (str(binding["member_command"]), "--help"),
                )
                version_text = str(version_probe.get("stdout", ""))
                version_match = re.fullmatch(
                    r"researchguard\s+([0-9]+(?:\.[0-9]+){2}(?:[-+][A-Za-z0-9._-]+)?)",
                    version_text,
                )
                version_probe["version_format_current"] = bool(version_match)
                version_probe.pop("stdout", None)
                member_probe.pop("stdout", None)
                available = (
                    bool(version_probe.get("passed"))
                    and bool(version_match)
                    and bool(member_probe.get("passed"))
                )
                evidence.update(
                    {
                        "suite_version": version_match.group(1) if version_match else None,
                        "version_probe": version_probe,
                        "member_capability_probe": member_probe,
                    }
                )
                status = "current_pass" if available else "provider_unavailable"
    elif provider in MODULE_PROVIDERS:
        module_name, required_capabilities = MODULE_PROVIDERS[provider]
        try:
            module = importlib.import_module(module_name)
            missing = [name for name in required_capabilities if not hasattr(module, name)]
            version = getattr(module, "__version__", None) or getattr(module, "SCHEMA_VERSION", None)
            available = not missing and version is not None
            evidence.update(
                {
                    "module_importable": True,
                    "provider_version": str(version) if version is not None else None,
                    "capability_probe": {name: hasattr(module, name) for name in required_capabilities},
                    "missing_capabilities": missing,
                }
            )
        except Exception as exc:
            available = False
            evidence.update(
                {
                    "module_importable": False,
                    "probe_error": f"{type(exc).__name__}: {exc}",
                }
            )
        status = "current_pass" if available else "provider_unavailable"
    elif provider in SKILL_PROVIDERS:
        expected_name, capability_tokens = SKILL_PROVIDERS[provider]
        root = Path(provider_root).expanduser().resolve() if provider_root else None
        manifest_name, manifest_text = _skill_manifest(root) if root else (None, "")
        token_probe = {token: token.casefold() in manifest_text.casefold() for token in capability_tokens}
        available = bool(root and manifest_name == expected_name and all(token_probe.values()))
        status = "current_pass" if available else "provider_unavailable"
        evidence.update(
            {
                "skill_manifest_present": bool(root and (root / "SKILL.md").is_file()),
                "declared_provider_id": manifest_name,
                "provider_id_matches": manifest_name == expected_name,
                "capability_probe": token_probe,
            }
        )
        if provider == "documents" and require_render:
            renderer = shutil.which("soffice") or shutil.which("libreoffice")
            evidence["renderer_available"] = bool(renderer)
            if available and not renderer:
                status = "render_not_run"
        elif provider == "pdf" and require_render:
            renderer = shutil.which("pdftoppm") or shutil.which("mutool")
            evidence["renderer_available"] = bool(renderer)
            if available and not renderer:
                status = "render_not_run"
    else:
        status = "blocked"
        evidence["reason"] = "unknown provider id"

    public_evidence = {
        key: value
        for key, value in evidence.items()
        if key not in {"path", "origin", "provider_root"}
    }
    return validation_result(
        status=status,
        provider=provider,
        evidence=public_evidence,
        preflight_fingerprint=fingerprint(public_evidence),
        claim_boundary=(
            "provider availability only; native domain work is not run"
            if status == "current_pass"
            else "provider or render dependency is not currently available"
        ),
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "provider",
        choices=tuple(RESEARCHGUARD_MEMBERS)
        + tuple(MODULE_PROVIDERS)
        + tuple(SKILL_PROVIDERS),
    )
    parser.add_argument("--provider-root")
    parser.add_argument("--require-render", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = preflight(args.provider, provider_root=args.provider_root, require_render=args.require_render)
    dump_json(result, args.output)
    return 0 if result["status"] == "current_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
