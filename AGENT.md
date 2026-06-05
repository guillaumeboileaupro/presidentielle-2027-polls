# AGENT.md

Operational guidance for automated contributors, coding agents and future maintainers working on `presidentielle-2027-polls`.

## Mission

The repository exists to build a maintainable polling data pipeline for the 2027 French presidential election.

Agents working in this repository should optimize for:

- data traceability;
- methodological clarity;
- reproducibility;
- modular code;
- explicit uncertainty;
- conservative interpretation of outputs.

Do not optimize for flashy forecasts or overconfident narratives.

## Non-negotiable rules

### 1. Never present outputs as certain election predictions

This project handles polling data, adjustments and experimental bias correction.

It does not produce deterministic forecasts.

Any generated text, docs or dashboard copy must preserve that distinction.

### 2. Preserve source provenance

When importing or transforming data:

- keep the source URL whenever available;
- keep raw source text when useful for auditability;
- avoid destroying intermediate context that could help later validation;
- log ingestion actions when possible.

### 3. Keep raw, processed and derived data separated

- `data/raw/` is for untouched or near-untouched source artifacts;
- `data/interim/` is for temporary transformations;
- `data/processed/` is for normalized tabular outputs;
- `data/exports/` is for analytical exports;
- `data/historical/` is reserved for future historical datasets.

Agents should not silently overwrite raw inputs.

### 4. Prefer explicit normalization over ad hoc shortcuts

If a source is semi-structured:

- parse it into a normalized dataframe;
- preserve confidence metadata;
- document parsing assumptions;
- prefer extension points over hardcoded one-off fixes.

### 5. Avoid hidden methodological claims

If code applies a weighting, smoothing or correction:

- keep formulas explicit;
- expose parameters where reasonable;
- document assumptions in code or README;
- do not imply causal validity where only heuristic correction exists.

## Repository mental model

### Main layers

- `ingestion/`: fetch source artifacts.
- `extraction/`: parse heterogeneous source formats into normalized rows.
- `db/`: persist normalized data.
- `analytics/`: compute aggregated or smoothed views.
- `adjustments/`: apply explicit methodological corrections.
- `ml/`: experimental correction models, not prediction engines.
- `dashboard/`: visualization and exploration.

### Preferred flow

1. collect raw source
2. normalize into common schema
3. persist into database
4. compute aggregates or adjustments
5. expose outputs via CSV exports or dashboard

## Data standards

Normalized polling rows should target these concepts:

- poll identity
- source provenance
- polling company
- fieldwork dates
- publication date
- sample size and population
- methodology fields when available
- round and scenario
- candidate identity
- candidate-level estimate
- optional uncertainty fields
- raw context
- extraction confidence

When data is missing:

- use `None` or explicit `unknown` depending on field semantics;
- do not fabricate precise metadata.

## Confidence and missingness conventions

### `extraction_confidence`

Use a conservative score:

- `0.0` for synthetic sample/demo data;
- lower confidence for reconstructed rows from raw vectors or messy wiki tables;
- higher confidence for directly structured rows like clean second-round duel tables;
- never use confidence to imply truth, only extraction reliability.

### Unknown methodological fields

For fields like `collection_method`, `quota_method`, `population`, `commissioner`:

- prefer `unknown` or `None`;
- do not infer from pollster brand alone unless the inference is explicitly documented and justified.

## Excel and Wikipedia ingestion guidance

The repository currently supports multiple workbook shapes derived from Wikipedia extraction.

### V1-style workbook

Typical sheets:

- `first_round`
- `second_round`
- `data_quality`

### V2-style workbook

Typical sheets:

- `first_round_raw_vectors`
- `second_round_structured`
- `scenario_polling_raw`
- candidate order sheets

### Expectations for agents

When extending Excel parsing:

- detect formats by sheet names, not filename only;
- write parsers that degrade gracefully;
- keep format-specific parsing logic isolated;
- preserve enough raw context to audit the transformation later.

## Dashboard rules

The dashboard is exploratory.

Agents editing dashboard logic should:

- keep labels readable for French-speaking users;
- avoid overstating model certainty;
- ensure the app still works with fallback datasets;
- keep the shell and figures on clear backgrounds only;
- keep party-series colors distinct from the app shell branding;
- use party logos only as labels or metadata aids, not as substitutes for data;
- preserve the current high-level split between:
  - first round by force politics,
  - historically corrected first round,
  - second round with legislative benchmark,
  - sources and metadata;
- treat first-round reading primarily as a force-political view, not as a scenario-by-scenario candidate picker;
- preserve filtering by period and pollster inside each view;
- keep the UI functional even when some columns are missing or sparse.

The dashboard should not reintroduce:

- mixed first-round and second-round plots;
- mixed second-round duels;
- candidate-name scenario selectors as the main first-round entry point;
- candidate and generic party/bloc comparisons in the same analytical view.

When working on corrections:

- prefer source-backed historical calibration files over ad hoc constants;
- document which source powers each correction family;
- keep 2022 presidential first-round data as the baseline for first-round bias correction;
- keep 2024 legislative bloc results as the experimental baseline for second-round reserve benchmarks.

## Database rules

When modifying models:

- preserve compatibility with SQLite by default;
- keep future PostgreSQL compatibility in mind;
- avoid denormalizing unless there is a clear performance reason;
- prefer additive schema changes over destructive rewrites.

If schema changes become substantial, add or prepare Alembic migrations.

## Machine learning rules

The ML layer is explicitly experimental.

Agents must follow these constraints:

- do not market ML outputs as election predictions;
- frame them as bias-correction experiments only;
- require explicit training targets for meaningful learning;
- document the target column used;
- preserve artifact paths and metrics;
- do not silently train on synthetic sample data and present the model as meaningful.

## Testing expectations

Every meaningful parser or transformation change should ideally add or update tests.

Priority test targets:

- normalization of new source formats;
- date parsing;
- candidate vector explosion;
- weighted average calculations;
- database persistence invariants;
- adjustment functions.

## Documentation expectations

When making material changes:

- update `README.md` if behavior changes;
- update notebook instructions if kernel or notebook structure changes;
- document new sources or new file formats;
- explain assumptions if new heuristics are introduced;
- keep launch instructions accurate.

## Notebook rules

Notebooks are part of the supported workflow.

Agents editing notebooks should:

- keep one analytical purpose per notebook;
- avoid mixing raw and corrected datasets in the same notebook unless the comparison is the explicit purpose;
- keep first round and second round separated;
- target the project kernel `presidentielle2027-polls` / `Présidentielle 2027 (.venv)`;
- keep notebook steps runnable top-to-bottom with the project `.venv`.

## Safe defaults for future work

If uncertain, prefer:

- storing more context rather than less;
- lower confidence rather than inflated confidence;
- explicit TODO notes rather than hidden assumptions;
- modular parsing helpers rather than one large function;
- source-aligned naming rather than speculative renaming.

## Good next tasks for agents

- merge and deduplicate V1 and V2 normalized datasets;
- enrich polls with metadata from Commission des sondages notices;
- normalize scenario names across institutions and languages;
- improve candidate-party-family mappings;
- add historical 2017/2022 truth data for backtesting;
- store smoothed estimates in the database;
- add export commands for reproducible analytical snapshots.

## Anti-patterns to avoid

- hardcoding one fixed candidate table as if the candidate set were stable;
- deleting raw context because it looks messy;
- conflating publication date and fieldwork end date without documenting it;
- silently replacing missing metadata with guessed values;
- presenting aggregates as a forecast;
- stuffing all logic into the CLI;
- adding one-off parsing hacks that cannot be tested.

## Final note

This repository should become a reliable polling research tool, not a black-box election oracle.

Every contribution should improve either:

- source coverage,
- normalization quality,
- methodological transparency,
- analytical usefulness,
- or reproducibility.
