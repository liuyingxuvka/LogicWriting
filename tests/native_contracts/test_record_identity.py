"""The original real edit/refuse/restore/check lifecycle, without a model runner."""
import pytest
from _common import require_exact_fingerprint, ValidationError


@pytest.mark.rule('LW_RECORD_IDENTITY')
def test_real_exact_record_identity_native_contract():
    record = {'version': 0, 'record_fingerprint':
              'sha256:8a4d9669945dc4f8b42e982d9fd1f7e6bbf70c632969f7986aaad09d9b334a57'}
    assert require_exact_fingerprint(record, 'record_fingerprint') is None
    record['version'] = 1
    with pytest.raises(ValidationError, match='record_fingerprint does not bind the exact current object'):
        require_exact_fingerprint(record, 'record_fingerprint')
    record['version'] = 0
    assert require_exact_fingerprint(record, 'record_fingerprint') is None
