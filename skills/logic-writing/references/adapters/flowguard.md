# FlowGuard adapter

FlowGuard owns behavior/state modeling, process order, staleness propagation,
no-progress handling, release/retirement sequencing, and model-derived closure
constraints.

Keep `agent_operation` and `development_process` evidence separate. Editing a
user report does not stale release validation unless an explicit dependency
edge says it is a release input. Editing source, models, contracts, tests, or
toolchain identity stales only the development owners that consume them.

FlowGuard process success cannot replace SourceGuard, LogicGuard, TraceGuard,
Documents, PDF, or reader-quality evidence.
