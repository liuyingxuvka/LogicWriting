"""Synthetic protocol-chain builders for reader-v2 contract regression tests.

These helpers create deterministic transport, fingerprint, and closure inputs;
they are not writer output and their scores are never quality-benchmark evidence.
"""

from __future__ import annotations

from pathlib import Path

from _common import fingerprint, fingerprint_text, fingerprint_without
from reader_pipeline import build_artifact_map, build_reader_audit, build_reader_brief


NOW = "2026-07-29T12:00:00Z"
NATIVE_FP = fingerprint({"native": "current-pass"})


def _with_fp(value: dict, field: str) -> dict:
    value[field] = fingerprint_without(value, field)
    return value


def make_intent(*, language: str = "zh-CN", mode: str = "create_new") -> dict:
    return _with_fp({
        "schema_version": "2.0",
        "artifact_mode": mode,
        "language": language,
        "audience": "需要一篇连贯成品的普通读者",
        "purpose": "给出完整、自然、有证据边界的成品",
        "structure": {
            "mode": "partially_fixed",
            "requested_outline": [{
                "outline_id": "outline:answer",
                "parent_outline_id": None,
                "order": 1,
                "label": "完整回答",
                "required": True,
                "title_locked": True,
                "source": "user",
            }],
        },
        "heading_policy": "preserve_requested",
        "list_policy": "prose_default",
        "style": {
            "voice": "自然、清楚、像人在解释",
            "formality": "neutral",
            "required_traits": ["连贯", "具体"],
            "forbidden_traits": ["卡片式碎片", "工作流术语"],
        },
        "extent": {"unit": "characters", "minimum": 80, "target": 240, "maximum": 600},
        "artifact_format": "markdown",
        "citation_policy": "none",
        "table_policy": "allowed",
        "required_content": ["完整回答"],
        "forbidden_content": ["内部工作流"],
        "reference_examples": [],
        "unresolved_choices": [],
    }, "intent_fingerprint")


def route_request(kind: str, *, research: bool = False) -> dict:
    intent = make_intent()
    deliverable = {
        "kind": kind,
        "description": f"Current {kind} terminal deliverable",
        "acceptance_criteria": ["Preserve ReaderIntent exactly."],
    }
    deliverable["fingerprint"] = fingerprint(deliverable)
    writing_request = {
        "schema_version": "2.0",
        "request_id": f"request:{kind}",
        "terminal_deliverable": deliverable,
        "reader_intent": intent,
    }
    writing_request["request_fingerprint"] = fingerprint(writing_request)
    return {
        "writing_request": writing_request,
        "decision_id": f"decision:{kind}",
        "decided_at": NOW,
        "material_assumptions": [],
        "substantial_research_required": research,
    }


def make_plan(intent: dict, owner: str) -> dict:
    return _with_fp({
        "schema_version": "2.0",
        "plan_id": f"plan:{owner}",
        "reader_intent_fingerprint": intent["intent_fingerprint"],
        "final_owner": owner,
        "central_question": "怎样把证据或故事材料组织成一篇完整成品？",
        "central_throughline": "从读者问题出发，经过必要支撑，抵达有边界的结论或变化。",
        "artifact_form": "完整读者成品",
        "structure_authority": "user_partial",
        "opening_job": "让读者知道真正的问题和阅读方向。",
        "conclusion_job": "收束前文并明确边界或后续行动。",
        "planned_units": [{
            "planned_unit_id": "unit:answer",
            "parent_unit_id": None,
            "unit_kind": "section",
            "order": 1,
            "required": True,
            "title": "完整回答",
            "source_outline_ids": ["outline:answer"],
            "reader_job": "把核心材料组织成前后相接的解释。",
            "content_unit_ids": ["content:answer"],
            "limitation_ids": [],
            "relation_to_previous": "这是开篇主单元。",
            "incoming_reader_state": "知道问题但不知道答案为何成立。",
            "outgoing_reader_state": "理解答案、支撑、边界以及下一步。",
            "downstream_unit_ids": [],
            "presentation_mode": "prose",
            "target_extent": 200,
        }],
        "allowed_list_zones": [],
        "content_dispositions": [{
            "content_unit_id": "content:answer",
            "disposition": "consumed",
            "planned_unit_ids": ["unit:answer"],
            "reason": "这是成品必须实现的核心内容。",
        }],
        "unresolved_conflicts": [],
    }, "plan_fingerprint")


def make_route_composition(owner: str, intent: dict, plan: dict) -> dict:
    common = {
        "schema_version": "2.0",
        "composition_id": f"composition:{owner}",
        "final_owner": owner,
        "reader_intent_fingerprint": intent["intent_fingerprint"],
        "composition_plan_fingerprint": plan["plan_fingerprint"],
    }
    if owner == "investigation":
        common.update({
            "profile": "explanatory_report",
            "bounded_answer_content_unit_ids": ["content:answer"],
            "evidence_strength_rows": [{
                "content_unit_id": "content:answer",
                "strength": "moderate",
                "reason": "当前材料支持有边界的解释。",
            }],
            "alternative_ids": [],
            "unresolved_discriminators": [],
            "limitation_ids": [],
            "fallback_or_recheck_units": [{
                "action_id": "action:recheck",
                "condition": "事实状态发生变化",
                "action": "重新核验来源后再更新结论",
                "planned_unit_id": "unit:answer",
            }],
            "actual_artifact_review_required": True,
        })
    elif owner == "academic-writing":
        common.update({
            "artifact_mode": "create_new",
            "profile": "conceptual_argument",
            "research_question": "完整结构如何改善读者理解？",
            "central_contribution": "用整篇组合约束取代小点拼接。",
            "hierarchy": [{
                "unit_id": "unit:answer",
                "parent_unit_id": None,
                "unit_kind": "document",
                "research_question_contribution": "直接回答研究问题。",
                "incoming_dependency": "读者已有问题背景。",
                "new_claim_or_warrant": "组合计划使段落承担不同且相连的论证职责。",
                "evidence_ids": ["evidence:one"],
                "qualification": {
                    "status": "not_applicable",
                    "reason": "概念论证没有需要声明的实证方法限定。",
                    "source_refs": [],
                },
                "downstream_consumer_ids": [],
            }],
            "figure_table_jobs": [],
            "revision_provenance_applicability": "not_applicable",
            "actual_artifact_review_required": True,
        })
    elif owner == "fiction-writing":
        common.update({
            "output_room": "reader_native",
            "artifact_kind": "short_story",
            "prose_phase": "integrated_draft",
            "structure_authority": "user_partial",
            "voice_contract_ref": "voice:close-third",
            "story_movements": [{
                "movement_id": "movement:one",
                "unit_ids": ["unit:answer"],
                "entry_story_state": "承诺尚未付出代价。",
                "primary_pressure": "人物必须在信任与目标之间选择。",
                "reader_state_change": "读者看见选择的真实代价。",
                "irreversible_change": "关系中的信任被具体损伤。",
                "exit_story_state": "人物得到目标却失去旧有关系。",
                "downstream_unit_ids": [],
                "promise_ids": ["promise:trust"],
            }],
            "unit_plans": [{
                "unit_id": "unit:answer",
                "unit_kind": "story",
                "contribution": "让承诺通过行动产生代价。",
                "entry_state": "两人仍互相信任。",
                "exit_state": "信任被选择改变。",
                "focal_desire": "完成承诺。",
                "resistance_or_cost": "必须牺牲同伴的信任。",
                "reader_state_before": "以为承诺可以轻易兑现。",
                "reader_state_after": "理解兑现承诺的代价。",
                "open_questions_in": ["人物会选择什么？"],
                "open_questions_out": [],
                "voice_owner": "主视角人物",
                "rhythm_role": "推进并收束",
                "prohibited_reveals": [],
                "downstream_unit_ids": [],
            }],
            "promise_and_reveal_bindings": [{
                "binding_id": "binding:promise",
                "promise_or_reveal_id": "promise:trust",
                "setup_unit_ids": ["unit:answer"],
                "movement_unit_ids": ["unit:answer"],
                "payoff_unit_ids": ["unit:answer"],
                "status": "paid",
            }],
            "realization_boundaries": ["成品必须用场景行动实现，而不是用模型标签解释。"],
        })
    else:
        common.update({
            "artifact_mode": "create_new",
            "guide_kind": "destination_guide",
            "structure_authority": "user_partial",
            "body_sections": [{
                "section_id": "unit:answer",
                "section_kind": "orientation",
                "section_role": "帮助旅行者形成可执行选择。",
                "incoming_traveler_state": "不了解目的地取舍。",
                "outgoing_traveler_state": "知道适合自己的路线和边界。",
                "route_refs": ["route:one"],
                "traveler_fit_refs": ["fit:one"],
                "local_texture_refs": ["local:one"],
                "risk_fallback_binding_ids": ["risk-binding:one"],
                "next_consumer_ids": [],
                "prose_required": True,
                "list_or_table_allowed": False,
            }],
            "appendix_sections": [{
                "section_id": "appendix:ops",
                "operational_kinds": ["source_recheck", "fallback"],
                "consumer_section_ids": ["unit:answer"],
            }],
            "source_boundary_placement": "appendix:ops",
            "recheck_placement": "appendix:ops",
            "local_texture_candidates": [{
                "candidate_id": "local:one",
                "canonical_name": "Old Market",
                "local_name": "老市场",
                "accepted_aliases": [],
                "category": "neighborhood",
                "intended_section_ids": ["unit:answer"],
            }],
            "risk_fallback_bindings": [{
                "binding_id": "risk-binding:one",
                "risk_id": "risk:rain",
                "affected_section_ids": ["unit:answer"],
                "trigger": "持续降雨",
                "affected_travelers": ["步行耐受较低的旅行者"],
                "mitigation": "缩短室外段",
                "fallback_id": "fallback:covered",
                "reachable_from_route_node_ids": ["route:one"],
                "evidence_mode": "recheck_required",
            }],
        })
    return _with_fp(common, "extension_fingerprint")


def make_reader_chain(workdir: Path, owner: str = "investigation", *, language: str = "zh-CN") -> dict:
    workdir.mkdir(parents=True, exist_ok=True)
    intent = make_intent(language=language)
    plan = make_plan(intent, owner)
    route = make_route_composition(owner, intent, plan)
    deliverable = {
        "kind": {
            "investigation": "research_report",
            "academic-writing": "paper",
            "fiction-writing": "short_story",
            "travel-guide": "destination_guide",
        }[owner],
        "description": "一篇完整、连贯、可直接阅读的成品",
        "acceptance_criteria": ["结构完整", "正文连贯", "边界明确"],
    }
    deliverable["fingerprint"] = fingerprint(deliverable)
    decision = _with_fp({
        "schema_version": "2.0",
        "decision_id": f"decision:{owner}",
        "request_fingerprint": fingerprint({"request": owner, "intent": intent["intent_fingerprint"]}),
        "reader_intent": intent,
        "reader_intent_fingerprint": intent["intent_fingerprint"],
        "terminal_deliverable": deliverable,
        "final_owner": owner,
        "child_routes": [],
        "material_assumptions": [],
        "intent_conflicts": [],
        "status": "current",
        "reason": "The requested terminal deliverable selects this owner.",
        "stale_because": [],
        "decided_at": NOW,
    }, "decision_fingerprint")
    boundaries = {
        "content_units": [{
            "content_unit_id": "content:answer",
            "safe_meaning": "成品必须把中心问题、支撑、边界和收束写成连续正文。",
            "required": True,
            "evidence_anchor_ids": [],
            "alternative_ids": [],
            "limitation_ids": [],
            "model_row_ids": ["model:throughline"],
        }],
            "evidence_anchors": [{
                "anchor_id": "evidence:one",
                "source_id": "source:synthetic",
                "locator": "synthetic:one",
                "relation": "support",
                "observed_summary": "合成测试材料支持结构性论证。",
                "boundary": "仅用于协议测试，不代表真实学术证据。",
            }],
        "alternatives": [],
        "limitations": [],
        "citation_duties": [],
        "must_preserve_tokens": [],
        "verbatim_obligations": [],
        "prohibited_overclaims": [],
    }
    brief = build_reader_brief(
        route_decision=decision,
        content_boundaries=boundaries,
        composition_plan=plan,
        route_composition=route,
        native_dependency_receipt_fingerprints=[NATIVE_FP],
        content_authority_fingerprints={"content:answer": fingerprint({"content": owner})},
        brief_id=f"brief:{owner}",
    )
    artifact_path = workdir / f"{owner}.md"
    if language.casefold().startswith("en"):
        artifact_text = (
            "# 完整回答\n\n"
            "The real problem is not how to list more points, but how each paragraph can do a different job while the next paragraph builds on what the reader has already learned. The reader can then understand the question, see the support and limits, and reach the conclusion naturally.\n\n"
            "The artifact therefore treats structure as forward movement: the opening sets direction, the middle explains reasons and tradeoffs, and the ending closes the boundary and next action. It keeps necessary information without exposing model labels or workflow steps."
        )
    else:
        artifact_text = (
            "# 完整回答\n\n"
            "真正需要解决的不是如何罗列更多要点，而是如何让每一段承担不同职责，并让后一句建立在前一句已经说明的内容上。这样，读者先理解问题，再看到支撑和限制，最后能够自然抵达结论。\n\n"
            "这份成品因此把结构当作整篇文章的推进关系：开头确定方向，中间解释原因与取舍，结尾收束边界和后续行动。它保留必要信息，却不把模型标签或写作步骤暴露给读者。"
        )
    artifact_path.write_text(artifact_text, encoding="utf-8")
    amap = build_artifact_map(artifact_path, map_id=f"map:{owner}", language=language)
    paragraph = next(row for row in amap["units"] if row["unit_kind"] == "paragraph")
    body_units = [
        row for row in amap["units"]
        if row["unit_kind"] in {"paragraph", "list", "table", "quote", "scene"}
    ]
    spans = [{
        "artifact_unit_id": row["artifact_unit_id"],
        "locator": row["locator"],
        "content_fingerprint": row["content_fingerprint"],
    } for row in body_units]
    shared = _with_fp({
        "schema_version": "2.0",
        "contract_id": f"shared:{owner}",
        "final_owner": owner,
        "route_decision_fingerprint": decision["decision_fingerprint"],
        "reader_intent_fingerprint": intent["intent_fingerprint"],
        "reader_brief_fingerprint": brief["brief_fingerprint"],
        "composition_plan_fingerprint": plan["plan_fingerprint"],
        "route_extension_fingerprint": route["extension_fingerprint"],
        "artifact_map_fingerprint": amap["map_fingerprint"],
        "artifact_path": str(artifact_path.resolve()),
        "artifact_fingerprint": amap["artifact_fingerprint"],
        "iteration_id": "iteration:one",
        "unit_bindings": [{
            "binding_id": "binding:answer",
            "planned_unit_id": "unit:answer",
            "artifact_unit_ids": [row["artifact_unit_id"] for row in body_units],
            "content_unit_ids": ["content:answer"],
            "model_row_ids": ["model:throughline"],
            "route_surface_ids": [f"route:{owner}:actual-artifact"],
            "artifact_spans": spans,
        }],
        "coverage_dispositions": [],
    }, "contract_fingerprint")
    audit = build_reader_audit(
        audit_id=f"audit:{owner}",
        artifact_map=amap,
        reader_brief=brief,
        shared_writing=shared,
        audited_at=NOW,
    )
    return {
        "intent": intent, "plan": plan, "route_decision": decision,
        "route_composition": route, "reader_brief": brief,
        "artifact_path": artifact_path, "artifact_map": amap,
        "shared_writing": shared, "deterministic_audit": audit,
        "paragraph": paragraph,
    }


def span_evidence(chain: dict, excerpt: str | None = None) -> dict:
    unit = chain["paragraph"]
    text = excerpt or unit["text"][:60]
    return {
        "artifact_unit_id": unit["artifact_unit_id"],
        "locator": unit["locator"],
        "excerpt": text,
        "excerpt_fingerprint": fingerprint_text(text),
    }


def complete_chain(
    workdir: Path,
    owner: str = "investigation",
    *,
    pass_quality: bool = True,
    language: str = "zh-CN",
) -> dict:
    """Build a synthetic protocol chain; do not treat it as a blind review."""
    from derive_closure import REQUIRED_DIMENSIONS

    chain = make_reader_chain(workdir, owner, language=language)
    evidence = span_evidence(chain)
    body_units = [
        row for row in chain["artifact_map"]["units"]
        if row["unit_kind"] in {"paragraph", "list", "table", "quote", "scene"}
    ]
    reverse_outline = [{
        "artifact_unit_id": unit["artifact_unit_id"],
        "parent_unit_id": unit["parent_unit_id"],
        "observed_job": "解释中心答案及其结构理由。",
        "main_point": "完整写作依赖整篇推进而不是小点拼接。",
        "support_or_action": "实际文本说明段落职责、支撑和收束。",
        "content_unit_ids": ["content:answer"],
        "carries_from_unit_ids": [],
        "relation_to_previous": "由前一正文单元进入当前解释。",
        "downstream_effect": "使结尾能够收束边界。",
        "orphaned": False,
        "overloaded": False,
        "evidence": {
            "artifact_unit_id": unit["artifact_unit_id"],
            "locator": unit["locator"],
            "excerpt": unit["text"][:60],
            "excerpt_fingerprint": fingerprint_text(unit["text"][:60]),
        },
    } for unit in body_units]
    route_review = {
        "schema_version": "2.0",
        "review_id": f"review:{owner}",
        "final_owner": owner,
        "route_profile": str(chain["reader_brief"]["route_extension"]["profile"]),
        "route_extension_fingerprint": chain["route_composition"]["extension_fingerprint"],
        "artifact_map_fingerprint": chain["artifact_map"]["map_fingerprint"],
        "artifact_fingerprint": chain["artifact_map"]["artifact_fingerprint"],
        "dimensions": [{
            "dimension_id": dimension,
            "status": "passed" if pass_quality else ("repair" if index == 0 else "passed"),
            "reason": "The current span realizes this route obligation." if pass_quality or index else "The current span is too weak.",
            "evidence": [evidence],
        } for index, dimension in enumerate(REQUIRED_DIMENSIONS[owner])],
        "findings": [] if pass_quality else [{
            "finding_id": "route:defect",
            "dimension_id": REQUIRED_DIMENSIONS[owner][0],
            "severity": "repair",
            "observation": "The opening does not yet establish the route-specific job.",
            "reader_effect": "The reader cannot tell why the artifact matters.",
            "evidence": evidence,
            "repair_owner": owner,
            "repair_target_unit_ids": [chain["paragraph"]["artifact_unit_id"]],
            "preserve_refs": ["content:answer"],
        }],
        "required_repairs": [] if pass_quality else ["route:defect"],
        "status": "passed" if pass_quality else "repair",
        "reviewed_at": NOW,
    }
    route_review["review_fingerprint"] = fingerprint(route_review)
    judge_execution = {
        "schema_version": "1.0",
        "record_id": f"execution:judge:{owner}",
        "role": "judge",
        "backend_id": "synthetic-protocol-only",
        "run_id": f"run:judge:{owner}",
        "context_id": f"context:judge:{owner}",
        "parent_orchestrator_run_id": f"run:orchestrator:{owner}",
        "input_reader_intent_fingerprint": chain["intent"]["intent_fingerprint"],
        "input_writer_input_fingerprint": chain["reader_brief"]["writer_input_fingerprint"],
        "input_artifact_fingerprint": chain["artifact_map"]["artifact_fingerprint"],
        "rubric_fingerprint": fingerprint({"profile": owner, "protocol_only": True}),
        "model_id": "synthetic-protocol-only",
        "settings_fingerprint": fingerprint({"protocol_only": True}),
        "started_at": NOW,
        "finished_at": NOW,
        "terminal_status": "completed",
        "output_fingerprint": fingerprint({"judgment": owner, "protocol_only": True}),
        "provider_completion_ref": f"synthetic://protocol-only/{owner}",
        "independence_status": "verified",
        "evaluation_mode": "single",
        "pair_inputs": [],
        "pair_input_fingerprint": None,
        # The synthetic protocol chain models a single-article judge.  Keep
        # its writer context explicit so the execution validator can enforce
        # the same one-writer binding required by the native hold-out path.
        "writer_context_ids": ["context:writer:synthetic"],
    }
    judge_execution["record_fingerprint"] = fingerprint(judge_execution)
    scores = {key: 5 if pass_quality else 3 for key in (
        "clarity", "structure_fidelity", "coherence", "naturalness", "reader_fit",
        "content_fidelity", "genre_fit", "instruction_fidelity",
    )}
    judgment = {
        "schema_version": "2.0",
        "judgment_id": f"judgment:{owner}",
        "final_owner": owner,
        "producer_id": "producer:writer",
        "judge_id": "judge:independent",
        "evaluation_profile_fingerprint": fingerprint({"profile": owner, "v": 2}),
        "reader_intent_fingerprint": chain["intent"]["intent_fingerprint"],
        "reader_brief_fingerprint": chain["reader_brief"]["brief_fingerprint"],
        "composition_plan_fingerprint": chain["plan"]["plan_fingerprint"],
        "artifact_map_fingerprint": chain["artifact_map"]["map_fingerprint"],
        "shared_writing_contract_fingerprint": chain["shared_writing"]["contract_fingerprint"],
        "deterministic_audit_fingerprint": chain["deterministic_audit"]["audit_fingerprint"],
        "route_audit_fingerprint": route_review["review_fingerprint"],
        "artifact_fingerprint": chain["artifact_map"]["artifact_fingerprint"],
        "execution_record_fingerprint": judge_execution["record_fingerprint"],
        "reverse_outline": reverse_outline,
        "scores": scores,
        "defects": [] if pass_quality else [{
            "observation_id": "judge:defect",
            "dimension": "coherence",
            "message": "The actual opening does not yet license the conclusion.",
            "severity": "repair",
            "evidence": evidence,
        }],
        "strengths": [{
            "observation_id": "judge:strength",
            "dimension": "clarity",
            "message": "The actual wording is concrete and readable.",
            "severity": "strength",
            "evidence": evidence,
        }],
        "required_repairs": [] if pass_quality else [{
            "repair_id": "repair:coherence",
            "defect_ids": ["judge:defect"],
            "target_unit_ids": [chain["paragraph"]["artifact_unit_id"]],
            "required_change": "Rebuild the opening-to-conclusion dependency.",
            "repair_owner": owner,
        }],
        "status": "passed" if pass_quality else "repair",
        "judged_at": NOW,
    }
    judgment["judgment_fingerprint"] = fingerprint(judgment)
    provenance = {
        "schema_version": "2.0",
        "provenance_id": f"provenance:{owner}",
        "final_owner": owner,
        "artifact_mode": "create_new",
        "reader_intent_fingerprint": chain["intent"]["intent_fingerprint"],
        "source_artifact_fingerprint": None,
        "target_artifact_fingerprint": chain["artifact_map"]["artifact_fingerprint"],
        "applicability": "not_applicable",
        "unit_treatments": [],
        "recorded_at": NOW,
    }
    provenance["provenance_fingerprint"] = fingerprint(provenance)
    chain.update({
        "route_review": route_review,
        "judgment": judgment,
        "revision_provenance": provenance,
        "native_receipt_fingerprints": [NATIVE_FP],
        "closure_id": f"closure:{owner}",
        "reader_execution_records": [judge_execution],
    })
    return chain


def closure_input(chain: dict) -> dict:
    return {
        key: chain[key] for key in (
            "closure_id", "route_decision", "reader_brief", "route_composition",
            "artifact_map", "shared_writing", "deterministic_audit", "route_review",
            "judgment", "revision_provenance", "native_receipt_fingerprints",
        )
    } | {"repair_results": chain.get("repair_results", []), "reader_execution_records": chain.get("reader_execution_records", [])}
