# Claude project instructions

Read [AGENT.md](AGENT.md) for the shared project rules. The same instructions are exposed to other coding agents through [AGENTS.md](AGENTS.md).

Use the repository skills when the task matches them:

- [.claude/skills/audit-poll-ingestion/SKILL.md](.claude/skills/audit-poll-ingestion/SKILL.md) for sources, extraction, normalization, deduplication, and data migrations.
- [.claude/skills/validate-poll-adjustments/SKILL.md](.claude/skills/validate-poll-adjustments/SKILL.md) for weighting, historical corrections, uncertainty, model outputs, and dashboard interpretation.

Before editing, identify the affected data layer and read the relevant code, tests, and methodology in [METHODOLOGIE_BIAIS_ET_AJUSTEMENTS.md](METHODOLOGIE_BIAIS_ET_AJUSTEMENTS.md) when applicable. Report what was verified and which checks could not run. Do not claim a data correction is validated from a successful test run alone.
