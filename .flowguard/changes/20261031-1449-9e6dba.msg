LW-610: a WorldGuard tree report binds like one contract

This promotion ran one fresh target check with bound tests and the remaining function-selected tests; 3 warning(s) remained. The tree identifies the checked post-promotion content, before later component confirmation. Implementation provenance lists changed Python function definitions from the Git diff. Available static rule identities and checked PLAN lines are recorded. PLAN edit ordering, per-item clearance, acceptances, existing-item clearance and new-action judgments are not assessed; unknown order is null and unsupported lists are empty.

owner block (paste it unchanged into your final message):
- touch: skills/logic-writing/scripts/_common.py:worldguard_report_identity_problems
- touch: skills/logic-writing/scripts/_common.py:load_request
- touch: skills/logic-writing/scripts/derive_closure.py:provider_checks
- touch: skills/logic-writing/scripts/reader_plan.py:build_reader_brief
- touch: skills/logic-writing/scripts/run_chain.py:_refresh
- touch: skills/logic-writing/scripts/world_refs.py:validate_world_refs
- touch: skills/logic-writing/scripts/show_plan.py:_summary
- changes: closure_claim_model.world_report_belongs_to_the_contract by R1 "已有规则 `world_report_belongs_to_the_contract` 对树也成立，同一个规则管两种报告。"
  old rule:
    Invariant('world_report_belongs_to_the_contract', 'a world report counts only for its own world contract', world_report_belongs_to_the_contract)
    def provider(state):
        return 'researchguard' if state.owner == 'investigation' else 'worldguard'
    def world_report_belongs_to_the_contract(state, trace):
        if state.closed and provider(state) == 'worldguard' and (state.report == 'world_foreign') and (state.copied != 'failed' or not state.named):
            return InvariantResult.fail('a world report of another contract was counted for this world')
        return InvariantResult.pass_()
  new rule:
    Invariant('world_report_belongs_to_the_contract', 'a world report counts only for its own world contract', world_report_belongs_to_the_contract)
    WORLD_EXPECTED = {'mesh_bound': 'passed', 'contract_scope': 'passed', 'mesh_foreign': 'world_report_mismatch:mesh_id', 'mesh_old': 'world_report_unbound:world_mesh+regenerate', 'mesh_node_stale': 'world_report_stale:ch2_fixed.yaml', 'mesh_embedded_stale': 'world_report_stale:mesh_fixed.yaml', 'mesh_digest_omitted': 'world_report_stale:ch2_fixed.yaml'}
    def provider(state):
        return 'researchguard' if state.owner == 'investigation' else 'worldguard'
    def world_report_belongs_to_the_contract(state, trace):
        if state.world_case in {'mesh_bound', 'contract_scope', 'mesh_foreign', 'mesh_old'} and state.world_result != WORLD_EXPECTED[state.world_case]:
            return InvariantResult.fail('a tree report must bind by mesh_id; an old report needs the native regeneration command')
        if state.closed and provider(state) == 'worldguard' and (state.report == 'world_foreign') and (state.copied != 'failed' or not state.named):
            return InvariantResult.fail('a world report of another contract was counted for this world')
        return InvariantResult.pass_()
- changes: closure_claim_model.world_report_is_current by R1 "已有规则 `world_report_is_current` 对树报告的每个节点文件都成立。"
  old rule:
    Invariant('world_report_is_current', 'world inputs match the saved report', world_report_is_current)
    def provider(state):
        return 'researchguard' if state.owner == 'investigation' else 'worldguard'
    def world_report_is_current(state, trace):
        if state.closed and provider(state) == 'worldguard' and (state.report == 'world_stale') and (state.copied != 'failed' or state.broad or (not state.named)):
            return InvariantResult.fail('stale world report licensed closure')
        return InvariantResult.pass_()
  new rule:
    Invariant('world_report_is_current', 'world inputs match the saved report', world_report_is_current)
    WORLD_EXPECTED = {'mesh_bound': 'passed', 'contract_scope': 'passed', 'mesh_foreign': 'world_report_mismatch:mesh_id', 'mesh_old': 'world_report_unbound:world_mesh+regenerate', 'mesh_node_stale': 'world_report_stale:ch2_fixed.yaml', 'mesh_embedded_stale': 'world_report_stale:mesh_fixed.yaml', 'mesh_digest_omitted': 'world_report_stale:ch2_fixed.yaml'}
    def provider(state):
        return 'researchguard' if state.owner == 'investigation' else 'worldguard'
    def world_report_is_current(state, trace):
        if state.world_case in {'mesh_node_stale', 'mesh_embedded_stale', 'mesh_digest_omitted'} and state.world_result != WORLD_EXPECTED[state.world_case]:
            return InvariantResult.fail('tree bytes and every file node must be covered by current raw input digests')
        if state.closed and provider(state) == 'worldguard' and (state.report == 'world_stale') and (state.copied != 'failed' or state.broad or (not state.named)):
            return InvariantResult.fail('stale world report licensed closure')
        return InvariantResult.pass_()
- changes: world_references.world_refs_name_contract_ids by R1 "已有规则 `world_refs_name_contract_ids` 对树也成立。"
  old rule:
    Invariant('world_refs_name_contract_ids', 'world_refs name ids declared by the world contract', world_refs_name_contract_ids)
    def world_refs_name_contract_ids(state: State, trace) -> InvariantResult:
        if state.case in {'undeclared_ref', 'no_contract'} and state.result == 'accepted':
            return InvariantResult.fail('a world reference was accepted without a declared contract id')
        return InvariantResult.pass_()
  new rule:
    Invariant('world_refs_name_contract_ids', 'world_refs name ids declared by the world contract', world_refs_name_contract_ids)
    CASES = {'declared_ref': 'accepted', 'undeclared_ref': 'unknown_world_ref', 'no_contract': 'world_contract_missing', 'quoted_ref': 'no_risk', 'unquoted_ref': 'world_ref_unquoted', 'claim_on_planned_unit': 'accepted', 'claim_outside_plan': 'unit_not_in_plan', 'mesh_file_ref': 'accepted', 'mesh_embedded_ref': 'accepted', 'mesh_unknown_ref': 'unknown_world_ref', 'mesh_exclusive': 'rejected'}
    def world_refs_name_contract_ids(state: State, trace) -> InvariantResult:
        if state.case.startswith('mesh_') and state.result != CASES[state.case]:
            return InvariantResult.fail('mesh references must resolve file and embedded ids and reject unknown or ambiguous inputs')
        if state.case in {'undeclared_ref', 'no_contract'} and state.result == 'accepted':
            return InvariantResult.fail('a world reference was accepted without a declared contract id')
        return InvariantResult.pass_()
