---
name: canonical-party-vocabulary
description: Change or review party, political-family, bloc, color, logo, or label handling in the presidential polling project's extraction and dashboard code. Use before adding an alias, mapping, color, table column, or filter that mentions a party, a family, or a bloc.
---

# Canonical party vocabulary

Read `AGENT.md` and `src/presidentielle2027/extraction/canonicalization.py` first. Party names reach the dashboard through several distinct vocabularies; merging them silently changes displayed political data.

1. Resolve raw party and family labels only in `canonicalization.py` (`canonicalize_candidate_fields`, `PARTY_ALIASES`, `FAMILY_ALIASES`, `PARTY_FAMILY_DEFAULTS`). Dashboard and analytics code must import these tables, never re-hardcode an alias such as `LE`→`EELV` or `REN`→`RE`.
2. Keep three vocabularies separate, and name which one a value belongs to before touching it:
   - `political_family`: the canonical French value shown to users (`centre_gauche`, `écologistes`, `droite_nationale`, ...). Display it with `table_views.USER_VALUE_REPLACEMENTS`; do not recompute it from the party code.
   - `broad_bloc`: the coarse electoral grouping used for vote transfers. Always derive it with `historical_corrections.normalize_broad_bloc`; never copy `political_family` into it.
   - 2024 legislative nuance and force codes in `analysis_2024*.py`: a separate official vocabulary that does not go through `canonicalize_candidate_fields`.
3. `FAMILY_BROAD_BLOC_MAP` exists twice with different values (`canonicalization.py` and `historical_corrections.py`). Check which one the code imports before changing or comparing it; do not merge them without a before/after comparison of the second-round transfer results.
4. The 2022 backtest deliberately uses `PS-PP` as its `force_label` join key with `data/reference/historical_results_2022_presidential_first_round.csv`. Do not rename it without migrating that reference file and its consumers. It must never appear in the 2027 `candidate_party` column.
5. Colors and logos (`colors.py`, `party_assets.py`) are lookups keyed by canonical values. Add a key only for a canonical code; check that a change does not alter `get_political_color` for existing parties.
6. Dashboard loaders load the database or CSV, then re-parse the raw Wikipedia tables and replace the `RAW-FR-`/`RAW-SR-` rows. A parser fix is therefore visible immediately in the dashboard, while the persisted CSV and database stay stale until the next refresh; say so in the report.
7. Add tests for the alias, the canonical value shown, and the absence of the legacy token in the final frame. Report the exact commands and any check you could not run.
