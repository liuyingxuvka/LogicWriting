"""Each public native route command preserves its owner's review contract."""
from pathlib import Path
import importlib
import sys
import pytest
from _common import ValidationError
from tests.v2_support import complete_chain

OWNERS={'academic-writing':'academic','fiction-writing':'fiction','investigation':'investigation','travel-guide':'travel'}

def command(owner):
    route=OWNERS[owner]
    path=str(Path(__file__).resolve().parents[2]/f'skills/logic-writing/routes/{route}/scripts')
    if path not in sys.path:sys.path.insert(0,path)
    return getattr(importlib.import_module(f'validate_{route}_artifact'),f'validate_{route}_artifact')

def request(chain,brief=None):
    return {'review':chain['route_review'],'route_composition':chain['route_composition'],
            'artifact_map':chain['artifact_map'],'shared_writing':chain['shared_writing'],
            'reader_brief':brief or chain['reader_brief']}

@pytest.mark.parametrize('owner',OWNERS)
def test_route_command_reviews_for_its_own_owner(tmp_path,owner):
    chain=complete_chain(tmp_path/'own',owner)
    sibling=next(other for other in OWNERS if other!=owner)
    other=complete_chain(tmp_path/'other',sibling)
    with pytest.raises(ValidationError,match='sibling'):
        command(owner)(request(chain,other['reader_brief']))

@pytest.mark.parametrize('owner',OWNERS)
@pytest.mark.parametrize('passed',[True,False])
def test_failed_route_review_is_partial(tmp_path,owner,passed):
    chain=complete_chain(tmp_path,owner,pass_quality=passed)
    result=command(owner)(request(chain))
    assert result['status']==('current_pass' if passed else 'partial')
    assert result['route_review']['status']==('passed' if passed else 'repair')
