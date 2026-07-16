# Story Project Model Mesh

The project manifest is the aggregate identity owner for a StorylineDesign
project. It names one project id, model revision, compiled route decision,
explicit external nodes, and every in-scope native surface.

The mesh checker opens each surface and invokes that surface’s existing native
validator. It does not copy field semantics into a broad report checker.

After native validation, the mesh reconciles:

- project id, model revision, route/phase, and final artifact identity;
- book, volume, chapter, and scene parents and dependencies;
- story-unit parent contribution and downstream use;
- arc, thread, promise, payoff, and continuity references;
- chapter interfaces, prose blueprints, and reverse outlines;
- model-prose bindings and closure scope.

Every edge resolves to a declared object or an explicit typed external node.
Cross-project mixing, dangling parents, stale revisions, and different
manuscript hashes block aggregate closure even when every individual JSON file
is shape-valid.
