## ADDED Requirements

### Requirement: Investigation selects an explicit report composition profile
Before final drafting, the investigation route SHALL select `explanatory_report`, `decision_analysis`, `evidence_audit`, or `case_trace`, or a user-defined equivalent, and SHALL map the bounded answer, evidence strength, live alternatives, unresolved discriminators, limitations, fallback or recheck conditions, and user structure into the report plan.

#### Scenario: Decision analysis has unresolved alternatives
- **WHEN** two explanations remain materially live
- **THEN** the plan places both explanations, the discriminating evidence, and the current decision boundary near the affected conclusion

### Requirement: Investigation final review opens the actual report
Investigation closure SHALL require a route-native review of the current artifact spans for recoverable question, bounded answer, evidence strength, negative evidence, alternatives, conditions, fallback or recheck action, and conclusion scope. A complete ResearchPacket or argument model SHALL NOT substitute for this review.

#### Scenario: Research packet is complete but report is a finding dump
- **WHEN** the final report copies evidence rows without a reader-facing throughline
- **THEN** route-native review fails and returns the affected report units for repair

#### Scenario: Conclusion drops a material boundary
- **WHEN** the current report conclusion exceeds its evidence or omits an assigned limitation
- **THEN** investigation closure remains blocked

### Requirement: Investigation composition binds actual report units
Every required investigation plan unit SHALL bind its content, alternatives, limitations, and reader-state contribution to current ArtifactMap spans. Internal research ids or model order SHALL NOT become the default visible report order.

#### Scenario: Model row is cited as a section
- **WHEN** a report section exists only as an internal model label without current prose spans
- **THEN** model-artifact binding fails
