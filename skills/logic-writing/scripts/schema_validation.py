"""Current JSON Schema runtime gate for Logic Writing artifacts.

The skill ships its contracts with the runtime, so validation must remain
deterministic and offline.  This module loads the exact fourteen Draft 2020-12
schemas relative to this file, resolves their local cross-schema references,
and exposes the only two artifact-validation entry points:

``validate_schema(schema_name, artifact)``
    Return a stable tuple of validation issues.  An empty tuple means valid.

``assert_schema_valid(schema_name, artifact)``
    Raise :class:`SchemaValidationError` when any issue is present.

Schema names are the canonical ``*.schema.json`` filenames.  Unknown names,
unresolvable references, malformed bundled schemas, and unsupported schema
formats are hard failures; there is no network lookup or fallback validator.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping
from urllib.parse import unquote, urldefrag, urljoin


DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_BASE_URI = "https://github.com/liuyingxuvka/LogicWriting/schemas/"
SUPPORTED_SCHEMA_NAMES = (
    "adapter-request.schema.json",
    "adapter-result.schema.json",
    "claim-support.schema.json",
    "closure.schema.json",
    "obligation-manifest.schema.json",
    "reader-audit.schema.json",
    "reader-brief.schema.json",
    "reader-judgment.schema.json",
    "evidence-receipt.schema.json",
    "research-packet.schema.json",
    "revision-provenance.schema.json",
    "route-decision.schema.json",
    "source-registry.schema.json",
    "source-unit-manifest.schema.json",
)

_SCHEMA_ROOT = Path(__file__).resolve().parents[1] / "assets" / "schemas"
_DATE_TIME = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}[Tt]"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]+)?"
    r"(?:[Zz]|[+-][0-9]{2}:[0-9]{2})$"
)
_SUPPORTED_SCHEMA_KEYWORDS = frozenset(
    {
        "$schema",
        "$id",
        "$ref",
        "$defs",
        "$comment",
        "title",
        "description",
        "default",
        "examples",
        "deprecated",
        "readOnly",
        "writeOnly",
        "type",
        "const",
        "enum",
        "allOf",
        "anyOf",
        "oneOf",
        "not",
        "if",
        "then",
        "else",
        "required",
        "properties",
        "patternProperties",
        "additionalProperties",
        "propertyNames",
        "minProperties",
        "maxProperties",
        "items",
        "minItems",
        "maxItems",
        "uniqueItems",
        "minLength",
        "maxLength",
        "pattern",
        "format",
        "minimum",
        "maximum",
    }
)


class SchemaRuntimeConfigurationError(RuntimeError):
    """The bundled schema authority cannot be loaded or resolved safely."""


class UnknownSchemaError(ValueError):
    """The caller requested a name outside the current schema authority."""


@dataclass(frozen=True, order=True)
class SchemaValidationIssue:
    """One deterministic, reader-readable artifact validation failure."""

    path: str
    keyword: str
    message: str

    def __str__(self) -> str:
        return f"{self.path} [{self.keyword}]: {self.message}"


class SchemaValidationError(ValueError):
    """Raised by :func:`assert_schema_valid` for an invalid artifact."""

    def __init__(
        self,
        schema_name: str,
        issues: tuple[SchemaValidationIssue, ...],
    ) -> None:
        if not issues:
            raise ValueError("SchemaValidationError requires at least one issue")
        self.schema_name = schema_name
        self.issues = issues
        rendered = "; ".join(str(issue) for issue in issues)
        super().__init__(f"{schema_name}: {rendered}")


@dataclass(frozen=True)
class _SchemaResource:
    name: str
    base_uri: str
    document: Mapping[str, Any]


def _load_schema_documents() -> dict[str, dict[str, Any]]:
    if not _SCHEMA_ROOT.is_dir():
        raise SchemaRuntimeConfigurationError(
            f"schema directory is missing: {_SCHEMA_ROOT}"
        )

    discovered = {path.name for path in _SCHEMA_ROOT.glob("*.schema.json")}
    expected = set(SUPPORTED_SCHEMA_NAMES)
    if discovered != expected:
        missing = sorted(expected - discovered)
        unexpected = sorted(discovered - expected)
        raise SchemaRuntimeConfigurationError(
            "schema inventory does not match the current authority "
            f"(missing={missing}, unexpected={unexpected})"
        )

    documents: dict[str, dict[str, Any]] = {}
    for name in SUPPORTED_SCHEMA_NAMES:
        path = _SCHEMA_ROOT / name
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise SchemaRuntimeConfigurationError(
                f"cannot load bundled schema {name}: {exc}"
            ) from exc
        if not isinstance(document, dict):
            raise SchemaRuntimeConfigurationError(
                f"bundled schema {name} must be a JSON object"
            )
        documents[name] = document
    return documents


class _LocalSchemaRegistry:
    def __init__(self, documents: Mapping[str, Mapping[str, Any]]) -> None:
        resources: dict[str, _SchemaResource] = {}
        resources_by_uri: dict[str, _SchemaResource] = {}
        for name in SUPPORTED_SCHEMA_NAMES:
            document = documents[name]
            dialect = document.get("$schema")
            if dialect != DRAFT_2020_12:
                raise SchemaRuntimeConfigurationError(
                    f"{name} declares {dialect!r}; expected {DRAFT_2020_12!r}"
                )
            expected_uri = SCHEMA_BASE_URI + name
            base_uri = document.get("$id")
            if base_uri != expected_uri:
                raise SchemaRuntimeConfigurationError(
                    f"{name} has non-canonical $id {base_uri!r}; expected {expected_uri!r}"
                )
            resource = _SchemaResource(name, base_uri, document)
            if base_uri in resources_by_uri:
                raise SchemaRuntimeConfigurationError(
                    f"duplicate bundled schema $id: {base_uri}"
                )
            resources[name] = resource
            resources_by_uri[base_uri] = resource

        self.by_name = MappingProxyType(resources)
        self.by_uri = MappingProxyType(resources_by_uri)
        for resource in self.by_name.values():
            self._check_schema_node(resource.document, resource, "#", is_root=True)

    def require(self, schema_name: str) -> _SchemaResource:
        if not isinstance(schema_name, str) or schema_name not in self.by_name:
            expected = ", ".join(SUPPORTED_SCHEMA_NAMES)
            raise UnknownSchemaError(
                f"unknown Logic Writing schema {schema_name!r}; expected one of: {expected}"
            )
        return self.by_name[schema_name]

    def resolve(
        self,
        ref: str,
        current: _SchemaResource,
    ) -> tuple[Any, _SchemaResource]:
        if not isinstance(ref, str) or not ref:
            raise SchemaRuntimeConfigurationError(
                f"{current.name} contains an empty or non-string $ref"
            )
        resolved = urljoin(current.base_uri, ref)
        resource_uri, fragment = urldefrag(resolved)
        target_resource = self.by_uri.get(resource_uri)
        if target_resource is None:
            raise SchemaRuntimeConfigurationError(
                f"{current.name} references an unknown local schema resource: {ref}"
            )
        return self._resolve_pointer(target_resource, fragment), target_resource

    @staticmethod
    def _resolve_pointer(resource: _SchemaResource, fragment: str) -> Any:
        if not fragment:
            return resource.document
        pointer = unquote(fragment)
        if not pointer.startswith("/"):
            raise SchemaRuntimeConfigurationError(
                f"{resource.name} uses unsupported non-pointer fragment #{fragment}"
            )
        current: Any = resource.document
        for raw_token in pointer.lstrip("/").split("/"):
            token = raw_token.replace("~1", "/").replace("~0", "~")
            try:
                if isinstance(current, list):
                    current = current[int(token)]
                else:
                    current = current[token]
            except (KeyError, IndexError, TypeError, ValueError) as exc:
                raise SchemaRuntimeConfigurationError(
                    f"unresolvable JSON Pointer #{fragment} in {resource.name}"
                ) from exc
        return current

    def _check_schema_node(
        self,
        node: Any,
        resource: _SchemaResource,
        path: str,
        *,
        is_root: bool = False,
    ) -> None:
        if isinstance(node, bool):
            return
        if not isinstance(node, dict):
            raise SchemaRuntimeConfigurationError(
                f"schema node at {resource.name}{path} must be an object or boolean"
            )

        unsupported = sorted(set(node) - _SUPPORTED_SCHEMA_KEYWORDS)
        if unsupported:
            raise SchemaRuntimeConfigurationError(
                f"unsupported schema keyword(s) at {resource.name}{path}: {unsupported}"
            )
        if not is_root and "$id" in node:
            raise SchemaRuntimeConfigurationError(
                f"nested $id is outside the current local registry vocabulary at "
                f"{resource.name}{path}"
            )

        if "$ref" in node:
            self.resolve(node["$ref"], resource)
        if "pattern" in node:
            pattern = node["pattern"]
            if not isinstance(pattern, str):
                raise SchemaRuntimeConfigurationError(
                    f"{resource.name}{path}/pattern must be a string"
                )
            try:
                re.compile(pattern)
            except re.error as exc:
                raise SchemaRuntimeConfigurationError(
                    f"invalid pattern at {resource.name}{path}: {exc}"
                ) from exc
        if "format" in node and node["format"] != "date-time":
            raise SchemaRuntimeConfigurationError(
                f"unsupported format {node['format']!r} at {resource.name}{path}"
            )

        for container_key in ("$defs", "properties", "patternProperties"):
            if container_key not in node:
                continue
            container = node[container_key]
            if not isinstance(container, dict):
                raise SchemaRuntimeConfigurationError(
                    f"{container_key} at {resource.name}{path} must be an object"
                )
            for name, child in container.items():
                if container_key == "patternProperties":
                    try:
                        re.compile(name)
                    except re.error as exc:
                        raise SchemaRuntimeConfigurationError(
                            f"invalid patternProperties key at {resource.name}{path}: {exc}"
                        ) from exc
                self._check_schema_node(
                    child,
                    resource,
                    f"{path}/{container_key}/{name}",
                )

        for array_key in ("allOf", "anyOf", "oneOf"):
            if array_key not in node:
                continue
            children = node[array_key]
            if not isinstance(children, list):
                raise SchemaRuntimeConfigurationError(
                    f"{array_key} at {resource.name}{path} must be an array"
                )
            for index, child in enumerate(children):
                self._check_schema_node(
                    child,
                    resource,
                    f"{path}/{array_key}/{index}",
                )

        for single_key in (
            "not",
            "if",
            "then",
            "else",
            "additionalProperties",
            "propertyNames",
            "items",
        ):
            if single_key in node:
                self._check_schema_node(
                    node[single_key],
                    resource,
                    f"{path}/{single_key}",
                )


def _json_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left == right
    if (
        isinstance(left, (int, float))
        and isinstance(right, (int, float))
        and not isinstance(left, bool)
        and not isinstance(right, bool)
    ):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(
            _json_equal(left[key], right[key]) for key in left
        )
    if isinstance(left, list):
        return len(left) == len(right) and all(
            _json_equal(a, b) for a, b in zip(left, right)
        )
    return left == right


def _matches_type(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return (
            isinstance(instance, (int, float))
            and not isinstance(instance, bool)
            and (not isinstance(instance, float) or math.isfinite(instance))
        )
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    raise SchemaRuntimeConfigurationError(f"unsupported schema type: {expected!r}")


def _child_path(path: str, key: Any) -> str:
    if isinstance(key, str) and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
        return f"{path}.{key}"
    if isinstance(key, str):
        rendered = json.dumps(key, ensure_ascii=False)
    else:
        rendered = repr(key)
    return f"{path}[{rendered}]"


def _stable_property_keys(instance: Mapping[Any, Any]) -> list[Any]:
    return sorted(instance, key=lambda key: (type(key).__name__, repr(key)))


def _issue(path: str, keyword: str, message: str) -> SchemaValidationIssue:
    return SchemaValidationIssue(path=path, keyword=keyword, message=message)


class _Draft202012Runtime:
    """Validate the Draft 2020-12 vocabulary used by the bundled contracts."""

    def __init__(self, registry: _LocalSchemaRegistry) -> None:
        self.registry = registry

    def validate(
        self,
        instance: Any,
        schema: Any,
        resource: _SchemaResource,
        path: str = "$",
    ) -> list[SchemaValidationIssue]:
        if schema is True:
            return []
        if schema is False:
            return [_issue(path, "falseSchema", "value is rejected by a false schema")]
        if not isinstance(schema, dict):
            raise SchemaRuntimeConfigurationError(
                f"schema node in {resource.name} is not an object or boolean"
            )

        issues: list[SchemaValidationIssue] = []
        if "$ref" in schema:
            target, target_resource = self.registry.resolve(schema["$ref"], resource)
            issues.extend(self.validate(instance, target, target_resource, path))
            siblings = {key: value for key, value in schema.items() if key != "$ref"}
            if siblings:
                issues.extend(self.validate(instance, siblings, resource, path))
            return issues

        if "const" in schema and not _json_equal(instance, schema["const"]):
            issues.append(
                _issue(path, "const", f"expected {schema['const']!r}, got {instance!r}")
            )
        if "enum" in schema and not any(
            _json_equal(instance, candidate) for candidate in schema["enum"]
        ):
            issues.append(
                _issue(path, "enum", f"value {instance!r} is not an allowed value")
            )

        expected_type = schema.get("type")
        if expected_type is not None:
            alternatives = (
                expected_type if isinstance(expected_type, list) else [expected_type]
            )
            if not all(isinstance(item, str) for item in alternatives):
                raise SchemaRuntimeConfigurationError(
                    f"invalid type declaration in {resource.name}"
                )
            if not any(_matches_type(instance, item) for item in alternatives):
                actual = type(instance).__name__
                issues.append(
                    _issue(
                        path,
                        "type",
                        f"expected {' or '.join(alternatives)}, got {actual}",
                    )
                )
                return issues

        for child in schema.get("allOf", []):
            issues.extend(self.validate(instance, child, resource, path))
        if "anyOf" in schema:
            branches = schema["anyOf"]
            if not any(not self.validate(instance, child, resource, path) for child in branches):
                issues.append(_issue(path, "anyOf", "no allowed alternative matched"))
        if "oneOf" in schema:
            match_count = sum(
                not self.validate(instance, child, resource, path)
                for child in schema["oneOf"]
            )
            if match_count != 1:
                issues.append(
                    _issue(
                        path,
                        "oneOf",
                        f"expected exactly one matching alternative, got {match_count}",
                    )
                )
        if "not" in schema and not self.validate(instance, schema["not"], resource, path):
            issues.append(_issue(path, "not", "prohibited schema matched"))
        if "if" in schema:
            predicate_matches = not self.validate(instance, schema["if"], resource, path)
            selected = "then" if predicate_matches else "else"
            if selected in schema:
                issues.extend(self.validate(instance, schema[selected], resource, path))

        if isinstance(instance, dict):
            ordered_keys = _stable_property_keys(instance)
            for key in schema.get("required", []):
                if key not in instance:
                    issues.append(
                        _issue(
                            _child_path(path, key),
                            "required",
                            f"required property {key!r} is missing",
                        )
                    )
            minimum = schema.get("minProperties")
            if minimum is not None and len(instance) < minimum:
                issues.append(
                    _issue(
                        path,
                        "minProperties",
                        f"expected at least {minimum} properties, got {len(instance)}",
                    )
                )
            maximum = schema.get("maxProperties")
            if maximum is not None and len(instance) > maximum:
                issues.append(
                    _issue(
                        path,
                        "maxProperties",
                        f"expected at most {maximum} properties, got {len(instance)}",
                    )
                )

            evaluated: set[Any] = set()
            for key in ordered_keys:
                if not isinstance(key, str):
                    issues.append(
                        _issue(
                            _child_path(path, key),
                            "propertyNames",
                            "JSON object property names must be strings",
                        )
                    )
                    evaluated.add(key)
            for key, child in schema.get("properties", {}).items():
                if key in instance:
                    issues.extend(
                        self.validate(
                            instance[key], child, resource, _child_path(path, key)
                        )
                    )
                    evaluated.add(key)
            for pattern, child in schema.get("patternProperties", {}).items():
                compiled = re.compile(pattern)
                for key in ordered_keys:
                    if isinstance(key, str) and compiled.search(key):
                        issues.extend(
                            self.validate(
                                instance[key], child, resource, _child_path(path, key)
                            )
                        )
                        evaluated.add(key)
            if "propertyNames" in schema:
                for key in ordered_keys:
                    if not isinstance(key, str):
                        continue
                    key_path = f"{path}{{property {json.dumps(key, ensure_ascii=False)}}}"
                    issues.extend(
                        self.validate(key, schema["propertyNames"], resource, key_path)
                    )

            additional = schema.get("additionalProperties", True)
            for key in _stable_property_keys(
                {key: instance[key] for key in set(instance) - evaluated}
            ):
                key_path = _child_path(path, key)
                if additional is False:
                    issues.append(
                        _issue(
                            key_path,
                            "additionalProperties",
                            f"unexpected property {key!r}",
                        )
                    )
                elif isinstance(additional, (dict, bool)):
                    issues.extend(
                        self.validate(instance[key], additional, resource, key_path)
                    )

        if isinstance(instance, list):
            minimum = schema.get("minItems")
            if minimum is not None and len(instance) < minimum:
                issues.append(
                    _issue(
                        path,
                        "minItems",
                        f"expected at least {minimum} items, got {len(instance)}",
                    )
                )
            maximum = schema.get("maxItems")
            if maximum is not None and len(instance) > maximum:
                issues.append(
                    _issue(
                        path,
                        "maxItems",
                        f"expected at most {maximum} items, got {len(instance)}",
                    )
                )
            if schema.get("uniqueItems"):
                for index, value in enumerate(instance):
                    duplicate = next(
                        (
                            prior
                            for prior in range(index)
                            if _json_equal(value, instance[prior])
                        ),
                        None,
                    )
                    if duplicate is not None:
                        issues.append(
                            _issue(
                                f"{path}[{index}]",
                                "uniqueItems",
                                f"duplicates item at index {duplicate}",
                            )
                        )
            if "items" in schema:
                for index, value in enumerate(instance):
                    issues.extend(
                        self.validate(
                            value, schema["items"], resource, f"{path}[{index}]"
                        )
                    )

        if isinstance(instance, str):
            minimum = schema.get("minLength")
            if minimum is not None and len(instance) < minimum:
                issues.append(
                    _issue(
                        path,
                        "minLength",
                        f"expected at least {minimum} characters, got {len(instance)}",
                    )
                )
            maximum = schema.get("maxLength")
            if maximum is not None and len(instance) > maximum:
                issues.append(
                    _issue(
                        path,
                        "maxLength",
                        f"expected at most {maximum} characters, got {len(instance)}",
                    )
                )
            pattern = schema.get("pattern")
            if pattern is not None and re.search(pattern, instance) is None:
                issues.append(
                    _issue(path, "pattern", f"value does not match {pattern!r}")
                )
            if schema.get("format") == "date-time" and not _valid_date_time(instance):
                issues.append(
                    _issue(
                        path,
                        "format",
                        "expected an RFC 3339 date-time with an explicit UTC offset",
                    )
                )

        if isinstance(instance, (int, float)) and not isinstance(instance, bool):
            minimum = schema.get("minimum")
            if minimum is not None and instance < minimum:
                issues.append(
                    _issue(path, "minimum", f"value must be at least {minimum}")
                )
            maximum = schema.get("maximum")
            if maximum is not None and instance > maximum:
                issues.append(
                    _issue(path, "maximum", f"value must be at most {maximum}")
                )

        return issues


def _valid_date_time(value: str) -> bool:
    if _DATE_TIME.fullmatch(value) is None:
        return False
    normalized = value
    if normalized.endswith(("Z", "z")):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() is not None


_SCHEMA_DOCUMENTS = MappingProxyType(_load_schema_documents())
_REGISTRY = _LocalSchemaRegistry(_SCHEMA_DOCUMENTS)
_RUNTIME = _Draft202012Runtime(_REGISTRY)


def validate_schema(
    schema_name: str,
    artifact: Any,
) -> tuple[SchemaValidationIssue, ...]:
    """Return stable issues for ``artifact`` under one canonical schema.

    Unknown schema names raise :class:`UnknownSchemaError` instead of being
    converted into a validation issue.  The artifact is never mutated.
    """

    resource = _REGISTRY.require(schema_name)
    issues = _RUNTIME.validate(artifact, resource.document, resource)
    return tuple(sorted(set(issues)))


def assert_schema_valid(schema_name: str, artifact: Any) -> None:
    """Raise a stable :class:`SchemaValidationError` unless the artifact is valid."""

    issues = validate_schema(schema_name, artifact)
    if issues:
        raise SchemaValidationError(schema_name, issues)


__all__ = [
    "DRAFT_2020_12",
    "SUPPORTED_SCHEMA_NAMES",
    "SchemaRuntimeConfigurationError",
    "SchemaValidationError",
    "SchemaValidationIssue",
    "UnknownSchemaError",
    "assert_schema_valid",
    "validate_schema",
]
