from __future__ import annotations
import argparse, json, os, subprocess, sys
from pathlib import Path

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[1])
    ap.add_argument('--output-dir',type=Path,required=True)
    ap.add_argument('--receipt-dir',type=Path,required=True)
    ap.add_argument('--json',action='store_true')
    args=ap.parse_args(); root=args.root.resolve(); out=args.output_dir.resolve(); rec=args.receipt_dir.resolve()
    out.mkdir(parents=True,exist_ok=True); rec.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy(); env.update({'FLOWGUARD_PROJECT_ROOT':str(root),'FLOWGUARD_MODEL_RECEIPT_ROOT':str(rec)})
    order=['behavior_commitment_ledger','plan_detailing','writer_projection','editorial_disposition','composition_graph','artifact_audit','execution_binding','researchguard_handoff','release_retirement_model','route_and_guard_model','research_packet_model','fiction_route_model','travel_route_model','investigation_route_model','academic_route_model','operation_freshness_closure_model','test_mesh','primary_path_authority','model_test_alignment','reader_artifact_model','development_process_flow','logic_writing_models']
    results=[]
    for model in order:
        od=out/model; od.mkdir(parents=True,exist_ok=True); env['FLOWGUARD_OUTPUT_DIR']=str(od)
        cp=subprocess.run([sys.executable,str(root/'.flowguard'/'verification'/'owners'/model/'run_checks.py')],cwd=root,env=env,text=True,capture_output=True,encoding='utf-8',errors='replace')
        results.append({'model_id':model,'exit_code':cp.returncode,'stdout_tail':cp.stdout[-1000:],'stderr_tail':cp.stderr[-1000:]})
        if cp.returncode!=0: break
    report={'schema_version':'logic-writing.model-regression-topological-run.v1','status':'pass' if results and all(x['exit_code']==0 for x in results) and len(results)==len(order) else 'fail','order':order,'results':results,'receipt_dir':str(rec),'output_dir':str(out)}
    (out/'topological-report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2) if args.json else report['status'])
    return 0 if report['status']=='pass' else 1
if __name__=='__main__': raise SystemExit(main())
