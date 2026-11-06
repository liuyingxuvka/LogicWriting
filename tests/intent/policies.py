"""One real identity decision and existing structural maintenance policies."""
from flowguard.intent import Refused, allow, row, rule, structure_rule
from tests.contract.error_policy import NON_RAISING_HANDLERS, violations, default_violations


@rule('LW_RECORD_IDENTITY', decides='exact_record_identity', fields={'changed': bool},
      source='doc docs/architecture.md "A record fingerprint binds the exact current object"')
def LW_RECORD_IDENTITY(changed):
    return Refused(ValueError, contains='record_fingerprint') if changed else True


LW_RECORD_IDENTITY.rows(
    row(changed=False, expect=True, why='the original object remains bound by its saved digest'),
    row(changed=True, expect=Refused(ValueError, contains='record_fingerprint'),
        why='editing a bound object cannot keep its old identity'))


@LW_RECORD_IDENTITY.home('_common:require_exact_fingerprint')
def record_identity(c, fn):
    record = {'version': 0, 'record_fingerprint':
              'sha256:8a4d9669945dc4f8b42e982d9fd1f7e6bbf70c632969f7986aaad09d9b334a57'}
    if c.changed:
        record['version'] = 1
    fn(record, 'record_fingerprint')
    return True


@structure_rule('LW_ERROR_ROUTES',
    source='doc AGENTS.md "One route per function: when a step fails, the error reaches the caller or is reported with its text"')
def LW_ERROR_ROUTES(graph):
    return violations(graph)


LW_ERROR_ROUTES.allows(*(allow(key, entry.reason) for key, entry in NON_RAISING_HANDLERS.items()))


@structure_rule('LW_DEFAULT_READS',
    source='doc AGENTS.md "new code reads required fields directly"')
def LW_DEFAULT_READS(graph):
    return default_violations(graph)
