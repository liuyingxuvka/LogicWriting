# SourceGuard Canon Contract

Use this reference when user-provided material, prior drafts, canon, adaptation
source, historical facts, research notes, external sources, or fixed world
notes constrain a StorylineDesign task.

## Triggers

Use SourceGuard support when:

- the user supplies earlier chapters, a series bible, notes, or canon;
- the story adapts another artifact;
- historical, technical, cultural, legal, medical, or factual material matters;
- the user says to preserve specific events, names, relationships, or rules;
- final closure claims coverage of original user requirements.

## Source Surface

Record:

- source id or material ref;
- source role: requirement, canon, prior draft, adaptation, external fact,
  style sample, or user preference;
- can-support;
- cannot-support;
- story rows affected;
- safe wording;
- status: passed, partial, blocked, stale, human_review, or not_applicable_with_reason.

## Closure Use

SourceGuard blocks or downgrades closure when:

- supplied canon is not represented in the model;
- final prose contradicts a preserved user requirement;
- a prior draft is rewritten without recording what was kept, changed, cut, or
  downgraded;
- external factual claims exceed the available source role;
- source evidence was produced before the final artifact changed.

When no user, canon, adaptation, historical, or external source material is in
scope, record `not_applicable_with_reason`.
