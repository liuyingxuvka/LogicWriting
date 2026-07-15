"""Report provider availability without persisting machine-specific paths."""

from __future__ import annotations

import argparse
import importlib
import re
import shutil
from pathlib import Path

from _common import dump_json, fingerprint, validation_result


MODULE_PROVIDERS = {
    "sourceguard": ("sourceguard", ("build_source_coverage_universe", "build_source_depth_receipt")),
    "logicguard": ("logicguard", ("ArgumentBlock", "DepthCoverageSummary")),
    "traceguard": ("traceguard", ("derive_trace_handoffs", "evaluate_storyline_depth")),
    "flowguard": ("flowguard", ("SCHEMA_VERSION", "FlowGuardCheckPlan")),
}
SKILL_PROVIDERS = {
    "documents": ("documents", ("docx", "render")),
    "pdf": ("pdf", ("pdf", "render")),
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
    parser.add_argument("provider", choices=tuple(MODULE_PROVIDERS) + tuple(SKILL_PROVIDERS))
    parser.add_argument("--provider-root")
    parser.add_argument("--require-render", action="store_true")
    parser.add_argument("--output")
    args = parser.parse_args()
    result = preflight(args.provider, provider_root=args.provider_root, require_render=args.require_render)
    dump_json(result, args.output)
    return 0 if result["status"] == "current_pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
