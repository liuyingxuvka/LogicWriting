"""Structural links from a writing plan to native world ids and current quotations.

This reader never runs WorldGuard or interprets the contract's natural language.
"""
from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from _common import ValidationError


def planned_world_refs(plan):
    """Return only explicit, nonempty references; ordinary plans stay unchanged."""
    result = {}
    for unit in plan.get("planned_units", []):
        refs = unit.get("world_refs", [])
        if not isinstance(refs, list) or any(not isinstance(ref, str) or not ref for ref in refs):
            raise ValidationError("world_refs must be a list of nonempty world ids")
        if len(refs) != len(set(refs)):
            raise ValidationError("world_refs must not contain duplicate ids")
        if refs:
            result[unit["planned_unit_id"]] = tuple(refs)
    return result


def _world_symbols(composition, base_dir=None):
    """Read the same native world objects used by id validation; no re-evaluation."""
    mesh = composition.get('world_mesh')
    kind = 'world_mesh' if mesh is not None else 'world_contract'
    location = mesh if mesh is not None else composition.get("world_contract")
    if not isinstance(location, str) or not location:
        raise ValidationError(f"{kind}_missing: planned units name world_refs")
    path = Path(location).expanduser()
    if not path.is_absolute():
        path = Path(base_dir or Path.cwd()) / path
    try:
        import yaml
        world = yaml.safe_load(path.read_text(encoding="utf-8"))
        worlds = [world]
        if mesh is not None:
            nodes = world.get('nodes') if isinstance(world, Mapping) else None
            if not isinstance(nodes, list) or any(not isinstance(node, Mapping) for node in nodes):
                raise ValidationError('world_mesh_unreadable: expected mesh nodes')
            worlds = []
            for node in nodes:
                contract = node.get('contract')
                if isinstance(contract, str):
                    contract = yaml.safe_load((path.parent / contract).read_text(encoding='utf-8'))
                worlds.append(contract)
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValidationError(f"{kind}_unreadable: {path}: {exc}") from exc
    except ImportError as exc:
        raise ValidationError(f"{kind}_unreadable: PyYAML is required") from exc
    except yaml.YAMLError as exc:
        raise ValidationError(f"{kind}_unreadable: {path}: {exc}") from exc
    symbols = {}
    for world in worlds:
        if not isinstance(world, Mapping):
            raise ValidationError(f"{kind}_unreadable: {path}: expected a mapping")
        claim = world.get("claim", {})
        inputs = world.get("inputs", {})
        if not isinstance(claim, Mapping) or not isinstance(inputs, Mapping):
            raise ValidationError(f"{kind}_unreadable: {path}: invalid claim/inputs")
        events = inputs.get("events", [])
        if not isinstance(events, list) or any(not isinstance(event, Mapping) for event in events):
            raise ValidationError(f"{kind}_unreadable: {path}: invalid events")
        for event in events:
            if 'event_id' in event and isinstance(event['event_id'], str):
                symbols.setdefault(event['event_id'], []).append(('event', event))
        if 'claim_id' in claim and isinstance(claim['claim_id'], str):
            symbols.setdefault(claim['claim_id'], []).append(('claim', claim))
    return symbols


def _world_ref_context(plan, composition, base_dir=None):
    if 'world_contract' in composition and 'world_mesh' in composition:
        raise ValidationError('world_contract and world_mesh are mutually exclusive')
    refs = planned_world_refs(plan)
    if not refs:
        return refs, {}
    symbols = _world_symbols(composition, base_dir)
    for unit_id, ids in refs.items():
        for ref in ids:
            if ref not in symbols:
                raise ValidationError(f"unknown_world_ref:{unit_id}:{ref}")
    return refs, symbols


def validate_world_refs(plan, composition, base_dir=None):
    """Resolve a composition-relative contract and validate its native ids."""
    return _world_ref_context(plan, composition, base_dir)[0]


def _world_value_risks(symbols, unit_id, ref, excerpt):
    """Only explicit participant ids and one literal date/time per bound event.

    Symbolic time and ambiguous excerpts do not turn a conditional world into
    observation-based validation. WorldGuard remains the world evaluator.
    """
    from claim_readings import agrees, readings
    import re
    entries = symbols[ref]
    if len(entries) != 1:
        return [f'world_ref_ambiguous:{unit_id}:{ref}']
    kind, event = entries[0]
    stated = [row for row in readings(excerpt) if row['kind'] in ('time', 'date')]
    if kind != 'event':
        return [f'world_ref_scope_unverified:{unit_id}:{ref}'] if stated else []
    risks = []
    expected = [row for row in readings(str(event['at'])) if row['kind'] in ('time', 'date')] if 'at' in event else []
    for value_kind in ('time', 'date'):
        claims = [row for row in stated if row['kind'] == value_kind]
        facts = [row for row in expected if row['kind'] == value_kind]
        if not claims:
            continue
        if len(claims) != 1 or len(facts) != 1:
            risks.append(f'world_ref_{value_kind}_unverified:{unit_id}:{ref}')
        elif not agrees(claims[0], facts[0]):
            raise ValidationError(f'world_ref_value_disagrees:{unit_id}:{ref}:{value_kind} (current quoted text differs from the native event)')
    if 'actor' in event and isinstance(event['actor'], str):
        known = {data['actor'] for values in symbols.values() for entry_kind, data in values
                 if entry_kind == 'event' and 'actor' in data and isinstance(data['actor'], str)}
        named = {actor for actor in known if re.search(r'(?<!\w)' + re.escape(actor) + r'(?!\w)', excerpt, re.I)}
        participants = {event['actor'], *(event['with'] if 'with' in event else [])}
        if len(named) == 1 and not named <= participants:
            raise ValidationError(f'world_ref_value_disagrees:{unit_id}:{ref}:actor (current quoted text names a different native participant)')
        if named and named != {event['actor']}:
            risks.append(f'world_ref_role_unverified:{unit_id}:{ref}')
    return risks


def world_ref_unquoted(plan, review, shared, verify_evidence, *, composition=None, base_dir=None):
    """Validate supplied real spans, returning missing-quote risks without gating."""
    refs, symbols = (_world_ref_context(plan, composition, base_dir) if composition is not None
                     else (planned_world_refs(plan), {}))
    risks = []
    allowed_units = {}
    for binding in shared.get("unit_bindings", []):
        allowed_units.setdefault(binding["planned_unit_id"], set()).update(binding["artifact_unit_ids"])
    quoted = set()
    rows = review.get("world_ref_checks", [])
    if not isinstance(rows, list):
        raise ValidationError("world_ref_checks must be a list")
    seen = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise ValidationError("world_ref_checks rows must be mappings")
        key = (row.get("planned_unit_id"), row.get("world_ref"))
        if (not all(isinstance(value, str) for value in key)
                or key[0] not in refs or key[1] not in refs[key[0]]):
            raise ValidationError("world_ref_checks names an unknown unit/world reference")
        if key in seen:
            raise ValidationError("world_ref_checks repeats a unit/world reference")
        seen.add(key)
        evidence = row.get("evidence", [])
        if not isinstance(evidence, list):
            raise ValidationError("world_ref_checks.evidence must be a list")
        for span in evidence:
            if not isinstance(span, Mapping):
                raise ValidationError("world_ref_checks.evidence rows must be mappings")
            verify_evidence(span)
            if span["artifact_unit_id"] not in allowed_units.get(key[0], set()):
                raise ValidationError("world_ref_checks excerpt must belong to its planned unit")
            if symbols:
                risks.extend(_world_value_risks(symbols, key[0], key[1], span['excerpt']))
        if evidence:
            quoted.add(key)
    return risks + [f"world_ref_unquoted:{unit}:{ref}" for unit, ids in refs.items()
                    for ref in ids if (unit, ref) not in quoted]


def validate_world_claim_units(ledger, plan):
    """A fiction ledger's world claim must point to a plan unit with world refs."""
    refs = planned_world_refs(plan)
    return [f"unit_not_in_plan:worldguard_claims:{row.get('id', '')}"
            for row in ledger.get("worldguard_claims", [])
            if isinstance(row, Mapping) and row.get("source_row_id") not in refs]
