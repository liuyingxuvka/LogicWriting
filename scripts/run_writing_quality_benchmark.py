"""Run the local LogicWriting writer/judge benchmark.

With no backend this command emits an unavailable receipt and never invents a
score.  With ``--backend-plan`` it starts the pinned local Codex CLI through
``LocalCodexBackend`` and records every writer, artifact, pair judge, and
aggregation input below one owner run root.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = ROOT / "skills" / "logic-writing" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from _common import ValidationError, fingerprint, fingerprint_text  # noqa: E402
from execution_record_resolver import LocalExecutionRecordResolver  # noqa: E402
from local_execution_backend import (  # noqa: E402
    DEFAULT_CLI_SHA256,
    DEFAULT_CLI_VERSION,
    DEFAULT_MODEL_ID,
    DEFAULT_REASONING_EFFORT,
    LocalCodexBackend,
)
from reader_execution import dispatch_judge, dispatch_writer, validate_execution_record  # noqa: E402
from reader_pipeline import build_artifact_map  # noqa: E402


CASE_COUNT = 12
REPEATS = 2
VERSIONS = ("baseline", "repaired")
CASE_ORDER = ("I01", "A01", "F01", "T01", "I02", "A02", "F02", "T02", "I03", "A03", "F03", "T03")
DIMENSIONS = (
    "clarity", "coherence", "naturalness", "reader_fit", "genre_fit",
    "content_fidelity", "instruction_fidelity", "structure_fidelity",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _bytes_fp(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _material_files(cases_dir: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for path in sorted(cases_dir.glob("materials-*.json")):
        value = _read_json(path)
        if not isinstance(value, dict) or not isinstance(value.get("records"), list):
            raise ValueError(f"material pack is invalid: {path.name}")
        file_fp = _bytes_fp(path.read_bytes())
        for row in value["records"]:
            if not isinstance(row, dict) or not isinstance(row.get("id"), str) or not isinstance(row.get("text"), str):
                raise ValueError(f"material record is invalid: {path.name}")
            material_id = row["id"]
            if material_id in result:
                raise ValueError(f"duplicate material id: {material_id}")
            result[material_id] = {
                **row,
                "source_file": path.name,
                "source_file_fingerprint": file_fp,
                "synthetic": bool(value.get("synthetic", False)),
            }
    if len(result) != 26:
        raise ValueError(f"expected 26 frozen material records, found {len(result)}")
    return result


def _load_cases(cases_dir: Path) -> list[dict[str, Any]]:
    """Load the canonical manifest; old per-case files remain fallback only."""

    manifest_path = cases_dir / "case-manifest.json"
    if manifest_path.is_file():
        manifest = _read_json(manifest_path)
        if not isinstance(manifest, list) or len(manifest) != CASE_COUNT:
            raise ValueError("case-manifest.json must contain exactly twelve cases")
        materials = _material_files(cases_dir)
        cases: list[dict[str, Any]] = []
        seen: set[str] = set()
        manifest_fp = _bytes_fp(manifest_path.read_bytes())
        for row in manifest:
            if not isinstance(row, dict) or not isinstance(row.get("case_id"), str):
                raise ValueError("case manifest row has no case_id")
            case_id = row["case_id"]
            if case_id in seen:
                raise ValueError(f"duplicate case id: {case_id}")
            seen.add(case_id)
            refs = row.get("material_refs")
            if not isinstance(refs, list) or not refs:
                raise ValueError(f"case {case_id} has no material_refs")
            selected: list[dict[str, Any]] = []
            for ref in refs:
                if not isinstance(ref, dict) or not isinstance(ref.get("id"), str):
                    raise ValueError(f"case {case_id} has an invalid material ref")
                material = materials.get(ref["id"])
                if material is None or material["source_file"] != ref.get("path"):
                    raise ValueError(f"case {case_id} has a foreign or missing material {ref.get('id')}")
                selected.append(material)
            cases.append({**row, "materials": [item["id"] for item in selected], "material_records": selected, "case_manifest_fingerprint": manifest_fp})
        return cases
    cases = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(cases_dir.glob("*.json"))]
    if len(cases) != CASE_COUNT or any(not isinstance(case, dict) or not case.get("materials") for case in cases):
        raise ValueError("legacy case inputs must contain twelve cases with materials")
    return cases


def _load_frozen_inputs(cases_dir: Path) -> tuple[list[dict[str, Any]], str, str, str, dict[str, str]]:
    cases = _load_cases(cases_dir)
    rubric_path = cases_dir / "judge-rubric.md"
    if not rubric_path.is_file():
        raise ValueError("judge-rubric.md is required")
    manifest_path = cases_dir / "input-manifest.json"
    input_manifest_fp = _bytes_fp(manifest_path.read_bytes()) if manifest_path.is_file() else fingerprint({"cases": cases})
    material_files = {path.name: _bytes_fp(path.read_bytes()) for path in sorted(cases_dir.glob("materials-*.json"))}
    source_manifest_fp = fingerprint({
        "input_manifest": input_manifest_fp,
        "case_manifest": _bytes_fp((cases_dir / "case-manifest.json").read_bytes()) if (cases_dir / "case-manifest.json").is_file() else None,
        "materials": material_files,
        "rubric": _bytes_fp(rubric_path.read_bytes()),
    })
    return cases, rubric_path.read_text(encoding="utf-8"), input_manifest_fp, source_manifest_fp, material_files


def _resolve_backend(spec: str | None) -> Callable[..., Any] | None:
    if not spec:
        return None
    if ":" not in spec:
        raise ValueError("backend must use module:function syntax")
    module_name, function_name = spec.split(":", 1)
    function = getattr(importlib.import_module(module_name), function_name, None)
    if not callable(function):
        raise ValueError(f"backend function is not callable: {spec}")
    return function


def _writer_prompt(case: Mapping[str, Any], version: str) -> str:
    materials = "\n".join(f"[{row['id']}] {row['text']}" for row in case["material_records"])
    route_focus = {
        "investigation": (
            "调查/简报要先给读者可执行的回答，再用最少但足够的证据推进判断；"
            "每个限制都要说明它改变了结论、范围或下一步什么，不要把资料目录逐项复述。"
            "按任务声明的篇幅单位做最后一次长度核对，超出或不足都要用有信息作用的删改解决。"
        ),
        "academic-writing": (
            "学术文本要让中心论点统领证据：每一段都应有新的论证工作，并说明证据如何支持、"
            "限制如何收紧解释；表格或标题只在任务要求或确有功能时使用。"
            "同一证据的研究含义只在一个最合适的位置完整展开，其他位置只承担新的论证工作；"
            "条件句必须准确表达未知项，不能把已确认的条件写成未知，也不能把未知补成事实。"
        ),
        "fiction-writing": (
            "小说要让信息按视角和场景时序自然出现，用可见的动作、物件、声音和关系变化承载因果；"
            "不要替人物或作者解释主题，不要提前泄露受限信息，也不要用一句话抹平代价。"
            "分别核对读者此刻能知道什么、视角人物此刻能知道什么；若揭示被禁止，不能用对白、动作结果或"
            "紧邻反应间接确认同一事实。开门、救援等关键动作必须有与已知条件相容的可见来源，不能让受限物件"
            "既被判定无效又无来源地完成动作。"
        ),
        "travel-guide": (
            "行程要围绕旅客当天的体力、时间和天气决策组织；先说明安排为何可行，再给出触发条件和可执行备用，"
            "未知的开放时间、路线、票价或无障碍属性必须写成待核实，不能补造。"
            "把每一段必要接驳、连续步行上限和实际休息地点逐一接回默认方案；时间表的比较理由只能使用已知时刻，"
            "未知班次必须转成出发前核查与明确替代方案。只改任务要求的受影响安排，不为显得全面而扩展风险清单。"
        ),
    }.get(str(case.get("route")), "")
    if version == "repaired":
        editorial = (
            "请在内部完成一次完整的‘读者契约→证据/事实核对→论证或场景图→成稿→反向检查’，但不要输出这些步骤。"
            "先确定一个能回答任务的中心判断或场景推进，再为每个正文单元明确：它承接什么、改变读者什么判断、"
            "为下一单元提供什么。只保留会改变理解、决定、行动或情节的材料，把数字、限制、反例和备用方案放在"
            "它们真正改变推理的位置。成稿完成后逐项核对语言、篇幅、格式、事实、因果强度、视角/旅行条件和所有禁项；"
            "删掉无新信息的重复限制、机械的对称转折、泛化的安全措辞、资料卡片式并列、作者自我说明和内部流程词。"
            "用自然的连续段落推进，让每个段落有明确功能和下一步去向；不要为了显得严谨堆叠‘这不意味着’、"
            "‘尽管如此’或‘需要指出’，不要解释你的写作流程。"
            "修订版必须在不牺牲事实、边界、格式或体裁的前提下，真正改善主线推进和读者可用性；"
            "不要声明自己完成了检查，也不要提到存在另一版稿件。"
            + route_focus
        )
    else:
        editorial = (
            "直接完成用户要求；使用材料中的相关事实，遵守约束，只输出成稿，不输出分析、评分或执行记录。"
        )
    return (
        "你正在本机完成一篇最终成稿。只能使用下面显式给出的任务、约束和材料；不要读取文件、运行命令、调用工具或寻找其它资料。"
        "不要提到这些指令、版本、模型或内部流程。\n\n"
        f"任务：{case['task']}\n约束：{case['constraints']}\n\n冻结材料：\n{materials}\n\n"
        f"写作要求：{editorial}\n返回完整成稿，不要包裹 Markdown 代码围栏，不要附加自评。"
    )


def _judge_prompt(case: Mapping[str, Any], rubric_text: str, pair: list[dict[str, Any]]) -> str:
    materials = "\n".join(f"[{row['id']}] {row['text']}" for row in case["material_records"])
    articles = "\n\n".join(f"===== {row['anonymous_label']} =====\n{row['artifact_text']}" for row in pair)
    schema_hint = (
        '{"schema_version":"logic-writing.local-pair-judgment.v1","judgments":[{"anonymous_label":"X","reverse_outline":[],"obligation_results":[],"scores":{"clarity":1,"coherence":1,"naturalness":1,"reader_fit":1,"genre_fit":1,"content_fidelity":1,"instruction_fidelity":1,"structure_fidelity":1},"defects":[],"strengths":[],"required_repairs":[]},{"anonymous_label":"Y","reverse_outline":[],"obligation_results":[],"scores":{"clarity":1,"coherence":1,"naturalness":1,"reader_fit":1,"genre_fit":1,"content_fidelity":1,"instruction_fidelity":1,"structure_fidelity":1},"defects":[],"strengths":[],"required_repairs":[]}],"preference":"X","preference_reason":"..."}'
    )
    return (
        "你是本次成文质量评审者。你没有参与这两篇稿件的生成。只能使用本提示中给出的任务、约束、冻结材料、评分规则和匿名稿件；"
        "不要读取文件、运行命令、调用工具，不要猜测稿件版本。先为X和Y各写实际反向提纲，再核对事实和约束，最后评分。"
        f"每个正文段或功能区域必须能回指稿件中的真实文字。只返回一个 JSON 对象，格式示例：{schema_hint}。"
        "scores 必须是1到5的整数；preference 只能是 X、Y、tie 或 unable；不得添加作者/版本信息。\n\n"
        f"用户任务：{case['task']}\n约束：{case['constraints']}\n\n冻结材料：\n{materials}\n\n"
        f"评分规则：\n{rubric_text}\n\n匿名稿件：\n{articles}"
    )


def _pair_writer_input_fingerprint(pair: list[Mapping[str, Any]]) -> str:
    """Fingerprint the two writer inputs in a JSON-serializable order."""

    return fingerprint(sorted(str(row["writer_input_fingerprint"]) for row in pair))


def _execute_judge_job(
    *,
    case: Mapping[str, Any],
    repeat: int,
    judge_index: int,
    order: tuple[Mapping[str, Any], Mapping[str, Any]],
    rubric_text: str,
    cases_dir: Path,
    judge_dir: Path,
    local_backend: LocalCodexBackend | None,
    backend: Callable[..., Any] | None,
    resolver: LocalExecutionRecordResolver | None,
) -> dict[str, Any]:
    pair: list[dict[str, Any]] = []
    for label, writer in zip(("X", "Y"), order, strict=True):
        pair.append({
            "anonymous_label": label,
            "artifact_fingerprint": writer["artifact_fingerprint"],
            "writer_run_id": writer["record"]["run_id"],
            "writer_context_id": writer["record"]["context_id"],
            "writer_input_fingerprint": writer["record"]["input_writer_input_fingerprint"],
            "artifact_path": writer["artifact_path"],
            "artifact_text": writer["artifact_text"],
        })
    prompt = _judge_prompt(case, rubric_text, pair)
    intent, _ = _request_metadata(case, "judge", repeat, prompt)
    request = {
        "request_id": f"judge:{case['case_id']}:{repeat}:{judge_index}",
        "run_id": f"judge:{case['case_id']}:{repeat}:{judge_index}",
        "parent_orchestrator_run_id": "orchestrator:logic-writing-quality",
        "reader_intent_fingerprint": fingerprint(intent),
        "writer_input_fingerprint": _pair_writer_input_fingerprint(pair),
        "rubric_fingerprint": _bytes_fp((cases_dir / "judge-rubric.md").read_bytes()),
        "evaluation_mode": "pair",
        "pair_inputs": [
            {key: row[key] for key in ("anonymous_label", "artifact_fingerprint", "writer_run_id", "writer_context_id", "writer_input_fingerprint")}
            for row in pair
        ],
        "writer_context_ids": [row["writer_context_id"] for row in pair],
        "settings": local_backend.settings() if local_backend else {},
        "prompt": prompt,
    }
    row: dict[str, Any] = {
        "case_id": case["case_id"],
        "repeat": repeat,
        "judge_index": judge_index,
        "pair_order": ["baseline" if item is order[0] else "repaired" for item in order],
        "request": request,
        "request_fingerprint": fingerprint(request),
        "status": "failed",
    }
    try:
        if local_backend is not None:
            dispatched = dispatch_judge(request, local_backend)
            row["dispatch_status"] = dispatched.get("status")
            record = dispatched.get("record")
            row["record"] = record
            if isinstance(record, Mapping) and record.get("terminal_status") == "completed" and resolver is not None:
                validate_execution_record(record, resolver)
                raw_path = (local_backend.run_root / Path(str(record["raw_output_locator"]))).resolve()
                raw_text = raw_path.read_text(encoding="utf-8")
                parsed = _validate_judgment_payload(_extract_json(raw_text))
                row.update({"status": "completed", "raw_output": raw_text, "judgment": parsed, "judgment_fingerprint": fingerprint(parsed)})
        elif backend is not None:
            response = backend({"case": case, "pair": pair, "prompt": prompt})
            row["response"] = response
            row["status"] = "completed" if isinstance(response, Mapping) else "failed"
    except (OSError, ValueError, ValidationError) as exc:
        row["error"] = str(exc)
    path = judge_dir / str(case["case_id"]) / str(repeat) / str(judge_index) / "judge.json"
    _write_json(path, row)
    return row


def _extract_json(text: str) -> dict[str, Any]:
    candidate = text.strip()
    if "```" in candidate:
        chunks = candidate.split("```")
        candidate = next((chunk.strip().removeprefix("json").strip() for chunk in chunks if "{" in chunk), candidate)
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("judge output has no JSON object")
        value = json.loads(candidate[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError("judge output is not an object")
    return value


def _validate_judgment_payload(value: Mapping[str, Any]) -> dict[str, Any]:
    if value.get("schema_version") != "logic-writing.local-pair-judgment.v1":
        raise ValueError("judge schema_version is not current")
    judgments = value.get("judgments")
    labels = {row.get("anonymous_label") for row in judgments if isinstance(row, dict)} if isinstance(judgments, list) else set()
    if not isinstance(judgments, list) or len(judgments) != 2 or labels != {"X", "Y"}:
        raise ValueError("judge output must contain exactly X and Y judgments")
    if value.get("preference") not in {"X", "Y", "tie", "unable"}:
        raise ValueError("judge preference is invalid")
    for row in judgments:
        if not isinstance(row, dict) or not isinstance(row.get("scores"), dict):
            raise ValueError("judge judgment is missing scores")
        scores = row["scores"]
        if set(scores) != set(DIMENSIONS) or any(not isinstance(scores[key], int) or not 1 <= scores[key] <= 5 for key in DIMENSIONS):
            raise ValueError("judge scores must contain the eight 1-5 dimensions")
        if not isinstance(row.get("reverse_outline"), list) or not isinstance(row.get("defects"), list) or not isinstance(row.get("required_repairs"), list):
            raise ValueError("judge judgment is missing outline/defect arrays")
    return dict(value)


def _request_metadata(case: Mapping[str, Any], version: str, repeat: int, prompt: str) -> tuple[dict[str, Any], dict[str, Any]]:
    intent = {
        "case_id": case["case_id"], "route": case["route"], "language": case["language"],
        "task": case["task"], "constraints": case["constraints"], "material_refs": case["material_refs"], "rubric_ref": case["rubric_ref"],
    }
    writer_input = {
        "case_id": case["case_id"], "version": version, "repeat": repeat,
        "task": case["task"], "constraints": case["constraints"],
        "materials": [{"id": row["id"], "text": row["text"]} for row in case["material_records"]],
        "prompt_fingerprint": fingerprint_text(prompt),
    }
    return intent, writer_input


def _load_plan(plan_path: Path | None, *, source_manifest_fp: str) -> dict[str, Any]:
    if plan_path is None:
        return {
            "schema_version": "logic-writing.local-backend-plan.v1", "backend_id": "local-codex:0.153.4:gpt-6-astra:xhigh",
            "model_id": DEFAULT_MODEL_ID, "reasoning_effort": DEFAULT_REASONING_EFFORT, "cli_version": DEFAULT_CLI_VERSION,
            "cli_sha256": DEFAULT_CLI_SHA256, "timeout_seconds": 900, "max_attempts": 1,
            "source_manifest_fingerprint": source_manifest_fp,
        }
    value = _read_json(plan_path)
    if not isinstance(value, dict) or value.get("schema_version") != "logic-writing.local-backend-plan.v1":
        raise ValueError("local backend plan schema is not current")
    if value.get("model_id") != DEFAULT_MODEL_ID or value.get("reasoning_effort") != DEFAULT_REASONING_EFFORT:
        raise ValueError("local backend plan does not use the frozen model/settings")
    return value


def _unavailable_result(plan: Mapping[str, Any], *, source_manifest_fp: str, output_dir: Path, reason: str) -> dict[str, Any]:
    result = {
        "schema_version": "logic-writing.writing-quality-run-result.v2", "benchmark_id": "logic-writing-real-quality-12x2x2",
        "status": "not_run", "terminal_reason": reason, "quality_claim_status": "incomplete",
        "planned_writer_count": CASE_COUNT * REPEATS * len(VERSIONS), "planned_judge_count": CASE_COUNT * REPEATS * 2,
        "planned_execution_count": CASE_COUNT * REPEATS * (len(VERSIONS) + 2), "actual_writer_count": 0, "actual_judge_count": 0,
        "actual_execution_count": 0, "successful_artifact_count": 0, "backend_id": plan.get("backend_id"),
        "source_manifest_fingerprint": source_manifest_fp, "created_at": _now(),
        "claim_boundary": "No local writer or independent judge ran; this receipt contains no quality score.",
    }
    _write_json(output_dir / "run_result.json", result)
    return result


def _copy_artifact(capture_root: Path, record: Mapping[str, Any], target: Path) -> tuple[Path, dict[str, Any]]:
    locator = record.get("raw_output_locator")
    if not isinstance(locator, str):
        raise ValidationError("writer execution has no raw output locator")
    source = (capture_root / Path(locator)).resolve()
    try:
        source.relative_to(capture_root.resolve())
    except ValueError as exc:
        raise ValidationError("writer output escaped capture root") from exc
    if not source.is_file() or source.is_symlink():
        raise ValidationError("writer output capture is missing or symlinked")
    data = source.read_bytes()
    if not data.strip() or _bytes_fp(data) != record.get("raw_output_fingerprint"):
        raise ValidationError("writer output bytes do not match execution record")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    artifact_map = build_artifact_map(target, map_id=f"artifact:{record['run_id']}", language="und")
    return target, artifact_map


def _execute_writer_job(
    *,
    case: Mapping[str, Any],
    repeat: int,
    version: str,
    writer_dir: Path,
    local_backend: LocalCodexBackend | None,
    backend: Callable[..., Any] | None,
    resolver: LocalExecutionRecordResolver | None,
) -> dict[str, Any]:
    """Execute one writer job and persist only its own artifact directory.

    Writer jobs are independent: every job has a unique logical run id and
    output path.  Keeping all mutable state inside this function makes it safe
    to run local Codex writers concurrently while retaining the same row shape
    and byte-level capture validation as the serial path.
    """
    prompt = _writer_prompt(case, version)
    intent, writer_input = _request_metadata(case, version, repeat, prompt)
    request = {
        "request_id": f"writer:{case['case_id']}:{repeat}:{version}",
        "run_id": f"writer:{case['case_id']}:{repeat}:{version}",
        "parent_orchestrator_run_id": "orchestrator:logic-writing-quality",
        "reader_intent_fingerprint": fingerprint(intent),
        "writer_input_fingerprint": fingerprint(writer_input),
        "settings": local_backend.settings() if local_backend else {},
        "prompt": prompt,
    }
    row: dict[str, Any] = {
        "case_id": case["case_id"],
        "repeat": repeat,
        "version": version,
        "request": request,
        "request_fingerprint": fingerprint(request),
        "status": "failed",
        "artifact_path": None,
        "artifact_fingerprint": None,
    }
    try:
        if local_backend is not None:
            dispatched = dispatch_writer(request, local_backend)
            row["dispatch_status"] = dispatched.get("status")
            record = dispatched.get("record")
            row["record"] = record
            if isinstance(record, Mapping) and record.get("terminal_status") == "completed" and resolver is not None:
                validate_execution_record(record, resolver)
                artifact_path, artifact_map = _copy_artifact(
                    local_backend.run_root,
                    record,
                    writer_dir / str(case["case_id"]) / str(repeat) / version / "artifact.md",
                )
                _write_json(
                    writer_dir / str(case["case_id"]) / str(repeat) / version / "artifact-map.json",
                    artifact_map,
                )
                row.update({
                    "status": "completed",
                    "artifact_path": artifact_path.relative_to(writer_dir.parent.parent).as_posix(),
                    "artifact_fingerprint": artifact_map["artifact_fingerprint"],
                    "artifact_map_fingerprint": artifact_map["map_fingerprint"],
                    "artifact_text": artifact_path.read_text(encoding="utf-8"),
                })
        elif backend is not None:
            response = backend({"case": case, "version": version, "repeat": repeat, "prompt": prompt})
            row["response"] = response
            row["status"] = "completed" if isinstance(response, Mapping) and response.get("artifact_fingerprint") else "failed"
    except (OSError, ValueError, ValidationError) as exc:
        row["error"] = str(exc)
    row_path = writer_dir / str(case["case_id"]) / str(repeat) / version / "writer.json"
    _write_json(row_path, row)
    return row


def run_benchmark(
    root: Path,
    *,
    output_dir: Path,
    cases_dir: Path | None = None,
    backend: Callable[..., Any] | None = None,
    backend_id: str | None = None,
    backend_plan: Path | None = None,
    run_writers: bool = True,
    run_judges: bool = True,
    summarize_only: bool = False,
) -> dict[str, Any]:
    root = root.resolve()
    cases_dir = (cases_dir or root / "tests/fixtures/writing_quality").resolve()
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cases, rubric_text, input_manifest_fp, source_manifest_fp, material_files = _load_frozen_inputs(cases_dir)
    by_case_id = {str(case["case_id"]): case for case in cases}
    if set(by_case_id) != set(CASE_ORDER):
        raise ValueError("canonical case manifest does not contain the required twelve case IDs")
    cases = [by_case_id[case_id] for case_id in CASE_ORDER]
    plan = _load_plan(backend_plan, source_manifest_fp=source_manifest_fp)
    plan.update({
        "schema_version": "logic-writing.writing-quality-run.v2", "benchmark_id": "logic-writing-real-quality-12x2x2",
        "evidence_mode": "real_execution", "case_count": CASE_COUNT, "repeats_per_version": REPEATS,
        "versions": list(VERSIONS), "planned_writer_count": CASE_COUNT * REPEATS * len(VERSIONS),
        "planned_judge_count": CASE_COUNT * REPEATS * 2, "planned_execution_count": CASE_COUNT * REPEATS * (len(VERSIONS) + 2),
        "rubric_fingerprint": _bytes_fp((cases_dir / "judge-rubric.md").read_bytes()), "input_manifest_fingerprint": input_manifest_fp,
        "source_manifest_fingerprint": source_manifest_fp, "material_file_fingerprints": material_files,
        "case_order": [case["case_id"] for case in cases], "created_at": _now(),
    })
    _write_json(output_dir / "benchmark_plan.json", plan)
    _write_json(output_dir / "case_requests.json", [{"case": case, "case_fingerprint": fingerprint(case)} for case in cases])
    if summarize_only:
        return summarize_run(output_dir)
    if backend is None and backend_plan is None:
        return _unavailable_result(plan, source_manifest_fp=source_manifest_fp, output_dir=output_dir, reason="execution_provider_unavailable")
    local_backend: LocalCodexBackend | None = None
    resolver: LocalExecutionRecordResolver | None = None
    if backend_plan is not None:
        local_backend = LocalCodexBackend(
            output_dir / "attempts", model_id=str(plan["model_id"]), reasoning_effort=str(plan["reasoning_effort"]),
            timeout_seconds=int(plan.get("timeout_seconds", 900)), expected_cli_version=str(plan.get("cli_version", DEFAULT_CLI_VERSION)),
            expected_executable_sha256=str(plan.get("cli_sha256", DEFAULT_CLI_SHA256)),
        )
        resolver = LocalExecutionRecordResolver(local_backend.run_root, expected_cli_version=local_backend.cli_version, expected_cli_sha256=local_backend.executable_sha256, expected_backend_id=local_backend.backend_id)
    writers: list[dict[str, Any]] = []
    writer_index: dict[tuple[str, int, str], dict[str, Any]] = {}
    writer_dir = output_dir / "artifacts" / "writers"
    if run_writers:
        jobs: list[dict[str, Any]] = []
        case_position = {case["case_id"]: index for index, case in enumerate(cases)}
        for repeat in range(1, REPEATS + 1):
            sequence = cases if repeat == 1 else list(reversed(cases))
            for case_index, case in enumerate(sequence):
                version_order = VERSIONS if (case_index + repeat) % 2 else tuple(reversed(VERSIONS))
                for version in version_order:
                    jobs.append({
                        "case": case,
                        "repeat": repeat,
                        "version": version,
                        "order": (repeat, case_position[case["case_id"]], version),
                    })
        writer_workers = max(1, min(int(plan.get("concurrency", 1)), len(jobs) or 1))
        if local_backend is not None and writer_workers > 1:
            with ThreadPoolExecutor(max_workers=writer_workers, thread_name_prefix="logic-writing-writer") as executor:
                futures = [
                    executor.submit(
                        _execute_writer_job,
                        case=job["case"],
                        repeat=job["repeat"],
                        version=job["version"],
                        writer_dir=writer_dir,
                        local_backend=local_backend,
                        backend=backend,
                        resolver=resolver,
                    )
                    for job in jobs
                ]
                rows = [future.result() for future in futures]
        else:
            rows = [
                _execute_writer_job(
                    case=job["case"],
                    repeat=job["repeat"],
                    version=job["version"],
                    writer_dir=writer_dir,
                    local_backend=local_backend,
                    backend=backend,
                    resolver=resolver,
                )
                for job in jobs
            ]
        for row in sorted(rows, key=lambda item: (int(item.get("repeat", 0)), case_position.get(str(item.get("case_id")), 999), str(item.get("version")))):
            writers.append(row)
            writer_index[(str(row["case_id"]), int(row["repeat"]), str(row["version"]))] = row
    else:
        for path in sorted(writer_dir.glob("**/writer.json")):
            row = _read_json(path)
            if isinstance(row, dict):
                writers.append(row)
                writer_index[(str(row.get("case_id")), int(row.get("repeat", 0)), str(row.get("version")))] = row
    judges: list[dict[str, Any]] = []
    judge_dir = output_dir / "artifacts" / "judges"
    if run_judges:
        jobs: list[dict[str, Any]] = []
        for repeat in range(1, REPEATS + 1):
            for case in cases:
                baseline = writer_index.get((case["case_id"], repeat, "baseline"))
                repaired = writer_index.get((case["case_id"], repeat, "repaired"))
                if not baseline or not repaired or baseline.get("status") != "completed" or repaired.get("status") != "completed":
                    continue
                for judge_index, order in enumerate(((baseline, repaired), (repaired, baseline)), start=1):
                    jobs.append({"case": case, "repeat": repeat, "judge_index": judge_index, "order": order})
        max_workers = max(1, min(int(plan.get("concurrency", 1)), len(jobs) or 1))
        if max_workers == 1:
            judges = [
                _execute_judge_job(
                    case=job["case"], repeat=job["repeat"], judge_index=job["judge_index"], order=job["order"],
                    rubric_text=rubric_text, cases_dir=cases_dir, judge_dir=judge_dir, local_backend=local_backend,
                    backend=backend, resolver=resolver,
                )
                for job in jobs
            ]
        else:
            with ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="logic-writing-judge") as executor:
                futures = [
                    executor.submit(
                        _execute_judge_job,
                        case=job["case"], repeat=job["repeat"], judge_index=job["judge_index"], order=job["order"],
                        rubric_text=rubric_text, cases_dir=cases_dir, judge_dir=judge_dir, local_backend=local_backend,
                        backend=backend, resolver=resolver,
                    )
                    for job in jobs
                ]
                judges = [future.result() for future in futures]
    else:
        for path in sorted(judge_dir.glob("**/judge.json")):
            row = _read_json(path)
            if isinstance(row, dict):
                judges.append(row)
    summary = _aggregate(cases, writers, judges)
    result = {
        "schema_version": "logic-writing.writing-quality-run-result.v2", "benchmark_id": plan["benchmark_id"],
        "status": "completed" if len(writers) == plan["planned_writer_count"] and len(judges) == plan["planned_judge_count"] else "incomplete",
        "terminal_reason": None, "quality_claim_status": "passed" if summary["status"] == "passed" else ("failed" if summary["status"] == "failed" else "incomplete"),
        "planned_writer_count": plan["planned_writer_count"], "planned_judge_count": plan["planned_judge_count"], "planned_execution_count": plan["planned_execution_count"],
        "actual_writer_count": len(writers), "actual_judge_count": len(judges), "actual_execution_count": len(writers) + len(judges),
        "successful_artifact_count": sum(row.get("status") == "completed" for row in writers), "successful_judge_count": sum(row.get("status") == "completed" for row in judges),
        "backend_id": local_backend.backend_id if local_backend else backend_id, "source_manifest_fingerprint": source_manifest_fp, "created_at": _now(),
        "claim_boundary": "Scores are claimed only when every writer and pair judge has a verified local capture and parseable judgment.",
        "summary_fingerprint": fingerprint(summary),
    }
    _write_json(output_dir / "writers.json", writers)
    _write_json(output_dir / "judges.json", judges)
    _write_json(output_dir / "summary.json", summary)
    _write_json(output_dir / "run_result.json", result)
    return result


def _preference_for_version(preference: str, pair_order: list[str]) -> str:
    if preference not in {"X", "Y"}:
        return preference
    return pair_order[0] if preference == "X" else pair_order[1]


def _aggregate(cases: list[dict[str, Any]], writers: list[dict[str, Any]], judges: list[dict[str, Any]]) -> dict[str, Any]:
    by_pair: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in judges:
        if row.get("status") == "completed" and isinstance(row.get("judgment"), Mapping):
            by_pair[(str(row["case_id"]), int(row["repeat"]))].append(row)
    case_rows: list[dict[str, Any]] = []
    for case in cases:
        repeats: list[dict[str, Any]] = []
        score_values: dict[str, dict[str, list[int]]] = {version: {dimension: [] for dimension in DIMENSIONS} for version in VERSIONS}
        repaired_issues: list[dict[str, Any]] = []
        for repeat in range(1, REPEATS + 1):
            pair_rows = by_pair.get((case["case_id"], repeat), [])
            preferences = [_preference_for_version(str(row["judgment"]["preference"]), list(row["pair_order"])) for row in pair_rows]
            consensus = preferences[0] if len(preferences) == 2 and preferences[0] == preferences[1] else ("disagreement" if len(preferences) == 2 else "incomplete")
            for row in pair_rows:
                order = list(row["pair_order"])
                for judgment in row["judgment"].get("judgments", []):
                    label = judgment.get("anonymous_label")
                    if label not in {"X", "Y"}:
                        continue
                    version = order[0] if label == "X" else order[1]
                    for dimension in DIMENSIONS:
                        score_values[version][dimension].append(int(judgment["scores"][dimension]))
                    if version == "repaired":
                        scores = judgment["scores"]
                        defects = judgment.get("defects", [])
                        repairs = judgment.get("required_repairs", [])
                        blocking = [item for item in defects if isinstance(item, Mapping) and item.get("severity") in {"blocking", "repair"}]
                        if any(scores[dimension] < 4 for dimension in ("clarity", "coherence", "content_fidelity", "instruction_fidelity")) or blocking or repairs:
                            repaired_issues.append({"repeat": repeat, "judge_index": row.get("judge_index"), "label": label, "reason": "repaired judgment has a core score below 4 or an unresolved defect"})
            repeats.append({"repeat": repeat, "preferences": preferences, "consensus": consensus, "judge_count": len(pair_rows)})
        repaired_wins = sum(row["consensus"] == "repaired" for row in repeats)
        baseline_wins = sum(row["consensus"] == "baseline" for row in repeats)
        means = {version: {dimension: (sum(values) / len(values) if values else None) for dimension, values in dimensions.items()} for version, dimensions in score_values.items()}
        natural_non_decrease = all(
            means["repaired"][dimension] is not None and means["baseline"][dimension] is not None and means["repaired"][dimension] >= means["baseline"][dimension]
            for dimension in ("naturalness", "coherence")
        )
        improved = repaired_wins >= 1 and baseline_wins == 0 and not repaired_issues and natural_non_decrease and all(row["consensus"] not in {"incomplete", "disagreement"} for row in repeats)
        case_rows.append({"case_id": case["case_id"], "repeat_results": repeats, "improved": improved, "repaired_wins": repaired_wins, "baseline_wins": baseline_wins, "score_means": means, "repaired_issues": repaired_issues, "naturalness_coherence_non_decrease": natural_non_decrease})
    complete = len(writers) == CASE_COUNT * REPEATS * 2 and len(judges) == CASE_COUNT * REPEATS * 2 and all(row.get("status") == "completed" for row in writers + judges)
    improved_count = sum(row["improved"] for row in case_rows)
    status = "incomplete" if not complete else ("passed" if improved_count >= 9 else "failed")
    return {"schema_version": "logic-writing.writing-quality-summary.v2", "status": status, "case_count": CASE_COUNT, "improved_case_count": improved_count, "required_improved_case_count": 9, "cases": case_rows, "writer_count": len(writers), "judge_count": len(judges), "claim_boundary": "This is a bounded twelve-case comparison, not a universal or statistical claim about all topics or models."}


def summarize_run(output_dir: Path) -> dict[str, Any]:
    path = output_dir / "summary.json"
    result = _read_json(path) if path.is_file() else {"status": "incomplete", "error": "summary.json is missing"}
    _write_json(output_dir / "summary-consumer.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--cases-dir", type=Path)
    parser.add_argument("--backend", help="Legacy explicit module:function backend")
    parser.add_argument("--backend-plan", type=Path, help="Portable local-backend-plan.json")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--run-writers", action="store_true")
    parser.add_argument("--run-judges", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    args = parser.parse_args()
    try:
        cases_dir = (args.cases_dir or args.root / "tests/fixtures/writing_quality").resolve()
        if args.summarize:
            result = run_benchmark(args.root, output_dir=args.output_dir, cases_dir=cases_dir, summarize_only=True)
        elif args.plan_only:
            result = run_benchmark(args.root, output_dir=args.output_dir, cases_dir=cases_dir, backend_plan=args.backend_plan, run_writers=False, run_judges=False)
        else:
            backend = _resolve_backend(args.backend)
            explicit_stage = args.run_writers or args.run_judges
            result = run_benchmark(args.root, output_dir=args.output_dir, cases_dir=cases_dir, backend=backend, backend_id=args.backend, backend_plan=args.backend_plan, run_writers=args.run_writers or not explicit_stage, run_judges=args.run_judges or not explicit_stage)
    except (OSError, ValueError, ValidationError, json.JSONDecodeError, ImportError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    if result.get("status") == "passed" or result.get("quality_claim_status") == "passed":
        return 0
    if result.get("status") == "not_run":
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
