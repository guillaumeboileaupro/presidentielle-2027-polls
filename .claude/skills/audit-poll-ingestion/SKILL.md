---
name: audit-poll-ingestion
description: Audit or modify the presidential polling project's source ingestion, Excel or Wikipedia extraction, normalization, deduplication, and stored datasets while preserving provenance and rows. Use for parser changes, malformed percentages, missing dates, candidate mapping, and data migrations.
---

# Audit poll ingestion

Read `AGENT.md`, the relevant parser and its tests, and `TODO_CODEX_PRESIDENTIELLE2027.md` for known data issues.

1. Identify the source artifact, its URL and retrieval date if known, the raw location, and the normalized output. Keep raw inputs unchanged.
2. Record row, poll, scenario, and candidate counts before and after each transformation. Preserve a stable identity and report any discarded or merged records.
3. Parse dates, percentages, and candidate vectors at the scenario level. Check units and plausible scenario totals without turning ambiguous values into guessed observations.
4. Keep unparseable cells, mismatched vector lengths, missing dates, and uncertain party aliases in a diagnostic report. Distinguish a candidate absent from a scenario from a failed extraction.
5. Canonicalize party and political-family names centrally before aggregation. Resolve composite labels only with evidence from the candidate or source; preserve the original label.
6. For persisted data changes, back up the dataset, run an idempotent migration, and compare counts and diagnostic reports. Check both SQLite and CSV consumers where applicable.
7. Add focused tests for normal, malformed, ambiguous, and duplicate cases. State the exact commands and before/after counts in the result.

Never silently drop a valid poll because its percentage, date, or source metadata could not be parsed.
