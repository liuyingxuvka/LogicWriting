"""Stateless references to rows in an existing saved provider report."""
from __future__ import annotations

import re
from urllib.parse import quote, unquote

from _common import ValidationError


PREFIX = 'pg-report://'


def report_row_ref(path, row_id):
    """Use an existing provider_reports path, escaped independently of the row ID."""
    return PREFIX + quote(str(path), safe='') + '#' + quote(row_id, safe='')


def split_report_row_ref(value):
    """Return the two decoded fields, or None for an ordinary legacy identifier."""
    if not value.startswith(PREFIX):
        return None
    path, separator, row_id = value[len(PREFIX):].partition('#')
    if not separator or not path or not row_id or '#' in row_id or any(
            re.search(r'%(?![0-9a-fA-F]{2})', part) for part in (path, row_id)):
        raise ValidationError('invalid qualified PhysicsGuard row reference: ' + value)
    try:
        return unquote(path, errors='strict'), unquote(row_id, errors='strict')
    except UnicodeError as exc:
        raise ValidationError('qualified PhysicsGuard row reference is not UTF-8: ' + value) from exc


def rewrite_row_ref(value, transform):
    parts = split_report_row_ref(value)
    return report_row_ref(transform(parts[0]), parts[1]) if parts else value


def rewrite_model_row_paths(value, transform):
    """Change only report paths inside model_row_ids, never prose or other IDs."""
    if isinstance(value, dict):
        for key, child in value.items():
            if key == 'model_row_ids':
                # The schema owns malformed values; path resolution must not
                # turn its useful rejection into an AttributeError first.
                if isinstance(child, list):
                    value[key] = [rewrite_row_ref(identity, transform) if isinstance(identity, str) else identity
                                  for identity in child]
            else:
                rewrite_model_row_paths(child, transform)
    elif isinstance(value, list):
        for child in value:
            rewrite_model_row_paths(child, transform)
