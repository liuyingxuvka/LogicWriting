"""Run native reader-chain steps on existing text; never generate prose."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile

from _common import ValidationError, dump_json, load_request, validation_result
from select_route import validate_request as select
from build_reader_brief import validate_request as brief_step
from build_artifact_map import validate_request as map_step
from validate_shared_writing import validate_shared_writing
from audit_reader_output import audit_reader_output
from derive_closure import CLOSURE_INPUT_FILES, derive_closure
from reader_fill import fill_closure_fingerprints
from provider_preflight import provider_command
from show_plan import plan_view

SKILL_ROOT=Path(__file__).resolve().parents[1]
for route_directory in ('academic','fiction','investigation','travel'):
    directory=str(SKILL_ROOT/'routes'/route_directory/'scripts')
    if directory not in sys.path:sys.path.insert(0,directory)
from validate_academic_artifact import validate_academic_artifact
from validate_fiction_artifact import validate_fiction_artifact
from validate_investigation_artifact import validate_investigation_artifact
from validate_travel_artifact import validate_travel_artifact

ROUTES={'academic-writing':validate_academic_artifact,'fiction-writing':validate_fiction_artifact,
        'investigation':validate_investigation_artifact,'travel-guide':validate_travel_artifact}
STEPS=('route','brief','map','binding','audit','review','closure')
OUTPUTS={'route':'route-decision.json','brief':'reader-brief.json','map':'artifact-map.json',
         'binding':'shared-writing-result.json','audit':'audit.json','review':'route-review-result.json','closure':'closure.json'}


def _refresh(request,folder):
    research=request.get('research_folder')
    if research:
        target=Path(request.get('research_status') or folder/'research-status.json')
        command=provider_command('researchguard')
        with tempfile.TemporaryDirectory(prefix='lw-refresh-research-') as directory:
            output=Path(directory)/'report.json'
            result=subprocess.run([*command,'status',str(research),'--json','--output',str(output)],capture_output=True,text=True)
            if result.returncode not in (0,1) or not output.is_file():
                raise ValidationError('ResearchGuard refresh failed: '+(result.stderr or result.stdout).strip())
            document=json.loads(output.read_text())
            if not isinstance(document,dict) or 'input_digests' not in document:
                raise ValidationError('Install ResearchGuard >= 0.5.16 to refresh input digests')
            target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(output.read_bytes())
        request['research_status']=str(target)
    route=request.get('route_composition') or {}
    world=route.get('world_contract')
    if world:
        command=provider_command('worldguard')
        result=subprocess.run([*command,'check','--contract',str(world)],capture_output=True,text=True)
        if result.returncode not in (0,1,2):raise ValidationError('WorldGuard refresh failed: '+result.stderr.strip())
        document=json.loads(result.stdout)
        if not isinstance(document,dict) or 'input_digests' not in document:
            raise ValidationError('Install WorldGuard >= 0.7.23 beside Logic Writing to refresh input digests')
        (folder/'worldguard-check.json').write_text(result.stdout,encoding='utf-8')


def _failure(step,payload):
    errors=payload.get('errors') or []
    findings=payload.get('findings') or payload.get('reader_audit',{}).get('findings') or []
    provider_reasons=[str(row['reason']) for row in payload.get('closure',{}).get('provider_checks',[]) if not row.get('passed') and row.get('reason')]
    reason=str(errors[0]) if errors else str(findings[0].get('code')) if findings else provider_reasons[0] if provider_reasons else str(payload.get('status','failed'))
    return {'step':step,'code':reason.split(':',1)[0],'message':reason}


def _finish(folder,results,first,code):
    brief=results.get('brief',{}).get('reader_brief')
    amap=results.get('map',{}).get('artifact_map')
    binding=results.get('shared_writing',{})
    added=[]
    try:
        request={'reader_brief':brief,'artifact_map':amap} if brief else load_request(folder/'brief-request.json')
        if binding.get('shared_writing'):request['shared_writing']=binding['shared_writing']
        elif binding:
            request.update(load_request(folder/'shared-writing.json'));request['_binding_blocked']=binding
        view=plan_view(request,input_path=folder/'closure-input.json')
        summary=view['summary'];added=view['added_by_writer']
    except (OSError,ValueError,KeyError,TypeError):
        summary='units: unavailable; chain: '+('not_run' if first is None else first['step']+' blocked')
    return {'status':'passed' if code==0 else 'failed','exit_code':code,'results':results,'first_failure':first,'summary':summary,'added_by_writer':added}


def run_chain(folder, *, until='closure', refresh_providers=False):
    folder=Path(folder).expanduser().resolve()
    if until not in STEPS:raise ValueError('unknown chain step: '+str(until))
    results={}
    if not folder.is_dir():return _finish(folder,results,{'step':'input','code':'input_unreadable','message':'folder is not readable: '+str(folder)},2)
    brief_request=None
    for step in STEPS:
        try:
            if step=='route':payload=select(load_request(folder/'route-request.json'))
            elif step=='brief':
                brief_request=load_request(folder/'brief-request.json')
                if refresh_providers:
                    try:_refresh(brief_request,folder)
                    except (OSError,ValueError) as exc:
                        return _finish(folder,results,{'step':'providers','code':'provider_refresh_failed','message':str(exc)},2)
                payload=brief_step(brief_request)
            elif step=='map':
                path=folder/'map-request.json'
                request=load_request(path) if path.is_file() else {'artifact_path':str(folder/'piece.md'),'map_id':'map:'+results['brief']['reader_brief']['brief_id'],
                    'language':results['brief']['reader_brief']['reader_intent']['language'],'artifact_format':results['brief']['reader_brief']['reader_intent']['artifact_format']}
                payload=map_step(request)
            elif step=='binding':payload=validate_shared_writing(load_request(folder/'shared-writing.json'))
            elif step=='audit':
                path=folder/'audit-request.json'
                request=load_request(path) if path.is_file() else {'audit_id':'audit:'+results['brief']['reader_brief']['brief_id'],
                    'reader_brief':results['brief']['reader_brief'],'artifact_map':results['map']['artifact_map'],
                    'shared_writing':results['shared_writing']['shared_writing']}
                payload=audit_reader_output(request)
            elif step=='review':
                owner=results['route']['route_decision']['final_owner']
                payload=ROUTES[owner](load_request(folder/'route-review.json'))
            else:
                request=fill_closure_fingerprints(load_request(folder/'closure-input.json',defaults=CLOSURE_INPUT_FILES))
                closed=derive_closure(request)['closure'];payload=validation_result(status=closed['status'],closure=closed)
            dump_json(payload,folder/OUTPUTS[step])
            results['shared_writing' if step=='binding' else step]=payload
        except (OSError,json.JSONDecodeError) as exc:
            payload=validation_result(status='blocked',errors=[str(exc)]);dump_json(payload,folder/OUTPUTS[step]);results['shared_writing' if step=='binding' else step]=payload
            return _finish(folder,results,_failure(step,payload),2)
        except (ValidationError,ValueError,KeyError,TypeError) as exc:
            payload=validation_result(status='blocked',errors=[str(exc)]);dump_json(payload,folder/OUTPUTS[step]);results['shared_writing' if step=='binding' else step]=payload
            return _finish(folder,results,_failure(step,payload),1)
        if payload.get('status') not in {'current_pass','passed'}:
            return _finish(folder,results,_failure(step,payload),1)
        if step=='closure' and any(row.get('required') and not row.get('passed') for row in payload['closure'].get('provider_checks',[])):
            return _finish(folder,results,_failure(step,payload),1)
        if step==until:return _finish(folder,results,None,0)
    raise AssertionError('unreachable chain step')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("folder")
    parser.add_argument("--until", choices=STEPS, default="closure")
    parser.add_argument("--refresh-providers", action="store_true")
    args = parser.parse_args()
    result = run_chain(args.folder, until=args.until, refresh_providers=args.refresh_providers)
    print(result["summary"])
    for row in result['added_by_writer']:
        print(f"added by the writer: {row['content_unit_id']}: {row['text']}")
    if result["first_failure"]:
        row = result["first_failure"]
        message = row["message"]
        if not message.startswith(row["code"] + ":"):
            message = row["code"] + ": " + message
        if "research_report_stale:" in message or "world_report_stale:" in message:
            message += " (saved report is from other inputs; run with --refresh-providers)"
        print(f"first failure: {row['step']}: {message}")
    return result["exit_code"]


if __name__=='__main__':raise SystemExit(main())
