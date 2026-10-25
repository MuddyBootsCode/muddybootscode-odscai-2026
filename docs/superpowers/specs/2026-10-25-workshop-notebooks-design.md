# Two notebooks: context defines correctness

Build the river notebook and the user-selected higher-education notebook for
the ODSC workshop. The user's clarification governs the design: demonstrate
ontology-driven development, rather than only debugging or counting.

Each lesson exposes a versioned ontology (entities, relationships, vocabulary,
scope, rationale and named rules), a task prompt for the attendee's agent,
a deliberately faulty reference implementation, counterexamples linked to
rules, and a repaired reference. Reference code is authored teaching material;
no simulated agent failure is presented as an observed result.

## Approaches

- Higher education was selected over land evidence and casing fit. Reporting
  grain complements river semantics and avoids repeating the casing exercise.
- Use self-contained Python/Jupyter notebooks with synthetic fixtures and a
  fixed clock. This is an implementation choice: offline execution, no API keys,
  no model SDK, no external files required by a downloaded notebook.
- An optional controlled agent comparison records actual outcomes. It does not
  claim these examples establish causal or universal improvements in models.

## Lessons

River: a stage reading can be compared to a demonstration threshold only for
the same gauge, quantity and datum, after unit normalization and a timestamp
freshness check. Distinguish unavailable comparison from below threshold.
Gage height is relative to a datum, not necessarily water depth. The threshold
and 15-minute freshness policy are invented classroom choices, not flood guidance.

Higher education: count distinct people with completed records at the selected
institution. Degrees and jobs may multiply profile rows; employment is not a
cohort condition. Counting completions is a separate, legitimate report with
a different unit. Supplied person IDs are assumed resolved; no identity matching,
causal employment claims, or universal definition of graduate is implied.

## Deliverables and acceptance

Two notebooks with saved verified outputs; canonical percent-cell Python sources;
two ontology documents; a standard-library test command; a reproducible notebook
builder; Jupyter setup and Colab links; facilitator and agent-comparison guidance.
Tests must catch unit, context, freshness, identity, multiplicity and cohort errors.
Run notebooks from fresh kernels and verify public file contents after check-in.
Preserve the repository's existing skill/hooks and the local PowerPoint/kit.
