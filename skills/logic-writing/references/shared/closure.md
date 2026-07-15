# Evidence freshness and closure

Each receipt binds producer skill and native route, run id, covered obligations,
exact input and output fingerprints, artifact fingerprint, scope, evidence
domain, actual status, safe claim, unsafe boundary, sequence/timestamp, and its
own content fingerprint.

Closure follows explicit dependency edges:

`source -> claim support -> ResearchPacket -> ReaderBrief -> artifact -> audit -> closure`

A material upstream change stales every affected downstream receipt. Reports,
logs, and progress files do not stale source authority unless declared as
functional inputs.

Aggregate monotonically: the final claim is no stronger than the weakest
unresolved important obligation. Planning artifacts and self-reported statuses
are never proof. Broad words such as complete, comprehensive, conclusive,
publication-ready, or submission-ready require current broad evidence in every
applicable domain.

Only the final route closes the user artifact. Non-pass closure reports the
missing or failed obligation, affected claim/unit, safe wording, unsafe
boundary, next owner, and whether to rerun, downgrade, omit, or request human
review. Two identical failed attempts with no new evidence end in a visible
no-progress terminal.
